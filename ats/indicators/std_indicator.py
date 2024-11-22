import math
from ats.indicators.base_indicator import BaseIndicator


class StdIndicator(BaseIndicator):
    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.sums is None:
            self.sums = {'sum': 0, 'sqr_diff': 0}

        time_series_len = len(self.time_series)
        self.sums['sum'] += new_data_point

        mean = self.sums['sum'] / (time_series_len + 1) if time_series_len > 0 else self.sums['sum']
        diff_sqr = (mean - new_data_point) ** 2

        self.sums['sqr_diff'] += diff_sqr

        if self.is_ready():
            self.sums['sum'] -= popped_data_point['raw_data']
            self.sums['sqr_diff'] -= popped_data_point['sqr_diff']
            self.result = math.sqrt(self.sums['sqr_diff'] / (self.N-1))

        return {
            'raw_data': new_data_point,
            'sqr_diff': diff_sqr,
        }
