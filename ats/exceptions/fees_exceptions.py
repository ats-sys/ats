class FeesNotSetException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Fees not set : {error_message}")



