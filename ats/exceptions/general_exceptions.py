class IncompleteModuleImplementationException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Incomplete module exception: {error_message}")


class ConfigValidationException(Exception):
    def __init__(self, config_name, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Config validation exception for {config_name}: {error_message}")



