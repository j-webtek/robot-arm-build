"""Development-only visibility/pose error association; no runtime authority."""
import hashlib
import json
from pathlib import Path
AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]


def summarize(rows, minimum_support=3, tolerance_mm=3):
    result = {}
    for condition in sorted({r['condition'] for r in rows}):
        cases = [r for r in rows if r['condition'] == condition]
        counts = dict(accepted_good=0, accepted_bad=0, rejected_good=0, rejected_bad=0)
        for row in cases:
            accepted = row['supported_corners'] >= minimum_support
            bad = row['arms']['pose']['maximum_mm'] > tolerance_mm
            counts[('accepted' if accepted else 'rejected') + ('_bad' if bad else '_good')] += 1
        accepted = counts['accepted_good'] + counts['accepted_bad']
        bad = counts['accepted_bad'] + counts['rejected_bad']
        result[condition] = dict(counts, cases=len(cases), coverage=accepted / len(cases),
            baseline_bad_rate=bad / len(cases),
            accepted_bad_rate=counts['accepted_bad'] / accepted if accepted else None,
            failure_detection_rate=counts['rejected_bad'] / bad if bad else None)
    return result


def run():
    plan_path = AI / 'eval/pose_visibility_v0_plan.json'
    plan = json.loads(plan_path.read_text())
    for path, digest in plan['file_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    source = json.loads((ROOT / plan['input']).read_text())
    rows = source['rows']
    assert len(rows) == 800 and len({(r['seed'], r['condition']) for r in rows}) == 800
    report = dict(plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        summaries=summarize(rows, plan['minimum_support'], plan['tolerance_mm']),
        hardware_writes=0, physical_movements=0, qualification_installed=False,
        limitations=['Reused synthetic development; no new model inference or fresh holdout',
            'Visibility is not localization uncertainty; no threshold tuning or runtime gate',
            'Three millimetres is a diagnostic error threshold, not target-specific admission'])
    output = AI / 'eval/pose_visibility_v0_report.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run()
