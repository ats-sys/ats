class ValidationException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Model validation error: {error_message}")


class InvalidRelationConfigException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Model relation config error: {error_message}")


class InvalidRelationException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Invalid relation error: {error_message}")