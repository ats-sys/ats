import unittest
import yaml
import pandas as pd
import random
from ats.exchanges.exchanges.back_trading.exchange import Exchange
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.order import Order

RAND_LIMIT = 1000  # upper limit of the random int generation (going from 0 to RAND_LIMIT)
TRADE_RATE_CONTROL = 100  # A trade will happen when the random int is a multiple of this number


class TestExchange(unittest.TestCase):
    def setUp(self) -> None:
        with open('tests/configs/back_trading_exchange_config.yaml', 'r') as file:
            # Load the YAML content into a dictionary
            self.config = yaml.safe_load(file)
            self.exchange = Exchange(self.config['exchange']['config'])

            df = pd.read_csv(self.config['exchange']['config']['extra']['data_source'])
            self.back_trading_data = df.values.tolist()

    def test_exchange_run(self):
        """
        Check if the back trading runs properly
        - A run should go through all the candles in the dataset (number of on_data callback calls == length of data)
        - Every datapoint coming to the on_data must be a Candle object
        - TODO: Verify, if every execution happened at the right price condition
        """
        self.__counter = 0

        def on_data_callable(candle):
            self.assertIsInstance(candle, Candle)
            self.__counter += 1

            order_type = 'MARKET' if random.randint(0, RAND_LIMIT) % 3 == 0 else 'LIMIT'
            order_side = 'BUY' if random.randint(0, RAND_LIMIT) % 2 == 0 else 'SELL'

            random_num = random.randint(0, RAND_LIMIT)
            price = candle.close * (1 + random_num / RAND_LIMIT/5) if order_side == 'SELL' else candle.close * (1 - random_num / RAND_LIMIT / 5)

            wallet_balance = self.exchange.get_wallet_balance()

            # Random submission
            if random.randint(0, RAND_LIMIT) % TRADE_RATE_CONTROL == 0:
                order = Order(
                    quote_symbol='USD',
                    base_symbol='BTC',
                    order_type=order_type,
                    order_side=order_side,
                    price=price if order_type == 'LIMIT' else None,
                    size=wallet_balance['BTC'].free / 1000,
                    time=candle.time
                )
                self.exchange.submit_order(order)

        self.exchange.on_candle(on_data_callable)
        self.exchange.connect()
        self.assertEqual(self.__counter, len(self.back_trading_data))

        plot_configs = []

        for topic in self.exchange.get_plot_data().get_topics():
            plot_configs.append({
                'topic': topic,
                'col': 1,
                'row': 1,
            })

        fig = self.exchange.get_plot_data().plot_topics(plots=plot_configs)
        fig.show()

