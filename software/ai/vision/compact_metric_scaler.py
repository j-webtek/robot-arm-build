"""A compact risk-aware scale correction for a frozen metric bound."""

import torch
from torch import nn


class CompactMetricScaler(nn.Module):
    """Predict one bounded multiplier from base-bound and risk evidence."""

    def __init__(self, mean, scale):
        super().__init__()
        self.register_buffer("mean", torch.as_tensor(mean, dtype=torch.float32))
        self.register_buffer("scale", torch.as_tensor(scale, dtype=torch.float32))
        self.linear = nn.Linear(2, 1)

    def forward(self, features):
        normalized = (features - self.mean) / self.scale
        return self.linear(normalized).squeeze(-1)


def bounded_multiplier(raw, minimum, maximum):
    """Map an unconstrained scalar to the preregistered multiplier interval."""

    return minimum + (maximum - minimum) * torch.sigmoid(raw)
