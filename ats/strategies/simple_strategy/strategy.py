import random
from ats.strategies.base_strategy import BaseStrategy
from ats.exceptions.general_exceptions import ConfigValidationException
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.order import Order
from ats.utils.logging.logger import logger


class Strategy(BaseStrategy):
    """
    This strategy trades randomly.
    It take the number "random_number_limit" in config and generate a random number from 0 to random_number_limit.
    Then if that number is divisible by "execution_rate_control", a trade is made
        - Half of the time, a BUY trade is made
        - 1/3rd of the time a MARKET order is submitted (either BUY or SELL)
    """
    # Implemented the base class abstract method
    def validate_config(self) -> None:
        required_properties = ['random_number_limit', 'trade_rate_control', 'order_size', 'price_step',
                               'base_symbol', 'quote_symbol']

        for prop in required_properties:
            if prop not in self.config:
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

    # Implemented the base class abstract method
    def on_candle(self, candle: Candle) -> None:
        rand_limit = self.config['random_number_limit']
        trade_rate_control = self.config['trade_rate_control']
        log_trade_activity = self.config['log_trade_activity']
        price_step = self.config['price_step']
        order_size = self.config['order_size']

        order_type = 'MARKET' if random.randint(0, rand_limit) % 3 == 0 else 'LIMIT'
        order_side = 'BUY' if random.randint(0, rand_limit) % 2 == 0 else 'SELL'

        price = candle.close + price_step if order_side == 'SELL' else candle.close - price_step

        # Random submission
        if random.randint(0, rand_limit) % trade_rate_control == 0:
            order = Order(
                quote_symbol=self.config['quote_symbol'],
                base_symbol=self.config['base_symbol'],
                order_type=order_type,
                order_side=order_side,
                price=price if order_type == 'LIMIT' else None,
                size=order_size,
                time=candle.time
            )

            if log_trade_activity:
                logger.info(f'Trade submitted: {order}')

            self.exchange.submit_order(order)


