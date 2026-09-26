"""Differentiable synthetic key displacement; no runtime calibration."""
import math
import torch


def project_keys(pose, offsets):
    center=pose[:,:2]*pose.new_tensor([30.,24.])+pose.new_tensor([235.,154.])
    angle=math.pi+.2*pose[:,2]
    c,s=angle.cos()[:,None],angle.sin()[:,None]
    x=c*offsets[None,:,0]-s*offsets[None,:,1]
    y=s*offsets[None,:,0]+c*offsets[None,:,1]
    return torch.stack((x,y),dim=-1)+center[:,None,:]


def key_loss(prediction,truth,offsets):
    # Fixed 30 mm reference scale; average squared Euclidean key error.
    return (project_keys(prediction,offsets)-project_keys(truth,offsets)).square().sum(-1).mean()/900
