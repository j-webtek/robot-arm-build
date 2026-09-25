"""Small image-to-keyboard-pose CNN for synthetic research only."""

from __future__ import annotations

import torch
from torch import nn


class KeyboardPoseNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(64, 96, 3, stride=2, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4)), nn.Flatten(),
            nn.Linear(96 * 4 * 4, 128), nn.ReLU(),
        )
        self.head = nn.Linear(128, 3)  # normalized board center x/y and yaw / 0.2 rad

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(image))
