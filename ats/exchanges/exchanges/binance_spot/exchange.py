import os
import time
import json
import pandas as pd
import requests
import datetime
import pytz
import traceback
import numpy as np
from typing import Union, List, Dict, Type, Literal, Tuple
from binance.spot import Spot

from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient

from ats.exceptions.general_exceptions import ConfigValidationException
from ats.exceptions import exchange_exceptions
from ats.utils.logging.logger import logger
from utils.general import helpers as general_helpers
from ats.utils.general import helpers as generic_helpers
from ats.exchanges.base_exchange import BaseExchange
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.asset_balance import AssetBalance
from ats.state.order_list_state import OrderListState
from ats.exchanges.exchanges.back_trading.wallet import Wallet
from ats.exchanges.base_fees import BaseFees
from ats.utils.time.timer import Timer
from ats.utils.logging.logger import logger

BINANCE_TEST_HTTP_URL = 'https://testnet.binance.vision'
BINANCE_LIVE_HTTP_URL = 'https://api.binance.com'
BINANCE_TEST_WS_URL = 'wss://testnet.binance.vision'
BINANCE_LIVE_WS_URL = 'wss://stream.binance.com:9443'


class Exchange(BaseExchange):
    def validate_config(self) -> None:
        required_properties = ['extra.api_key', 'extra.api_secret', 'extra.trading_mode']

        for prop in required_properties:
            if not general_helpers.check_nested_property_in_dict(prop, self.config):
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

    def is_back_trading(self) -> bool:
        return False

    # Implemented the base class abstract method
    def connect(self):
        # There can be previous states loaded. Even from a previously version of the current object.
        # It is important to initialize only if the property is None

        #  Keeps track of the orders that are not completed ('FILLED', 'REJECTED' or 'CANCELED')
        if self._state.get('incomplete_orders') is None:
            self._state.set('incomplete_orders', OrderListState())

        self._is_ready_for_trading = False

        # This will be updated periodically
        self._wallet_balance = None

        trading_mode = self.config['extra']['trading_mode']  # live or test

        if trading_mode not in ['TEST', 'LIVE']:
            raise ConfigValidationException("extra.trading_mode must be either 'TEST' or 'LIVE'")

        http_client_params = {
            'api_key': self.config['extra']['api_key'],
            'api_secret': self.config['extra']['api_secret'],
            'timeout': 60
        }

        ws_client_params = {
            'on_message': self.__on_ws_data_callback
        }

        if self.config['extra']['trading_mode'] == 'TEST':
            http_client_params['base_url'] = BINANCE_TEST_HTTP_URL
            ws_client_params['stream_url'] = BINANCE_TEST_WS_URL
        else:
            http_client_params['base_url'] = BINANCE_LIVE_HTTP_URL
            ws_client_params['stream_url'] = BINANCE_LIVE_WS_URL

        self.__fee_class = generic_helpers.get_class_from_namespace('fees:generic')

        self.__http_client_params = http_client_params
        self.__ws_client_params = ws_client_params

        # Create Binance HTTP API client and Binance WS Stream client
        logger.info('Creating Binance HTTP and WS clients')
        self.__http_client = Spot(**http_client_params)
        # self.__ws_client = SpotWebsocketStreamClient(**ws_client_params)

        self.is_connected = True

        # Get the listen key. This is required for getting data from user_data stream
        # Refer: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
        logger.info('Getting a new listen key from Binance')
        listen_key = self.__http_client.new_listen_key()
        self.__binance_listen_key = listen_key['listenKey']

        # Start WS stream for getting candle data
        self._init_ws_stream(ws_client_params)

        # Get symbol information such as precision
        self.__exchange_info = self.__http_client.exchange_info(
            self.config['symbol']['base'] + self.config['symbol']['quote'])

        logger.info(f"Binance filters: \n {self.__exchange_info['symbols'][0]['filters']} \n")

        for symbol_filter in self.__exchange_info['symbols'][0]['filters']:
            if symbol_filter['filterType'] == 'PRICE_FILTER':
                self.__binance_price_filter = symbol_filter

            if symbol_filter['filterType'] == 'LOT_SIZE':
                self.__binance_size_filter = symbol_filter

            if symbol_filter['filterType'] == 'NOTIONAL':
                self.__binance_notional_filter = symbol_filter

        # sync order states with exchange (to stop out-of sync pending orders)
        self.__order_ststus_refresh_timer = Timer(on_timer=self.__refresh_order_status, interval=60)

        # Listen key is expired after 60 minutes if not refreshed.
        # Refreshing listen key before 60 minutes.
        self.__listen_key_refresh_timer = Timer(on_timer=self.__refresh_binance_listen_key, interval=300)

        # Restarts the websocket stream every hour to solve Binance random connection resetting
        self.__restart_ws_stream_timer = Timer(on_timer=self._restart_ws_stream, interval=3600)

        # Calling wallet balance refresh on a timer every 5 sec
        # TODO: Implement a thread lock
        self.__wallet_balance_refresh_timer = Timer(on_timer=self.__refresh_wallet_balance, interval=5)

        # We have to keep track of last candle times. Binance sends more than one record for candles
        # especially at higher candle time frames. As an example, 1m candle might have several updates on how the candle
        # is changed even within the 1m time interval. Therefore, it is important to pick the last data point of the
        # candle update. To do that, we must monitor the candle start time and end time. If they are different, we know
        # that we have just started a new candle
        self.__last_binance_candle_message = None

        self.__order_ststus_refresh_timer.start()
        self.__listen_key_refresh_timer.start()
        self.__wallet_balance_refresh_timer.start()
        self.__restart_ws_stream_timer.start()

    # Implemented the base class abstract method
    def disconnect(self):
        logger.info('Binance exchange disconnect() called.')
        try:
            self.__order_ststus_refresh_timer.delete()
        except Exception as e:
            logger.warn('Order status refresh timer cannot be deleted due to error. Therefore, skipping timer stopping.')
            traceback.print_exc()

        try:
            self.__listen_key_refresh_timer.delete()
        except Exception as e:
            logger.warn('Listen key timer cannot be deleted due to error. Therefore, skipping timer stopping.')
            traceback.print_exc()

        try:
            self.__wallet_balance_refresh_timer.delete()
        except Exception as e:
            logger.warn(
                'Wallet balance refresh timer cannot be deleted due to error. Therefore, skipping timer stopping.')
            traceback.print_exc()

        self._is_ready_for_trading = False

        try:
            self.__ws_client.stop()
        except Exception as e:
            logger.warn('Binance WS client cannot be stopped due to error. Therefore, skipping Binance WS stopping.')
            logger.error(e)
            logger.info(
                'Binance WS error for thread join() happens when exchange.disconnect() is called on _on_candle_callable()')
            traceback.print_exc()

        self.is_connected = False

        logger.info('Binance exchange is disconnected.')

    # Implemented the base class abstract method
    def submit_order(self, order: Order) -> None:
        params = {
            'symbol': order.base_symbol + order.quote_symbol,
            'side': order.order_side,
            'type': 'LIMIT_MAKER' if order.order_type == 'LIMIT' else 'MARKET',
            'quantity': self.__approximate_and_format_size_or_price('SIZE', order.size),
            'newClientOrderId': order.order_id
        }

        logger.info('Binance order submission.')
        logger.info(order)

        # Register plotting hook
        order.on_status_change(self._order_on_status_change_callback_for_plotting)

        # Trigger pending order
        self._order_on_status_change_callback_for_plotting(order=order, modified_time=order.time)

        if order.order_type == 'LIMIT':
            params['price'] = self.__approximate_and_format_size_or_price('PRICE', order.price, round_down=params['side'] == "BUY")
            assert float(params['price']) * float(params['quantity']) >= float(self.__binance_notional_filter["minNotional"]), f"Order size {float(params['price']) * float(params['quantity'])} is less than minNotional of {float(self.__binance_notional_filter['minNotional'])}"

        order.no_state_trail = True

        try:
            response = self.__http_client.new_order(**params)
            self._state.get('incomplete_orders').add(order)

            if 'fills' in response and len(response[
                                               'fills']) > 0:  # LIMIT orders (or some MARKET orders) are not filled at the time of the submission
                last_fill = response['fills'][-1]

                if 'status' in response and response[
                    'status'] != 'PARTIALLY_FILLED':  # We ignore partially filled here.
                    is_fulfilled = True if response['status'] == 'FILLED' else False
                    self.__sync_order_status_with_binance(
                        binance_order_status=response['status'],
                        order_id=response['clientOrderId'],
                        binance_fee=last_fill['commission'] if is_fulfilled else None,
                        fee_symbol=last_fill['commissionAsset'] if is_fulfilled else None,
                        event_time=datetime.datetime.now(pytz.utc),
                        filled_price=last_fill['price'] if is_fulfilled else None,
                        filled_size=last_fill['qty'] if is_fulfilled else None  # Acts as size_delta for parial orders
                    )

        except Exception as e:
            logger.error(f'Error happened while submitting order: {order.order_id}. Hence order is rejected. {e}')
            order.reject(modified_time=datetime.datetime.now(pytz.utc))

    def cancel_order(self, order: Order) -> None:
        logger.info(f'Cancelling order: {order.order_id}')
        self.__http_client.cancel_order(symbol=order.base_symbol + order.quote_symbol, origClientOrderId=order.order_id)
        order.cancel()
        logger.info(f'Cancelled order: {order.order_id}')

    # Implemented the base class abstract method
    def get_order(self, order_id) -> Union[Order, None]:
        incomplete_orders = self._state.get('incomplete_orders').get_all_as_ordered_list()

        for incomplete_order in incomplete_orders:
            if incomplete_order.order_id == order_id:
                return incomplete_order

        # If no previous order is found the following code is executed

        response = self.__http_client.get_order(
            symbol=self.config['symbol']['base'] + self.config['symbol']['quote'],
            origClientOrderId=order_id)

        if response['symbol'] != self.config['symbol']['base'] + self.config['symbol']['quote']:
            raise Exception(f"Received symbol from exchange {response['symbol']} does not match base symbol {self.config['symbol']['base']} and quote symbol {self.config['symbol']['quote']}")

        order_type = 'LIMIT' if 'LIMIT' in response['type'] else 'MARKET' # TODO: Review this again since Binance has more than two order types

        order = Order(
            order_id=order_id,
            base_symbol=self.config['symbol']['base'],
            quote_symbol=self.config['symbol']['quote'],
            order_side=response['side'],
            order_type=order_type,
            size=float(response['origQty']),
            no_state_trail=True,
            price=float(response['price']) if order_type == 'LIMIT' else None
            # Important because we create a new object here rather than updating the previous order object
        )

        if 'fills' in response and len(response[
                                           'fills']) > 0:  # LIMIT orders (or some MARKET orders) are not filled at the time of the submission
            last_fill = response['fills'][-1]

            if 'status' in response and response[
                'status'] != 'PARTIALLY_FILLED':  # We ignore partially filled here.
                is_fulfilled = True if response['status'] == 'FILLED' else False
                self.__sync_order_status_with_binance(
                    binance_order_status=response['status'],
                    order_id=response['clientOrderId'],
                    binance_fee=last_fill['commission'] if is_fulfilled else None,
                    fee_symbol=last_fill['commissionAsset'] if is_fulfilled else None,
                    event_time=datetime.datetime.now(pytz.utc),
                    filled_price=last_fill['price'] if is_fulfilled else None,
                    filled_size=last_fill['qty'] if is_fulfilled else None  # Acts as size_delta for parial orders
                )
                return order

        # fix for POM reloading filled orders
        elif response['status'] == 'FILLED':
            logger.warn(f"Exchange: Order id {order_id} is fetched with FILLED state but not 'fills' and 'fees' found. Setting fees to 0.")

            incomplete_orders = self._state.get('incomplete_orders')
            if incomplete_orders is not None:
                incomplete_order: Order = incomplete_orders.get(order_id)
                if incomplete_order is not None:
                    incomplete_orders.pop(order_id)

            fees = self.__fee_class(config={})
            fees.set(base_fee=0, quote_fee=0)
            order.fully_fill(
                modified_time=datetime.datetime.now(pytz.utc),
                price=None if order.order_type == 'LIMIT' else response['price'],
                fees=fees
            )
            return order

        elif response['status'] == 'CANCELED':
            order.cancel()
            return order
        elif response['status'] == 'REJECTED':
            order.reject()
            return order

        # Register plotting hook
        order.on_status_change(self._order_on_status_change_callback_for_plotting)

        # Trigger pending order
        self._order_on_status_change_callback_for_plotting(order=order, modified_time=order.time,
                                                           note='Order was not submitted by this execution session.')

        self._state.get('incomplete_orders').add(order)

        return order

    # Implemented the base class abstract method
    def get_wallet_balance(self) -> Dict[str, AssetBalance]:
        return self._wallet_balance

    def get_fees(self) -> Tuple[float, float]:
        if self.maker_fee_rate is None or self.taker_fee_rate is None:
            symbol = self.config['symbol']['base'] + self.config['symbol']['quote']
            fee_res = self.__http_client.trade_fee(symbol=symbol)
            for record in fee_res:
                if record["symbol"] == symbol:
                    self.maker_fee_rate = float(record['makerCommission'])
                    self.taker_fee_rate = float(record['takerCommission'])
                    break
            else:
                print("Symbol fees not found!")

        return self.maker_fee_rate, self.taker_fee_rate

    def _init_ws_stream(self, ws_client_param):
        self.__ws_client = SpotWebsocketStreamClient(**ws_client_param)
        symbol_pair = self.config['symbol']['base'] + self.config['symbol']['quote']

        # Subscribe for the candle WS event and the user_data WS event. user_data event fetches order updates and wallet updates
        # For websocket, the symbol pair is given in lower case. For HTTP, symbol pair is given in upper case
        self.__ws_client.kline(symbol=symbol_pair.lower(), interval=self.config['extra']['candle_time'])
        self.__ws_client.user_data(symbol=symbol_pair.lower(), listen_key=self.__binance_listen_key)
        self.is_connected = True

    def _restart_ws_stream(self):
        try:
            logger.info('Binance WS connection restart timer is called')
            self.__ws_client.stop()

            del self.__ws_client

            self.is_connected = False
            self._init_ws_stream(self.__ws_client_params)
            logger.info('Binance WS connection restarted')
        except Exception as e:
            logger.warn('Binance WS client cannot be stopped due to error. Therefore, skipping Binance WS stopping.')
            logger.error(e)
            logger.info(
                'Binance WS error for thread join() happens when exchange.disconnect() is called on _on_candle_callable()')
            traceback.print_exc()

    def __on_ws_data_callback(self, _, message_text):
        try:
            if self._is_ready_for_trading:
                message = json.loads(message_text)
                symbol_pair = self.config['symbol']['base'] + self.config['symbol']['quote']
                if 'e' in message and 's' in message and message['s'] == symbol_pair:
                    # Condition checks if we have a new candle.
                    # Note that Binance sends multiple updates for the same candle (candle progressing update.)
                    if message['e'] == 'kline':
                        if self.__last_binance_candle_message is not None and self.__last_binance_candle_message['k'] != \
                                message['k']:
                            if self.__last_binance_candle_message is None:
                                self.__last_binance_candle_message = message

                            candle = Candle(
                                open=float(self.__last_binance_candle_message['k']['o']),
                                high=float(self.__last_binance_candle_message['k']['h']),
                                low=float(self.__last_binance_candle_message['k']['l']),
                                close=float(self.__last_binance_candle_message['k']['c']),
                                symbol=self.__last_binance_candle_message['k']['s'],
                                buy_vol=float(self.__last_binance_candle_message['k']['V']),
                                sell_vol=float(self.__last_binance_candle_message['k']['Q']),
                                # TODO: Q is in quote asset
                                time=datetime.datetime.fromtimestamp(
                                    self.__last_binance_candle_message['k']['t'] / 1000).astimezone(pytz.utc)
                            )

                            self.__close_old_incomplete_order_forced(candle=candle)

                            if self._on_candle_callable is not None:
                                self._on_candle_callable(candle)

                        self.__last_binance_candle_message = message

                    if message['e'] == 'executionReport':
                        event_time = datetime.datetime.fromtimestamp(message['E'] / 1000).astimezone(pytz.utc)

                        # Note: Binance's has this extremely weired way of implementing APIs.
                        # Ref: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md#order-update
                        order_id = message['C'] if message['X'] == 'CANCELED' else message['c']

                        # TODO: Delay added to avoid raise conditions.
                        #  __sync_order_status_with_binance is called earlier under order submit.
                        #  This can introduce raise conditions. We rely on incomplete_orders.pop(order_id) to avoid duplicate updates.
                        time.sleep(2)

                        self.__sync_order_status_with_binance(
                            binance_order_status=message['X'] if 'X' in message else None,
                            order_id=order_id,
                            binance_fee=float(message['n']) if 'n' in message else None,
                            fee_symbol=message['N'] if 'N' in message else None,
                            event_time=event_time,
                            filled_price=float(message['Z']) if 'Z' in message else None,
                            filled_size=float(message['l']) if 'l' in message else None
                        )

        except Exception as e:
            if os.getenv(
                    'LOG_LEVEL') == 'DEBUG':  # Errors within the callbacks do not print stack trace. So we force to print
                traceback.print_exc()
            raise e

    def __refresh_order_status(self):
        logger.info('Binance order status refreshed')
        incomplete_orders = self._state.get('incomplete_orders').get_all_as_ordered_list()

        for order in incomplete_orders:
            order_id = order.order_id
            try:
                response = self.__http_client.get_order(
                    symbol=self.config['symbol']['base'] + self.config['symbol']['quote'],
                    origClientOrderId=order_id
                )
            except requests.exceptions.Timeout:
                logger.error("[TIMEOUT] Order Status Check Timeout")
                continue
            except Exception as e:
                logger.error(e)
                traceback.print_exc()
                continue

            if response['symbol'] != self.config['symbol']['base'] + self.config['symbol']['quote']:
                raise Exception(
                    f"Received symbol from exchange {response['symbol']} does not match base symbol {self.config['symbol']['base']} and quote symbol {self.config['symbol']['quote']}")

            if 'status' in response and response['status'] != 'PARTIALLY_FILLED':  # We ignore partially filled here.
                is_fulfilled = response['status'] == 'FILLED'
                self.__sync_order_status_with_binance(
                    binance_order_status=response['status'],
                    order_id=response['clientOrderId'],
                    binance_fee=None,
                    fee_symbol=None,
                    event_time=datetime.datetime.now(pytz.utc),
                    filled_price=response['price'] if (is_fulfilled and order.order_type != 'LIMIT') else None,
                    filled_size=response['executedQty'] if is_fulfilled else None  # Acts as size_delta for parial orders
                )



    def __refresh_binance_listen_key(self):
        logger.info('Binance listen token refreshed')
        try:
            self.__http_client.renew_listen_key(listenKey=self.__binance_listen_key)
        except requests.exceptions.Timeout:
            logger.error("[TIMEOUT] Binance Listen Key Refresh Timeout")
            return None
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
            return None

    def __refresh_wallet_balance(self):
        logger.info('Wallet balance refreshed')

        try:
            binance_balance = self.__http_client.account()
        except requests.exceptions.Timeout:
            logger.error("[TIMEOUT] Wallet Balance Refresh Timeout")
            return None
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
            return None

        wallet_balance = {}

        if 'balances' not in binance_balance:
            raise exchange_exceptions.NoWalletAssetFoundException('Binance wallet balance is not returned.')

        for binance_balance_item in binance_balance['balances']:
            wallet_balance[binance_balance_item['asset']] = AssetBalance(symbol=binance_balance_item['asset'],
                                                                         free=float(binance_balance_item['free']),
                                                                         holding=float(binance_balance_item['locked']),
                                                                         )

        self._wallet_balance = wallet_balance

        # At least one wallet balance update must be received.
        self._is_ready_for_trading = True

    def __sync_order_status_with_binance(self,
                                         binance_order_status: str,
                                         order_id: str, binance_fee: float,
                                         fee_symbol: str,
                                         event_time,
                                         filled_price: float = None,
                                         filled_size: float = None,
                                         res=None
                                         ):
        """
        This method modifies an incomplete (pending or partially filled) order status, by updating its status.
        If the order is completed, it is removed from the incomplete_order state
        Args:
            binance_order_status:
            order_id:
            binance_fee:
            fee_symbol:
            event_time:
            filled_price:
            filled_size:

        Returns:

        """
        incomplete_orders = self._state.get('incomplete_orders')

        try:  # Exceptions can occur due to race conditions.
            order = None

            if incomplete_orders is not None:
                order: Order = incomplete_orders.get(order_id)

            if order is not None:  # If order is None that means we received an order that is not recorded as submitted
                if binance_order_status == 'REJECTED':
                    order.reject(modified_time=event_time)
                    incomplete_orders.pop(order_id)

                if binance_order_status == 'CANCELED':
                    order.cancel(modified_time=event_time)
                    incomplete_orders.pop(order_id)

                if binance_order_status == 'FILLED':
                    # Remove the order from incomplete orders
                    incomplete_orders.pop(order_id)

                    binance_base_fee = 0
                    binance_quote_fee = 0

                    if fee_symbol == order.base_symbol:
                        binance_base_fee = float(binance_fee)

                    if fee_symbol == order.quote_symbol:
                        binance_quote_fee = float(binance_fee)

                    fees = self.__fee_class(config={})
                    fees.set(base_fee=binance_base_fee, quote_fee=binance_quote_fee)

                    order.fully_fill(
                        modified_time=event_time,
                        price=None if order.order_type == 'LIMIT' else filled_price,
                        fees=fees
                    )

                if binance_order_status == 'PARTIALLY_FILLED':
                    fees = self.__fee_class(config={})

                    fees.set(base_fee=0,
                             quote_fee=0)  # We define the fee for partial order is zero because it is not clear in the Binance API

                    # When the partial order is turned into a FILLED order, we are anyway adding fees and filled price
                    order.fill(
                        modified_time=event_time,
                        size_delta=filled_size,
                        fees_delta=fees
                    )
            else:
                logger.debug(f'Received an order that is not registered: {order_id} - {binance_order_status}')
        except Exception as e:  # Exceptions can occur due to race conditions.
            logger.error(f'Error occurred while trying to close the order forcefully. {e}')

    def __close_old_incomplete_order_forced(self, candle: Candle):
        """
        If a LIMIT order is not completed after a certain time, then the order is forcefully closed considering candle values
        Args:
            candle: current candle

        Returns:
            None
        """
        incomplete_orders = self._state.get('incomplete_orders')
        order_list = incomplete_orders.get_all_as_ordered_list()

        force_close_time = self.config['extra']['force_close_time']

        for order in order_list:
            diff_sec = (candle.time - order.time).total_seconds()
            try:  # It is expected to have errors here due to race conditions.
                if diff_sec > force_close_time and order.order_type == 'LIMIT':
                    if order.price > candle.low and order.order_side == 'BUY' or order.price < candle.high and order.order_side == 'SELL':
                        fees = self.__fee_class(config={})
                        fees.set(base_fee=0, quote_fee=0)
                        order.fully_fill(fees=fees, modified_time=candle.time)
                        incomplete_orders.pop(order.order_id)
                        logger.warn(f'Order {order.order_id} is closed forcefully due to idle time being reached')
            except Exception as e:  # Exceptions can occur due to race conditions.
                logger.error(f'Error occurred while trying to close the order forcefully. {e}')

    def __approximate_and_format_size_or_price(self, size_or_price: Literal['SIZE', 'PRICE'],
                                               num: Union[float, int], round_down: bool = False) -> str:
        """
        The exchange does not accept any price or size.
        It has to be below a step of a defined delta.
        This method rounds off any number to desired step size (step size depends on size or price)
        Args:
            size_or_price: 'SIZE' or 'PRICE'
            num: Number to be converted

        Returns:

        """

        if size_or_price == 'PRICE':
            min_step_str = self.__binance_price_filter['tickSize']

        if size_or_price == 'SIZE':
            min_step_str = self.__binance_size_filter['stepSize']

        min_step = float(min_step_str)

        float_str = min_step_str.lstrip('0')

        # Count the number of decimal places
        precision = len(float_str.split('.')[1]) - len(float_str.split('.')[1].lstrip('0')) + 1 if '.' in float_str else 0

        if round_down:
            return "{:.{}f}".format(round(num / min_step) * min_step, precision)
        else:
            return f"{np.ceil(num * 10**precision) / 10 ** precision:.{precision}f}"
