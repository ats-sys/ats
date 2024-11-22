from ats.exchanges.data_classes.candle import Candle
from ats.indicators.base_indicator import BaseIndicator


class CandleIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self._is_ready = True
        self.curr_candle = None
        self.candle_number = 0
        self.end_of_candle = False
        self.sub_candle_count = 0

    def add(self, candle: Candle):
        """
        Adds a new datapoint
        Args:
            candle: new datapoint

        Returns:
            None
        """
        self.curr_candle = self.running_calc(None, candle)

    def running_calc(self, popped_data_point, new_data_point: Candle) -> any:
        if self.curr_candle is None:
            curr_candle = new_data_point
        else:
            curr_candle = Candle(
                open=self.curr_candle.open,
                high=max(self.curr_candle.high, new_data_point.high),
                low=min(self.curr_candle.low, new_data_point.low),
                close=new_data_point.close,
                symbol=self.curr_candle.symbol,
                buy_vol=self.curr_candle.buy_vol + new_data_point.buy_vol,
                sell_vol=self.curr_candle.sell_vol + new_data_point.sell_vol,
                time=new_data_point.time
            )

        self.sub_candle_count += 1

        self.result = {
            "candle_number": self.candle_number,
            "candle": curr_candle
        }

        if self.sub_candle_count == self.N:
            curr_candle = None
            self.sub_candle_count = 0
            self.end_of_candle = True
            self.candle_number += 1
        else:
            self.end_of_candle = False

        self.result["end_of_candle"] = self.end_of_candle

        return curr_candle
