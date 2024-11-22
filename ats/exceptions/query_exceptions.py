class QueryFormatException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Query format error: {error_message}")


class NoDataFoundException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"No data found: {error_message}")


class PresentationLoadingException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Query presentation processor loading error: {error_message}")
