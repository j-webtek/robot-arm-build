import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_temperature_bias_recount():
    p=AI/'eval/temperature_bias_v0.manifest.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/temperature_bias_v0_report.json').read_text())
    assert r['manifest_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==3200
    for group in ('clear','hidden'):
        for visible in (False,True):
            rows=[v for v in r['rows'] if v['visibility_class']==group and (v['predicted_visibility']>=.5)==visible]
            actual=r['decision_groups'][group+'_'+str(visible)]
            assert actual['corners']==len(rows)
            for key,field in [('mass_mean','mass_within_8px'),('entropy_mean','entropy'),('peak_error_mean','peak_error_px')]:assert actual[key]==float(np.mean([v[field] for v in rows]))
    parity=json.loads((AI/'eval/temperature_visibility_t05_parity_report.json').read_text())
    for mode,rows in r['threshold_margins'].items():
        assert [[v['image'],v['corner']] for v in rows]==parity['comparisons']['cpu_1_vs_'+mode]['changed_indices']
        for v in rows:
            i,j=v['image'],v['corner']
            assert v['cpu_distance']==abs(parity['runs']['cpu_1']['probabilities'][i][j]-.5)
            assert v['gpu_distance']==abs(parity['runs'][mode]['probabilities'][i][j]-.5)
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']

    for group,metrics in r['coordinate_summary'].items():
        rows=[v for v in r['rows'] if v['visibility_class']==group]
        for field,values in metrics.items():
            assert values['mean']==float(np.mean([v[field] for v in rows]))
            assert values['p95']==float(np.percentile([v[field] for v in rows],95))
        for v in rows:
            assert abs(np.linalg.norm(v['soft_bias_px'])-v['soft_error_px'])<1e-4
            assert abs(np.linalg.norm(v['sharp_bias_px'])-v['sharp_error_px'])<1e-4
