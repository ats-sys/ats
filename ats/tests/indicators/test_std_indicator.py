import unittest
import statistics
import math
import random
from ats.indicators.std_indicator import StdIndicator


def create_random_list(lower_bound, upper_bound, list_size):
    """Creates a list of random integers within a range."""
    random_list = []
    for _ in range(list_size):
        random_number = random.randint(lower_bound, upper_bound)
        random_list.append(random_number)
    return random_list


class TestStdIndicator(unittest.TestCase):

    def test_variance(self):
        N = 50
        variance_indicator = StdIndicator({'N': N})
        time_series = create_random_list(0, 10, 1000)

        for idx, time_step in enumerate(time_series):
            variance_indicator.add(time_step)

            if variance_indicator.is_ready():
                result_1 = variance_indicator.result
                result_2 = statistics.stdev(time_series[(idx - N + 1): (idx + 1)])
                assert math.isclose(result_1, result_2, abs_tol=1)
