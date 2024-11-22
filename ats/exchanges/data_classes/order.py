from typing import Literal, Union, List, Callable
import datetime
import time
import copy
import uuid
import pytz
from dataclasses import dataclass
from threading import Lock

from ats.exceptions.order_exceptions import UnsupportedStatusException, OrderFillingException, InvalidOrderException, OrderStateSyncException, InvalidOrderOperationException
from ats.exchanges.base_fees import BaseFees


class OrderStatus:
    """
    Order class supports multi threading.
    Note that all the status reads are done using queue (in a thread safe way) while all the writes are done using thread locks
    """
    PENDING = 'PENDING'
    FILLED = 'FILLED'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    REJECTED = 'REJECTED'
    CANCELED = 'CANCELED'


@dataclass
class Order:
    """
    This class models an order.
    Order objects are submitted to an Exchange object.
    The status change of the order is automatically handled by the exchange object and therefore
        the Strategy objects and other objects referring the same Order object will get the updates immediately.
    """
    quote_symbol: str
    base_symbol: str
    order_side: Literal['BUY', 'SELL']
    order_type: Literal['LIMIT', 'MARKET']
    size: Union[int, float]
    price: Union[int, float] = None
    order_id: Union[str, None] = None
    time: Union[datetime.datetime, None] = None  # Required for back trading

    no_state_trail: bool = False  # If set to True, state trail will not be stored
    # This can be used, when live trading where, we cannot sync with the actual state trail

    def __post_init__(self):
        self._thread_lock = Lock()

        self.order_id = str(uuid.uuid4()) if self.order_id is None else self.order_id
        self.time = datetime.datetime.now(pytz.utc) if self.time is None else self.time

        # On status change hook callables
        self._on_status_changes: List[Callable] = []

        self._last_modified_time = self.time
        self.order_status = OrderStatus.PENDING

        self.filled_size = 0

        # Fees associated with the order
        self.fees: Union[dict, None] = None

        # When order is filled, this indicates the last filled size.
        # If an order is filled fully at once, self._size_delta becomes equal to self.filled_size
        self._filled_size_delta = 0

        self._state_trail: List[dict] = []

        self._validate_config()

        if self.order_type == 'LIMIT' and self.price is None:
            raise InvalidOrderException(order=self, error_message='Limit orders cannot be initiated without a price')

        if self.order_type == 'MARKET' and self.price is not None:
            raise InvalidOrderException(order=self, error_message='Market orders cannot be initiated with a price')

        self._state_trail.append(copy.deepcopy(self.get_state(is_thread_safe=False)))

    def get_state(self, is_thread_safe: bool = True) -> dict:
        """
        Get order state as a dict
        Args:
            is_thread_safe: If True, states are done in a thread safe way
        Returns:
            Dict containing the order status
        """
        if is_thread_safe:
            lock_acquire_count = 0

            while True:
                if not self._thread_lock.acquire(timeout=1):
                    if lock_acquire_count > 2:
                        raise Exception('order.get_state() failed to acquire thread lock. Tried 3 times.')
                    lock_acquire_count += 1
                    continue

                state_to_return = {
                    'id': self.order_id,
                    'order_id': self.order_id,
                    'quote_symbol': self.quote_symbol,
                    'base_symbol': self.base_symbol,
                    'order_side': self.order_side,
                    'order_type': self.order_type,
                    'size': self.size,
                    'price': self.price,
                    'filled_size': self.filled_size,
                    'filled_size_delta': self._filled_size_delta,
                    'fees': self.fees,
                    'order_status': self.order_status,
                    'time': self.time,
                    'last_modified_time': self._last_modified_time
                }

                self._thread_lock.release()

                return state_to_return


        return {
                'id': self.order_id,
                'order_id': self.order_id,
                'quote_symbol': self.quote_symbol,
                'base_symbol': self.base_symbol,
                'order_side': self.order_side,
                'order_type': self.order_type,
                'size': self.size,
                'price': self.price,
                'filled_size': self.filled_size,
                'filled_size_delta': self._filled_size_delta,
                'fees': self.fees,
                'order_status': self.order_status,
                'time': self.time,
                'last_modified_time': self._last_modified_time
            }

    def get_state_trail(self, is_thread_safe=True) -> List[dict]:
        """
        Get the state trail (sequence of events took place for the order)
        Returns:

        """
        if is_thread_safe:
            lock_acquire_count = 0

            while True:
                if not self._thread_lock.acquire(timeout=1):
                    if lock_acquire_count > 2:
                        raise Exception('order.get_state_trail() failed to acquire thread lock. Tried 3 times.')
                    lock_acquire_count += 1
                    continue

                state_to_return = copy.deepcopy(self._state_trail)

                self._thread_lock.release()

                return state_to_return

        return copy.deepcopy(self._state_trail)

    def fill(self, size_delta: Union[int, float], fees_delta: BaseFees, modified_time: datetime.datetime = None) -> None:
        """
        Fill the order with size delta.
        Args:
            size_delta:
            fees_delta:
            modified_time:

        Returns:
            None
        """
        lock_acquire_count = 0

        while True:
            if not self._thread_lock.acquire(timeout=1):
                if lock_acquire_count > 2:
                    raise Exception('order.fill() failed to acquire thread lock. Tried 3 times.')
                lock_acquire_count += 1
                continue
            try:
                if self.filled_size + size_delta > self.size:
                    raise OrderFillingException(order=self,
                                                error_message=f"Max fill size {self.size}, but filled with size {self.filled_size + size_delta}")

                if size_delta <= 0:
                    raise OrderFillingException(order=self, error_message=f"Order must be filled with positive size_delta")

                fees_delta = fees_delta.get()

                if self.fees is None:
                    self.fees = fees_delta
                else:
                    self.fees['base_fee'] += fees_delta['base_fee']
                    self.fees['quote_fee'] += fees_delta['quote_fee']

                self.filled_size += size_delta
                self._filled_size_delta = size_delta

                # Important: - order status update must be done at the end
                #            - This must me outside the thread lock. Otherwise, a deadlock happens
                if abs(self.filled_size - self.size) < 1e-9:  # Floating point errors must be accounted for
                    self._update_status(OrderStatus.FILLED, modified_time)
                else:
                    self._update_status(OrderStatus.PARTIALLY_FILLED, modified_time)

                self._thread_lock.release()
            except Exception as e:
                self._thread_lock.release()
                raise e

            break

    def fully_fill(self, fees: BaseFees, price: float = None, modified_time: datetime.datetime = None) -> None:
        """
        Fully fill an order (LIMIT or MARKET).
        Args:
            fees: Fee object for filling
            price: Leave None if LIMIT order
            modified_time: Datetime object (UTC) for the filling event

        Returns:
            None
        """
        lock_acquire_count = 0
        while True:
            if not self._thread_lock.acquire(timeout=1):
                if lock_acquire_count > 2:
                    raise Exception('order.fully_fill() failed to acquire thread lock. Tried 3 times.')
                lock_acquire_count += 1
                continue
            try:
                self.filled_size = self.size
                self._filled_size_delta = self.size
                self.fees = fees.get()

                if self.order_type == 'LIMIT' and price is not None:
                    raise OrderFillingException(order=self, error_message='For a LIMIT order, price is already set. '
                                                                          'No need to define the price when filling')
                if self.order_type == 'MARKET' and price is None:
                    raise OrderFillingException(order=self,
                                                error_message='For a MARKET order, price is always required '
                                                              'when filling')

                if price is not None:
                    self.price = price

                # Important: - order status update must be done at the end
                #            - This must me outside the thread lock. Otherwise, a deadlock happens
                self._update_status(OrderStatus.FILLED, modified_time)
                self._thread_lock.release()
            except Exception as e:
                self._thread_lock.release()
                raise e

            break


    def cancel(self, modified_time: datetime.datetime = None) -> None:
        """
        Cancels the order
        Args:
            modified_time:

        Returns:

        """
        lock_acquire_count = 0
        while True:
            if not self._thread_lock.acquire(timeout=1):
                if lock_acquire_count > 2:
                    raise Exception('order.cancel() failed to acquire thread lock. Tried 3 times.')
                lock_acquire_count += 1
                continue
            try:
                self._update_status(OrderStatus.CANCELED, modified_time)
                self._thread_lock.release()
            except Exception as e:
                self._thread_lock.release()
                raise e

            break

    def reject(self, modified_time: datetime.datetime = None) -> None:
        """
        Rejects the order
        Args:
            modified_time:

        Returns:
            None
        """
        lock_acquire_count = 0
        while True:
            if not self._thread_lock.acquire(timeout=1):
                if lock_acquire_count > 2:
                    raise Exception('order.reject() failed to acquire thread lock. Tried 3 times.')
                lock_acquire_count += 1
                continue
            try:
                self._update_status(OrderStatus.REJECTED, modified_time)
                self._thread_lock.release()
            except Exception as e:
                self._thread_lock.release()
                raise e

            break

    def on_status_change(self, callback: Callable) -> None:
        """
        Register an on status callback
        Args:
            callback: A callable. Receives following arguments
                        - order: Order object
                        - time: Datetime

        Returns:
            None
        """
        self._on_status_changes.append(callback)

    def _update_status(self, order_status: str, modified_time: datetime) -> None:
        if order_status not in [attr for attr in dir(OrderStatus) if not attr.startswith('_')]:
            raise UnsupportedStatusException(order=self, error_message=f"Unsupported order status {order_status}")

        if order_status == OrderStatus.CANCELED and self.order_status != OrderStatus.PENDING:
            return
            # raise UnsupportedStatusException(order=self,
            #                                  error_message=f"Can't cancel an order with status {self.order_status}")

        if order_status == OrderStatus.REJECTED and self.order_status != OrderStatus.PENDING:
            return
            # raise UnsupportedStatusException(order=self,
            #                                  error_message=f"Can't reject an order with status {self.order_status}")

        if order_status == OrderStatus.FILLED and not (
                self.order_status == OrderStatus.PENDING or self.order_status == OrderStatus.PARTIALLY_FILLED):
            raise UnsupportedStatusException(order=self,
                                             error_message=f"Can't fill an order with status {self.order_status}")

        if order_status == OrderStatus.PARTIALLY_FILLED and not (
                self.order_status == OrderStatus.PENDING or self.order_status == OrderStatus.PARTIALLY_FILLED):
            raise UnsupportedStatusException(order=self,
                                             error_message=f"Can't partially fill an order with status {self.order_status}")

        self.order_status = order_status
        self._last_modified_time = modified_time if modified_time is not None else datetime.datetime.now(pytz.utc)

        if not self.no_state_trail:
            self._state_trail.append(copy.deepcopy(self.get_state(is_thread_safe=False)))

        for on_status_change in self._on_status_changes:
            on_status_change(self, self._last_modified_time)

    def _validate_config(self):
        if self.order_type not in ['LIMIT', 'MARKET']:
            raise InvalidOrderException(self, "Order type must be either 'LIMIT' or 'MARKET'")

        if self.order_side not in ['SELL', 'BUY']:
            raise InvalidOrderException(self, "Order type must be either 'SELL' or 'BUY'")

        if self.order_type == 'LIMIT' and self.price is None:
            raise InvalidOrderException(self, 'Limit order must have a price.')

        if self.order_type == 'MARKET' and self.price is not None:
            raise InvalidOrderException(self, 'Market order cannot have a price.')

        if self.size < 0:
            raise InvalidOrderException(self, "Size cannot be negative")

        if self.price is not None and self.price < 0:
            raise InvalidOrderException(self, "Price cannot be negative")
