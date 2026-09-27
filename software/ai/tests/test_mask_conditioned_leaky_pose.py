import sys
from pathlib import Path
import pytest
import torch
AI=Path(__file__).resolve().parents[1];sys.path.insert(0,str(AI))
from vision.mask_conditioned_pose import MaskConditionedPoseNet
from vision.mask_conditioned_leaky_pose import LeakyMaskConditionedPoseNet


def test_negative_gradient_and_initial_identity():
    torch.manual_seed(4);old=MaskConditionedPoseNet('predicted')
    torch.manual_seed(4);model=LeakyMaskConditionedPoseNet('predicted')
    assert all(torch.equal(a,b) for a,b in zip(old.state_dict().values(),model.state_dict().values()))
    x=torch.rand(2,3,96,128)
    with torch.no_grad():assert torch.equal(model(x),old(x)) and torch.equal(model(x),model.backbone(x))
    negative=torch.tensor([-2.,-1.],requires_grad=True);model.residual[1](negative).sum().backward()
    assert torch.equal(negative.grad,torch.full_like(negative,.01))


def test_versioned_nonzero_roundtrip_and_legacy_rejection():
    model=LeakyMaskConditionedPoseNet('constant')
    with torch.no_grad():model.residual[-1].weight.fill_(.01)
    artifact=model.export();restored=LeakyMaskConditionedPoseNet.from_export(artifact);x=torch.rand(2,3,96,128)
    with torch.no_grad():assert torch.equal(restored(x),model(x))
    with pytest.raises(ValueError):MaskConditionedPoseNet.from_export(artifact)
    with pytest.raises(ValueError):LeakyMaskConditionedPoseNet.from_export(MaskConditionedPoseNet('constant').export())
    artifact['negative_slope']=.1
    with pytest.raises(ValueError):LeakyMaskConditionedPoseNet.from_export(artifact)
