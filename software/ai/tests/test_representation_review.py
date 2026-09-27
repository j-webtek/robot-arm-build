import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]


def test_retained_resolution_review_lineage():
    p=AI/'eval/representation_review_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/representation_review_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    old=json.loads((AI/'eval/matched_resolution_v0_scorecard.json').read_text())['results']
    assert r['larger_to_smaller_mean_ratio']==old[1]['mean_mm']/old[0]['mean_mm']
    for item,source in zip(r['resolution'],old):
        for k,v in item.items():assert source[k]==v
    assert r['clutter_tails']==dict(original=32,no_arm=17,no_ruler=25,neither=11)
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
