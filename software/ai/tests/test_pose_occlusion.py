import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from train.train_pose_occlusion import conditions


def test_equal_budget_and_intervention():
    assert conditions('control')==['standard','appearance_shift','standard','standard']
    assert conditions('occlusion')==['standard','appearance_shift','partial','full']
    assert len(conditions('control'))==len(conditions('occlusion'))


def test_report_metrics_selection_and_frozen_checks():
    p=AI/'train/pose_occlusion_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/pose_occlusion_v0_report.json').read_text())
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
            ck=AI/'results'/('pose_occlusion_v0_'+arm)/'pose_model.pt'
            assert hashlib.sha256(ck.read_bytes()).hexdigest()==result['checkpoint_sha256']
    for ref,checks in r['checks'].items():
        for c in plan['conditions']:
            a=r['results'][ref]['summaries'][c];b=r['results']['occlusion']['summaries'][c]
            assert checks[c]==dict(mean=b['mean_mm']<=a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
    assert r['passed'] is False
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
