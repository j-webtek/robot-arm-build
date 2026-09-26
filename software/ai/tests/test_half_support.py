import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_half_support_evidence():
    p=AI/'eval/half_support_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/half_support_v0_report.json').read_text());old=json.loads((AI/'eval/visible_candidate_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==800
    for a,b in zip(r['rows'],old['rows']):
        assert (a['seed'],a['condition'],a['accepted'])==(b['seed'],b['condition'],b['accepted'])
        for key,value in b['arms'].items():assert a['arms'][key]==value
    for c,summary in r['summaries'].items():
        rows=[v for v in r['rows'] if v['condition']==c and v['accepted']]
        assert summary['accepted']==len(rows)
        for arm in ('subpixel','equal_support','equal'):
            assert summary[arm]['mean_mm']==float(np.mean([v['arms'][arm]['mean_mm'] for v in rows]))
            assert summary[arm]['tail']==sum(v['arms'][arm]['maximum_mm']>3 for v in rows)
        for reference in ('subpixel','equal_support'):
            a,b=summary[reference],summary['equal']
            assert r['checks'][c][reference]==dict(coverage=summary['coverage']>=.9,mean=b['mean_mm']<=a['mean_mm']+1e-12,tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
    assert r['passed']==all(all(v.values()) for c in r['checks'].values() for v in c.values())
    assert r['hardware_writes']==r['physical_movements']==0
