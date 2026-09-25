"""Offline zero-position investigation; no device access or model changes.

Explicit cohorts avoid guessing preceding commands from file timestamps.
Only the journal-linked third trial has a retained same-session predecessor here.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from review_cross_session_roll import completed_journal
from review_wifi_roll_export import review
from review_roll_load import summarize_samples

TRIALS=(
    'wizard-20260917T023236485605Z-be2d2f06a4664d56bfa79fc78cfc6b5d',
    'wizard-20260917T115329625195Z-443e8a3260834658af22778859f4f70e',
    'wizard-20260917T115916898649Z-ca21b67e6f5e4cfa83076736434949ee')


def original_fields(sample):
    """Retain raw fields without labeling them temperature, torque or load."""
    raw=base64.b64decode(sample['response_base64'],validate=True)
    if len(raw)!=sample['response_bytes'] or hashlib.sha256(raw).hexdigest()!=sample['response_sha256']:
        raise ValueError('Original body mismatch')
    body=json.loads(raw)
    return {key:body.get(key) for key in ('tB','tS','tE','tT','tR')}


def analyze(folder):
    evidence=review(folder)
    if not evidence['full_validation_success']:
        raise ValueError('Complete endpoint and hold required for this cohort')
    reports=[]
    for item in json.loads((folder/'manifest.json').read_bytes())['files']:
        if item['name'].startswith('attachment-result-'):
            reports.extend(step['report'] for step in json.loads((folder/item['name']).read_bytes()).get('steps',[]) if 'report' in step)
    movement=next(r for r in reports if 'outcome' in r)
    hold=next(r for r in reports if 'samples' in r)
    tx=movement['outcome']['transaction']
    return dict(export_id=folder.name,manifest_sha256=evidence['manifest_file_sha256'],
        command=tx['command'],baseline_rad=tx['baseline'],
        baseline_raw_fields=original_fields(movement['baseline']),
        final_deg=evidence['final_deg'],timeline=evidence['trial_timeline'],
        endpoint_raw_fields=[original_fields(s) for s in movement['outcome']['feedback_originals']],
        hold=evidence['hold'],hold_raw_tR=summarize_samples(hold['samples']),
        preceding_history=dict(status='NOT_ESTABLISHED_BY_THIS_REVIEW'))


def collect(root):
    exports=root/'software/runs/wizard-exports'
    legs=completed_journal(exports,'86b99f6aa91c4e0b800ad17ac13945b9',expected_legs=8,
        expected_final_hash='edb6dc46db55beeef5daa7274e9a4b47dc72421ffbbafec4824d1a5c3ade1646')
    records=[analyze(exports/name) for name in TRIALS]
    if legs[0]['export_id']!=TRIALS[1] or legs[6]['export_id']!=TRIALS[2]:
        raise ValueError('Expected zero-position journal legs')
    for record,leg in ((records[1],legs[0]),(records[2],legs[6])):
        if record['manifest_sha256']!=leg['manifest_file_sha256']:
            raise ValueError('Journal/export mismatch')
    records[1]['preceding_history']=dict(status='FIRST_LEG_NO_IN_SESSION_PREDECESSOR')
    previous=legs[6]['predecessor']; prior=analyze(exports/previous['export_id'])
    if previous['manifest_file_sha256']!=prior['manifest_sha256']:
        raise ValueError('Predecessor mismatch')
    records[2]['preceding_history']=dict(status='JOURNAL_LINKED',
        export_id=prior['export_id'],manifest_sha256=prior['manifest_sha256'],
        command=prior['command'],final_deg=prior['final_deg'],
        hold_raw_tR=prior['hold_raw_tR'],hold=prior['hold'],
        hold_to_dispatch_s=legs[6]['measured_interval_s'])
    return dict(schema='rocell.zero_variability_review.v1',records=records,
        commands_equal=all(r['command']==records[0]['command'] for r in records),
        reported_baselines_equal=all(r['baseline_rad']==records[0]['baseline_rad'] for r in records),
        endpoint_span_deg=max(r['final_deg'] for r in records)-min(r['final_deg'] for r in records),
        cause_identified=False,raw_field_units_verified=False,model_fitted=False,
        motion_authorized=False,physical_accuracy_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=collect(Path(__file__).resolve().parents[2])
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
