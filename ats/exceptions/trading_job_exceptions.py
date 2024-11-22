class TradingJobNotFoundException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Trading job not found: {error_message}")


class TradingJobNotRunningException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Trading job not running: {error_message}")


class TradingJobAlreadyRunningException(Exception):
    def __init__(self, error_message):
        self.show_in_response = True  # if True, the error details will be displayed in the frontend
        super().__init__(f"Trading already running: {error_message}")



