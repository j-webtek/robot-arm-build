"""Compact image-only obstruction classifier for synthetic research."""

import torch
from torch import nn


class ObstructionRiskNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 5, stride=2, padding=2),
            nn.SiLU(),
            nn.Conv2d(16, 28, 3, stride=2, padding=1),
            nn.SiLU(),
            nn.Conv2d(28, 44, 3, stride=2, padding=1),
            nn.SiLU(),
            nn.Conv2d(44, 64, 3, stride=2, padding=1),
            nn.SiLU(),
            nn.AdaptiveAvgPool2d((3, 3)),
            nn.Flatten(),
            nn.Linear(64 * 3 * 3, 48),
            nn.SiLU(),
        )
        self.head = nn.Linear(48, 1)

    def forward(self, image):
        if (
            image.ndim != 4
            or tuple(image.shape[1:]) != (3, 96, 128)
            or image.dtype != torch.float32
        ):
            raise ValueError("expected float32 N x 3 x 96 x 128")
        return self.head(self.features(image)).squeeze(1)
