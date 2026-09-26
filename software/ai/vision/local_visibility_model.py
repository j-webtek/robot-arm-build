"""Predicted-peak local visibility features; no oracle coordinates or confidence."""
import torch
from vision.landmark_model import KeyboardLandmarkNet

class LocalVisibilityNet(KeyboardLandmarkNet):
    def __init__(self,mode):
        super().__init__()
        if mode not in ('global','local'):raise ValueError(mode)
        self.mode=mode

    def forward(self,image):
        if image.ndim!=4 or image.shape[1:]!=(3,192,256):raise ValueError('Expected Bx3x192x256')
        f=self.features(image);h=self.heatmaps(f)
        if self.mode=='global':v=self.visibility(f)
        else:
            # Hard predicted peak; detached position, identical learned head weights.
            peak=h.flatten(2).argmax(-1)
            x=(peak%64).to(f.dtype);y=(peak//64).to(f.dtype)
            offsets=torch.tensor([(a,b) for b in (-1,0,1) for a in (-1,0,1)],device=f.device,dtype=f.dtype)
            grid=torch.stack((x,y),-1)[:,:,None,:]+offsets
            grid=grid/torch.tensor([63,47],device=f.device,dtype=f.dtype)*2-1
            sampled=torch.nn.functional.grid_sample(f,grid,align_corners=True,padding_mode='border').mean(-1).transpose(1,2)
            head=self.visibility[2]
            v=(sampled*head.weight[None,:,:]).sum(-1)+head.bias
        return dict(heatmap_logits=h,visibility_logits=v)
