from ats.indicators.base_indicator import BaseIndicator


def multiply_lists_recursive(list1, list2, index=0):
    if index == len(list1):
        return []
    return [list1[index] * list2[index]] + multiply_lists_recursive(list1, list2, index + 1)


class MeanIndicator(BaseIndicator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.candle_length = config.get("candle_length", 1)
        self.is_weighted = config.get('is_weighted', False)

        if self.is_weighted:
            d = (1 + self.N) * self.N / 2
            self.weights = [(i + 1) / d for i in range(self.N)]
        else:
            self.weights = None

        self.sub_candle_count = 0

    def add(self, data):
        """
        Adds a new datapoint
        Args:
            data: new datapoint

        Returns:
            None
        """
        if self.candle_length == 1 or (self.sub_candle_count == self.candle_length - 1):
            popped = None
            if len(self.time_series) == self.N:
                self._is_ready = True
                # popped = self.time_series.pop(0)
                popped = self.time_series.popleft()

            calculated_data_point = self.running_calc(popped, data)
            self.time_series.append(calculated_data_point)
            self.sub_candle_count = 0
        else:
            self.sub_candle_count += 1

    def running_calc(self, popped_data_point, new_data_point) -> any:
        if self.is_weighted:
            if self.is_ready():
                # self.result = sum(multiply_lists_recursive(self.time_series + [new_data_point], self.weights))
                self.result = sum(list(map(lambda x, y: x * y, self.time_series + [new_data_point], self.weights)))
        else:
            if self.sums is None:
                self.sums = 0

            self.sums += new_data_point

            if self.is_ready():
                self.sums -= popped_data_point
                self.result = self.sums / self.N

        return new_data_point
