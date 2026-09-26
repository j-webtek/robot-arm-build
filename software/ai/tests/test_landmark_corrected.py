import hashlib,json,sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from train.train_landmarks_corrected import balanced_visibility_loss


def test_balanced_visibility_rare_hidden_gradient():
    logits=torch.zeros(10,requires_grad=True);labels=torch.tensor([1.]*9+[0.])
    loss=balanced_visibility_loss(logits,labels);loss.backward()
    assert abs(logits.grad[:9].sum().item()+logits.grad[9].item())<1e-6
    assert logits.grad[9]>0 and logits.grad[0]<0
    assert torch.isfinite(balanced_visibility_loss(torch.zeros(4),torch.ones(4)))


def test_paired_provenance_selection_and_counts():
    path=AI/'train/landmark_corrected_v0_plan.json';m=json.loads(path.read_text())
    reports=[json.loads((AI/f'eval/landmark_corrected_v0_{name}_scorecard.json').read_text()) for name in ('control','corrected')]
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    a,b=reports
    assert a['training_pixels_sha256']==b['training_pixels_sha256']
    assert a['development_pixels_sha256']==b['development_pixels_sha256']
    for r in reports:
        assert r['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
        assert r['selected_epoch']==min(r['history'],key=lambda e:e['development_loss'])['epoch']
        values=[(t,p) for c in r['cases'] for t,p in zip(c['visibility_targets'],c['visibility_probabilities'])]
        assert sum(t==0 and p>=.5 for t,p in values)==r['false_visible_occluded']
        assert sum(t==1 and p>=.5 for t,p in values)==r['true_visible_clear']
    comparison=json.loads((AI/'eval/landmark_corrected_v0_comparison.json').read_text())
    for name,key in [('control','control_report_sha256'),('corrected','candidate_report_sha256')]:
        assert hashlib.sha256((AI/f'eval/landmark_corrected_v0_{name}_scorecard.json').read_bytes()).hexdigest()==comparison[key]
    for c,check in comparison['checks'].items():
        x,y=a['summaries'][c]['landmark'],b['summaries'][c]['landmark']
        assert check==dict(mean=y['mean_mm']<x['mean_mm'],tail=y['tail']<=x['tail'],yaw=y['yaw_p95']<=1.1*x['yaw_p95'])
    assert comparison['visibility_pass']==(b['false_visible_occluded']<a['false_visible_occluded'] and b['true_visible_clear']/b['clear_corners']>=.9)
    assert comparison['corrective_rule_passed']==(all(all(c.values()) for c in comparison['checks'].values()) and comparison['visibility_pass'])
