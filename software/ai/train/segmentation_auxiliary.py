"""Training-only visible-case labels and auxiliary segmentation head."""
import numpy as np
from PIL import Image,ImageDraw
import torch
from torch import nn
from torch.nn import functional as F
from vision.pose_model import KeyboardPoseNet


def visible_case_target(label,foreground_mask):
    if foreground_mask.size!=tuple(label['image_size']):raise ValueError('mask/image size mismatch')
    polygon=Image.new('L',foreground_mask.size)
    ImageDraw.Draw(polygon).polygon([(p['x_px'],p['y_px']) for p in label['landmarks']],fill=255)
    visible=(np.asarray(polygon)>0)&(np.asarray(foreground_mask)==0)
    target=torch.from_numpy(visible.astype(np.float32))[None,None]
    return F.interpolate(target,size=(24,32),mode='area')[0]


def balanced_mask_loss(logits,target):
    # Mean positive/negative soft-label contributions, averaging nonempty classes.
    positive=target.sum();negative=(1-target).sum()
    terms=[]
    if positive.item()>0:terms.append(-(target*F.logsigmoid(logits)).sum()/positive)
    if negative.item()>0:terms.append(-((1-target)*F.logsigmoid(-logits)).sum()/negative)
    return torch.stack(terms).mean()


class SegmentationPoseNet(nn.Module):
    def __init__(self):
        super().__init__();self.backbone=KeyboardPoseNet();self.segmentation=nn.Conv2d(32,1,1)

    def forward(self,image):
        x=image
        for layer in self.backbone.features[:4]:x=layer(x)
        mask=self.segmentation(x)
        for layer in self.backbone.features[4:]:x=layer(x)
        return dict(pose=self.backbone.head(x),mask_logits=mask)

    def load_pose_weights(self,state):
        self.backbone.load_state_dict(state,strict=True)
