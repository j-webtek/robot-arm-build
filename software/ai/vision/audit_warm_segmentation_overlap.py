"""Audit retained pose predictions; no new inference or model selection."""
import hashlib
import json
import math
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]


def index(rows):
    result = {}
    for row in rows:
        key = (row['seed'], row['condition'])
        if key in result:
            raise ValueError('duplicate scene key')
        if not math.isfinite(row['maximum_mm']) or row['maximum_mm'] < 0:
            raise ValueError('invalid error')
        result[key] = row
    return result


def analyze(reports, prior_rows):
    indexed = [{a: index(r['results'][a]['rows']) for a in ('baseline', 'control', 'occlusion')} for r in reports]
    if not indexed:
        raise ValueError('no reports')
    keys = set(indexed[0]['baseline'])
    prior = index(prior_rows)
    if set(prior) != keys or any(set(rows) != keys for run in indexed for rows in run.values()):
        raise ValueError('scene populations differ')
    if any(run['baseline'] != indexed[0]['baseline'] for run in indexed):
        raise ValueError('baseline predictions differ')
    rows = []
    for key in sorted(keys):
        pairs = []
        for run in indexed:
            a, b = run['control'][key], run['occlusion'][key]
            pairs.append(dict(control_maximum_mm=a['maximum_mm'], candidate_maximum_mm=b['maximum_mm'],
                recovered=a['maximum_mm'] > 3 and b['maximum_mm'] <= 3,
                introduced=a['maximum_mm'] <= 3 and b['maximum_mm'] > 3,
                delta_maximum_mm=b['maximum_mm'] - a['maximum_mm']))
        rows.append(dict(seed=key[0], condition=key[1], prior_persistent=prior[key]['trained_failure_count'] == 6,
            baseline_bad=indexed[0]['baseline'][key]['maximum_mm'] > 3, pairs=pairs,
            control_failure_count=sum(p['control_maximum_mm'] > 3 for p in pairs),
            candidate_failure_count=sum(p['candidate_maximum_mm'] > 3 for p in pairs)))
    n = len(reports)
    summaries = {}
    for condition in ['all'] + sorted({k[1] for k in keys}):
        group = [r for r in rows if condition == 'all' or r['condition'] == condition]
        old = [r for r in group if r['prior_persistent']]
        summaries[condition] = dict(cases=len(group),
            recovered_by_seed=[sum(r['pairs'][i]['recovered'] for r in group) for i in range(n)],
            introduced_by_seed=[sum(r['pairs'][i]['introduced'] for r in group) for i in range(n)],
            control_tails=[sum(r['pairs'][i]['control_maximum_mm'] > 3 for r in group) for i in range(n)],
            candidate_tails=[sum(r['pairs'][i]['candidate_maximum_mm'] > 3 for r in group) for i in range(n)],
            prior_persistent=len(old), prior_still_bad_all_candidates=sum(r['candidate_failure_count'] == n for r in old),
            prior_recovered_all_candidates=sum(r['candidate_failure_count'] == 0 for r in old),
            persistent_all_pairs=sum(r['control_failure_count'] == n and r['candidate_failure_count'] == n for r in group),
            consistently_recovered=sum(all(p['recovered'] for p in r['pairs']) for r in group),
            consistently_introduced=sum(all(p['introduced'] for p in r['pairs']) for r in group))
    return rows, summaries


def run():
    path = AI / 'eval/warm_segmentation_overlap_v0_plan.json'
    plan = json.loads(path.read_text())
    for name, digest in plan['file_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('frozen artifact mismatch: ' + name)
    reports = [json.loads((ROOT / f).read_text()) for f in plan['reports']]
    old = json.loads((ROOT / plan['prior']).read_text())
    # Prior audit does not store maximum error; index only needs it for structural checks.
    prior = [dict(r, maximum_mm=0.) for r in old['rows']]
    rows, summaries = analyze(reports, prior)
    result = dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), seeds=plan['seeds'],
        rows=rows, summaries=summaries, new_forward_passes=0, optimizer_updates=0,
        hardware_writes=0, physical_movements=0, qualification_installed=False,
        limitations=['Retained predictions on reused synthetic development, not fresh inference or holdout',
        'Threshold >3mm is a descriptive research failure criterion, not an execution tolerance',
        'Paired training contains GPU nondeterminism; overlap does not establish causal representation defects',
        'No calibration, confidence qualification, exclusions, or target corrections derived'])
    output = AI / 'eval/warm_segmentation_overlap_v0_report.json'
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    run()
