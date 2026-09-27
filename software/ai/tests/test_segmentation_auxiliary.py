import hashlib,json,sys
from pathlib import Path
import torch
from PIL import Image,ImageDraw
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from train.segmentation_auxiliary import SegmentationPoseNet,visible_case_target,balanced_mask_loss
from vision.pose_model import KeyboardPoseNet
from evidence_artifacts import verify_frozen_artifacts


def test_area_labels_foreground_and_empty_region():
    label=dict(image_size=[256,192],landmarks=[dict(x_px=x,y_px=y) for x,y in [(0,0),(7,0),(7,7),(0,7)]])
    mask=Image.new('L',(256,192));target=visible_case_target(label,mask)
    assert target.shape==(1,24,32) and target.sum()==1 and target[0,0,0]==1
    ImageDraw.Draw(mask).rectangle((0,0,3,7),fill=255)
    target=visible_case_target(label,mask);assert target.sum()==.5 and target[0,0,0]==.5
    assert visible_case_target(label,Image.new('L',(256,192),255)).sum()==0
    for value in [0.,1.,.5]:
        logits=torch.zeros(1,1,24,32,requires_grad=True);loss=balanced_mask_loss(logits,torch.full_like(logits,value))
        assert torch.isfinite(loss);loss.backward();assert torch.isfinite(logits.grad).all()


def test_initial_pose_equivalence_and_discardable_head():
    torch.manual_seed(12);base=KeyboardPoseNet().eval();model=SegmentationPoseNet().eval();model.load_pose_weights(base.state_dict());x=torch.rand(2,3,96,128)
    with torch.no_grad():out=model(x);reference=base(x)
    assert torch.equal(out['pose'],reference) and out['mask_logits'].shape==(2,1,24,32)
    restored=KeyboardPoseNet().eval();restored.load_state_dict(model.backbone.state_dict())
    with torch.no_grad():assert torch.equal(restored(x),reference)


def test_probe_lineage_and_zero_updates():
    p=AI/'eval/segmentation_feasibility_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/segmentation_feasibility_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest();verify_frozen_artifacts(ROOT,plan['file_sha256'])
    assert len(r['rows'])==4 and sum(v['images'] for v in r['rows'])==128
    assert all(v['pose_max_delta']==0 for v in r['rows'])
    for v in r['rows']:assert abs(v['weighted_gradient_ratio']-plan['probe_coefficient']*v['mask_gradient_norm']/v['pose_gradient_norm'])<1e-7
    assert r['extra_parameters']==33 and r['optimizer_updates']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
