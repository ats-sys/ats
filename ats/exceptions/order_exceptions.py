class InvalidOrderOperationException(Exception):
    def __init__(self, order, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Invalid order operation {order.get_state(is_thread_safe=False)['id']}: {error_message}")

class InvalidOrderException(Exception):
    def __init__(self, order, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Invalid order {order.get_state(is_thread_safe=False)['id']}: {error_message}")

class UnsupportedStatusException(Exception):
    def __init__(self, order, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Unsupported status for order id {order.get_state(is_thread_safe=False)['id']}: {error_message}")


class OrderFillingException(Exception):
    def __init__(self, order, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        order_state = order.get_state(is_thread_safe=False)
        super().__init__(f"Order over fill for order id {order_state['id']}: {error_message} ")

class OrderStateSyncException(Exception):
    def __init__(self, order, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        order_state = order.get_state(is_thread_safe=False)
        super().__init__(f"Order state sync {order_state['id']}: {error_message} ")


