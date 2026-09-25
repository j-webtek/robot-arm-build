"""Build a pinned full roll history and offline screen; no hardware access."""
import base64
import json
from pathlib import Path
import runpy
import math
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.arm.roll_history_assessment import assess_roll_history


def review():
    software=Path(__file__).resolve().parents[1]
    pins=json.loads((software/'docs/WRIST_ROLL_HISTORY_PINS_20260915.json').read_bytes())['campaigns']
    rows=[]
    for pin in pins:
        cid=pin['campaign_id'];root=software/'runs/wizard-exports'/cid
        v=verify_native_retained_export(root,cid+'-parent-report.json')
        if not v['valid'] or v['report_sha256']!=pin['report_sha256']:
            raise ValueError('Original integrity/pin mismatch: '+cid)
        def original(name):
            return base64.b64decode(json.loads((root/(cid+'-parent-'+name+'.original.json')).read_bytes())['base64'],validate=True)
        body=decode_request(original('request'))['payload']['campaign_intent']
        if body.get('selected_joint')!='r' or body['issued_ns']!=pin['issued_ns']:
            raise ValueError('Inventory binding differs')
        path=root/(cid+'-parent-trial.original.json')
        trial=json.loads(original('trial')) if path.exists() else None
        e=v['endpoint_diagnostics'][0] if v['endpoint_diagnostics'] else None
        persistent=bool(e and e.get('persistence',{}).get('status')=='REPORTED_ENDPOINT_PERSISTENT')
        duration=body['limits']['observation_s']
        eligible=bool(v['reconstruction_consistent'] and v['endpoint_completion_consistent'] and duration==35 and persistent)
        reason=('ELIGIBLE_35S_PERSISTENT' if eligible else 'NO_RETAINED_TRIAL' if trial is None
                else 'HISTORICAL_HOLD_OR_INCOMPLETE' if not v['reconstruction_consistent']
                else 'SHORT_OBSERVATION_NOT_35S' if duration!=35 else 'NOT_PERSISTENT')
        command=body['legs'][0]['command']
        row=dict(campaign_id=cid,report_sha256=pin['report_sha256'],issued_ns=body['issued_ns'],
            schema=body['schema'],**body['references'],command=command,spd=command['spd'],acc=command['acc'],
            staged_start=body['start_joints_rad'],start_rad=e['start_rad'] if e else None,
            target_rad=command['rad'],final_rad=e['final_rad'] if e else None,
            error_deg=math.degrees(e['signed_error_rad']) if e else None,
            direction='INCREASING' if command['rad']>body['start_joints_rad'][4] else 'DECREASING',
            observation_s=duration,eligible=eligible,eligibility_reason=reason,
            reconstruction_consistent=v['reconstruction_consistent'],
            historical_endpoint_completion=v['endpoint_completion_consistent'],
            native_submission_attempts=trial['native_submission_attempts'] if trial else None,
            historical_status=trial['status'] if trial else 'NO_RETAINED_TRIAL',
            endpoint_diagnostics=None if e is None else dict(
                status=e['status'],arrival=e.get('persistence',{}).get('full_window_endpoint',{}),
                persistence_status=e.get('persistence',{}).get('status'),
                sample_count=e['post_sample_count'],
                horizon_endpoints=[dict(seconds=h['seconds'],final_rad=h['final_rad'],covered=h['covered'])
                    for h in e.get('persistence',{}).get('horizons',[])],
                late_transition_count=e.get('persistence',{}).get('after_5s_transition_count'),
                other_joint_drift=e.get('persistence',{}).get('other_joint_maximum_drift_rad'),
                framing_status=e.get('cross_window_framing',{}).get('status')),
            write=trial['legs'][0]['write'] if trial and trial['legs'] else None,
            cleanup=trial['cleanup'] if trial else None)
        rows.append(row)
    # These diagnostic replays retain the old hold and short-window outcome;
    # neither is promoted into clean training data by its later observations.
    held=runpy.run_path(str(Path(__file__).with_name('review_roll_cross_window_20260915.py')))['review']()
    delayed_short=json.loads((software/'runs/WRIST_ROLL_SECOND_POINT_20260915.json').read_bytes())
    return dict(schema='rocell.roll_history_dataset.v1',pin_manifest='software/docs/WRIST_ROLL_HISTORY_PINS_20260915.json',
        rows=rows,assessment=assess_roll_history(rows),historical_hold_replay=held,
        short_window_followup_reference=dict(path='software/runs/WRIST_ROLL_SECOND_POINT_20260915.json',
            historical_only=True,not_training_data=True,schema=delayed_short['schema']),
        new_hardware_connections=0,new_commands_sent=0,compensation_applied=False)


if __name__=='__main__':
    print(json.dumps(review(),indent=2))
