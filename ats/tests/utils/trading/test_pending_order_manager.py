import unittest
import yaml
import pandas as pd
import random
from ats.exchanges.exchanges.back_trading.exchange import Exchange
from ats.exchanges.data_classes.candle import Candle
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.utils.trading.pending_order_manager import PendingOrderManager

RAND_LIMIT = 1000  # upper limit of the random int generation (going from 0 to RAND_LIMIT)
TRADE_RATE_CONTROL = 100  # A trade will happen when the random int is a multiple of this number


class TestOrderManager(unittest.TestCase):
    def setUp(self) -> None:
        with open('tests/configs/back_trading_exchange_config.yaml', 'r') as file:
            # Load the YAML content into a dictionary
            self.config = yaml.safe_load(file)
            df = pd.read_csv(self.config['exchange']['config']['extra']['data_source'])
            self.back_trading_data = df.values.tolist()

    def test_cancel_and_re_enter_buy(self):
        """
        Testing order cancellation and reentering BUY order
        - Order is placed,
        - Since the order is far away (compared to price_gap_perc_cancel) order is cancelled immediately
        - Order is reentered at price_gap_perc_reenter
        """
        self.__counter = 0
        PRICE_GAP_PERC_CANCEL = 2
        PRICE_GAP_PERC_REENTER = 0.1
        ALMOST_MARKET_ORDER_PERC = 0.01

        exchange = Exchange(self.config['exchange']['config'])
        pending_order_manager = PendingOrderManager(exchange=exchange,
                                                    config={'price_gap_perc_cancel': PRICE_GAP_PERC_CANCEL,
                                                            'price_gap_perc_reenter': PRICE_GAP_PERC_REENTER,
                                                            'almost_market_order_perc': ALMOST_MARKET_ORDER_PERC})
        orders_n_candles = []

        def on_new_order_callback(new_order, event_candle):
            orders_n_candles.append([new_order, event_candle, self.__counter])

        def on_cancel_order_callback(cancelled_order, event_candle):
            orders_n_candles.append([cancelled_order, event_candle, self.__counter])

        pending_order_manager.on_new_order(on_new_order_callback)
        pending_order_manager.on_cancel_order(on_cancel_order_callback)

        def on_data_callable(candle):
            # print(candle)
            self.assertIsInstance(candle, Candle)
            self.__counter += 1

            order_type = 'MARKET' if random.randint(0, RAND_LIMIT) % 3 == 0 else 'LIMIT'
            order_side = 'BUY' if random.randint(0, RAND_LIMIT) % 2 == 0 else 'SELL'

            random_num = random.randint(0, RAND_LIMIT)
            price = candle.close * (1 + random_num / RAND_LIMIT / 5) if order_side == 'SELL' else candle.close * (
                    1 - random_num / RAND_LIMIT / 5)

            wallet_balance = exchange.get_wallet_balance()

            pending_order_manager.watch_price(candle)

            if self.__counter == 100:
                order = Order(
                    quote_symbol='USD',
                    base_symbol='BTC',
                    order_type='LIMIT',
                    order_side='BUY',
                    price=candle.close * 0.95,
                    size=wallet_balance['BTC'].free / 1000,
                    time=candle.time
                )
                exchange.submit_order(order)
                pending_order_manager.register_order(order)
                orders_n_candles.append([order, candle, self.__counter])

        exchange.on_candle(on_data_callable)
        exchange.connect()

        # Original order is cancelled
        self.assertEqual(orders_n_candles[0][0].order_status, OrderStatus.CANCELED)

        # Order is immediately cancelled in the next candle since the order was placed away from the candle
        self.assertEqual(orders_n_candles[0][2], orders_n_candles[1][2] - 1)

        # Cancelled at the right time
        self.assertGreater(
            ( orders_n_candles[1][1].close - orders_n_candles[0][0].price) / orders_n_candles[0][0].price * 100,
            PRICE_GAP_PERC_CANCEL)

        # Reentered at the right price
        self.assertLess(
            (orders_n_candles[2][1].close - orders_n_candles[0][0].price) / orders_n_candles[0][0].price * 100,
            PRICE_GAP_PERC_REENTER)

        # Finally the order is filled
        self.assertEqual(orders_n_candles[2][0].order_status, OrderStatus.FILLED)

        plot_configs = []

        for topic in exchange.get_plot_data().get_topics():
            plot_configs.append({
                'topic': topic,
                'col': 1,
                'row': 1,
            })

        fig = exchange.get_plot_data().plot_topics(plots=plot_configs)
        # fig.show()

    def test_cancel_and_re_enter_sell(self):
        """
        Testing order cancellation and reentering SELL order
        - Order is placed,
        - Since the order is far away (compared to price_gap_perc_cancel) order is cancelled immediately
        - Order is reentered at price_gap_perc_reenter
        """
        self.__counter = 0
        PRICE_GAP_PERC_CANCEL = 2
        PRICE_GAP_PERC_REENTER = 0.1
        ALMOST_MARKET_ORDER_PERC = 0.01

        exchange = Exchange(self.config['exchange']['config'])
        pending_order_manager = PendingOrderManager(exchange=exchange,
                                                    config={'price_gap_perc_cancel': PRICE_GAP_PERC_CANCEL,
                                                            'price_gap_perc_reenter': PRICE_GAP_PERC_REENTER,
                                                            'almost_market_order_perc': ALMOST_MARKET_ORDER_PERC})
        orders_n_candles = []

        def on_new_order_callback(new_order, event_candle):
            orders_n_candles.append([new_order, event_candle, self.__counter])

        def on_cancel_order_callback(cancelled_order, event_candle):
            orders_n_candles.append([cancelled_order, event_candle, self.__counter])

        pending_order_manager.on_new_order(on_new_order_callback)
        pending_order_manager.on_cancel_order(on_cancel_order_callback)

        def on_data_callable(candle):
            # print(candle)
            self.assertIsInstance(candle, Candle)
            self.__counter += 1

            order_type = 'MARKET' if random.randint(0, RAND_LIMIT) % 3 == 0 else 'LIMIT'
            order_side = 'BUY' if random.randint(0, RAND_LIMIT) % 2 == 0 else 'SELL'

            random_num = random.randint(0, RAND_LIMIT)
            price = candle.close * (1 + random_num / RAND_LIMIT / 5) if order_side == 'SELL' else candle.close * (
                    1 - random_num / RAND_LIMIT / 5)

            wallet_balance = exchange.get_wallet_balance()

            pending_order_manager.watch_price(candle)

            if self.__counter == 7000:
                order = Order(
                    quote_symbol='USD',
                    base_symbol='BTC',
                    order_type='LIMIT',
                    order_side='SELL',
                    price=candle.close * 1.05,
                    size=wallet_balance['BTC'].free / 1000,
                    time=candle.time
                )
                exchange.submit_order(order)
                pending_order_manager.register_order(order)
                orders_n_candles.append([order, candle, self.__counter])

        exchange.on_candle(on_data_callable)
        exchange.connect()

        # Original order is cancelled
        self.assertEqual(orders_n_candles[0][0].order_status, OrderStatus.CANCELED)

        # Order is immediately cancelled in the next candle since the order was placed away from the candle
        self.assertEqual(orders_n_candles[0][2],orders_n_candles[1][2] - 1)

        # Cancelled at the right time
        self.assertGreater(
            (orders_n_candles[0][0].price - orders_n_candles[1][1].close) / orders_n_candles[0][0].price * 100,
            PRICE_GAP_PERC_CANCEL)

        # Reentered at the right price
        self.assertLess(
            (orders_n_candles[0][0].price - orders_n_candles[2][1].close) / orders_n_candles[0][0].price * 100,
            PRICE_GAP_PERC_REENTER)

        # Finally the order is filled
        self.assertEqual(orders_n_candles[2][0].order_status, OrderStatus.FILLED)

        plot_configs = []

        for topic in exchange.get_plot_data().get_topics():
            plot_configs.append({
                'topic': topic,
                'col': 1,
                'row': 1,
            })

        fig = exchange.get_plot_data().plot_topics(plots=plot_configs)
        # fig.show()

    def test_cancel_and_re_enter_delayed(self):
        """
        Testing order cancellation and reentering sell order
        - Order is placed,
        - Order is within the range of price_gap_perc_cancel
        - Then the order is far away from price_gap_perc_cancel after some time
        - The order is cancelled immediately
        - Order is reentered at price_gap_perc_reenter
        """
        self.__counter = 0
        PRICE_GAP_PERC_CANCEL = 1
        PRICE_GAP_PERC_REENTER = 0.5
        ALMOST_MARKET_ORDER_PERC = 0.01

        exchange = Exchange(self.config['exchange']['config'])
        pending_order_manager = PendingOrderManager(exchange=exchange, config={'price_gap_perc_cancel': PRICE_GAP_PERC_CANCEL,
                                                                                         'price_gap_perc_reenter': PRICE_GAP_PERC_REENTER,
                                                                                         'almost_market_order_perc': ALMOST_MARKET_ORDER_PERC})
        orders_n_candles = []

        def on_new_order_callback(new_order, event_candle):
            orders_n_candles.append([new_order, event_candle])

        def on_cancel_order_callback(cancelled_order, event_candle):
            orders_n_candles.append([cancelled_order, event_candle])

        pending_order_manager.on_new_order(on_new_order_callback)
        pending_order_manager.on_cancel_order(on_cancel_order_callback)

        def on_data_callable(candle):
            # print(candle)
            self.assertIsInstance(candle, Candle)
            self.__counter += 1

            order_type = 'MARKET' if random.randint(0, RAND_LIMIT) % 3 == 0 else 'LIMIT'
            order_side = 'BUY' if random.randint(0, RAND_LIMIT) % 2 == 0 else 'SELL'

            random_num = random.randint(0, RAND_LIMIT)
            price = candle.close * (1 + random_num / RAND_LIMIT/5) if order_side == 'SELL' else candle.close * (1 - random_num / RAND_LIMIT / 5)

            wallet_balance = exchange.get_wallet_balance()

            pending_order_manager.watch_price(candle)

            if self.__counter == 7050:
                order = Order(
                    quote_symbol='USD',
                    base_symbol='BTC',
                    order_type='LIMIT',
                    order_side='SELL',
                    price=candle.close * 1.005,
                    size=wallet_balance['BTC'].free / 1000,
                    time=candle.time
                )
                exchange.submit_order(order)
                pending_order_manager.register_order(order)
                orders_n_candles.append([order, candle])

        exchange.on_candle(on_data_callable)
        exchange.connect()

        # Original order is cancelled
        self.assertEqual(orders_n_candles[0][0].order_status, OrderStatus.CANCELED)

        # Cancelled at the right time
        self.assertGreater((orders_n_candles[0][0].price - orders_n_candles[1][1].close)/orders_n_candles[0][0].price * 100, PRICE_GAP_PERC_CANCEL)

        # Reentered at the right price
        self.assertLess((orders_n_candles[0][0].price - orders_n_candles[2][1].close)/orders_n_candles[0][0].price * 100, PRICE_GAP_PERC_REENTER)

        # Finally the order is filled
        self.assertEqual(orders_n_candles[2][0].order_status, OrderStatus.FILLED)

        plot_configs = []

        for topic in exchange.get_plot_data().get_topics():
            plot_configs.append({
                'topic': topic,
                'col': 1,
                'row': 1,
            })

        fig = exchange.get_plot_data().plot_topics(plots=plot_configs)
        fig.update_layout(
            title="Pending Order Manager: Cancels order and reenter (SELL)"
        )
        # fig.show()

    def test_rejection(self):
        """
        Check rejection when reentering
        - Reenters at book crossing
        - Exchange rejects the order
        - Reenters at the right price
        - Note: rejection is similated with negative price_gap_perc_reenter
        -       Check visually
        """
        self.__counter = 0
        PRICE_GAP_PERC_CANCEL = 2
        PRICE_GAP_PERC_REENTER = -1
        ALMOST_MARKET_ORDER_PERC = 0.01

        exchange = Exchange(self.config['exchange']['config'])
        pending_order_manager = PendingOrderManager(exchange=exchange,
                                                    config={'price_gap_perc_cancel': PRICE_GAP_PERC_CANCEL,
                                                            'price_gap_perc_reenter': PRICE_GAP_PERC_REENTER,
                                                            'almost_market_order_perc': ALMOST_MARKET_ORDER_PERC})
        orders_n_candles = []

        def on_new_order_callback(new_order, event_candle):
            orders_n_candles.append([new_order, event_candle, self.__counter])

        def on_cancel_order_callback(cancelled_order, event_candle):
            orders_n_candles.append([cancelled_order, event_candle, self.__counter])

        pending_order_manager.on_new_order(on_new_order_callback)
        pending_order_manager.on_cancel_order(on_cancel_order_callback)

        def on_data_callable(candle):
            # print(candle)
            self.assertIsInstance(candle, Candle)
            self.__counter += 1

            order_type = 'MARKET' if random.randint(0, RAND_LIMIT) % 3 == 0 else 'LIMIT'
            order_side = 'BUY' if random.randint(0, RAND_LIMIT) % 2 == 0 else 'SELL'

            random_num = random.randint(0, RAND_LIMIT)
            price = candle.close * (1 + random_num / RAND_LIMIT / 5) if order_side == 'SELL' else candle.close * (
                    1 - random_num / RAND_LIMIT / 5)

            wallet_balance = exchange.get_wallet_balance()

            pending_order_manager.watch_price(candle)

            if self.__counter == 100:
                order = Order(
                    quote_symbol='USD',
                    base_symbol='BTC',
                    order_type='LIMIT',
                    order_side='BUY',
                    price=candle.close * 0.95,
                    size=wallet_balance['BTC'].free / 1000,
                    time=candle.time
                )
                exchange.submit_order(order)
                pending_order_manager.register_order(order)
                orders_n_candles.append([order, candle, self.__counter])

        exchange.on_candle(on_data_callable)
        exchange.connect()

        # Original order is cancelled
        self.assertEqual(orders_n_candles[0][0].order_status, OrderStatus.CANCELED)

        # The original order is immediately cancelled in the next candle since the order was placed away from the candle
        self.assertEqual(orders_n_candles[0][2], orders_n_candles[1][2] - 1)

        # Cancelled at the right time
        self.assertGreater(
            (orders_n_candles[1][1].close - orders_n_candles[0][0].price) / orders_n_candles[0][0].price * 100,
            PRICE_GAP_PERC_CANCEL)

        # Reentered at the right price
        self.assertLess(
            (orders_n_candles[2][1].close - orders_n_candles[0][0].price) / orders_n_candles[0][0].price * 100,
            PRICE_GAP_PERC_REENTER)

        # Reentered order is rejected (Forced rejection)
        self.assertEqual(orders_n_candles[2][0].order_status, OrderStatus.REJECTED)

        # After rejection, another order was placed considering almost_market_order_perc
        self.assertLess((orders_n_candles[3][1].close - orders_n_candles[3][0].price) / orders_n_candles[3][1].close * 100, ALMOST_MARKET_ORDER_PERC)

        # The retried order with "almost_market_order_perc" is filled
        self.assertEqual(orders_n_candles[3][0].order_status, OrderStatus.FILLED)

        plot_configs = []

        for topic in exchange.get_plot_data().get_topics():
            plot_configs.append({
                'topic': topic,
                'col': 1,
                'row': 1,
            })

        fig = exchange.get_plot_data().plot_topics(plots=plot_configs)
        # fig.show()


