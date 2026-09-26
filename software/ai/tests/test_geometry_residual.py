import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))

def test_residual_report():
    p=AI/'eval/geometry_residual_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/geometry_residual_v0_report.json').read_text());old=json.loads((AI/'eval/geometry_candidate_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==800
    for a,b in zip(r['rows'],old['rows']):
        assert (a['seed'],a['condition'])==(b['seed'],b['condition'])
        assert a['arms']['actual']['mean_mm']==b['arms']['geometry']['mean_mm']
        assert abs(a['arms']['translation_only']['mean_mm']-a['translation_mm'])<1e-10
    for condition,summary in r['summaries'].items():
        rows=[v for v in r['rows'] if v['condition']==condition]
        for arm in ('actual','translation_only','rotation_only','oracle_nearest_grid'):
            assert summary[arm]==dict(mean_mm=float(np.mean([v['arms'][arm]['mean_mm'] for v in rows])),tail=sum(v['arms'][arm]['maximum_mm']>3 for v in rows))
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
