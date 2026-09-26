import hashlib,json,math
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]


def test_calibration_selection_and_diagnostic_metrics():
    path=AI/'eval/stable_errors_v0.manifest.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/stable_errors_v0_report.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    cases=json.loads((ROOT/m['source']).read_text())['fitting_cases']
    low=[c for c in cases if c['bin']==0];bad=[c for c in low if c['maximum_error_mm']>3]
    assert len(low)==r['low_disagreement_images']
    assert len(bad)==r['above_3mm_images']==len(r['details'])
    assert len({c['seed'] for c in bad})==r['above_3mm_seed_groups']
    for c,d in zip(bad,r['details']):
        assert (c['seed'],c['condition'])==(d['seed'],d['condition'])
        assert 24000000<=d['seed']<24001000
        assert abs(math.dist(c['predicted_pose'][:2],c['truth_pose'][:2])-d['center_error_mm'])<1e-12
        assert abs(abs(math.degrees(c['predicted_pose'][2]-c['truth_pose'][2]))-d['yaw_error_degrees'])<1e-12
    assert len(r['selected_images'])==len({c['seed'] for c in r['selected_images']})==12
    assert sum(v['above_3mm'] for v in r['summaries'].values())==len(bad)
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
