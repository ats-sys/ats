import numpy as np
from ats.exchanges.data_classes.candle import Candle
from ats.indicators.base_indicator import BaseIndicator


class SuperTrendIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.prev_close = None
        self.prev_atr = None
        self.prev_st_upper = None
        self.prev_st_lower = None
        self.prev_st = True
        self.multiplier = config["multiplier"]

    def add(self, candle: Candle):
        """
        Adds a new datapoint
        Args:
            candle: new candle

        Returns:
            None
        """
        popped = None
        if len(self.time_series) == self.N:
            self._is_ready = True
            # popped = self.time_series.pop(0)
            popped = self.time_series.popleft()

        tr = self.running_calc(popped, candle)
        self.time_series.append(tr)

    def running_calc(self, popped_data_point, new_data_point) -> any:
        high = new_data_point.high
        low = new_data_point.low
        close = new_data_point.close
        hl2 = (high + low) / 2

        if self.prev_close is None:
            self.prev_close = close

        tr = max(high - low, abs(high - self.prev_close), abs(self.prev_close - low))
        L = len(self.time_series)
        atr = (np.sum(self.time_series) + tr) / (L + 1)

        st_upper = hl2 + self.multiplier * atr
        st_lower = hl2 - self.multiplier * atr

        if self.prev_st_upper is None:
            self.prev_st_upper, self.prev_st_lower = st_upper, st_lower

        # if current close price crosses above upperband
        if close > self.prev_st_upper:
            st = True
        # if current close price crosses below lowerband
        elif close < self.prev_st_lower:
            st = False
        # else, the trend continues
        else:
            st = self.prev_st

            # adjustment to the final bands
            if st and st_lower < self.prev_st_lower:
                st_lower = self.prev_st_lower
            if not st and st_upper > self.prev_st_upper:
                st_upper = self.prev_st_upper

        self.result = {
            "st": st,
            "st_upper": st_upper,
            "st_lower": st_lower
        }

        self.prev_close = close
        self.prev_atr = atr
        self.prev_st_upper = st_upper
        self.prev_st_lower = st_lower
        self.prev_st = st

        return tr
