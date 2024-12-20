import math
from collections import deque
from ats.exchanges.data_classes.candle import Candle


class PriceProbModel:
    """
    Creates a probabilistic model of how likely the price can be, considering past states.
    """
    def __init__(self, step: float, history_len = 10):
        self._price_freq_lookup = {}
        # self._candle_history = []
        self._candle_history = deque()
        self._step = step
        self._tot = 0
        self._history_len = history_len
        self._max = 1

    def get_prob(self, price: float) -> float:
        """
        Returns prob score for a price based on history data
        Args:
            price: price

        Returns:
            Value ranging from 0 to 1
        """
        steps = math.floor(price/self._step)

        if len(self._price_freq_lookup) == 0 or steps not in self._price_freq_lookup or self._tot == 0:
            return 0

        return self._price_freq_lookup[steps] / self._max

    def add(self, candle: Candle):
        low_steps = math.floor(candle.low/self._step)
        high_steps = math.floor(candle.high/self._step)
        tot_steps = high_steps - low_steps + 1

        self._candle_history.append({
            'candle': candle,
            'low_steps': low_steps,
            'high_steps': high_steps,
            'tot_steps': tot_steps
        })

        # Create new zero entries if not existing
        # self._zero_entries_if_not_exist(up_to=high_steps)

        # Updating the lookup
        for i in range(low_steps, high_steps + 1): # +1 to include high_steps
            if i not in self._price_freq_lookup:
                self._price_freq_lookup[i] = 0

            self._price_freq_lookup[i] += 1

            if self._price_freq_lookup[i] > self._max:
                self._max = self._price_freq_lookup[i]

        self._tot += 1

        if len(self._price_freq_lookup) > self._history_len:
            # oldest_item = self._candle_history.pop(0)
            oldest_item = self._candle_history.popleft()

            max_changed = False

            for i in range(oldest_item['low_steps'], oldest_item['high_steps'] + 1):  # +1 to include high_steps
                if i in self._price_freq_lookup and self._price_freq_lookup[i] > 0:
                    self._price_freq_lookup[i] -= 1

                    if self._price_freq_lookup[i] + 1 == self._max:
                        max_changed = True

            # Recalculate max value if last deducted value is the previous max
            if max_changed:
                self._max = max(self._price_freq_lookup.values())

            if self._tot > 0:
                self._tot -= 1
