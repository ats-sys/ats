from abc import ABC, abstractmethod
from typing import Dict, Union, Literal
from ats.exceptions.fees_exceptions import FeesNotSetException


class BaseFees(ABC):
    """
    Implements fee calculation.
    In the back trading env, fee calculation is required with the given setup
    In a real exchange, you can use the set() method to set the fees
    In back trading and live env, use get() method to get the fees
    Every class that extents from this class is expected to implement _calculate() method capturing fee calculation logic
    """
    def __init__(self, config):
        self.config = config
        self._fees = None

    def get(self) -> dict:
        """
        Get fees dict.
        There are two keys 'base_fee' and 'quote_fee'
        Returns:
            Dict with fees
        """
        if self._fees is None:
            raise FeesNotSetException('Fees must be set using set() or calculate() methods')
        return self._fees

    def set(self, base_fee: Union[int, float], quote_fee: Union[int, float]) -> None:
        """
        Set the fees
        Args:
            base_fee: Base fee
            quote_fee: Quote fee

        Returns:
            None
        """
        self._fees = {
            'base_fee': base_fee,
            'quote_fee': quote_fee
        }

    def calculate(self, size: Union[int, float], price: Union[int, float],
                  order_type: Literal['LIMIT', 'MARKET'], order_side: Literal['BUY', 'SELL']) -> None:
        """
        Give order's size, price, order_type and order_side, this method calculates the fees
        Args:
            size: Size of the order
            price: Price of the base asset
            order_type: Order type. 'LIMIT' or 'MARKET'
            order_side: Order side. 'BUY' or 'SELL'

        Returns:

        """
        calculated_fee = self._calculate(size, price, order_type, order_side)
        self.set(calculated_fee['base_fee'], calculated_fee['quote_fee'])

    @abstractmethod
    def _calculate(self, size: Union[int, float], price: Union[int, float],
                   order_type: Literal['LIMIT', 'MARKET'], order_side: Literal['BUY', 'SELL']) -> Dict:
        """
        Calculate the fee component using the base asset size and the quote asset price
        Args:
            size:
            price:
            order_type:
            order_side

        Returns:
            Dict containing fee in terms of base asset and fee in terms of quote asset.
            Example:
                {
                    "base_fee": 0.01,
                    "quote_fee": 777
                }
        """
        pass
