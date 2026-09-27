import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]


def test_visual_lineage_and_pair_selection():
    p=AI/'eval/persistent_visual_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/persistent_visual_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/persistent_pose_v0_report.json').read_text());counts={(v['seed'],v['condition']):v['trained_failure_count'] for v in source['rows']}
    assert len(r['pairs'])==19
    for pair in r['pairs']:
        a,b=pair['failure'],pair['success']
        assert a['condition']==b['condition']
        assert counts[(a['seed'],a['condition'])]==6 and counts[(b['seed'],b['condition'])]==0
        for info in [a,b]:assert info['label_projection_max_delta_px']==0 and info['corner_min_margin_px']>=0
    for fig in r['figures']:assert hashlib.sha256((ROOT/fig['path']).read_bytes()).hexdigest()==fig['sha256']
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
