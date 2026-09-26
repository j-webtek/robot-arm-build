import hashlib,json,sys,math
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.geometry_candidate_decoder import LOCAL,fit_pose

def test_rigid_fit_translation_rotation():
    a=2.7;c,s=math.cos(a),math.sin(a);points=LOCAL@np.array([[c,s],[-s,c]])+[231,167]
    pose,residual=fit_pose(points)
    assert np.allclose(pose,[231,167,a],atol=1e-9)
    assert residual<1e-20

def test_geometry_report_recount():
    p=AI/'eval/geometry_candidate_fresh_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/geometry_candidate_fresh_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==2000
    assert {v['seed'] for v in r['rows']}==set(range(27000000,27000500))
    assert {v['condition'] for v in r['rows']}==set(m['conditions'])
    assert len({(v['seed'],v['condition']) for v in r['rows']})==2000
    for condition,summary in r['summaries'].items():
        rows=[v for v in r['rows'] if v['condition']==condition]
        for arm,metrics in summary.items():
            assert metrics['mean_mm']==float(np.mean([v['arms'][arm]['mean_mm'] for v in rows]))
            assert metrics['tail']==sum(v['arms'][arm]['maximum_mm']>3 for v in rows)
        a,b=summary['soft'],summary['geometry']
        assert r['checks'][condition]==dict(mean=b['mean_mm']<a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=a['yaw_p95']*1.1)
    assert r['passed']==all(all(c.values()) for c in r['checks'].values())
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
