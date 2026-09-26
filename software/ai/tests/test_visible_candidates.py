import hashlib,json,sys,math
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.visible_candidate_decoder import weighted_fit
from vision.geometry_candidate_decoder import LOCAL

def test_weighted_fit_and_abstention():
    a=2.8;c,s=math.cos(a),math.sin(a);p=LOCAL@np.array([[c,s],[-s,c]])+[231,167];p[3]+=100
    assert np.allclose(weighted_fit(p,[1,.8,.7,0]),[231,167,a],atol=1e-9)
    assert weighted_fit(p,[1,1,0,0]) is None

def test_visibility_report():
    p=AI/'eval/visible_candidate_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/visible_candidate_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==800
    for row in r['rows']:assert row['accepted']==(sum(v>=.5 for v in row['visibility'])>=3)
    for condition,summary in r['summaries'].items():
        allrows=[v for v in r['rows'] if v['condition']==condition];rows=[v for v in allrows if v['accepted']]
        assert summary['accepted']==len(rows)
        assert summary['coverage']==len(rows)/len(allrows)
        for arm in ('subpixel','visible'):
            assert summary[arm]['mean_mm']==float(np.mean([v['arms'][arm]['mean_mm'] for v in rows]))
            assert summary[arm]['tail']==sum(v['arms'][arm]['maximum_mm']>3 for v in rows)
        a,b=summary['subpixel'],summary['visible']
        assert r['checks'][condition]==dict(coverage=len(rows)>=len(allrows)*.9,mean=b['mean_mm']<a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=a['yaw_p95']*1.1)
    assert r['passed']==all(all(v.values()) for v in r['checks'].values())
    assert r['hardware_writes']==r['physical_movements']==0
