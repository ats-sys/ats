from ats.exchanges.data_classes.candle import Candle
from ats.indicators.base_indicator import BaseIndicator


class ObvIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.candle_length = config.get("candle_length", 1)
        # self._is_ready = True
        self.sub_candle_count = 0
        self.candle_vol = 0
        self.previous_close = None

    def add(self, candle: Candle):
        """
        Adds a new datapoint
        Args:
            candle: new candle

        Returns:
            None
        """
        vol = candle.buy_vol + candle.sell_vol
        self.candle_vol += vol

        if self.candle_length == 1 or (self.sub_candle_count == self.candle_length - 1):
            close = candle.close

            # Initialize previous_close if this is the first candle
            if self.previous_close is None:
                self.previous_close = close
                self._is_ready = True
                self.result = (0, 0)  # Initial OBV value and change
                return

            _ = self.running_calc(None, close)

            self.sub_candle_count = 0
            self.candle_vol = 0
            self.previous_close = close
        else:
            self.sub_candle_count += 1

    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.sums is None:
            self.sums = 0

        if new_data_point > self.previous_close:
            diff = self.candle_vol
        elif new_data_point < self.previous_close:
            diff = -self.candle_vol
        else:
            diff = 0

        self.sums += diff

        self.result = (self.sums, diff)
        self._is_ready = True

        return new_data_point
