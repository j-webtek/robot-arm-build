import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_support_attribution():
    p=AI/'eval/support_attribution_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/support_attribution_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==800
    for row in r['rows']:
        clear=sum(row['geometric_visibility'][i]==1 for i in row['excluded']);occ=len(row['excluded'])-clear
        assert (clear,occ)==(row['clear_exclusions'],row['occluded_exclusions'])
        assert row['group']==('none' if not row['excluded'] else 'mixed' if clear and occ else 'clear_only' if clear else 'occluded_only')
    for group,s in r['summary'].items():
        rows=[v for v in r['rows'] if v['group']==group];a=[v for v in rows if v['accepted']]
        assert (s['cases'],s['accepted'],s['abstained'])==(len(rows),len(a),len(rows)-len(a))
        for key in ('clear_exclusions','occluded_exclusions'):assert s[key]==sum(v[key] for v in rows)
        for key,field in [('new_tails','new_tail'),('recovered_tails','recovered_tail')]:assert s[key]==sum(v[field] for v in a)
        for key in ('mean_delta_mm','translation_delta_mm','yaw_delta_degrees'):assert s[key]==(float(np.mean([v[key] for v in a])) if a else None)
    assert r['hardware_writes']==r['physical_movements']==0
