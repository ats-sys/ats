from ats.exchanges.base_fees import BaseFees
from typing import Union, Dict, Literal


class Generic(BaseFees):
    """
    Models fees for back trading.
    """
    def _calculate(self, size: Union[int, float], price: Union[int, float],
                   order_type: Literal['LIMIT', 'MARKET'], order_side: Literal['BUY', 'SELL']) -> Dict[str, str]:
        return {
            'base_fee': size * self.config[order_type.lower()][order_side.lower()]['base'] / 100,
            'quote_fee': size * price * self.config[order_type.lower()][order_side.lower()]['quote'] / 100,
        }