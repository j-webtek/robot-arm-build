"""Replay an exported forward leg and summarize raw-reference servo feedback.

Offline only. No device access, physical scaling, fault diagnosis or compensation.
"""
import argparse
import base64
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_observed_forward import replay_observed_pair_forward
from rocell.application.product_ghost_export_review import _read
from rocell.application.servo_register_reference import decode_feedback_block, PROFILE_ID
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward-export',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    replay=replay_observed_pair_forward(root,args.forward_export)
    bundle,_=_read(root,args.forward_export,'attachment-observed-pair-forward.json')
    snapshots=[];action=None
    for response in bundle['responses']:
        envelope=json.loads(base64.b64decode(response['raw_base64']))
        if 'raw_json' not in envelope:continue
        record=json.loads(envelope['raw_json'])
        if record.get('schema')=='rocell.hold_action.v1':action=record
        if record.get('schema')=='rocell.held_leg_snapshot.v1':snapshots.append(record)
    if action is None:raise ValueError('No command boundary available')
    samples=[]
    for snapshot in snapshots:
        if snapshot['profile_id']!=PROFILE_ID or snapshot['byte_order']!='little':
            raise ValueError('Unexpected feedback reference')
        for servo,address,width,read in snapshot['reads']:
            if servo!=action['servo_id'] or address!=56:continue
            if width!=15 or read[3]!=15 or read[4]!=0 or read[5] is not True:
                raise ValueError('Incomplete feedback read')
            decoded=decode_feedback_block(bytes.fromhex(read[6]),read_status='SUCCEEDED',byte_order='little')
            samples.append(dict(snapshot_index=snapshot['snapshot_index'],
                phase='after' if read[1]>action['finished_us'] else 'before',
                read_started_us=read[1],read_finished_us=read[2],
                values={k:v['decoded_value'] for k,v in decoded.items()}))
    summaries={}
    for phase in ('before','after'):
        rows=[r for r in samples if r['phase']==phase]
        if not rows:raise ValueError('Both sides of command required')
        summaries[phase]=dict(count=len(rows),fields={k:dict(
            minimum=min(r['values'][k] for r in rows),maximum=max(r['values'][k] for r in rows))
            for k in rows[0]['values']})
    report=dict(schema='rocell.pair_feedback_review.v1',source_export=args.forward_export,
        source_sha256=replay['export_sha256'],assessment=replay['assessment'],
        servo_id=action['servo_id'],summaries=summaries,samples=samples,
        units='RAW_REFERENCE',physical_scaling_verified=False,hardware_access=False,
        causal_diagnosis_verified=False,motion_authorized=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-pair-feedback-review'},[],
        attachments={'pair-feedback-review.json':canonical(report)})
    retained,_=_read(root,Path(saved['path']).name,'attachment-pair-feedback-review.json')
    if canonical(retained)!=canonical(report):raise ValueError('Review export differs')
    print(json.dumps(dict(export_path=saved['path'],summaries=summaries,units='RAW_REFERENCE')))


if __name__=='__main__':main()
