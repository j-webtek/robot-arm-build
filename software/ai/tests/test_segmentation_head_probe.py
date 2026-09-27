import hashlib,json,sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.train_segmentation_head_probe import metrics


def test_mask_overlap_known_case():
    logits=torch.tensor([[[[10.,-10.],[10.,-10.]]]])
    target=torch.tensor([[[[1.,0.],[0.,0.]]]])
    assert metrics(logits,target)['mean_iou']==.5
    assert metrics(logits,torch.tensor([[[[1.,0.],[1.,0.]]]]))['mean_iou']==1.


def test_frozen_pose_and_head_probe_evidence():
    p=AI/'train/segmentation_head_probe_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/segmentation_head_probe_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest();verify_frozen_artifacts(ROOT,plan['file_sha256'])
    assert [v['seed'] for v in r['runs']]==plan['seeds']
    assert r['head_updates_per_seed']==304 and r['pose_updates']==0
    for run in r['runs']:
        assert len(run['history'])==8 and run['final']['mean_iou']==run['history'][-1]['mean_iou']
        assert run['backbone_before_sha256']==run['backbone_after_sha256'] and run['pose_max_delta']==0
        assert run['passed']==(all(m['mean_iou']>=plan['minimum_iou'] for m in run['conditions'].values()) and run['final']['balanced_bce']<run['initial']['balanced_bce'])
        verify_frozen_artifacts(ROOT,{f"software/ai/results/segmentation_head_probe_{run['seed']}/head.pt":run['head_sha256']})
    earlier=json.loads((AI/'eval/pose_segmentation_260926_report.json').read_text())
    assert r['development_pixels_sha256']==earlier['development_pixels_sha256']
    assert r['training_targets_sha256']==earlier['results']['control']['training_mask_sha256']
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
