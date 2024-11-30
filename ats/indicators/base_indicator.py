from collections import deque
from abc import abstractmethod


# TODO: Make this thread safe.
class BaseIndicator:
    def __init__(self, config: dict):
        # self.time_series = []
        self.time_series = deque()
        self.config = config
        self.N = config['N']
        self.sums = None
        self.states = None
        self.result = None
        self._is_ready = False

    def add(self, data):
        """
        Adds a new datapoint
        Args:
            data: new datapoint

        Returns:
            None
        """
        popped = None
        if len(self.time_series) == self.N:
            self._is_ready = True
            # popped = self.time_series.pop(0)
            popped = self.time_series.popleft()

        calculated_data_point = self.running_calc(popped, data)
        self.time_series.append(calculated_data_point)

    @abstractmethod
    def running_calc(self, popped_data_point, new_data_point) -> any:
        """
        Calculates the indicators in a running window.
        self._result must be updated in this method
        Args:
            popped_data_point: the data point popped out from the running window
            new_data_point: New datapoint just arrived

        Returns:
            Returns the new data point appended to the running window.
            Note: new_data_point is not added to the running window by default
        """
        pass

    def is_ready(self) -> bool:
        return self._is_ready
