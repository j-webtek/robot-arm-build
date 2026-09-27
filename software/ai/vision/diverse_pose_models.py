"""Two compact pose architectures for synthetic ensemble research."""

import torch
from torch import nn


class SiLUPoseNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 24, 5, stride=2, padding=2),
            nn.SiLU(),
            nn.Conv2d(24, 40, 3, stride=2, padding=1),
            nn.SiLU(),
            nn.Conv2d(40, 64, 3, stride=2, padding=1),
            nn.SiLU(),
            nn.Conv2d(64, 96, 3, stride=2, padding=1),
            nn.SiLU(),
            nn.AdaptiveAvgPool2d((3, 3)),
            nn.Flatten(),
            nn.Linear(96 * 3 * 3, 96),
            nn.SiLU(),
        )
        self.head = nn.Linear(96, 3)

    def forward(self, image):
        if image.ndim != 4 or tuple(image.shape[1:]) != (3, 96, 128) or image.dtype != torch.float32:
            raise ValueError("expected normalized float32 N x 3 x 96 x 128")
        return self.head(self.features(image))


class SeparableBlock(nn.Module):
    def __init__(self, input_channels, output_channels, stride):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(
                input_channels,
                input_channels,
                3,
                stride=stride,
                padding=1,
                groups=input_channels,
            ),
            nn.Conv2d(input_channels, output_channels, 1),
            nn.SiLU(),
        )

    def forward(self, image):
        return self.block(image)


class SeparablePoseNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 24, 5, stride=2, padding=2),
            nn.SiLU(),
            SeparableBlock(24, 32, 2),
            SeparableBlock(32, 48, 2),
            SeparableBlock(48, 72, 2),
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(72 * 4 * 4, 64),
            nn.SiLU(),
        )
        self.head = nn.Linear(64, 3)

    def forward(self, image):
        if image.ndim != 4 or tuple(image.shape[1:]) != (3, 96, 128) or image.dtype != torch.float32:
            raise ValueError("expected normalized float32 N x 3 x 96 x 128")
        return self.head(self.features(image))


MODELS = {"silu": SiLUPoseNet, "separable": SeparablePoseNet}
