import unittest
import statistics
import math
import random

import numpy as np

from ats.indicators.trend_indicator import TrendIndicator


def create_random_list(lower_bound, upper_bound, list_size):
    """Creates a list of random integers within a range."""
    random_list = []
    for _ in range(list_size):
        random_number = random.randint(lower_bound, upper_bound)
        random_list.append(random_number)
    return random_list


class TestTrendIndicator(unittest.TestCase):

    def test_variance(self):
        N = 50
        trend_indicator = TrendIndicator({'N': N})
        time_series = create_random_list(0, 10, 1000)
        x = [i for i in range(N)]

        for idx, time_step in enumerate(time_series):
            trend_indicator.add(time_step)

            if trend_indicator.is_ready():
                result_1 = trend_indicator.result
                result_2 = statistics.linear_regression(x, time_series[(idx - N + 1): (idx + 1)]).slope
                assert math.isclose(result_1, result_2, abs_tol=1)
