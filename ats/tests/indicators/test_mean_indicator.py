import unittest
import statistics
import math
import random
from ats.indicators.mean_indicator import MeanIndicator


def create_random_list(lower_bound, upper_bound, list_size):
    """Creates a list of random integers within a range."""
    random_list = []
    for _ in range(list_size):
        random_number = random.randint(lower_bound, upper_bound)
        random_list.append(random_number)
    return random_list


class TestMeanIndicator(unittest.TestCase):

    def test_mean(self):
        N = 5
        mean_indicator = MeanIndicator({'N': N})
        time_series = create_random_list(0,10, 100)

        for idx, time_step in enumerate(time_series):
            mean_indicator.add(time_step)

            if mean_indicator.is_ready():
                result_1 = mean_indicator.result
                result_2 = statistics.mean(time_series[(idx - N + 1): (idx + 1)])
                assert math.isclose(result_1, result_2, abs_tol=1e-9)

    def test_mean_agg(self):
        N = 2
        candle_length = 3
        mean_indicator = MeanIndicator({'N': N, 'candle_length': candle_length})
        time_series = create_random_list(0,10, 100)

        for idx, time_step in enumerate(time_series):
            mean_indicator.add(time_step)

            if mean_indicator.is_ready() and (idx + 1) % candle_length == 0:
                result_1 = mean_indicator.result
                result_2 = statistics.mean(time_series[(idx - candle_length * N + candle_length): (idx + 1): candle_length])
                assert math.isclose(result_1, result_2, abs_tol=1e-9)
