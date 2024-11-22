import datetime
import time
import uuid
import pytz
from typing import Union, List
from ats.state.simple_state import SimpleState
from ats.utils.logging.logger import logger
from ats.utils.general import helpers as generic_helpers
from ats.exchanges.base_exchange import BaseExchange
from ats.strategies.base_strategy import BaseStrategy


class TradingJob:
    """
    TradingJob class links strategy and exchange together.
    Objects from this class is created based on Strategy and Exchange configurations by the trading manager
    This class hold all the required methods to manage the operations of trading jobs.
    """
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.exchange: Union[BaseExchange, None] = None
        self.strategy: Union[BaseStrategy, None] = None
        self.is_running = False
        self._last_started_time = None
        self._created_time = datetime.datetime.now(pytz.utc)
        self.config = {}

    def set_config(self, config: dict) -> None:
        """
        Sets the configurations
        Args:
            config: Configurations as a dict

        Returns:
            None
        """
        # TODO: Validate the configs
        self.config = config

    def load_exchange(self) -> bool:
        """
        Loads the exchange class according to the config.
        This reloads or loads the defined exchange class
            - loading means creating a new instance of the exchange class
            - reloading means creating a new instance of the exchange class with previous state.
                - This is important when we want to make some changes to the exchange class or its config and reload
                    without terminating a running trading job
        Returns:
            True if exchange is loaded with previous state. This means, reloading the exchange class
            False if exchange was loaded with no previous state
        """
        prev_state = None
        exchange_config = self.config['exchange']
        if self.exchange is not None:
            prev_state = self.exchange.get_state()
            logger.info(f"Exchange '{exchange_config['namespace']}' loading with previous state")

        exchange_class = generic_helpers.get_class_from_namespace(self.config['exchange']['namespace'])
        self.exchange = exchange_class(config=exchange_config['config'], state=prev_state)

        logger.info(f"Exchange '{exchange_config['namespace']}' loaded")

        return True if prev_state is not None else False

    def load_strategy(self) -> bool:
        """
        Loads the strategy class according to the config.
        This reloads or loads the defined strategy class
            - loading means creating a new instance of the strategy class
            - reloading means creating a new instance of the strategy class with previous state.
                - This is important when we want to make some changes to the exchange class or its config and reload
                    without terminating a running trading job
        Returns:
            True if strategy is loaded with previous state. This means, reloading the strategy class
            False if strategy was loaded with no previous state
        """
        prev_state = None
        strategy_config = self.config['strategy']
        if self.exchange is not None:
            prev_state = self.exchange.get_state()
            logger.info(f"Strategy '{strategy_config['namespace']}' loading with previous state")
        strategy_class = generic_helpers.get_class_from_namespace(self.config['strategy']['namespace'])
        self.strategy = strategy_class(config=strategy_config['config'], state=prev_state)

        logger.info(f"Strategy '{strategy_config['namespace']}' loaded")

        return True if prev_state is not None else False

    def run(self) -> None:
        """
        Runs the trading job
        Returns:
            None
        """
        try:
            self.strategy.set_exchange(exchange=self.exchange)
            self.exchange.on_candle(self.strategy.on_candle)
            self.is_running = True
            self._last_started_time = datetime.datetime.now(pytz.utc)

            # This line may not return (depending on the exchange). Do not write code after this section.
            self.exchange.connect()

            # In the case of back trading, connect() will execute the loop in a non-threaded way. That means, connect() will wait.
            if self.exchange.is_back_trading():
                self.stop()

        except Exception as e:
            self.is_running = False
            raise e

    def stop(self):
        """
        Stops the trading job
        Returns:
            None
        """
        self.strategy.on_stop()
        self.exchange.disconnect()
        self.is_running = False

    def get_status(self) -> dict:
        """
        Get the current status of the trading job
        Returns:
            Status of the trading job as a dict
        """
        status = {
            'id': self.id,
            'is_running': self.is_running and self.exchange.is_connected,
            'created_time': self._created_time.strftime('%Y-%m-%d %H:%M:%S'),
            'last_started_time': self._last_started_time.strftime('%Y-%m-%d %H:%M:%S') if self._last_started_time is not None else None,
            'exchange': {
                'namespace': self.config['exchange']['namespace']
            },
            'strategy': {
                'namespace': self.config['strategy']['namespace']
            }
        }

        if hasattr(self.exchange, 'get_back_trading_progress'):
            back_trading_progrsss = self.exchange.get_back_trading_progress()
            if back_trading_progrsss is not None:
                status['exchange']['back_trading_progress'] = back_trading_progrsss

        return status

    def get_plot_data(self):
        """
        Get the plots for the job
        Returns:
            None
        """
        return self.exchange.get_plot_data()
