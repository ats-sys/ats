import math
from ats.indicators.base_indicator import BaseIndicator


class StdIndicatorFirstDer(BaseIndicator):
    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.sums is None:
            self.sums = {'sum': 0, 'sqr_diff': 0}

        if self.states is None:
            self.states = {'prev_data': new_data_point}

        # First derivative
        first_der = new_data_point - self.states['prev_data']

        time_series_len = len(self.time_series)
        self.sums['sum'] += first_der

        mean = self.sums['sum'] / (time_series_len + 1) if time_series_len > 0 else self.sums['sum']
        diff_sqr = (mean - first_der) ** 2

        self.sums['sqr_diff'] += diff_sqr

        if self.is_ready():
            self.sums['sum'] -= popped_data_point['raw_data']
            self.sums['sqr_diff'] -= popped_data_point['sqr_diff']
            self.result = math.sqrt(self.sums['sqr_diff'] / (self.N-1))

        self.states = {'prev_data': new_data_point}

        return {
            'raw_data': first_der,
            'sqr_diff': diff_sqr,
        }
