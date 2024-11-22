import unittest
import datetime
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.fees.generic import Generic
from ats.exceptions.order_exceptions import UnsupportedStatusException, OrderFillingException, InvalidOrderException


class TestOrder(unittest.TestCase):
    def test_pending_order_creation(self):
        """
        Testing order creation
            - Order must be having PENDING status
            - Check for order id and order.time
            - Indirectly checking get_state()
        """
        order = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        order_state = order.get_state()

        self.assertEqual(order_state['order_status'], OrderStatus.PENDING)
        self.assertIsNotNone(order_state['order_id'])
        self.assertIsInstance(order_state['order_id'], str)
        self.assertIsNotNone(order_state['time'])
        self.assertIsInstance(order_state['time'], datetime.datetime)

    def test_limit_order_filling_fully(self):
        """
        Testing fully-filling a limit order
            - order.filled_size must be equal to order.size (Assuming a fully filling the order)
            - order status must be set to FILLED
        """
        order = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        fees = Generic({
                  "limit": {
                    "buy": {
                      "quote": 0,
                      "base": 0.001
                    },
                    "sell": {
                      "quote": 0.001,
                      "base": 0
                    }
                  },
                  "market": {
                    "buy": {
                      "quote": 0,
                      "base": 0.001
                    },
                    "sell": {
                      "quote": 0.001,
                      "base": 0
                    }
                  }
                })

        order_state = order.get_state()

        fees.calculate(
            size=order_state['size'],
            price=order_state['price'],
            order_type=order_state['order_type'],
            order_side=order_state['order_side']
        )

        order.fully_fill(fees=fees)

        order_state = order.get_state()

        self.assertEqual(order_state['order_status'], 'FILLED')
        self.assertEqual(order_state['size'], order_state['filled_size'])

    def test_market_order_with_price_exception(self):
        with self.assertRaises(InvalidOrderException):
            Order(
                quote_symbol='USD',
                base_symbol='BTC',
                order_side='BUY',
                order_type='MARKET',
                size=2.5,
                price=10000,
                order_id=None,
                time=None
            )

    def test_market_order_filling_no_price(self):
        """
        Testing the order filling with no price for market orders
            - If a market order is filled with no price, then OrderFillingException must be raised
            - If a market order is filled with price, it must be filled
                - order.filled_size must be equal to order.size (Assuming a fully filling the order)
                - order status must be set to FILLED
        """
        order = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='MARKET',
            size=2.5,
            order_id=None,
            time=None
        )

        fees = Generic({
                  "limit": {
                    "buy": {
                      "quote": 0,
                      "base": 0.001
                    },
                    "sell": {
                      "quote": 0.001,
                      "base": 0
                    }
                  },
                  "market": {
                    "buy": {
                      "quote": 0,
                      "base": 0.001
                    },
                    "sell": {
                      "quote": 0.001,
                      "base": 0
                    }
                  }
                })

        order_state = order.get_state()

        price = 10000

        fees.calculate(
            size=order_state['size'],
            price=price,
            order_type=order_state['order_type'],
            order_side=order_state['order_side']
        )

        with self.assertRaises(OrderFillingException):
            order.fully_fill(fees=fees)

        order.fully_fill(price=price, fees=fees)

        self.assertEqual(order.filled_size, order.size)
        self.assertEqual(order.order_status, OrderStatus.FILLED )

    def test_limit_order_filling_step_by_step_partially(self):
        """
        Order filling step by step is tested.
            - Order is filled with delta sizes in multiple steps
            - During the filling, order must have PARTIALLY_FILLED status
            - After the order is fully filled, the order must have FILLED status
        """
        order = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )

        fees = Generic({
            "limit": {
                "buy": {
                    "quote": 0,
                    "base": 0.001
                },
                "sell": {
                    "quote": 0.001,
                    "base": 0
                }
            },
            "market": {
                "buy": {
                    "quote": 0,
                    "base": 0.001
                },
                "sell": {
                    "quote": 0.001,
                    "base": 0
                }
            }
        })

        order_state = order.get_state()

        fees.calculate(
            size=1.5,
            price=order_state['price'],
            order_type=order_state['order_type'],
            order_side=order_state['order_side']
        )

        order.fill(1.5, fees_delta=fees)

        order_state = order.get_state()

        self.assertEqual(order_state['order_status'], OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(order_state['filled_size'], 1.5)
        self.assertLess(order_state['filled_size'], order_state['size'])

        fees.calculate(
            size=1,
            price=order_state['price'],
            order_type=order_state['order_type'],
            order_side=order_state['order_side']
        )

        order.fill(1, fees_delta=fees)
        order_state = order.get_state()

        self.assertEqual(order_state['order_status'], OrderStatus.FILLED)
        self.assertEqual(order_state['filled_size'], order_state['size'])

    def test_order_cancellation(self):
        """
        Test order cancellation status change and validation
            - Tested validations:
                - If the order is not in PENDING status, then UnsupportedStatusException must be raised
        """
        order = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=10000,
            order_id=None,
            time=None
        )
        order.cancel()
        order_state = order.get_state()

        self.assertEqual(order_state['order_status'], OrderStatus.CANCELED)


    def test_order_rejection(self):
        """
        Test order rejection status change and validation
            - Tested validations:
                - If the order is not in PENDING status, then UnsupportedStatusException must be raised
        """
        order = Order(
            quote_symbol='USD',
            base_symbol='BTC',
            order_side='BUY',
            order_type='LIMIT',
            size=2.5,
            price=1000,
            order_id=None,
            time=None
        )
        order.reject()
        order_state = order.get_state()

        self.assertEqual(order_state['order_status'], 'REJECTED')


if __name__ == '__main__':
    unittest.main()
