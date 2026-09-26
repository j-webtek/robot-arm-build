import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_ablation_provenance_and_decisions():
    path=AI/'train/landmark_ablation_v0_plan.json';plan=json.loads(path.read_text())
    for f,h in plan['file_sha256'].items():
        assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    control=json.loads((AI/'eval/landmark_corrected_v0_control_scorecard.json').read_text())
    comparison=json.loads((AI/'eval/landmark_ablation_v0_comparison.json').read_text())
    for mode in ('coordinate_only','visibility_only'):
        p=AI/f'eval/landmark_ablation_v0_{mode}_scorecard.json';r=json.loads(p.read_text())
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
