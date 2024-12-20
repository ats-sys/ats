import torch
from ats.indicators.base_indicator import BaseIndicator


class AiIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.model = config.get("model")
        self.candle_length = config.get("candle_length", 1)
        self.sub_candle_count = 0

    def add(self, data):
        """
        Adds a new datapoint
        Args:
            data: new datapoint

        Returns:
            None
        """
        if self.candle_length == 1 or (self.sub_candle_count == self.candle_length - 1):
            popped = None
            if len(self.time_series) == self.N:
                self._is_ready = True
                # popped = self.time_series.pop(0)
                popped = self.time_series.popleft()

            self.time_series.append(data)
            _ = self.running_calc(popped, data)
            self.sub_candle_count = 0
        else:
            self.sub_candle_count += 1
            self.result = None

    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.time_series:

            if self.is_ready():
                x = torch.tensor(self.time_series).unsqueeze(0)
                with torch.no_grad():
                    y = self.model(x)

                # Keep in memory
                self.result = y

        return new_data_point
