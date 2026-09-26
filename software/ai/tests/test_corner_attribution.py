import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_corner_attribution_recount():
    p=AI/'eval/corner_attribution_v0.manifest.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/corner_attribution_v0_report.json').read_text())
    assert r['manifest_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==3200
    for group,actual in r['summaries'].items():
        rows=[v for v in r['rows'] if v['visibility_class']==group];large=[v for v in rows if v['peak_error_px']>8]
        assert actual==dict(corners=len(rows),large_peak_errors=len(large),near_other_corner=sum(v['nearest_corner']!=v['corner'] and v['nearest_distance_px']<=8 for v in large),strong_rival=sum(v['rival_ratio']>=.5 for v in large),rival_near_correct=sum(v['rival_own_error_px']<=8 for v in large),strong_rival_near_correct=sum(v['rival_ratio']>=.5 and v['rival_own_error_px']<=8 for v in large))
    assert all(0<=v['rival_ratio']<=1 for v in r['rows'])
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
