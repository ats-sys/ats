import traceback
from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Union, Tuple

from ats.exceptions.general_exceptions import ConfigValidationException
from ats.exceptions.exchange_exceptions import OrderNotSubmittedException, ExchangeConnectionException
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.asset_balance import AssetBalance
from ats.exchanges.plot_data import PlotData
from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.utils.logging.logger import logger


class BaseExchange(ABC):
    """
    This is the base exchange class.
    Every exchange class must be implemented from this (Even the back trading must be extended from this class)
    """
    def __init__(self, config: dict, state: SimpleState = None):
        self.config = config

        self.is_connected = False

        self._validate_base_configs()
        # self._on_data_callable = None
        self.__on_candle_callable_custom = None
        self._state: SimpleState = state if state is not None else SimpleState()

        self.validate_config()
        self.maker_fee_rate, self.taker_fee_rate = None, None

        self._plot_data = PlotData(max_len=config['plot_data_max_len'])

        self._plot_data.set_topic(topic='Candle Close Price', color='blue', lines_or_markers='lines', pattern='solid')

        self._plot_data.set_topic(topic='LIMIT Order Placed: Buy', color='blue', lines_or_markers='markers',
                                  pattern='circle')
        self._plot_data.set_topic(topic='LIMIT Order Placed: Sell', color='blue', lines_or_markers='markers',
                                  pattern='triangle-up')
        self._plot_data.set_topic(topic='LIMIT Order Completed: Buy', color='green', lines_or_markers='markers',
                                  pattern='circle')
        self._plot_data.set_topic(topic='LIMIT Order Completed: Sell', color='green', lines_or_markers='markers',
                                  pattern='triangle-up')
        self._plot_data.set_topic(topic='MARKET Order Completed: Buy', color='black', lines_or_markers='markers',
                                  pattern='circle')
        self._plot_data.set_topic(topic='MARKET Order Completed: Sell', color='black', lines_or_markers='markers',
                                  pattern='triangle-up')
        self._plot_data.set_topic(topic='Order Canceled: Buy', color='gray', lines_or_markers='markers',
                                  pattern='circle')
        self._plot_data.set_topic(topic='Order Canceled: Sell', color='gray', lines_or_markers='markers',
                                  pattern='triangle-up')
        self._plot_data.set_topic(topic='Order Rejected: Buy', color='red', lines_or_markers='markers',
                                  pattern='circle')
        self._plot_data.set_topic(topic='Order Rejected: Sell', color='red', lines_or_markers='markers',
                                  pattern='triangle-up')

    @abstractmethod
    def validate_config(self) -> None:
        """
        Validation of the configs
        Returns:
            Returns None
        Raises:
            ConfigValidationException
        """
        pass

    def is_back_trading(self) -> bool:
        """
        Defines if the exchange is a back trading exchange or a live exchange.
        If the exchange is a back trading exchange, the jobs are handled differently.
        Returns:
            True if back trading exchange, False if live exchange
        """
        pass

    @abstractmethod
    def connect(self) -> None:
        """
        This contains the logic of connecting the exchange.
        This method will be called once after construction
        This method initiates connections with the exchange
        Returns:
            None
        Raises:
            ExchangeConnectionException
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Contains all the logic related to disconnecting from the exchange
        Returns:
            None
        Raises:
            ExchangeConnectionException
        """
        pass

    @abstractmethod
    def submit_order(self, order: Order) -> None:
        """
        Submit a new order
        Args:
            order: Order object

        Returns:
            None
        Raises:
            OrderNotSubmittedException
        """
        pass

    @abstractmethod
    def cancel_order(self, order: Order) -> None:
        """
        Order cancellation
        Args:
            order: Order obj

        Returns:
            None
        """

    @abstractmethod
    def get_order(self, order_id) -> Union[Order, None]:
        """
        Get an order given order Id
        Args:
            order_id:

        Returns:

        """
        pass

    @abstractmethod
    def get_wallet_balance(self) -> Dict[str, AssetBalance]:
        """
        Get wallet balance as a list of AssetBalance objects
        Returns:
            List of AssetBalance objects
        """
        pass

    @abstractmethod
    def get_fees(self) -> Tuple[float, float]:
        """
        Get the maker and taker fee rates for the current trading pair
        Returns:
            maker and taker frr rates associated with the trading pair
        """
        pass

    def get_state(self) -> SimpleState:
        """
        Returns the internal state of the exchange
        Returns:
            Instance of BaseState containing all the states of the exchange
        """
        return self._state

    def on_candle(self, on_data_callable: Callable[[Candle], None]) -> None:
        """
        Registers a callable based on received data
        Args:
            on_data_callable: Callable to be called

        Returns:
            None
        """
        self.__on_candle_callable_custom = on_data_callable

    def remove_on_candle_callback(self) -> None:
        """
        Removes registered on_candle callback
        Returns:
            None
        """
        self.__on_candle_callable_custom = None

    def get_plot_data(self) -> PlotData:
        """
        Get the plot data object
        Returns:
            PlotData object
        """
        return self._plot_data

    def _on_candle_callable(self, candle: Candle) -> None:
        """
        On data callback
        Args:
            candle: Candle object

        Returns:

        """
        if self.__on_candle_callable_custom is not None:
            try:
                self.__on_candle_callable_custom(candle)
            except Exception as e:
                logger.error(e)
                traceback.print_exc()
                logger.error('Exchange is disconnecting due to error...')
                self.disconnect()
                logger.error('Exchange is disconnected.')

        self._plot_data.add(topic='Candle Close Price', num=candle.close, time=candle.time)

    def _validate_base_configs(self) -> None:
        """
        Validates the base configs
        Returns:
            Returns None
        Raises:
            ConfigValidationException
        """
        required_properties = ['symbol', 'extra', 'plot_data_max_len']

        for prop in required_properties:
            if prop not in self.config:
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

    def _order_on_status_change_callback_for_plotting(self, order: Order, modified_time, note: str = ''):
        plot_data = None

        plot_label = order.order_id if note == '' else order.order_id + '\n' + note

        if order.order_type == 'LIMIT':
            if order.order_status == OrderStatus.PENDING and order.order_side == 'BUY':
                plot_data = {
                    'topic': 'LIMIT Order Placed: Buy',
                    'time': modified_time,
                    'num': order.price,
                    'label': plot_label
                }

            if order.order_status == OrderStatus.PENDING and order.order_side == 'SELL':
                plot_data = {
                    'topic': 'LIMIT Order Placed: Sell',
                    'time': modified_time,
                    'num': order.price,
                    'label': plot_label
                }

            if order.order_status == OrderStatus.FILLED and order.order_side == 'BUY':
                plot_data = {
                    'topic': 'LIMIT Order Completed: Buy',
                    'time': modified_time,
                    'num': order.price,
                    'label': plot_label
                }

            if order.order_status == OrderStatus.FILLED and order.order_side == 'SELL':
                plot_data = {
                    'topic': 'LIMIT Order Completed: Sell',
                    'time': modified_time,
                    'num': order.price,
                    'label': plot_label
                }

        if order.order_type == 'MARKET':
            if order.order_status == OrderStatus.FILLED and order.order_side == 'BUY':
                plot_data = {
                    'topic': 'MARKET Order Completed: Buy',
                    'time': modified_time,
                    'num': order.price,
                    'label': plot_label
                }

            if order.order_status == OrderStatus.FILLED and order.order_side == 'SELL':
                plot_data = {
                    'topic': 'MARKET Order Completed: Sell',
                    'time': modified_time,
                    'num': order.price,
                    'label': plot_label
                }

        if order.order_status == OrderStatus.CANCELED and order.order_side == 'BUY':
            plot_data = {
                'topic': 'Order Canceled: Buy',
                'time': modified_time,
                'num': order.price,
                'label': plot_label
            }

        if order.order_status == OrderStatus.CANCELED and order.order_side == 'SELL':
            plot_data = {
                'topic': 'Order Canceled: Sell',
                'time': modified_time,
                'num': order.price,
                'label': plot_label
            }

        if order.order_status == OrderStatus.REJECTED and order.order_side == 'BUY':
            plot_data = {
                'topic': 'Order Rejected: Buy',
                'time': modified_time,
                'num': order.price,
                'label': plot_label
            }

        if order.order_status == OrderStatus.REJECTED and order.order_side == 'SELL':
            plot_data = {
                'topic': 'Order Rejected: Sell',
                'time': modified_time,
                'num': order.price,
                'label': plot_label
            }

        if plot_data is not None:
            self._plot_data.add(**plot_data)
