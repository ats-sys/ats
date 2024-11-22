import os
import pickle
import time
import uuid

from typing import List, Literal, Callable, Union
from threading import Lock

from ats.exchanges.base_exchange import BaseExchange
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.candle import Candle
from ats.utils.logging.logger import logger
from ats.utils.time.timer import Timer


STORE_PATH = './saved_states'


class PendingOrderManager:
    """
    TODO: This class is not thread safe. Make it thread safe.
    This class implements a mechanism of maintaining a list of pending trades and cancelling them
    Until the price is close to the pending trade's price
    When the price is close to the pending trade's level, then it resubmits the trade.
    This allows the trading algorithm to run efficiently and provides more usable asset to trade
    """

    def __init__(self, exchange: BaseExchange, config: dict, id: str = '') -> None:
        self.config = config

        # This name is used to save the states of the order manager
        self.id = id if id != '' else str(uuid.uuid4())

        self.exchange = exchange

        self._thread_lock = Lock()

        self._validate_config()

        self.orders_records = []
        self._on_new_order_callback = None
        self._on_cancel_order_callback = None
        self._price_gap_perc_cancel = float(config['price_gap_perc_cancel'])  # Price gap as a percentage for cancelling orders
        self._price_gap_perc_reenter = float(
            config['price_gap_perc_reenter'])  # Price gap as a percentage for reentering orders

        # Save the pending order state to the disk
        self._state_sync_disk_timer = Timer(on_timer=self._save_to_disk, interval=5, no_threading=False)

        logger.info(f'Pending order manager: Pending order manager was started with id {self.id}')

    def load(self):
        """
        Reload past states from the disk
        Note: on_new_order has to be registered before calling this
        Returns:
            None
        """
        if self._on_new_order_callback is None:
            raise Exception('on_new_order() must be called before calling reload_form_disk()')

        # Reload the previously saved status
        self._reload_from_disk()
        self._state_sync_disk_timer.start()

    def on_new_order(self, callback: Callable):
        self._on_new_order_callback = callback

    def on_cancel_order(self, callback: Callable):
        self._on_cancel_order_callback = callback

    def watch_price(self, candle: Candle):
        """
        Per every candle, order
        Args:
            candle: current Candle

        Returns:
            None
        """

        orders_to_remove = []
        for order_record_idx, order_record in enumerate(self.orders_records):
            order = order_record['order']
            # If an order is not pending or cancelled, then remove that order from the order list
            # If an order is in cancelled state and if it is not cancelled by this class. remove the order
            # If an order is in rejected state and if the order is not submitted by this class, remove the order
            if order.order_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED] \
                    or order.order_status == OrderStatus.CANCELED \
                    and order_record['is_cancelled_here'] == False:
                orders_to_remove.append(order_record_idx)

            else:  # else cancel or activate the order again
                what_to_do = self._what_to_do_to_order(order_record, candle)

                if what_to_do is not None:
                    new_order = self._change_order_status(order_record_idx, candle, what_to_do)

                    if new_order is not None and self._on_new_order_callback is not None:
                        self._on_new_order_callback(new_order, candle)

        self.orders_records = [order_record for idx, order_record in enumerate(self.orders_records) if
                               idx not in orders_to_remove]

    def register_order(self, order: Order):
        # Only limit orders are can become pending orders
        # And only pending orders are registered
        if order.order_type == 'LIMIT' and order.order_status == OrderStatus.PENDING:
            # TODO: make it more efficient with dict because we are using "in" on a list
            if order not in self.orders_records:
                self.orders_records.append({
                    'order': order,

                    # When cancelling the order by this class, this is set to True.
                    # Otherwise, we have no way to separate orders cancelled by the current class and
                    #   the orders separated by some external logic
                    'is_cancelled_here': False,

                    # True if the order is created in this class
                    # This is important to handle rejected states later
                    'is_order_created_here': False
                })

    def _validate_config(self):
        required_props = ['price_gap_perc_cancel','price_gap_perc_reenter', 'almost_market_order_perc']

        for required_prop in required_props:
            if required_prop not in self.config:
                raise Exception(f'{required_prop} is not found in PendingTradeManager config.')

    def _what_to_do_to_order(self, order_record: dict, candle: Union[Candle, None]) -> [None, str]:
        """
        Returns what should happen to the order
        Depending on the price the order must be cancelled, make active (pending) or do nothing
        Args:
            order: Order
            candle: Candle

        Returns:
            Returns what to do
        """
        order = order_record['order']
        if order.order_status == OrderStatus.PENDING:
            if order.order_side == 'BUY':
                dist_perc = 100 * (candle.close - order.price) / order.price
                if dist_perc >= self._price_gap_perc_cancel:
                    return OrderStatus.CANCELED

            if order.order_side == 'SELL':
                dist_perc = 100 * (order.price - candle.close) / order.price
                if dist_perc >= self._price_gap_perc_cancel:
                    return OrderStatus.CANCELED

        # Both REJECTED and CANCELLED orders must be retried
        # But they must be either cancelled by this class or created by this class
        if order.order_status == OrderStatus.CANCELED and order_record['is_cancelled_here'] \
                or order.order_status == OrderStatus.REJECTED and order_record['is_order_created_here']:
            if order.order_side == 'BUY':
                dist_perc = 100 * (candle.close - order.price) / order.price
                if dist_perc < self._price_gap_perc_reenter:  # Check if the distance is in -inf to self._price_gap_perc
                    return OrderStatus.PENDING

            if order.order_side == 'SELL':
                dist_perc = 100 * (order.price - candle.close) / order.price
                if dist_perc < self._price_gap_perc_reenter:  # Check if the distance is in -inf to self._price_gap_perc
                    return OrderStatus.PENDING
        return None

    def _change_order_status(self, order_rec_idx: int, candle: Candle, change_to_status: str) -> [None, Order]:
        """
        Change the order status by cancelling or resubmitting the order
        If the current order is cancelled, a new order will be submitted
        If the current order is in pending state, it will be cancelled
        This method doesn't care about the price distance logic
        If order goes from cancelled to pending state, a new order will be created and the new order id will be returned
        Args:
            order_rec_idx: index of the order in self.order_records.
            candle: Candle
            change_to_status: to which order status the order should be changed to
        Returns:
            Returns the changed order or None if the order goes from pending
        """
        order = self.orders_records[order_rec_idx]['order']
        if order.order_status == OrderStatus.PENDING and change_to_status == OrderStatus.CANCELED:
            self.exchange.cancel_order(order)
            self.orders_records[order_rec_idx]['is_cancelled_here'] = True

            if self._on_cancel_order_callback is not None:
                self._on_cancel_order_callback(order, candle)

        elif order.order_status in [OrderStatus.CANCELED, OrderStatus.REJECTED] and change_to_status == OrderStatus.PENDING:
            new_order_price = order.price

            if order.order_side == 'BUY' and new_order_price > candle.close:  # Candle is moved below the previous order price.
                # Just below the candle close price
                new_order_price = candle.close * (1 - self.config['almost_market_order_perc'] / 100)

            if order.order_side == 'SELL' and new_order_price < candle.close:
                # Just above the candle close price
                new_order_price = candle.close * (1 + self.config['almost_market_order_perc'] / 100)

            try:
                new_order = Order(
                    price=new_order_price,
                    size=order.size,
                    quote_symbol=order.quote_symbol,
                    base_symbol=order.base_symbol,
                    order_side=order.order_side,
                    order_type=order.order_type,
                    time=candle.time
                )
                self.exchange.submit_order(new_order)
                self.orders_records[order_rec_idx]['order'] = new_order
                self.orders_records[order_rec_idx]['is_order_created_here'] = True
                return new_order
            except Exception as e:
                # TODO: remove raising e.
                raise e

    def _reload_from_disk(self):
        """
        Reload the orders from the disk
        Returns:
            None
        """
        order_ids = []

        if os.path.exists(os.path.join(STORE_PATH, f'pending_order_manager_status_{self.id}.pickle')):
            with open(os.path.join(STORE_PATH, f"pending_order_manager_status_{self.id}.pickle"), "rb") as f:
                order_ids = pickle.load(f)
                logger.info(f'Pending order manager: loaded the order IDs from the disk {order_ids}')

        for order_id in order_ids:
            logger.info(f'Pending order manager: Fetching order objects from exchange for order id: {order_id}')
            try:
                order = self.exchange.get_order(order_id)
            except Exception as e:
                logger.info(f'Pending order manager: Order id {order_id} is not loaded because it is not registered in the exchange')
                continue

            if order.order_status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
                self._on_new_order_callback(order, None)
                self.orders_records.append({
                    'order': order,

                    # When cancelling the order by this class, this is set to True.
                    # Otherwise, we have no way to separate orders cancelled by the current class and
                    #   the orders separated by some external logic
                    'is_cancelled_here': False,

                    # True if the order is created in this class
                    # This is important to handle rejected states later
                    'is_order_created_here': False
                })
                logger.info(f'Pending order manager: Order id {order_id} is loaded.')
            else:
                logger.info(f'Pending order manager: Order id {order_id} is not loaded because it is in {order.order_status}')

            time.sleep(0.5)

    def _save_to_disk(self):
        """
        Saves the orders to the disk
        Returns:
            None
        """
        if not os.path.exists(STORE_PATH):
            try:
                os.makedirs(STORE_PATH)
                logger.info(f"Pending order manager: Directory created: {STORE_PATH} for saving states of pending order manager.")
                return True
            except OSError as error:
                print(f"Pending order manager: Error creating directory: {error}")
                return False

        order_ids = [order_record['order'].order_id for order_record in self.orders_records]

        with open(os.path.join(STORE_PATH, f"pending_order_manager_status_{self.id}.pickle"), "wb") as f:
            logger.info(f'Pending order manger: Saving {len(order_ids)} order ids.')
            pickle.dump(order_ids, f)

    def stop(self):
        """
        Stopping the pending order manager.
        Returns:

        """
        logger.info('Pending order manager: Stopping the pending order manager...')
        self._state_sync_disk_timer.delete()

