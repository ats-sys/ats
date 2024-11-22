import time

import pandas as pd
import datetime
from typing import Union, List, Dict, Type, Tuple

from ats.exceptions.general_exceptions import ConfigValidationException
from ats.exceptions import exchange_exceptions
from ats.utils.logging.logger import logger
from ats.utils.general import helpers as general_helpers
from ats.exchanges.base_exchange import BaseExchange
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.asset_balance import AssetBalance
from ats.exchanges.exchanges.back_trading.wallet import Wallet
from ats.exchanges.base_fees import BaseFees


class Exchange(BaseExchange):
    def validate_config(self) -> None:
        required_properties = ['extra.data_source', 'extra.wallet', 'extra.min_trading_size']

        for prop in required_properties:
            if not general_helpers.check_nested_property_in_dict(prop, self.config):
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

        if isinstance(self.config['extra']['min_trading_size'], float.__class__):
            raise ConfigValidationException('Exchange Config', f"extra.min_trading_size must be a float, got {type(self.config['extra']['min_trading_size'])} .")

    def is_back_trading(self) -> bool:
        return True

    # Implemented the base class abstract method
    def connect(self):
        # The self._state variable is not used because self._back_trading state doesn't have to be serializable
        self.is_connected = True
        self._back_trading_orders = {}  # Indexed with the order id
        self._back_trading_unprocessed_order_ids = []  # List of order ids.
        self._back_trading_execuiton_log = []  # holds the complete trade execution log
        self._back_trading_data = None
        self._back_trading_loop_stop = False
        self._back_trading_loop_current_candle = None
        self._back_trading_cur_candle_pos = 0  # For progress monitoring purposes only
        self._fee_class: Type[BaseFees] = general_helpers.get_class_from_namespace(self.config['extra']['fees']['namespace'])

        self._back_trading_load_data()
        self._back_trading_init_wallet()
        self._loop_through_data()

        self.is_connected = False

    # Implemented the base class abstract method
    def disconnect(self):
        self._back_trading_loop_stop = True
        self.is_connected = False

    # Implemented the base class abstract method
    def submit_order(self, order: Order) -> None:
        # Register plotting hook
        order.on_status_change(self._order_on_status_change_callback_for_plotting)

        # Trigger pending order
        self._order_on_status_change_callback_for_plotting(order=order, modified_time=order.time)

        if order.order_id in self._back_trading_orders:
            raise exchange_exceptions.InvalidOrderSubmissionException(order, 'Duplicate order submission')
        if order.size < self.config['extra']['min_trading_size']:
            raise exchange_exceptions.InvalidOrderSubmissionException(order, f"Order size {order.size} is less than allowed minimum size {self.config['extra']['min_trading_size']}")

        self._back_trading_orders[order.order_id] = order
        self._wallet.register_transaction(order)

        # Wallet might reject PENDING orders if there is no funding to hold asset for the LIMIT order.
        # Here we cover REJECT and CANCELED scenarios since the wallet has the right to change the status while registering
        if order.order_status != OrderStatus.REJECTED and order.order_status != OrderStatus.CANCELED:
            self._back_trading_unprocessed_order_ids.append(order.order_id)

        # TODO: Removed thread safety for faster execution
        self.__append_execution_log(order_state=order.get_state(is_thread_safe=False),
                                    candle=self._back_trading_loop_current_candle,
                                    wallet_balance=self._wallet.get_wallet_balance()
                                    )

    # Implemented the base class abstract method
    def cancel_order(self, order: Order) -> None:
        order.cancel(modified_time=self._back_trading_loop_current_candle.time)
        self._wallet.register_transaction(order)

    # Implemented the base class abstract method
    def get_order(self, order_id) -> Union[Order, None]:
        if order_id in self._back_trading_orders:
            return self._back_trading_orders[order_id]
        return None

    # Implemented the base class abstract method
    def get_wallet_balance(self) -> Dict[str, AssetBalance]:
        return self._wallet.get_wallet_balance()

    def get_fees(self) -> Tuple[float, float]:
        if self.maker_fee_rate is None or self.taker_fee_rate is None:
            fee_config = self.config['extra']['fees']["config"]
            assert fee_config["limit"]["buy"]["base"] == fee_config["limit"]["sell"]["quote"]
            assert fee_config["market"]["buy"]["base"] == fee_config["market"]["sell"]["quote"]

            self.maker_fee_rate = fee_config["limit"]["buy"]["base"] / 100
            self.taker_fee_rate = fee_config["market"]["buy"]["base"] / 100

        return self.maker_fee_rate, self.taker_fee_rate

    def get_back_trading_progress(self) -> Union[float, None]:
        """
        Returns the percentage of the back trading progress
        Returns:
            Progress as a float. Returns None if the back trading is not yet started
        """
        if hasattr(self, '_back_trading_data'):
            total_data_length = len(self._back_trading_data)
        else:
            return None
        return 100 *(self._back_trading_cur_candle_pos + 1) / total_data_length if total_data_length > 0 else 0.0

    def get_back_trading_execution_log(self) -> List[dict]:
        """
        Get back trading execution log.
        The log contains a list of all transactions. An element contains, order detail, the candle and the wallet balance
        Ex:
        [ {'order_state': <State of the order (dict)>, 'candle': <Candle object>, wallet_balance: <AssetBalance object>}]
        Returns:

        """
        return self._back_trading_execuiton_log

    def _back_trading_load_data(self) -> None:
        """
        Load data for back trading
        Returns:
            None
        """
        logger.info('Back trading data is being loaded.')

        data = self.__read_csv_as_list(self.config['extra']['data_source'])
        self._back_trading_data = data

        logger.info('Back trading data is loading completed.')

    def _back_trading_init_wallet(self) -> None:
        """
        Initialize wallet for back trading
        Returns:
            None
        """
        logger.info('Back trading wallet initialization.')
        self._wallet = Wallet(self.config['extra']['wallet'])

    def _loop_through_data(self) -> None:
        start_time = time.time()
        for idx, item in enumerate(self._back_trading_data):
            if self._back_trading_loop_stop:
                break

            self._back_trading_cur_candle_pos = idx

            candle = {
                'time': datetime.datetime.strptime(item[0], '%Y-%m-%d %H:%M:%S%z').replace(tzinfo=datetime.timezone.utc),
                'open': item[1],
                'high': item[2],
                'low': item[3],
                'close': item[4],
                'buy_vol': item[5],
                'sell_vol': item[6],
                'symbol': self.config['symbol']['base'] + self.config['symbol']['quote']
            }

            candle_data = Candle(**candle)
            self._back_trading_loop_current_candle = candle_data


            ids_to_be_removed = {}

            # Processing all the orders in the unprocessed orders list
            for unprocessed_order_id in self._back_trading_unprocessed_order_ids:
                order = self._back_trading_orders[unprocessed_order_id]
                processed = self.__process_order_with_candle(candle=candle_data, order=order)

                order._last_processed_candle = candle  # Marking the last processed candle for backtrading only

                if processed and order.order_status == OrderStatus.FILLED or order.order_status == OrderStatus.REJECTED or order.order_status == OrderStatus.CANCELED:
                    ids_to_be_removed[unprocessed_order_id] = True

            self._back_trading_unprocessed_order_ids = [item for item in self._back_trading_unprocessed_order_ids if item not in ids_to_be_removed]

            self._on_candle_callable(candle_data)

        end_time = time.time()
        logger.info(f"Back trading run completed in {end_time - start_time}")
        self.__back_trading_summary()

    def __process_order_with_candle(self, candle: Candle, order: Order) -> bool:
        """
        Trigger different wallet methods to change the status of the order
         - Order object is processed inside the wallet object
         - Since order object stored in self._back_trading_orders and in the Wallet object by reference,
            no need to return the Order object

        Args:
            candle: Candle object
            order: Order objects

        Returns:
            True: if processed, False: not processed
        """
        # Execute MARKET orders
        if order.order_type == 'MARKET':
            fees = self._fee_class(self.config['extra']['fees']['config'])
            fees.calculate(size=order.size, price=candle.close, order_type=order.order_type,
                           order_side=order.order_side)
            order.fully_fill(price=candle.close, fees=fees, modified_time=candle.time)
            self._wallet.register_transaction(order)  # Update the wallet

            if order.order_status == OrderStatus.REJECTED:
                return False

            # TODO: Removed thread safety for faster execution
            self.__append_execution_log(order_state=order.get_state(is_thread_safe=False),
                                        candle=candle,
                                        wallet_balance=self._wallet.get_wallet_balance()
                                        )
            return True

        # Execute LIMIT orders
        if order.order_type == 'LIMIT':
            # Reject order for book crossing
            if not hasattr(order, '_last_processed_candle') and (order.price > candle.close and order.order_side == 'BUY' \
                    or order.price < candle.close and order.order_side == 'SELL'):
                order.reject(modified_time=candle.time)
                self._wallet.register_transaction(order)  # Update the wallet
                logger.info(f'Order {order.order_id} got rejected for book crossing.  Candle close price: {candle.close}, order price: {order.price}, order side: {order.order_side}')
                return True

            # Execution after matching price
            if order.price >= candle.low and order.order_side == 'BUY' or order.price <= candle.high and order.order_side == 'SELL':
                fees = self._fee_class(self.config['extra']['fees']['config'])
                fees.calculate(size=order.size, price=candle.close, order_type=order.order_type,
                               order_side=order.order_side)
                order.fully_fill(fees=fees, modified_time=candle.time)
                self._wallet.register_transaction(order)  # Update the wallet
                self.__append_execution_log(order_state=order.get_state(is_thread_safe=False),
                                            candle=candle,
                                            wallet_balance=self._wallet.get_wallet_balance()
                                            )
                if order.order_status == OrderStatus.REJECTED:
                    return False
                return True

        return False

    def __read_csv_as_list(self, file_name: str):
        """
        Reads csv file (get_backtranding data)
        Returns:
            list
        """
        df = pd.read_csv(file_name)
        data_list = df.values.tolist()
        return data_list

    def __append_execution_log(self, order_state: dict, candle: Candle, wallet_balance: Dict[str, AssetBalance]) -> None:
        """
        Append the back trading execution log
        Args:
            order_state: order state
            candle: Candle object
            wallet_balance: AssetBalance object

        Returns:
            None
        """
        self._back_trading_execuiton_log.append({
            'order_state': order_state,
            'candle': candle,
            'wallet_balance': wallet_balance
        })

    def __back_trading_summary(self):
        execution_summary = {}
        for var_name, var_value in vars(OrderStatus).items():
            if not var_name.startswith('_'):
                # execution_summary[var_name] = 0
                execution_summary[var_name] = {
                    'ALL': 0,
                    'BUY': 0,
                    'SELL': 0
                }

        tot = 0

        for order_id, order in self._back_trading_orders.items():
            execution_summary[order.order_status]['ALL'] += 1
            execution_summary[order.order_status][order.order_side] += 1
            tot += 1

        summary_str = ''
        # for key, item in execution_summary.items():
        #     summary_str += f'\n\t{key}: {item}'
        for key, item in execution_summary.items():
            summary_str += f'\n\t{key}: {item["ALL"]}'
            summary_str += f'\n\t\tBUY: {item["BUY"]}'
            summary_str += f'\n\t\tSELL: {item["SELL"]}'

        summary_str += f'\n\tTotal: {tot}'

        logger.info(f'Execution summary: {summary_str}')
