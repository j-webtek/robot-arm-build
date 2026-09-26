import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]


def test_frozen_diagnostic_recount():
    path=AI/'eval/landmark_diagnostic_v0.manifest.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/landmark_diagnostic_v0_report.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==3200
    assert len({(c['seed'],c['condition'],c['corner']) for c in r['rows']})==3200
    for group,s in r['summaries'].items():
        rows=[c for c in r['rows'] if c['visibility_class']==group]
        assert s['corners']==len(rows)
        assert s['predicted_visible']==sum(c['predicted_visibility']>=.5 for c in rows)
        for metric,field in [('soft_mean_px','soft_error_px'),('peak_mean_px','peak_error_px'),('mass_within_8px_mean','mass_within_8px')]:
            assert abs(s[metric]-np.mean([c[field] for c in rows]))<1e-10
        assert all(0<=c['mass_within_8px']<=1.000001 and 0<=c['predicted_visibility']<=1 for c in rows)
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
