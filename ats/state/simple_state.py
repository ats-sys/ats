import datetime
import pickle
import copy
from typing import Union


class SimpleState:
    """This is the standard strategy state object"""
    def __init__(self):
        self._state = {}

    def set(self, key: str, value: Union[int, float, str, datetime.datetime, None]) -> None:
        """
        Sets a key value pair
        Args:
            key: string key value
            value: State value

        Returns:
            None
        """
        allowed_data_types = [int, float, datetime.datetime, type(None), str, SimpleState]
        is_valid_value = any([isinstance(value, allowed_data_type) for allowed_data_type in allowed_data_types])

        if not is_valid_value:
            raise ValueError('Trying to set a value of invalid type.')

        self._state[key] = value

    def get(self, key: str) -> Union[int, float, datetime.datetime, type(None), str, ]:
        """
        Returns the state given a key value
        Args:
            key: string key

        Returns:
            State related the key value
        """
        return self._state[key] if key in self._state else None

    def pop(self, key: str) -> Union[int, float, datetime.datetime, type(None), str ]:
        """
        Pops a state given a key value
        Args:
            key: string key

        Returns:
            Returns the value held by the key. If the key is not found returns None
        """
        if key in self._state:
            return self._state.pop(key)
        return None

    def serialize(self) -> bytes:
        """
        Returns the serialized state
        Returns:
            Serialized state
        """
        return pickle.dumps(self)

    def load(self, serialized: bytes) -> None:
        """
        Loads a serialized state
        Args:
            serialized: serialized state

        Returns:
            None
        """
        self._state = pickle.loads(serialized)
