from typing import Union
from abc import ABC, abstractmethod
from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.base_exchange import BaseExchange


class BaseStrategy(ABC):
    def __init__(self, config: dict, state: SimpleState = None):
        """
        Initiates Strategy object
        Args:
            config: Config as a dict
            state: State object. All the states of the strategy must be set as a key value pair here.
                    In the case of a restart, if the previous states to be continued, state object with backed up states
                    must be loaded
        """
        self.config = config
        self._state = state if state is not None else SimpleState()
        self.exchange: Union[BaseExchange, None] = None
        self.validate_config()

    @abstractmethod
    def validate_config(self) -> None:
        """
        Validates the config.
        The strategy must override with its own logic to validate received configs
        Returns:
            None
        """
        pass

    @abstractmethod
    def on_candle(self, candle: Candle) -> None:
        """
        This method is called when a candle is received from the exchange.
        The main logic of the strategy is written here.
        Args:
            candle: Candle

        Returns:

        """
        pass

    def set_exchange(self, exchange: BaseExchange) -> None:
        """
        Sets the exchange object.
        This is done by the trading job object after it initiates the strategy instance
        Args:
            exchange:

        Returns:
            None
        """
        self.exchange = exchange

    def get_state(self) -> SimpleState:
        """
        Returns the state of the strategy
        Returns:
            State as a SimpleState object
        """
        return self._state

    def on_stop(self) -> None:
        """
        This will be called by the trading job when the strategy is stopped
        Returns:
            None
        """
        pass