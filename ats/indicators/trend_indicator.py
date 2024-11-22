from ats.indicators.base_indicator import BaseIndicator
import numpy as np
import statistics


class TrendIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.x = np.array([i for i in range(self.N)])
        mu_x = np.mean(self.x)
        self.res_x = self.x - mu_x
        square_res_x = np.square(self.res_x)
        self.sum_square_res_x = np.sum(square_res_x)

    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.sums is None:
            self.sums = 0

        self.sums += new_data_point

        if self.is_ready():
            self.sums -= popped_data_point
            y = np.array(self.time_series + [new_data_point])
            mu_y = self.sums / self.N
            res_y = y - mu_y
            self.result = np.sum(self.res_x * res_y) / self.sum_square_res_x  # trend of last window_length elements

        return new_data_point
