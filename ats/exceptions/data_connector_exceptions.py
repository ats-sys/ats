class ConfigValidationException(Exception):
    def __init__(self, error_message):
        self.error_message = error_message
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"DataConnector config validation error: {error_message}")