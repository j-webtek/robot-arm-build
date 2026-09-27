"""Compact residual multiplier over a frozen metric uncertainty proposal."""

import torch
from torch import nn


class ResidualMetricHead(nn.Module):
    def __init__(self, mean=None, scale=None):
        super().__init__()
        mean = (
            torch.zeros(514, dtype=torch.float32)
            if mean is None
            else torch.as_tensor(mean, dtype=torch.float32)
        )
        scale = (
            torch.ones(514, dtype=torch.float32)
            if scale is None
            else torch.as_tensor(scale, dtype=torch.float32)
        )
        if (
            mean.shape != (514,)
            or scale.shape != (514,)
            or not torch.isfinite(mean).all()
            or not torch.isfinite(scale).all()
            or not (scale > 0).all()
        ):
            raise ValueError("expected finite 514-element normalization")
        self.register_buffer("mean", mean.clone())
        self.register_buffer("scale", scale.clone())
        self.head = nn.Sequential(
            nn.Linear(514, 96),
            nn.SiLU(),
            nn.Linear(96, 32),
            nn.SiLU(),
            nn.Linear(32, 1),
        )

    def forward(self, features):
        if (
            features.ndim != 2
            or features.shape[1] != 514
            or features.dtype != torch.float32
        ):
            raise ValueError("expected float32 N x 514 features")
        return self.head((features - self.mean) / self.scale).squeeze(1)


def bounded_multiplier(raw, minimum, maximum):
    if minimum <= 0 or maximum <= minimum:
        raise ValueError("invalid multiplier bounds")
    return minimum + (maximum - minimum) * torch.sigmoid(raw)
