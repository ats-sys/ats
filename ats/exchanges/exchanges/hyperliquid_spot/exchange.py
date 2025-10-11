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

from ats.exceptions.general_exceptions import ConfigValidationException
from ats.exceptions import exchange_exceptions
from ats.utils.logging.logger import logger
from ats.utils.general import helpers as general_helpers
from ats.utils.general import helpers as generic_helpers
from ats.exchanges.base_exchange import BaseExchange
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.asset_balance import AssetBalance
from ats.state.order_list_state import OrderListState
from ats.exchanges.exchanges.back_trading.wallet import Wallet
from ats.exchanges.base_fees import BaseFees
from ats.utils.time.timer import Timer

import eth_account
from eth_account.signers.local import LocalAccount

import uuid

from hyperliquid.utils import constants
from hyperliquid.utils.types import Cloid
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange as HyperliquidExchange


class Exchange(BaseExchange):
    """
    Functionalities to support
    - Update Wallet Balance - Done 
    - Candle Price Updates - Done
    - Submit Order 
        - Market - Okay - But default leverage is set, not sure why
        - Limit - Okay
    - Cancel Order - Done
    - Get Order  for a given order_id -- Done

    Questions:
    - What is the plotting hook in _order_on_status_change_callback_for_plotting?
    - How candle updates are handled, where do you update?
    - How in_complete orders are tracked? 
    - How tests are usually called.?
    - In get order is it okay to return market orders as limit orders? -- Hyperliquid side doesn't track it.
    - Why candle_symbol = basequote? not base/quote?
    """

        

    def validate_config(self) -> None:
        required_properties = ['extra.secret_key', 'extra.account_address', 'extra.trading_mode']

        for prop in required_properties:
            if not general_helpers.check_nested_property_in_dict(prop, self.config):
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

    def is_back_trading(self) -> bool:
        return False

    def connect(self):
        # Initialize incomplete orders tracking
        if self._state.get('incomplete_orders') is None:
            self._state.set('incomplete_orders', OrderListState())

        self._is_ready_for_trading = False
        self._wallet_balance = None

        trading_mode = self.config['extra']['trading_mode']  # live or test

        if trading_mode not in ['TEST', 'LIVE']:
            raise ConfigValidationException("extra.trading_mode must be either 'TEST' or 'LIVE'")

        # Set up base URL based on trading mode
        if trading_mode == 'TEST':
            self.base_url = constants.TESTNET_API_URL
        else:
            self.base_url = constants.MAINNET_API_URL

        # Set up Hyperliquid client
        self.secret_key = self.config['extra']['secret_key']
        self.account = eth_account.Account.from_key(self.secret_key)
        if self.config['extra']['account_address'] != "":
            self.account_address = self.config['extra']['account_address']
        else:
            self.account_address = self.account.address
        

        # Initialize Hyperliquid Info and Exchange clients
        try:
            self.info = Info(self.base_url, skip_ws=False)
        except Exception as e:
            logger.error(f'Error connecting to Hyperliquid: {e}')
            traceback.print_exc()
            raise e
        self.exchange_client = HyperliquidExchange(self.account, self.base_url, account_address=self.account_address, perp_dexs=None)
        self.__fee_class = generic_helpers.get_class_from_namespace('fees:generic')

        # Calling wallet balance refresh on a timer every 5 sec
        self.__wallet_balance_refresh_timer = Timer(on_timer=self.__refresh_wallet_balance, interval=5)


        self.subscription = {"type": "candle", "coin": self.config['symbol']['id'], "interval": self.config['extra']['candle_time']}
        self.subscription_id = self.info.subscribe(self.subscription, self.__on_ws_candle_callback)

        # We have to keep track of last candle times. Binance sends more than one record for candles
        # especially at higher candle time frames. As an example, 1m candle might have several updates on how the candle
        # is changed even within the 1m time interval. Therefore, it is important to pick the last data point of the
        # candle update. To do that, we must monitor the candle start time and end time. If they are different, we know
        # that we have just started a new candle
        # self.__last_binance_candle_message = None

        # self.__order_ststus_refresh_timer.start()
        # self.__listen_key_refresh_timer.start()
        self.__wallet_balance_refresh_timer.start()
        # self.__restart_ws_stream_timer.start()


    def __on_ws_candle_callback(self, message):
        try:
            if self._is_ready_for_trading and message and 'data' in message:
                candle_data = message['data']

                # Create a Candle object from the received data
                candle_symbol = self.config['symbol']['base'] + self.config['symbol']['quote']
                candle = Candle(
                    open=float(candle_data['o']),
                    high=float(candle_data['h']),
                    low=float(candle_data['l']),
                    close=float(candle_data['c']),
                    symbol=candle_symbol,
                    buy_vol=float(candle_data['v']),
                    sell_vol=float(candle_data['v']),
                    time=datetime.datetime.fromtimestamp(candle_data['t'] / 1000).astimezone(pytz.utc)
                )
                
                # Call the on_candle callback if registered
                if self._on_candle_callable is not None:
                    self._on_candle_callable(candle)
            else:
                logger.info(f'Candle before is_ready_for_trading' if 'data' in message else 'Candle message is empty or invalid')
        except Exception as e:
            logger.error(f'Error in candle WebSocket callback: {e}')
            traceback.print_exc()

    def __on_ws_user_events_callback(self, message):
        try:
            # Process user events like balance updates
            if message and 'data' in message:
                # Refresh wallet balance on user events
                self.__refresh_wallet_balance()
        except Exception as e:
            logger.error(f'Error in user events WebSocket callback: {e}')
            traceback.print_exc()

    def __on_ws_order_updates_callback(self, message):
        try:
            # Process order updates
            if message and 'data' in message:
                order_data = message['data']
                # Update order status based on the received data
                self.__sync_order_status_with_hyperliquid(order_data)
        except Exception as e:
            logger.error(f'Error in order updates WebSocket callback: {e}')
            traceback.print_exc()

    def disconnect(self):
        logger.info('Hyperliquid exchange disconnect() called.')
        try:
            # Stop timers
            # self.__order_status_refresh_timer.delete()
            self.__wallet_balance_refresh_timer.delete()
            self.info.unsubscribe(self.subscription, self.subscription_id)

            
            # Close WebSocket connections
            # Note: The Hyperliquid SDK might handle this automatically
            
            self._is_ready_for_trading = False
            self.is_connected = False
            
            logger.info('Hyperliquid exchange disconnected.')
        except Exception as e:
            logger.error(f'Error disconnecting from Hyperliquid: {e}')
            traceback.print_exc()

    def __get_cloid_from_order_id(self, order_id: str) -> Cloid:
        return Cloid.from_str(f"0x{uuid.UUID(order_id).int:032x}")

    def __approximate_and_format_size_or_price(self, size_or_price: Literal['SIZE', 'PRICE'],
                                               num: Union[float, int], round_down: bool = False) -> str:
        """
        Format price or size according to Hyperliquid tick and lot size rules.

        Price rules:
        - Max 5 significant figures
        - Max decimal places: MAX_DECIMALS - szDecimals (6 for perps, 8 for spot)
        - Integer prices always allowed

        Size rules:
        - Rounded to szDecimals

        Args:
            size_or_price: 'SIZE' or 'PRICE'
            num: Number to be formatted
            round_down: If True, round down instead of up

        Returns:
            Formatted string with trailing zeroes removed
        """

        # Get asset metadata if not already cached
        if not hasattr(self, '_asset_metadata'):
            meta = self.info.spot_meta()
            # symbol = self.config['symbol']['id']
            symbol = self.config['symbol']['base']

            # Find szDecimals for this asset
            self._sz_decimals = None

            # Check spot metadata
            if 'tokens' in meta:
                for token in meta['tokens']:
                    if token['name'] == symbol:
                        self._sz_decimals = token['szDecimals']
                        break

            # Check perp metadata if not found in spot
            if self._sz_decimals is None:
                meta = self.info.meta()

                if "universe" in meta:
                    for asset in meta['universe']:
                        if asset["name"] == symbol:
                            self._sz_decimals = asset['szDecimals']
                            break

            if self._sz_decimals is None:
                raise Exception(f"Could not find szDecimals for symbol {symbol}")

            self._asset_metadata = True

        if size_or_price == 'SIZE':
            # Size: Round to szDecimals
            precision = self._sz_decimals

            if round_down:
                formatted = f"{np.floor(num * 10 ** precision) / 10 ** precision:.{precision}f}"
            else:
                formatted = f"{np.ceil(num * 10 ** precision) / 10 ** precision:.{precision}f}"

        elif size_or_price == 'PRICE':
            # Price: Max 5 significant figures, max (MAX_DECIMALS - szDecimals) decimal places
            # Assuming spot (MAX_DECIMALS = 8), adjust if using perps (MAX_DECIMALS = 6)
            MAX_DECIMALS = 8  # Use 6 for perps
            max_decimal_places = MAX_DECIMALS - self._sz_decimals

            # Check if integer (integers always allowed regardless of sig figs)
            if num == int(num):
                return str(int(num))

            # Count significant figures and apply rounding
            # Convert to scientific notation to count sig figs
            num_str = f"{num:.15e}"  # High precision scientific notation
            mantissa, exponent = num_str.split('e')
            mantissa_clean = mantissa.replace('.', '').replace('-', '')

            # Round to 5 significant figures
            if len(mantissa_clean) > 5:
                # Need to round to 5 sig figs
                scale = 10 ** (int(exponent) - 4)  # Position for 5th sig fig
                if round_down:
                    num = np.floor(num / scale) * scale
                else:
                    num = np.ceil(num / scale) * scale

            # Now apply decimal place constraint
            if round_down:
                formatted = f"{np.floor(num * 10 ** max_decimal_places) / 10 ** max_decimal_places:.{max_decimal_places}f}"
            else:
                formatted = f"{np.ceil(num * 10 ** max_decimal_places) / 10 ** max_decimal_places:.{max_decimal_places}f}"

        else:
            raise ValueError(f"size_or_price must be 'SIZE' or 'PRICE', got {size_or_price}")

        # Remove trailing zeroes (required for Hyperliquid signing)
        formatted = formatted.rstrip('0').rstrip('.')

        return formatted

    def submit_order(self, order: Order) -> None:
        logger.info('Hyperliquid order submission.')
        logger.info(order)
        
        # Register plotting hook
        order.on_status_change(self._order_on_status_change_callback_for_plotting)
        
        # Trigger pending order
        self._order_on_status_change_callback_for_plotting(order=order, modified_time=order.time)
        
        try:
            # Format the symbol
            # symbol = f"{order.base_symbol}/{order.quote_symbol}" # <- BTC/USDC not working. 
            symbol = self.config['symbol']['id'] # <- UBTC/USDC
            
            time.sleep(1)
            # Determine if it's a buy or sell order
            is_buy = order.order_side == "BUY"

            # Format size and price using the new function
            size = float(self.__approximate_and_format_size_or_price('SIZE', order.size))
            price = float(self.__approximate_and_format_size_or_price('PRICE', order.price, round_down=(
                    order.order_side == "BUY"))) if order.order_type == "LIMIT" else None

            if order.order_id is None:
                raise exchange_exceptions.InvalidOrderSubmissionException(order, "Order id is not available")

            cloid = self.__get_cloid_from_order_id(order.order_id)
            # Set order type
            order_type = {}
            if order.order_type == "LIMIT":
                order_type = {"limit": {"tif": "Gtc"}}
                order_result = self.exchange_client.order(symbol, is_buy, size, price, order_type, cloid=cloid)
            else:  # MARKET order
                order_result = self.exchange_client.market_open(symbol, is_buy, size, cloid=cloid)

                # Alternatively submit order directly. But didn't work 
                # DEFAULT_SLIPPAGE = 0.05
                # px = self.exchange_client._slippage_price(symbol, is_buy, DEFAULT_SLIPPAGE, None)
                # order_type = { "trigger": {"isMarket": True,  "triggerPx": 0.0, "tpsl": "tp" } } # Double check this setup
                # order_result = self.exchange_client.order(symbol, is_buy, size, px, order_type, cloid=cloid)
            self._state.get('incomplete_orders').add(order)
            
            # Submit the order
            if order_result["status"] == "ok":
                for status in order_result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        self.__sync_order_status_with_hyperliquid(
                            order_data=status,
                            order_id=order.order_id,
                            event_time=datetime.datetime.now(pytz.utc)
                        )
                    if "error" in status:
                        error = status["error"]
                        logger.error(f'Order #{order.order_id} error: {error}')
                        order.reject(modified_time=datetime.datetime.now(pytz.utc))
            else:
                logger.error(f'Order rejected by Hyperliquid: {order_result["status"]} {order_result}')
                order.reject(modified_time=datetime.datetime.now(pytz.utc))

            return
            
            
            # Process the order result
            if order_result["status"] == "ok":
                status = order_result["response"]["data"]["statuses"][0]
                
                # Handle filled orders
                if "filled" in status:
                    # Process filled order
                    self.__sync_order_status_with_hyperliquid(
                        order_data=status,
                        order_id=order.order_id,
                        event_time=datetime.datetime.now(pytz.utc)
                    )
                # Handle resting orders
                elif "resting" in status:
                    # Store the Hyperliquid OID for later reference
                    order.hyperliquid_oid = status["resting"]["oid"]
            else:
                # Handle rejected orders
                logger.error(f'Order rejected by Hyperliquid: {order_result}')
                order.reject(modified_time=datetime.datetime.now(pytz.utc))
                
        except Exception as e:
            logger.error(f'Error happened while submitting order: {order.order_id}. Hence order is rejected. {e}')
            traceback.print_exc()
            order.reject(modified_time=datetime.datetime.now(pytz.utc))

    def cancel_order(self, order: Order) -> None:
        logger.info(f'Cancelling order: {order.order_id}')
        cloid = self.__get_cloid_from_order_id(order.order_id)
        symbol = self.config['symbol']['id'] # Use the id instead
        try:
            # Cancel the order
            cancel_result = self.exchange_client.cancel_by_cloid(symbol, cloid)
            # Sucess response format: {'status': 'ok', 'response': {'type': 'cancel', 'data': {'statuses': ['success']}}}
            success = cancel_result.get('response', {}).get('data', {}).get('statuses', [None])[0] == 'success'
            if success:
                time.sleep(1)
                order.cancel()
                logger.info(f'Cancelled order: {order.order_id}')
            else:
                logger.error(f'Failed to cancel order: {order.order_id}, result: {cancel_result}')
                
        except Exception as e:
            logger.error(f'Error cancelling order: {order.order_id}, {e}')
            traceback.print_exc()

    def get_order(self, order_id) -> Union[Order, None]:
        cloid = self.__get_cloid_from_order_id(order_id)
        query_result = self.info.query_order_by_cloid(self.account_address, cloid)
        if 'order' in query_result:
            order_info = query_result['order']['order']
            order_status = query_result['order']['status']
            order_type = "LIMIT" if order_info["orderType"]=="Limit" else "MARKET"
            order = Order(
                order_id=order_id,
                base_symbol=order_info['coin'],
                quote_symbol=self.config['symbol']['quote'],
                order_side="BUY" if order_info['side']=="B" else "SELL",
                order_type=order_type, 
                size=float(order_info['sz']),
                no_state_trail=True, 
                price=float(order_info['limitPx']) if order_type == 'LIMIT' else None,
            )

            # List of  order status: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#query-order-status-by-oid-or-cloid
            if order_status == "canceled" in order_status or "Cancelled" in order_status:
                order.cancel()
            elif "reject" in order_status or "Reject" in order_status:
                order.reject()
            elif order_status == "open":
                pass
            elif order_status == "filled":
                logger.error(f'Order {order_id} is filled, not implemented')
            else:
                logger.error(f'Unknown order status: {order_status} for order {order_id}')
            return order
        else:
            return None


    def get_wallet_balance(self) -> Dict[str, AssetBalance]:
        return self._wallet_balance

    def get_fees(self) -> Tuple[float, float]:
        # Hyperliquid fees are typically fixed
        # For now, we'll return default values
        # These should be updated based on actual Hyperliquid fee structure
        if not hasattr(self, 'maker_fee_rate') or not hasattr(self, 'taker_fee_rate') or \
           self.maker_fee_rate is None or self.taker_fee_rate is None:
            self.maker_fee_rate = 0.0002  # 0.02%
            self.taker_fee_rate = 0.0005  # 0.05%
            
        return self.maker_fee_rate, self.taker_fee_rate

    def __refresh_order_status(self):
        logger.info('Hyperliquid order status refresh')
        incomplete_orders = self._state.get('incomplete_orders').get_all_as_ordered_list()
        
        for order in incomplete_orders:
            try:
                # Get the Hyperliquid OID
                oid = getattr(order, 'hyperliquid_oid', None)
                
                if oid is None:
                    continue
                
                # Format the symbol
                symbol = f"{order.base_symbol}/{order.quote_symbol}"
                
                # Query the order status
                order_status = self.info.query_order_by_oid(self.account_address, oid)
                
                # Process the order status
                if order_status and "status" in order_status:
                    self.__sync_order_status_with_hyperliquid(
                        order_data=order_status,
                        order_id=order.order_id,
                        event_time=datetime.datetime.now(pytz.utc)
                    )
            except Exception as e:
                logger.error(f'Error refreshing order status for {order.order_id}: {e}')
                traceback.print_exc()

    def __refresh_wallet_balance(self):
        logger.info('Wallet balance refreshed')
        try:
            # Get spot user state
            spot_user_state = self.info.spot_user_state(self.account_address)
            wallet_balance = {}
            if "balances" in spot_user_state and len(spot_user_state["balances"]) > 0:
                for balance in spot_user_state["balances"]:
                    symbol = balance["coin"]
                    total_amount = float(balance["total"])
                    locked_amount = float(balance["hold"])
                    free_amount = total_amount - locked_amount
                    
                    wallet_balance[symbol] = AssetBalance(
                        symbol=symbol,
                        free=free_amount,
                        holding=locked_amount,
                        frozen=0.0  # Hyperliquid doesn't have a concept of frozen assets
                    )
            
            self._wallet_balance = wallet_balance
            
            # At least one wallet balance update must be received
            self._is_ready_for_trading = True
            
        except Exception as e:
            logger.error(f'Error refreshing wallet balance: {e}')
            traceback.print_exc()

    def __sync_order_status_with_hyperliquid(self, order_data, order_id=None, event_time=None):
        """
        Update order status based on Hyperliquid order data
        """
        try:
            incomplete_orders = self._state.get('incomplete_orders')
            
            # If order_id is not provided, try to extract it from order_data
            if order_id is None and "clientId" in order_data:
                order_id = order_data["clientId"]
            
            if order_id is None:
                logger.warn(f'Cannot sync order status: No order_id provided or found in order_data')
                return
            
            order = None
            if incomplete_orders is not None:
                order = incomplete_orders.get(order_id)
            
            if order is None:
                logger.debug(f'Received an order that is not registered: {order_id}')
                return
            
            # Set default event time if not provided
            if event_time is None:
                event_time = datetime.datetime.now(pytz.utc)
            
            # Process different order statuses
            if "filled" in order_data:
                # Order is filled
                incomplete_orders.pop(order_id)
                
                # Set up fees
                fees = self.__fee_class(config={})
                
                # Extract fee information if available
                base_fee = 0.0
                quote_fee = 0.0
                
                if "fee" in order_data["filled"]:
                    fee_amount = float(order_data["filled"]["fee"])
                    fee_currency = order_data["filled"].get("feeCurrency", order.quote_symbol)
                    
                    if fee_currency == order.base_symbol:
                        base_fee = fee_amount
                    elif fee_currency == order.quote_symbol:
                        quote_fee = fee_amount
                
                fees.set(base_fee=base_fee, quote_fee=quote_fee)
                
                # Get filled price if available
                filled_price = None
                if "avgPx" in order_data["filled"]:
                    filled_price = float(order_data["filled"]["avgPx"])
                
                order.fully_fill(
                    modified_time=event_time,
                    price=None if order.order_type == 'LIMIT' else filled_price,
                    fees=fees
                )
                
            elif "cancelled" in order_data:
                # Order is cancelled
                order.cancel(modified_time=event_time)
                incomplete_orders.pop(order_id)
                
            elif "rejected" in order_data:
                # Order is rejected
                order.reject(modified_time=event_time)
                incomplete_orders.pop(order_id)
                
            elif "partiallyFilled" in order_data:
                # Order is partially filled
                # Set up fees for the partial fill
                fees = self.__fee_class(config={})
                fees.set(base_fee=0, quote_fee=0)  # We'll set fees to 0 for partial fills for now
                
                # Get the filled size delta
                size_delta = float(order_data["partiallyFilled"]["size"])
                
                order.fill(
                    modified_time=event_time,
                    size_delta=size_delta,
                    fees_delta=fees
                )
                
        except Exception as e:
            logger.error(f'Error syncing order status with Hyperliquid: {e}')
            traceback.print_exc()
