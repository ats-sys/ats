import numpy as np
import copy
import uuid
from typing import Dict, List, Union
from ats.exceptions.general_exceptions import ConfigValidationException
from ats.exceptions import exchange_exceptions
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.asset_balance import AssetBalance
from ats.utils.logging.logger import logger

class Wallet:
    """
    Maintains back trading wallet for a given currency config
    """

    def __init__(self, config: dict):
        self.config = copy.deepcopy(config)  # If we do not copy, the config will be passed by reference and the asset change will change the config's "asset" section
        self._validate_config()
        self._assets: dict = copy.deepcopy(self.config['assets'])
        self._assets_after_holding: dict = copy.deepcopy(self.config['assets'])  # blocking happens for pending and partial orders

        # Key is the order id and value is the order
        self._orders: Dict[str, Order] = {}

        # Transaction log
        self._transactions = []
        logger.info(f'Backtrading wallet initiated.')

    def register_transaction(self, order: Order):
        """
        Every order must that does a transaction with the wallet must be registered
            - The order can be of any status such as PENDING, FILLED, REJECTED, CANCELED, etc
            - Different order status performs different actions on the wallet such as exchanging assets, holding and unholding assets
        Args:
            order:

        Returns:

        """
        order_state = order.get_state(is_thread_safe=False)
        quote_symbol = order_state['quote_symbol']
        base_symbol = order_state['base_symbol']
        order_size = order_state['size']
        order_filled_size_delta = order_state['filled_size_delta']
        order_price = order_state['price']
        order_status = order_state['order_status']
        order_side = order_state['order_side']
        order_type = order_state['order_type']
        order_fees = order_state['fees']

        if quote_symbol not in self._assets:
            raise exchange_exceptions.NoWalletAssetFoundException(quote_symbol)

        if base_symbol not in self._assets:
            raise exchange_exceptions.NoWalletAssetFoundException(base_symbol)

        if order_status == OrderStatus.PENDING:
            if order_side == 'BUY' and order_type == 'LIMIT':  # For MARKET orders, no holding
                deduction = order_size * order_price
                if not self.__check_negative_balance_and_reject_order(symbol=quote_symbol, deduction=deduction, order=order):
                    self._assets_after_holding[quote_symbol] -= deduction

            if order_side == 'SELL' and order_type == 'LIMIT':  # For MARKET orders, no holding
                deduction = order_size
                if not self.__check_negative_balance_and_reject_order(symbol=base_symbol, deduction=deduction, order=order):
                    self._assets_after_holding[base_symbol] -= deduction

        elif order_status == OrderStatus.PARTIALLY_FILLED or order_status == OrderStatus.FILLED:

            if order_side == 'BUY':
                deduction = order_filled_size_delta * order_price
                if not self.__check_negative_balance_and_reject_order(symbol=quote_symbol, deduction=deduction, order=order):
                    self._assets[quote_symbol] -= deduction
                    self._assets[base_symbol] += order_filled_size_delta - order_fees['base_fee']
                    self._assets_after_holding[base_symbol] += order_filled_size_delta - order_fees['base_fee']

                    # Because market orders do not have holding when the order is in PENDING mode
                    if order_type == 'MARKET':
                        self._assets_after_holding[quote_symbol] -= deduction

            if order_side == 'SELL':
                deduction = order_filled_size_delta
                if not self.__check_negative_balance_and_reject_order(symbol=base_symbol, deduction=deduction, order=order):
                    self._assets[base_symbol] -= deduction
                    self._assets[quote_symbol] += order_filled_size_delta * order_price - order_fees['quote_fee']
                    self._assets_after_holding[quote_symbol] += order_filled_size_delta * order_price - order_fees['quote_fee']
                    # Because market orders do not have holding when the order is in PENDING mode
                    if order_type == 'MARKET':
                        self._assets_after_holding[base_symbol] -= deduction

        elif order_status == OrderStatus.REJECTED or order_state['order_status'] == OrderStatus.CANCELED:
            if order_side == 'BUY':
                self._assets_after_holding[quote_symbol] += order_size * order_price  # Undoing the holding for PENDING
            if order_side == 'SELL':
                self._assets_after_holding[base_symbol] += order_size  # Undoing the holding for PENDING

        # Every transaction is logged regardless of the that transaction changing the wallet
        self._transactions.append(order.get_state(is_thread_safe=False))

    def get_wallet_balance(self) -> Dict[str, AssetBalance]:
        """
        Returns the wallet balance of all the assets.
        Returns:
            Dict of AssetBalance objects
            Dict is returned instead of a list to make the computation efficient when returning
        """
        assets = {}
        for key, val in self._assets.items():
            assets[key] = AssetBalance(
                symbol=key,
                free=self._assets_after_holding[key],
                holding=val - self._assets_after_holding[key],
                frozen=0
            )
        return assets

    def get_transaction_log(self) -> List[dict]:
        """
        Get the list of transactions happened.
        A transaction is considered as the state of an order registered to the wallet.
        Returns:
            List of order states involved in wallet transactions
        """
        return self._transactions

    def _validate_config(self):
        for key, item in self.config['assets'].items():
            if not isinstance(key, str):
                raise ConfigValidationException('Wallet Config', f'{key} must be a string.')

            if not np.isreal(item):
                raise ConfigValidationException('Wallet Config', f'{key} must have a number.')

    def __check_negative_balance_and_reject_order(self, symbol: str, deduction: Union[float, int], order: Order) -> bool:
        """
        Checks if the given amount can be deducted from the wallet for the given symbol.
        If not, this rejects the order and returns True, else False
        Note: This was encapsulated as a function as this is a common logic
        Args:
            symbol: Asset symbol
            deduction: Amount to be deducted

        Returns:
            True if deductable, False if Order is rejected
        """
        if self._assets_after_holding[symbol] < deduction:
            logger.warn(f'Order id: {order.order_id} is REJECTED on {order.order_side} since not enough {symbol}')

            # IMPORTANT: This doesn't work since FILLED orders cannot be rejected. But in back trading it must be allowed
            # This is overriden due to a practical issue of back trading. An order is fullfilled and then wallet decides to reject.
            order.order_status = OrderStatus.REJECTED
            order._state_trail.append(order.get_state(is_thread_safe=False))

            # Reset fees
            if order.fees is not None:
                order.fees['base_fee'] = 0
                order.fees['quote_fee'] = 0
            return True
        return False



