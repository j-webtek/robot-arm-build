"""Small research landmark network; logits are not calibrated confidence."""
import torch
from torch import nn


class KeyboardLandmarkNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features=nn.Sequential(nn.Conv2d(3,16,3,padding=1),nn.ReLU(),
            nn.Conv2d(16,32,3,stride=2,padding=1),nn.ReLU(),
            nn.Conv2d(32,64,3,stride=2,padding=1),nn.ReLU(),
            nn.Conv2d(64,64,3,padding=1),nn.ReLU())
        self.heatmaps=nn.Conv2d(64,4,1)
        self.visibility=nn.Sequential(nn.AdaptiveAvgPool2d(1),nn.Flatten(),nn.Linear(64,4))

    def forward(self,image):
        if image.ndim!=4 or image.shape[1:]!=(3,192,256):
            raise ValueError("Expected Bx3x192x256 synthetic images")
        features=self.features(image)
        return dict(heatmap_logits=self.heatmaps(features),visibility_logits=self.visibility(features))


def heatmap_coordinates(logits):
    """Soft-argmax in full-image pixel coordinates; not an uncertainty estimate."""
    if logits.ndim!=4 or logits.shape[1:]!=(4,48,64):
        raise ValueError("Expected Bx4x48x64 heatmaps")
    probability=logits.flatten(2).softmax(-1).reshape_as(logits)
    # Conv stride4 grid uses input centers 0,4,...,252 and 0,4,...,188.
    x=torch.arange(64,device=logits.device,dtype=logits.dtype)*4
    y=torch.arange(48,device=logits.device,dtype=logits.dtype)*4
    return torch.stack(((probability.sum(2)*x).sum(-1),(probability.sum(3)*y).sum(-1)),dim=-1)
