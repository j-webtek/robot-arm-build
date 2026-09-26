import hashlib
import json
import sys
from pathlib import Path
AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))
from vision.diagnose_pose_visibility import summarize


def test_threshold_edges_and_confusion():
    rows = [dict(condition='fixture', supported_corners=n, arms={'pose': {'maximum_mm': error}})
            for n, error in [(3, 3), (3, 3.001), (2, 3), (2, 4)]]
    r = summarize(rows)['fixture']
    assert [r[k] for k in ('accepted_good', 'accepted_bad', 'rejected_good', 'rejected_bad')] == [1, 1, 1, 1]
    assert r['coverage'] == r['failure_detection_rate'] == .5
    assert summarize(rows, minimum_support=4)['fixture']['accepted_bad_rate'] is None


def test_retained_evidence_recount():
    path = AI / 'eval/pose_visibility_v0_plan.json'
    plan = json.loads(path.read_text())
    report = json.loads((AI / 'eval/pose_visibility_v0_report.json').read_text())
    assert report['plan_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    for f, digest in plan['file_sha256'].items():
        assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == digest
    rows = json.loads((ROOT / plan['input']).read_text())['rows']
    assert report['summaries'] == summarize(rows, plan['minimum_support'], plan['tolerance_mm'])
    sums = report['summaries'].values()
    assert sum(r['accepted_bad'] for r in sums) == 28
    assert sum(r['rejected_bad'] for r in sums) == 4
    assert sum(r['rejected_good'] for r in sums) == 10
    assert report['hardware_writes'] == report['physical_movements'] == 0
    assert report['qualification_installed'] is False
