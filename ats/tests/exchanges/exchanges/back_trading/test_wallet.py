import unittest
import yaml
from ats.exchanges.exchanges.back_trading.wallet import Wallet
from ats.exchanges.data_classes.order import Order
from ats.exchanges.fees.generic import Generic


class TestWallet(unittest.TestCase):
    def setUp(self) -> None:
        with open('tests/configs/back_trading_exchange_config.yaml', 'r') as file:
            # Load the YAML content into a dictionary
            self.exchange_config = yaml.safe_load(file)['exchange']['config']

    def test_completed_buy_transactions(self):
        """
        Tests a few completed buy order transactions.
        Wallet assets must be properly balanced. (Considering asset_balance.free, asset_balance.holding components)
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='MARKET',
            size=1,
            order_id=None,
            time=None
        )

        order_3 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )

        fees_1 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_2 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_3 = Generic(self.exchange_config['extra']['fees']['config'])

        order_state_1 = order_1.get_state()
        order_state_2 = order_2.get_state()
        order_state_3 = order_3.get_state()

        fees_1.calculate(
            size=order_state_1['size'],
            price=order_state_1['price'],
            order_type=order_state_1['order_type'],
            order_side=order_state_1['order_side']
        )

        fees_2.calculate(
            size=order_state_2['size'],
            price=10005,
            order_type=order_state_2['order_type'],
            order_side=order_state_2['order_side']
        )

        fees_3.calculate(
            size=order_state_3['size'],
            price=order_state_3['price'],
            order_type=order_state_3['order_type'],
            order_side=order_state_3['order_side']
        )

        wallet.register_transaction(order=order_1)
        wallet.register_transaction(order=order_2)

        order_1.fully_fill(fees=fees_1)
        order_2.fully_fill(fees=fees_2, price=10005)

        wallet.register_transaction(order=order_2)
        wallet.register_transaction(order=order_1)

        wallet.register_transaction(order=order_3)
        order_3.fully_fill(fees=fees_3)
        wallet.register_transaction(order=order_3)

        wallet_balance = wallet.get_wallet_balance()

        self.assertEqual(wallet_balance['USD'].holding, 0.0)
        self.assertEqual(wallet_balance['BTC'].holding, 0.0)

        final_usd = wallet_config['assets']['USD'] \
                        - order_1.filled_size * order_1.price - order_1.fees['quote_fee'] \
                        - order_2.filled_size * order_2.price - order_2.fees['quote_fee'] \
                        - order_3.filled_size * order_3.price - order_3.fees['quote_fee']

        final_btc = wallet_config['assets']['BTC'] \
                        + order_1.filled_size - order_1.fees['base_fee'] \
                        + order_2.filled_size - order_2.fees['base_fee'] \
                        + order_3.filled_size - order_3.fees['base_fee']

        self.assertEqual(final_usd, wallet_balance['USD'].free)
        self.assertEqual(final_btc, wallet_balance['BTC'].free)

    def test_completed_and_pending_buy_transactions(self):
        """
        Tests a few completed and pending buy order transactions.
        Wallet assets must be properly balanced. (Considering asset_balance.free, asset_balance.holding components)
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=1.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='MARKET',
            size=1,
            order_id=None,
            time=None
        )

        order_3 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )

        fees_1 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_2 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_3 = Generic(self.exchange_config['extra']['fees']['config'])

        order_state_1 = order_1.get_state()
        order_state_2 = order_2.get_state()
        order_state_3 = order_3.get_state()

        fees_1.calculate(
            size=order_state_1['size'],
            price=order_state_1['price'],
            order_type=order_state_1['order_type'],
            order_side=order_state_1['order_side']
        )

        fees_2.calculate(
            size=order_state_2['size'],
            price=10005,
            order_type=order_state_2['order_type'],
            order_side=order_state_2['order_side']
        )

        fees_3.calculate(
            size=order_state_3['size'],
            price=order_state_3['price'],
            order_type=order_state_3['order_type'],
            order_side=order_state_3['order_side']
        )

        wallet.register_transaction(order=order_1)
        wallet.register_transaction(order=order_2)

        order_1.fully_fill(fees=fees_1)
        order_2.fully_fill(fees=fees_2, price=10005)

        wallet.register_transaction(order=order_2)
        wallet.register_transaction(order=order_1)

        wallet.register_transaction(order=order_3)
        # Note: Order 3 is still in pending

        wallet_balance = wallet.get_wallet_balance()

        self.assertEqual(wallet_balance['USD'].holding, order_3.size * order_3.price)
        self.assertEqual(wallet_balance['BTC'].holding, 0.0)

        final_usd = wallet_config['assets']['USD'] \
                        - order_1.filled_size * order_1.price - order_1.fees['quote_fee'] \
                        - order_2.filled_size * order_2.price - order_2.fees['quote_fee'] \
                        - order_3.size * order_3.price

        final_btc = wallet_config['assets']['BTC'] \
                        + order_1.filled_size - order_1.fees['base_fee'] \
                        + order_2.filled_size - order_2.fees['base_fee'] \
                        + order_3.filled_size

        self.assertEqual(final_usd, wallet_balance['USD'].free)
        self.assertEqual(final_btc, wallet_balance['BTC'].free)

    def test_completed_sell_transactions(self):
        """
        Tests a few completed sell order transactions.
        Wallet assets must be properly balanced. (Considering asset_balance.free, asset_balance.holding components)
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='MARKET',
            size=1,
            order_id=None,
            time=None
        )

        order_3 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )

        fees_1 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_2 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_3 = Generic(self.exchange_config['extra']['fees']['config'])

        order_state_1 = order_1.get_state()
        order_state_2 = order_2.get_state()
        order_state_3 = order_3.get_state()

        fees_1.calculate(
            size=order_state_1['size'],
            price=order_state_1['price'],
            order_type=order_state_1['order_type'],
            order_side=order_state_1['order_side']
        )

        fees_2.calculate(
            size=order_state_2['size'],
            price=10005,
            order_type=order_state_2['order_type'],
            order_side=order_state_2['order_side']
        )

        fees_3.calculate(
            size=order_state_3['size'],
            price=order_state_3['price'],
            order_type=order_state_3['order_type'],
            order_side=order_state_3['order_side']
        )

        wallet.register_transaction(order=order_1)
        wallet.register_transaction(order=order_2)

        order_1.fully_fill(fees=fees_1)
        order_2.fully_fill(fees=fees_2, price=10005)

        wallet.register_transaction(order=order_2)
        wallet.register_transaction(order=order_1)

        wallet.register_transaction(order=order_3)
        order_3.fully_fill(fees=fees_3)
        wallet.register_transaction(order=order_3)

        wallet_balance = wallet.get_wallet_balance()

        self.assertEqual(wallet_balance['USD'].holding, 0.0)
        self.assertEqual(wallet_balance['BTC'].holding, 0.0)

        final_usd = wallet_config['assets']['USD'] \
                        + order_1.filled_size * order_1.price - order_1.fees['quote_fee'] \
                        + order_2.filled_size * order_2.price - order_2.fees['quote_fee'] \
                        + order_3.filled_size * order_3.price - order_3.fees['quote_fee']

        final_btc = wallet_config['assets']['BTC'] \
                        - order_1.filled_size - order_1.fees['base_fee'] \
                        - order_2.filled_size - order_2.fees['base_fee'] \
                        - order_3.filled_size - order_3.fees['base_fee']

        self.assertEqual(final_usd, wallet_balance['USD'].free)
        self.assertEqual(final_btc, wallet_balance['BTC'].free)

    def test_completed_and_pending_sell_transactions(self):
        """
        Tests a few completed and pending sell order transactions.
        Wallet assets must be properly balanced. (Considering asset_balance.free, asset_balance.holding components)
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=1.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='MARKET',
            size=1,
            order_id=None,
            time=None
        )

        order_3 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )

        fees_1 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_2 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_3 = Generic(self.exchange_config['extra']['fees']['config'])

        order_state_1 = order_1.get_state()
        order_state_2 = order_2.get_state()
        order_state_3 = order_3.get_state()

        fees_1.calculate(
            size=order_state_1['size'],
            price=order_state_1['price'],
            order_type=order_state_1['order_type'],
            order_side=order_state_1['order_side']
        )

        fees_2.calculate(
            size=order_state_2['size'],
            price=10005,
            order_type=order_state_2['order_type'],
            order_side=order_state_2['order_side']
        )

        fees_3.calculate(
            size=order_state_3['size'],
            price=order_state_3['price'],
            order_type=order_state_3['order_type'],
            order_side=order_state_3['order_side']
        )

        wallet.register_transaction(order=order_1)
        wallet.register_transaction(order=order_2)

        order_1.fully_fill(fees=fees_1)
        order_2.fully_fill(fees=fees_2, price=10005)

        wallet.register_transaction(order=order_2)
        wallet.register_transaction(order=order_1)

        wallet.register_transaction(order=order_3)
        # Note: Order 3 is still in pending

        wallet_balance = wallet.get_wallet_balance()

        self.assertEqual(wallet_balance['USD'].holding, 0.0)
        self.assertEqual(wallet_balance['BTC'].holding, order_3.size)

        final_usd = wallet_config['assets']['USD'] \
                    + order_1.filled_size * order_1.price - order_1.fees['quote_fee'] \
                    + order_2.filled_size * order_2.price - order_2.fees['quote_fee'] \
                    + order_3.filled_size * order_3.price

        final_btc = wallet_config['assets']['BTC'] \
                    - order_1.filled_size - order_1.fees['base_fee'] \
                    - order_2.filled_size - order_2.fees['base_fee'] \
                    - order_3.size

        self.assertEqual(final_usd, wallet_balance['USD'].free)
        self.assertEqual(final_btc, wallet_balance['BTC'].free)

    def test_buy_and_sell_order_rejections(self):
        """
        Tests rejection of buy and sell orders.
        Rejection should restore the holding of assets.
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )


        wallet.register_transaction(order=order_1)
        order_1.reject()
        wallet.register_transaction(order=order_1)

        self.assertEqual(wallet_config['assets']['USD'], wallet.get_wallet_balance()['USD'].free)
        self.assertEqual(wallet.get_wallet_balance()['USD'].holding, 0)

        self.assertEqual(wallet_config['assets']['BTC'], wallet.get_wallet_balance()['BTC'].free)
        self.assertEqual(wallet.get_wallet_balance()['BTC'].holding, 0)

        wallet.register_transaction(order=order_2)
        order_2.reject()
        wallet.register_transaction(order=order_2)

        self.assertEqual(wallet_config['assets']['USD'], wallet.get_wallet_balance()['USD'].free)
        self.assertEqual(wallet.get_wallet_balance()['USD'].holding, 0)

        self.assertEqual(wallet_config['assets']['BTC'], wallet.get_wallet_balance()['BTC'].free)
        self.assertEqual(wallet.get_wallet_balance()['BTC'].holding, 0)

    def test_buy_and_sell_order_cancellation(self):
        """
        Tests cancellation of buy and sell orders.
        Cancellation should restore the holding of assets.
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )

        wallet.register_transaction(order=order_1)
        order_1.cancel()
        wallet.register_transaction(order=order_1)

        self.assertEqual(wallet_config['assets']['USD'], wallet.get_wallet_balance()['USD'].free)
        self.assertEqual(wallet.get_wallet_balance()['USD'].holding, 0)

        self.assertEqual(wallet_config['assets']['BTC'], wallet.get_wallet_balance()['BTC'].free)
        self.assertEqual(wallet.get_wallet_balance()['BTC'].holding, 0)

        wallet.register_transaction(order=order_2)
        order_2.cancel()
        wallet.register_transaction(order=order_2)

        self.assertEqual(wallet_config['assets']['USD'], wallet.get_wallet_balance()['USD'].free)
        self.assertEqual(wallet.get_wallet_balance()['USD'].holding, 0)

        self.assertEqual(wallet_config['assets']['BTC'], wallet.get_wallet_balance()['BTC'].free)
        self.assertEqual(wallet.get_wallet_balance()['BTC'].holding, 0)

    def test_transaction_log_sequence(self):
        """
        Wallet must record the transaction log of all transactions happened in excact order.
        """
        wallet_config = self.exchange_config['extra']['wallet']
        wallet = Wallet(wallet_config)

        order_1 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_2 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='MARKET',
            size=1,
            order_id=None,
            time=None
        )

        order_3 = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='SELL',
            order_type='LIMIT',
            size=2,
            price=10025,
            order_id=None,
            time=None
        )

        fees_1 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_2 = Generic(self.exchange_config['extra']['fees']['config'])
        fees_3 = Generic(self.exchange_config['extra']['fees']['config'])

        order_state_1 = order_1.get_state()
        order_state_2 = order_2.get_state()
        order_state_3 = order_3.get_state()

        fees_1.calculate(
            size=order_state_1['size'],
            price=order_state_1['price'],
            order_type=order_state_1['order_type'],
            order_side=order_state_1['order_side']
        )

        fees_2.calculate(
            size=order_state_2['size'],
            price=10005,
            order_type=order_state_2['order_type'],
            order_side=order_state_2['order_side']
        )

        fees_3.calculate(
            size=order_state_3['size'],
            price=order_state_3['price'],
            order_type=order_state_3['order_type'],
            order_side=order_state_3['order_side']
        )

        wallet.register_transaction(order=order_1)
        wallet.register_transaction(order=order_2)

        order_1.fully_fill(fees=fees_1)
        order_2.fully_fill(fees=fees_2, price=10005)

        wallet.register_transaction(order=order_2)
        wallet.register_transaction(order=order_1)

        wallet.register_transaction(order=order_3)
        order_3.fully_fill(fees=fees_3)
        wallet.register_transaction(order=order_3)

        transactions = wallet.get_transaction_log()

        self.assertEqual(transactions[0], order_1.get_state_trail()[0])
        self.assertEqual(transactions[1], order_2.get_state_trail()[0])
        self.assertEqual(transactions[2], order_2.get_state_trail()[1])
        self.assertEqual(transactions[3], order_1.get_state_trail()[1])
        self.assertEqual(transactions[4], order_3.get_state_trail()[0])
        self.assertEqual(transactions[5], order_3.get_state_trail()[1])

