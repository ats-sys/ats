from collections import deque

import numpy as np
from ats.indicators.base_indicator import BaseIndicator


class RsiIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.candle_length = config.get("candle_length", 1)
        # self.gains = []
        # self.losses = []
        self.gains = deque()
        self.losses = deque()
        self.prev_avg_gain = None
        self.prev_avg_loss = None
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

            calculated_data_point = self.running_calc(popped, data)
            self.time_series.append(calculated_data_point)
            self.sub_candle_count = 0
        else:
            self.sub_candle_count += 1

    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.sums is None:
            self.sums = 0

        if self.time_series:
            difference = new_data_point - self.time_series[-1]

            # Record positive differences as gains
            if difference > 0:
                gain = difference
                loss = 0
            # Record negative differences as losses
            elif difference < 0:
                gain = 0
                loss = abs(difference)
            # Record no movements as neutral
            else:
                gain = 0
                loss = 0

            # Save gains/losses
            self.gains.append(gain)
            self.losses.append(loss)

            if self.is_ready():
                # self.gains.pop(0)
                # self.losses.pop(0)
                self.gains.popleft()
                self.losses.popleft()

                avg_gain = (self.prev_avg_gain * (self.N - 1) + gain) / self.N
                avg_loss = (self.prev_avg_loss * (self.N - 1) + loss) / self.N

                # calculate the RSI
                rsi = 100 * avg_gain / (avg_gain + avg_loss)

                # Keep in memory
                self.result = rsi

            else:
                avg_gain = np.mean(self.gains)  # sum(self.gains) / len(self.gains)
                avg_loss = np.mean(self.losses)  # sum(self.losses) / len(self.losses)

            self.prev_avg_gain = avg_gain
            self.prev_avg_loss = avg_loss

        return new_data_point
