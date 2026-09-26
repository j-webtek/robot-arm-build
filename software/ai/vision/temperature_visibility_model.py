"""Continuous predicted heatmap weighting; synthetic research only."""
import torch
from vision.local_visibility_model import LocalVisibilityNet

class TemperatureVisibilityNet(LocalVisibilityNet):
    def __init__(self,mode):
        super().__init__('local')
        if mode not in ('t1','t05'):raise ValueError(mode)
        self.pooling_mode=mode

    def forward(self,image):
        if image.ndim!=4 or image.shape[1:]!=(3,192,256):raise ValueError('Expected Bx3x192x256')
        f=self.features(image);h=self.heatmaps(f)
        # Match the hard head's border-replicated 3x3 neighborhoods.
        neighborhoods=torch.nn.functional.avg_pool2d(torch.nn.functional.pad(f,(1,1,1,1),mode='replicate'),3,stride=1)
        # Detach location weights as hard argmax also blocks location gradients.
        temperature=1.0 if self.pooling_mode=='t1' else 0.5
        weights=(h.flatten(2)/temperature).softmax(-1).detach()
        sampled=torch.einsum('bkn,bcn->bkc',weights,neighborhoods.flatten(2))
        head=self.visibility[2];v=(sampled*head.weight[None,:,:]).sum(-1)+head.bias
        return dict(heatmap_logits=h,visibility_logits=v)
