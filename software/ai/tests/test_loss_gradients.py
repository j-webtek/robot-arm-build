import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))

def test_gradient_report():
    p=AI/'eval/gradient_diagnostic_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/gradient_diagnostic_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==12
    for row in r['rows']:
        n=row['gradient_norms'];assert np.isclose(row['geometry_base_norm_ratio'],n['geometry']/n['base'])
        assert all(np.isfinite(v) and v>=0 for v in row['losses'].values())
        assert all(v is None or -1.00001<=v<=1.00001 for v in row['cosines'].values())
    for start in m['batch_starts']:assert len({v['pixels_sha256'] for v in r['rows'] if v['batch_start']==start})==1
    for state,s in r['summary'].items():assert s['ratio_mean']==float(np.mean([v['geometry_base_norm_ratio'] for v in r['rows'] if v['state']==state]))
    assert r['hardware_writes']==r['physical_movements']==0
