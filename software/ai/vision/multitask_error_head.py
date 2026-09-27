"""Compact shared head for bounded metric error and tail-risk ranking."""

import torch
from torch import nn


class MultiTaskErrorHead(nn.Module):
    def __init__(self, mean=None, scale=None):
        super().__init__()
        mean = torch.zeros(513, dtype=torch.float32) if mean is None else torch.as_tensor(mean, dtype=torch.float32)
        scale = torch.ones(513, dtype=torch.float32) if scale is None else torch.as_tensor(scale, dtype=torch.float32)
        if mean.shape != (513,) or scale.shape != (513,) or not torch.isfinite(mean).all() or not torch.isfinite(scale).all() or not (scale > 0).all():
            raise ValueError("expected finite 513-element normalization")
        self.register_buffer("mean", mean.clone())
        self.register_buffer("scale", scale.clone())
        self.shared = nn.Sequential(
            nn.Linear(513, 96),
            nn.SiLU(),
            nn.Linear(96, 32),
            nn.SiLU(),
        )
        self.metric = nn.Linear(32, 1)
        self.tail = nn.Linear(32, 1)

    def forward(self, features):
        if features.ndim != 2 or features.shape[1] != 513 or features.dtype != torch.float32:
            raise ValueError("expected float32 N x 513 features")
        shared = self.shared((features - self.mean) / self.scale)
        return self.metric(shared).squeeze(1), self.tail(shared).squeeze(1)
