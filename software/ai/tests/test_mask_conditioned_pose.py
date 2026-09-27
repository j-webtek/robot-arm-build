import hashlib,json,sys
from pathlib import Path
import pytest
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.mask_conditioned_pose import MaskConditionedPoseNet
from evidence_artifacts import verify_frozen_artifacts


def test_initial_identity_and_image_only_interface():
    torch.manual_seed(4);model=MaskConditionedPoseNet('predicted').eval();x=torch.rand(2,3,96,128)
    with torch.no_grad():assert torch.equal(model(x),model.backbone(x))
    with pytest.raises(TypeError):model(x,torch.ones(2,1,24,32))
    with pytest.raises(ValueError):model(torch.rand(2,3,192,256))


def test_descriptor_retains_spatial_mask_location():
    features=torch.ones(1,32,24,32);left=torch.zeros(1,1,24,32);left[:,:,:,:16]=1
    right=1-left;a=MaskConditionedPoseNet.descriptor(features,left);b=MaskConditionedPoseNet.descriptor(features,right)
    assert a.shape==(1,512) and not torch.equal(a,b)
    assert torch.equal(a+b,torch.ones_like(a))


def test_nonzero_export_and_frozen_gradients():
    torch.manual_seed(7);model=MaskConditionedPoseNet('predicted');x=torch.rand(2,3,96,128)
    with torch.no_grad():model.residual[-1].weight.fill_(.01)
    y=model(x);y.square().mean().backward()
    assert all(p.grad is None for p in model.backbone.parameters())
    assert all(p.grad is None for p in model.segmentation.parameters())
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.residual.parameters())
    other=MaskConditionedPoseNet.from_export(model.export())
    with torch.no_grad():assert torch.equal(other(x),y)


@pytest.mark.parametrize('change',['mode','schema','extra','state'])
def test_bad_exports_rejected(change):
    artifact=MaskConditionedPoseNet('constant').export()
    if change=='mode':artifact['mode']='oracle'
    elif change=='schema':artifact['schema']='unknown'
    elif change=='extra':artifact['calibration']=True
    else:artifact['state'].pop('residual.2.weight')
    with pytest.raises((ValueError,RuntimeError)):MaskConditionedPoseNet.from_export(artifact)


def test_frozen_feasibility_evidence():
    p=AI/'eval/mask_conditioned_probe_v0_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/mask_conditioned_probe_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['images']==32 and len(r['runs'])==6
    assert {(a['seed'],a['mode']) for a in r['runs']}=={(s,m) for s in plan['seeds'] for m in ['constant','predicted']}
    for a in r['runs']:
        assert a['parameters']==293415 and a['trainable_parameters']==16515
        assert a['initial_max_pose_delta']==0 and a['nonzero_mask_conditioning_delta']>0
        assert a['roundtrip_exact'] and a['frozen_gradients_absent'] and a['residual_gradients_finite']
    assert r['optimizer_updates']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
