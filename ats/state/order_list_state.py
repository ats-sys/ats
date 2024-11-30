from typing import Union
from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.order import Order


class OrderListState(SimpleState):
    def __init__(self):
        super().__init__()
        self._state['__ordered_list'] = []

    def add(self, order: Order):
        if not isinstance(order, Order):
            raise ValueError('.add() method only supports order objects.')

        if order.order_id in self._state:
            raise Exception(f'{order.order_id} is already in the OrderList state')

        self._state[order.order_id] = order
        if self._state['__ordered_list'] and (order.time - self._state['__ordered_list'][-1].time).total_seconds() >= 0:
            self._state['__ordered_list'].append(order)
        else:
            self._state['__ordered_list'] = sorted(self._state['__ordered_list'] + [order], key=lambda x: x.time)

    def set(self, key, value) -> None:
        raise Exception('.set() method is not supported in order list.')

    def pop(self, key: str):
        popped_value = super().pop(key)

        if popped_value is not None:
            self._state['__ordered_list'] = [order for order in self._state['__ordered_list'] if order.order_id != key]

        return popped_value

    def get_by_time_order(self, time_order: int) -> Union[Order, None]:
        """
        Get an order object by the time order
        Args:
            time_order: int representing the order. 0 for the oldest and -1 for the latest

        Returns:
            Order object or None if not index is matched
        """

        if time_order < len(self._state['__ordered_list']):
            return self._state['__ordered_list'][time_order]
        return None

    def get_all_as_ordered_list(self):
        return self._state['__ordered_list']

