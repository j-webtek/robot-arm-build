import sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];sys.path.insert(0,str(AI))
from vision.local_visibility_model import LocalVisibilityNet

class ConstantFeatures(torch.nn.Module):
    def forward(self,x):return torch.ones(len(x),64,48,64)

def test_identical_initialization_and_constant_field_agreement():
    torch.manual_seed(17);a=LocalVisibilityNet('global')
    torch.manual_seed(17);b=LocalVisibilityNet('local')
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
    a.features=ConstantFeatures();b.features=ConstantFeatures()
    x=torch.zeros(2,3,192,256)
    assert torch.allclose(a(x)['visibility_logits'],b(x)['visibility_logits'],atol=1e-6)

def test_local_head_receives_feature_gradients():
    torch.manual_seed(17);m=LocalVisibilityNet('local');x=torch.rand(1,3,192,256)
    out=m(x);assert out['visibility_logits'].shape==(1,4)
    out['visibility_logits'].sum().backward()
    assert m.visibility[2].weight.grad.abs().sum()>0
    assert m.features[0].weight.grad.abs().sum()>0
    assert m.heatmaps.weight.grad is None # hard predicted location has no gradient

import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_local_visibility_provenance_and_decisions():
    path=AI/'train/landmark_local_visibility_v0_plan.json';plan=json.loads(path.read_text())
    for f,h in plan['file_sha256'].items():
        assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    control=json.loads((AI/'eval/landmark_local_visibility_v0_global_scorecard.json').read_text())
    comparison=json.loads((AI/'eval/landmark_local_visibility_v0_comparison.json').read_text())
    for mode in ('global','local'):
        p=AI/f'eval/landmark_local_visibility_v0_{mode}_scorecard.json';r=json.loads(p.read_text())
        assert hashlib.sha256(p.read_bytes()).hexdigest()==comparison['report_hashes'][mode]
        assert r['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
        assert r['loss_mode']==mode
        for key in ('training_pixels_sha256','development_pixels_sha256','training_images','development_images'):
            assert r[key]==control[key]
        assert len(r['history'])==8
        assert r['selected_epoch']==min(r['history'],key=lambda e:e['development_loss'])['epoch']
        values=[(t,p) for c in r['cases'] for t,p in zip(c['visibility_targets'],c['visibility_probabilities'])]
        assert sum(t==0 and p>=.5 for t,p in values)==r['false_visible_occluded']
        assert sum(t==1 and p>=.5 for t,p in values)==r['true_visible_clear']
        assert sum(t==1 for t,p in values)==r['clear_corners']
        checks=comparison['checks'][mode]
        for c,check in checks['conditions'].items():
            a,b=control['summaries'][c]['landmark'],r['summaries'][c]['landmark']
            assert check==dict(mean=b['mean_mm']<a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=a['yaw_p95']*1.1)
        assert checks['visibility_pass']==(r['false_visible_occluded']<control['false_visible_occluded'] and r['true_visible_clear']/r['clear_corners']>=.9)
        assert checks['passed']==(all(all(v.values()) for v in checks['conditions'].values()) and checks['visibility_pass'])
        assert r['hardware_writes']==r['physical_movements']==0
        assert not r['qualification_installed']
