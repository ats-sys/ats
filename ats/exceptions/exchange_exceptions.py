class InsufficientBalanceException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Insufficient balance: {error_message}")


class NoWalletAssetFoundException(Exception):
    def __init__(self, asset_type):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"No asset type found for {asset_type}")


class ExchangeConnectionException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"There is an issue connecting to the exchange : {error_message}")


class OrderNotSubmittedException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"There is an issue connecting to the exchange : {error_message}")


class InvalidOrderSubmissionException(Exception):
    def __init__(self, order, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        order_state = order.get_state(is_thread_safe=False)
        super().__init__(f"Invalid order submission for for order id {order_state['id']}: {error_message} ")




