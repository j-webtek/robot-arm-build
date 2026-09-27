"""Research-only frozen-feature residual pose model; image-only inference."""
from __future__ import annotations
import torch
from torch import nn
from torch.nn import functional as F
from vision.pose_model import KeyboardPoseNet


class MaskConditionedPoseNet(nn.Module):
    def __init__(self, mode: str):
        super().__init__()
        if mode not in ('predicted', 'constant'):
            raise ValueError('unknown mask mode')
        self.mode = mode
        self.backbone = KeyboardPoseNet()
        self.segmentation = nn.Conv2d(32, 1, 1)
        self.residual = nn.Sequential(nn.Linear(32 * 4 * 4, 32), nn.ReLU(), nn.Linear(32, 3))
        nn.init.zeros_(self.residual[-1].weight)
        nn.init.zeros_(self.residual[-1].bias)
        for module in (self.backbone, self.segmentation):
            for parameter in module.parameters():
                parameter.requires_grad_(False)

    @staticmethod
    def descriptor(features, mask):
        return F.adaptive_avg_pool2d(features * mask, (4, 4)).flatten(1)

    def forward(self, image):
        if image.ndim != 4 or tuple(image.shape[1:]) != (3, 96, 128):
            raise ValueError('expected N x 3 x 96 x 128 image tensor')
        # Both arms compute the same frozen features and mask. Only conditioning differs.
        with torch.no_grad():
            features = self.backbone.features[:4](image)
            predicted_mask = self.segmentation(features).sigmoid()
            base = self.backbone.head(self.backbone.features[4:](features))
        mask = predicted_mask if self.mode == 'predicted' else torch.ones_like(predicted_mask)
        return base + self.residual(self.descriptor(features, mask))

    def load_sources(self, pose_state, mask_state):
        self.backbone.load_state_dict(pose_state, strict=True)
        self.segmentation.load_state_dict(mask_state, strict=True)

    def export(self):
        return dict(schema='rocell.research.mask_conditioned_pose.v0', mode=self.mode,
                    state={key: value.detach().cpu().clone() for key, value in self.state_dict().items()})

    @classmethod
    def from_export(cls, artifact):
        if set(artifact) != {'schema', 'mode', 'state'} or artifact['schema'] != 'rocell.research.mask_conditioned_pose.v0':
            raise ValueError('invalid research model artifact')
        model = cls(artifact['mode'])
        model.load_state_dict(artifact['state'], strict=True)
        return model.eval()
