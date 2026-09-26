import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from train.train_pose_balanced import conditions


def test_equal_budget_and_intervention():
    from collections import Counter
    counts=Counter();corners=Counter()
    for seed in range(14000000,14000600):
        assert conditions('control',seed)==['standard','appearance_shift','standard','standard']
        candidate=conditions('occlusion',seed)
        assert len(candidate)==4
        counts.update(candidate)
        corners[(candidate[-1],seed%4)]+=1
    assert counts==dict(standard=1200,appearance_shift=600,partial=300,full=300)
    assert all(corners[(c,k)]==75 for c in ['partial','full'] for k in range(4))


def test_report_metrics_selection_and_frozen_checks():
    p=AI/'train/pose_balanced_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/pose_balanced_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    for arm,result in r['results'].items():
        assert len(result['rows'])==800
        for c,m in result['summaries'].items():
            rows=[v for v in result['rows'] if v['condition']==c]
            assert m['mean_mm']==float(np.mean([v['mean_mm'] for v in rows]))
            assert m['tail']==sum(v['maximum_mm']>3 for v in rows)
            assert m['yaw_p95']==float(np.percentile([v['yaw_degrees'] for v in rows],95))
        if arm!='baseline':
            assert result['training_images']==2400
            assert result['selected_epoch']==min(result['history'],key=lambda h:h['development_mse'])['epoch']
            ck=AI/'results'/('pose_balanced_v0_'+arm)/'pose_model.pt'
            assert hashlib.sha256(ck.read_bytes()).hexdigest()==result['checkpoint_sha256']
    for ref,checks in r['checks'].items():
        for c in plan['conditions']:
            a=r['results'][ref]['summaries'][c];b=r['results']['occlusion']['summaries'][c]
            assert checks[c]==dict(mean=b['mean_mm']<=a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
    assert r['development_pixels_sha256']==json.loads((AI/'eval/pose_occlusion_v0_report.json').read_text())['development_pixels_sha256']
    assert r['passed'] is False
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
