import torch
import random
import numpy as np
import torch.nn as nn
from collections import deque


class ATSModel(nn.Module):
    def __init__(self, n_inputs=1, hidden_size=50, num_layers=1, batch_first=True, n_classes=2, demo=True):
        super().__init__()
        assert n_classes > 1, f"n_classes should be greater than 2 but got {n_classes}"

        self.lstm = nn.LSTM(input_size=n_inputs, hidden_size=hidden_size, num_layers=num_layers,
                            batch_first=batch_first)
        self.linear = nn.Linear(hidden_size, n_classes)

        self.demo = demo
        # For Demo Only
        self.elements = [[1,0,0],[0,1,0],[0,0,1]]
        # self.probabilities = [0.5, 0.25, 0.25]
        self.probabilities = [0.8, 0.1, 0.1]

    def __demo_ops(self, x):
        # For Demo Only (since the model is not trained)
        x = random.choices(self.elements, weights=self.probabilities, k=1)
        x = torch.tensor(x)

        return x

    def forward(self, x):
        x, _ = self.lstm(x)
        x = self.linear(x[:, -1, :])
        x = torch.softmax(x, dim=-1)

        if self.demo:
            x = self.__demo_ops(x)

        return x

from abc import ABC, abstractmethod

class BaseAIModel(ABC):
    def __init__(self, model, *args, **kwargs):
        self.model = model
        self.model.eval()

    def _pre_process(self, x):
        """
        Data pre-processing logic
        Args:
            x: raw inputs for the model

        Returns:
            pre-processed input
        """
        return x

    def _post_process(self, y):
        """
        Response post-processing logic
        Args:
            y: immediate output from the model

        Returns:
            post-processed response
        """
        return y

    def _infer(self, x):
        """
        Model inference of the model
        Args:
            x: model input

        Returns:
            model output

        """

        with torch.no_grad():
            y = self.model(x)

        return y

    def predict(self, x):
        """
        Get desired output from inputs
        Args:
            x: input for prediction

        Returns:
            desired output

        """
        x = self._pre_process(x)
        y = self._infer(x)
        y = self._post_process(y)

        return y

class AIModel(BaseAIModel):
    def __init__(self, model, lookback):
        super().__init__(model, lookback)
        self.lookback = lookback
        # self.input_buffer = []
        self.input_buffer = deque()

    def _pre_process(self, x):
        self.input_buffer.append(x)

        if len(self.input_buffer) > self.lookback:
            # self.input_buffer.pop(0)
            self.input_buffer.popleft()

        # if len(self.input_buffer) < self.lookback:
        #     return False

        # Prepare windowed data
        x = torch.tensor(self.input_buffer[-self.lookback:]).unsqueeze(0)
        print(x.shape)

        return x

    def _post_process(self, y: torch.tensor):
        return torch.argmax(y, dim=-1).item()

    def predict(self, x):
        x = self._pre_process(x)

        if len(self.input_buffer) < self.lookback:
            return 0

        y = super()._infer(x)

        return self._post_process(y)


def get_random_data(n_inputs):
    # print(torch.tensor(np.random.uniform(0, 65_000, 2), dtype=torch.float32))
    # return torch.tensor(np.random.uniform(0, 65_000, 2), dtype=torch.float32)
    return np.random.uniform(0, 65_000, n_inputs).tolist()
    # return torch.randn(2).tolist()

if __name__ == "__main__":
    window_len = 30
    n_inputs = 2
    hidden_size = 50
    num_layers = 2
    n_classes = 3

    ats_model = ATSModel(n_inputs=n_inputs, hidden_size=hidden_size, num_layers=num_layers, n_classes=n_classes)
    ats_model.load_state_dict(torch.load("ai_model_clf.pt", weights_only=True))
    ai_model = AIModel(ats_model, window_len)

    for i in range(100):
        x = get_random_data(n_inputs)
        y = ai_model.predict(x)
        print(i, x, y)
        print("--------------------")