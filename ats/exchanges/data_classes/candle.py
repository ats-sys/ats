import datetime
from typing import Union, Literal
from dataclasses import dataclass
import json

@dataclass(frozen=True)
class Candle:
    """
    This holds data received from the exchange.
    Note: This class is immutable, hence thread safe in python
    """
    open: float
    high: float
    low: float
    close: float
    symbol: str
    buy_vol: float
    sell_vol: float
    time: datetime.datetime

    def __post_init__(self):
        # Validate and check if defined data types are matched with the input data types
        for field_name, expected_type in self.__annotations__.items():
            value = getattr(self, field_name)
            if not isinstance(value, expected_type):
                raise TypeError(f"{field_name} must be of type {expected_type}, not {type(value)}")

    def to_dict(self) -> dict:
        """
        Convert the candle object to a dict
        Returns:
            Dict containing candle data
        """
        public_properties = {key: value for key, value in self.__dict__.items()
                             if not key.startswith('_')}
        return public_properties
