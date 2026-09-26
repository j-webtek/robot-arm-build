import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_refined_bias_recount():
    p=AI/'eval/refined_bias_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/refined_bias_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==800
    for row in r['rows']:
        energy=sum(v*v for v in row['corner_error_mm']);common=sum(v*v for v in row['common_bias_mm'])
        assert np.isclose(energy,4*common+4*row['centered_rms_mm']**2)
        assert np.isclose(row['common_energy_fraction'],4*common/energy)
    for c,s in r['summaries'].items():
        rows=[v for v in r['rows'] if v['condition']==c];bad=[v for v in rows if v['maximum_key_error_mm']>3]
        assert s['bad']==len(bad)
        assert s['bad_common_majority']==sum(v['common_energy_fraction']>=.5 for v in bad)
        assert s['bad_single_corner_majority']==sum(v['largest_corner_energy_fraction']>=.5 for v in bad)
        assert s['low_residual_bad']==sum(v['fit_rms_mm']<=3 for v in bad)
        assert s['low_residual_total']==sum(v['fit_rms_mm']<=3 for v in rows)
    assert r['hardware_writes']==r['physical_movements']==0
