"""Image-only frozen linear residual research model; no calibration authority."""
import re
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from vision.pose_model import KeyboardPoseNet
from vision.evaluate_dark_only_normalization import normalize

SCHEMA='rocell.research.linear_residual_pose.v1'
PREPROCESS='dark_only_p95_v0_resize128x96_rgb'


class LinearResidualPoseNet(nn.Module):
    def __init__(self,pose_state,fit,source_report_sha256,source_checkpoint_sha256):
        super().__init__()
        for digest in [source_report_sha256,source_checkpoint_sha256]:
            if not isinstance(digest,str) or re.fullmatch('[0-9a-f]{64}',digest) is None:raise ValueError('invalid source digest')
        self.source_report_sha256=source_report_sha256;self.source_checkpoint_sha256=source_checkpoint_sha256
        self.backbone=KeyboardPoseNet();self.backbone.load_state_dict(pose_state,strict=True)
        for name,shape in [('mean',(512,)),('scale',(512,)),('weights',(512,3)),('intercept',(3,))]:
            value=torch.as_tensor(fit[name],dtype=torch.float64).clone()
            if value.shape!=shape or not torch.isfinite(value).all():raise ValueError('invalid '+name)
            if name=='scale' and not (value>0).all():raise ValueError('nonpositive scale')
            self.register_buffer(name,value)
        for param in self.parameters():param.requires_grad_(False)
        self.eval()

    def forward(self,image):
        if image.ndim!=4 or tuple(image.shape[1:])!=(3,96,128) or image.dtype!=torch.float32:raise ValueError('expected normalized float32 N x3 x96 x128')
        f=self.backbone.features[:4](image)
        base=self.backbone.head(self.backbone.features[4:](f)).double()
        descriptor=F.adaptive_avg_pool2d(f,(4,4)).flatten(1).double()
        return base+((descriptor-self.mean)/self.scale)@self.weights+self.intercept

    def predict_image(self,image):
        if image.mode!='RGB':raise ValueError('RGB image required')
        picture,_=normalize(image)
        x=torch.from_numpy(np.asarray(picture.resize((128,96))).transpose(2,0,1).copy())[None].float()/255
        with torch.no_grad():return self(x.to(self.mean.device))[0].cpu()

    def export(self):
        return dict(schema=SCHEMA,preprocess=PREPROCESS,source_report_sha256=self.source_report_sha256,
            source_checkpoint_sha256=self.source_checkpoint_sha256,state={k:v.detach().cpu().clone() for k,v in self.state_dict().items()})

    @classmethod
    def from_export(cls,artifact):
        if set(artifact)!={'schema','preprocess','source_report_sha256','source_checkpoint_sha256','state'} or artifact['schema']!=SCHEMA or artifact['preprocess']!=PREPROCESS:raise ValueError('invalid linear research artifact')
        state=artifact['state'];pose={k.removeprefix('backbone.'):v for k,v in state.items() if k.startswith('backbone.')}
        model=cls(pose,{k:state[k] for k in ['mean','scale','weights','intercept']},artifact['source_report_sha256'],artifact['source_checkpoint_sha256'])
        model.load_state_dict(state,strict=True)
        return model.eval()
