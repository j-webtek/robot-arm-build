import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_persistent_pose import analyze


def test_known_persistence_and_baseline_counted_once():
    def row(error):return dict(seed=1,condition='standard',maximum_mm=error,translation_mm=2.,rotation_only_maximum_mm=1.)
    reports=[dict(results={a:dict(rows=[row(4)]) for a in ['baseline','control','occlusion']}) for _ in range(3)]
    rows,s=analyze(reports)
    assert rows[0]['trained_failure_count']==6
    assert s['standard']['persistent_shared_with_baseline']==1
    reports[2]['results']['occlusion']['rows'][0]['maximum_mm']=3
    rows,s=analyze(reports)
    assert rows[0]['trained_failure_count']==5 and not s['standard']['persistent_seeds']


def test_frozen_report_recount():
    p=AI/'eval/persistent_pose_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/persistent_pose_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    rows,s=analyze([json.loads((ROOT/f).read_text()) for f in plan['inputs']])
    assert r['rows']==rows and r['summaries']==s and len(rows)==800
    assert sum(v['trained_failure_count']==6 for v in rows)==19
    assert sum(v['trained_failure_count'] for v in rows)==134
    assert all(v['baseline_bad'] for v in rows if v['trained_failure_count']==6)
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
