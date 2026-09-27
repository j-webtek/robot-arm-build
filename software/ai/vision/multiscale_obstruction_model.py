"""Localized multi-scale image-only obstruction classifier."""

import torch
from torch import nn


class MultiScaleObstructionNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features=nn.Sequential(
            nn.Conv2d(3,16,5,stride=2,padding=2),nn.SiLU(),
            nn.Conv2d(16,24,3,stride=2,padding=1),nn.SiLU(),
            nn.Conv2d(24,36,3,padding=1),nn.SiLU(),
            nn.Conv2d(36,48,3,stride=2,padding=1),nn.SiLU())
        self.projection=nn.Sequential(nn.Linear(96,64),nn.SiLU(),nn.Linear(64,1))

    def forward(self,image):
        if image.ndim!=4 or tuple(image.shape[1:])!=(3,96,128) or image.dtype!=torch.float32:
            raise ValueError('expected float32 N x 3 x 96 x 128')
        feature=self.features(image)
        average=torch.nn.functional.adaptive_avg_pool2d(feature,1).flatten(1)
        maximum=torch.nn.functional.adaptive_max_pool2d(feature,1).flatten(1)
        return self.projection(torch.cat([average,maximum],1)).squeeze(1)
