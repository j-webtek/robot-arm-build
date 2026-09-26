import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_alignment_report():
    p=AI/'eval/label_alignment_v0_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/label_alignment_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert r['images']==800 and len(r['rows'])==3200
    assert r['max_draw_label_delta_px']==0
    assert r['max_independent_formula_delta_px']<1e-10
    for condition,groups in r['summaries'].items():
        for i,s in groups.items():
            e=np.array([v['local_error_mm'] for v in r['rows'] if v['condition']==condition and v['corner']==int(i)])
            assert e.shape==(200,2)
            assert s['mean_local_xy_mm']==e.mean(0).tolist()
            assert s['median_local_xy_mm']==np.median(e,axis=0).tolist()
    assert r['hardware_writes']==r['physical_movements']==0
