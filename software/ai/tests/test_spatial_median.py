import hashlib,json,math,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.evaluate_spatial_median import median_pose


def test_circular_mean_crosses_pi_correctly():
    p=median_pose([(1,2,math.pi-.1),(3,4,-math.pi+.1)])
    assert p[:2]==(2,3) and abs(abs(p[2])-math.pi)<1e-12


def test_frozen_evidence_and_recount():
    path=AI/'eval/spatial_median_v0.manifest.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/spatial_median_v0_scorecard.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['cases'])==1400
    for condition in m['conditions']:
        rows=[c for c in r['cases'] if c['condition']==condition]
        assert [c['seed'] for c in rows]==list(range(15000000,15000200))
        for arm in ('control','median'):
            v=r['summaries'][condition][arm]
            assert abs(np.mean([c['arms'][arm]['mean_mm'] for c in rows])-v['mean_mm'])<1e-12
            assert sum(c['arms'][arm]['maximum_mm']>3 for c in rows)==v['above_3mm_images']
            assert all(0<=c['arms'][arm]['yaw_degrees']<=180 for c in rows)
        a,b=r['summaries'][condition]['control'],r['summaries'][condition]['median']
        assert r['checks'][condition]==dict(mean_error=b['mean_mm']/a['mean_mm']<=1.05,tail=b['above_3mm_images']<=a['above_3mm_images'],yaw=b['yaw_p95_degrees']/a['yaw_p95_degrees']<=1.1)
    assert r['evaluation_rule_passed']==all(all(c.values()) for c in r['checks'].values())
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']


def test_median_resists_single_outlier():
    p=median_pose([(1,2,math.pi-.01),(2,3,math.pi),(3,4,-math.pi+.01),(4,5,-math.pi+.02),(1000,2000,0)])
    assert p[:2]==(3,4)
    assert abs(abs(p[2])-math.pi)<.021
