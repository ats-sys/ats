import time
from typing import Union, List
from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.order import Order, OrderStatus


class OrderStateListState(SimpleState):
    def __init__(self):
        super().__init__()
        self._state['__ordered_list'] = []
        self._state['__open_order_list'] = {}
        self._state['__filled_order_list'] = {}
        self._state['__void_order_list'] = {}
        self._state['__order_pairs_list'] = []
        self._state['__order_exec_time_list'] = []
        self._state['__pnl_list'] = []

    def add(self, order: Order):
        if not isinstance(order, Order):
            raise ValueError('.add() method only supports order objects.')

        if order.order_id in self._state:
            raise Exception(f'{order.order_id} is already in the OrderList state')

        self._state[order.order_id] = order
        # t0 = time.time()
        if self._state['__ordered_list'] and (order.time - self._state['__ordered_list'][-1].time).total_seconds() >= 0:
            self._state['__ordered_list'].append(order)
        else:
            self._state['__ordered_list'] = sorted(self._state['__ordered_list'] + [order], key=lambda x: x.time)
        # print(f"Sorting time: {time.time() - t0} =============")

    def set(self, key, value) -> None:
        raise Exception('.set() method is not supported in order list.')

    def pop(self, key: str):
        popped_value = super().pop(key)

        if popped_value is not None:
            self._state['__ordered_list'] = [order for order in self._state['__ordered_list'] if order.order_id != key]

        return popped_value

    def update(self):
        new_filled_keys = {}
        new_void_keys = {}

        for order in self._state['__ordered_list']:
            k = order.order_id
            if order.order_status == OrderStatus.FILLED:
                self._state['__filled_order_list'][k] = True
                new_filled_keys[k] = True
                try:
                    del self._state['__open_order_list'][k]
                except:
                    ...

            elif order.order_status == OrderStatus.PENDING or order.order_status == OrderStatus.PARTIALLY_FILLED:
                # self._state['__open_order_list'][k] = True
                self._state['__open_order_list'][k] = order
                # self._state['__full_open_order_list'].append(order)

            elif order.order_status == OrderStatus.CANCELED or order.order_status == OrderStatus.REJECTED:
                self._state['__void_order_list'][k] = True
                new_void_keys[k] = True
                try:
                    del self._state['__open_order_list'][k]
                except:
                    ...

            else:
                raise Exception(f'{k} has a non-recognized order state: {order.order_status}')

        # self._state['__open_order_list'] = {order_id: order for order_id, order in self._state['__open_order_list'].items() if
        #                                     (order_id not in new_filled_keys) and (order_id not in new_void_keys)}

    def add_pair(self, pair: List[Order]):
        self._state['__order_pairs_list'].append(pair)
        pnl = self.calculate_pnl(pair)
        self._state['__pnl_list'].append(pnl)
        # print(f"[PAIR ADDED] --> BUY: {pair[0]} \n--> SELL: {pair[1]}\nCum PnL: {sum(self._state['__pnl_list'])}")
        return pnl

    @staticmethod
    def calculate_pnl(pair: List[Order]):
        # TODO: verify the calculations
        pnl = 0
        for order in pair:
            fee = order.fees
            if order.filled_size == 0:
                order_value = 0
                net_order_value = 0
            else:
                order_value = order.filled_size * order.price
                # TODO: The reason for the difference of mm_gain_component and the Net Profit (PnL) is that, PnL is calculated based on the executed price but mm_gain_component is always calculated based on the current market price
                net_order_value = (order.filled_size - fee['base_fee']) * order.price - fee['quote_fee']
            if order.order_side == 'BUY':
                # pnl -= net_order_value
                pnl -= order_value
            else:
                pnl += net_order_value

        return pnl

    def get_pnl(self):
        return sum(self._state['__pnl_list']), self._state['__pnl_list']

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

    def get_pending_orders(self):
        return [order for order in self._state['__ordered_list'] if order.order_status == OrderStatus.PENDING or order.order_status == OrderStatus.PARTIALLY_FILLED]

    def get_pending_orders_before_ts_old(self, curr_time, dt=3600):
        req_pending_orders = []
        for i, order in enumerate(self.get_pending_orders()):
            if (curr_time - order.time).total_seconds() > dt:
                req_pending_orders.append(order)

        return req_pending_orders

    def get_pending_orders_before_ts(self, curr_time, dt=3600):
        ordered_pending_orders = self.get_pending_orders()
        for i, order in enumerate(reversed(ordered_pending_orders)):
            if (curr_time - order.time).total_seconds() > dt:
                return ordered_pending_orders[:-i if i else None]

        return []

    def get(self, key):
        if key in self._state:
            return self._state[key]

        return None
