import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]

def test_local_diagnostic_provenance_and_strata():
    p=AI/'eval/local_visibility_diagnostic_v0.manifest.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/local_visibility_diagnostic_v0_report.json').read_text())
    assert r['manifest_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['rows'])==3200
    for group in ('clear','partial','hidden'):
        for key,lo,hi in [('0_4',0,4),('4_8',4,8),('8_inf',8,float('inf'))]:
            rows=[v for v in r['rows'] if v['visibility_class']==group and lo<=v['peak_error_px']<hi]
            assert r['strata'][group][key]==dict(corners=len(rows),predicted_visible=sum(v['predicted_visibility']>=.5 for v in rows))
        assert sum(v['corners'] for v in r['strata'][group].values())==r['summaries'][group]['corners']
    for mode in ('global','local'):
        a=r['paired'][mode];assert len(a['rows'])==a['pairs']
        assert sum(v['threshold_crossed'] for v in a['rows'])==a['threshold_crossings']
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
