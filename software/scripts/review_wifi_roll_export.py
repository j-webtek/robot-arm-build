"""Read-only replay of saved Wi-Fi endpoint evidence. Never opens arm transport.

Print a compact JSON record for review; this is evidence, never motion admission.
"""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path

from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.first_motion_contract import canonical
from rocell.arm.discrete_endpoint import verify_discrete_endpoint
from rocell.arm.first_motion_analysis import TOLERANCE_RAD
from rocell.arm.sustained_band import assess_sustained_band
from rocell.providers.windows.arm_wifi_observation import review_observation

JOINTS=('b','s','e','t','r','g')


def trial_timeline(transaction, hold_samples, receipt):
    """Summarize replayed evidence on the host clock, not physical motion time.

The receipt digest is checked against the exact serializer used by dispatch.
Response bytes are digest-checked but never interpreted as endpoint evidence.
"""
    payload_hash=hashlib.sha256(canonical(transaction['command'])).hexdigest()
    if receipt.get('payload_sha256')!=payload_hash:
        raise ValueError('Command payload digest mismatch')
    raw=base64.b64decode(receipt['response_base64'],validate=True)
    if hashlib.sha256(raw).hexdigest()!=receipt.get('response_sha256'):
        raise ValueError('Command response digest mismatch')
    dispatch=transaction['dispatch_started_ns']
    baseline=transaction['baseline_finished_ns']
    ack=transaction['acknowledgment_finished_ns']
    verified=transaction['result']['evaluated_ns']
    rows=transaction['rows']
    if not rows or not hold_samples or not baseline<=dispatch<=ack<=rows[0][0]:
        raise ValueError('Ordered baseline, dispatch, receipt and feedback required')
    if not rows[-1][1]<=verified<=round(hold_samples[0]['request_started_monotonic_s']*1e9):
        raise ValueError('Ordered verification and hold required')
    return dict(schema='rocell.trial_timeline.v1',
        command_payload_sha256=payload_hash,command_response_sha256=receipt['response_sha256'],
        receipt_kind=receipt.get('receipt_kind'),
        baseline_age_at_dispatch_ms=(dispatch-baseline)/1e6,
        dispatch_to_http_receipt_ms=(ack-dispatch)/1e6,
        dispatch_to_verification_s=(verified-dispatch)/1e9,
        verification_to_hold_request_s=hold_samples[0]['request_started_monotonic_s']-verified/1e9,
        endpoint_feedback=[dict(request_after_dispatch_s=(row[0]-dispatch)/1e9,
            response_after_dispatch_s=(row[1]-dispatch)/1e9,roll_deg=math.degrees(row[2][4]))
            for row in rows],
        physical_movement_duration_known=False,receipt_used_as_endpoint=False)


def receipt_summary(report):
    """Expose bounded failure metadata, never arbitrary response/exception text."""
    receipt=report.get('command_receipt') or {}
    category=receipt.get('failure_category')
    allowed={'TIMEOUT','CONNECTION_RESET','RESPONSE_OR_BINDING_REJECTED','IO_FAILURE'}
    return dict(status=receipt.get('status') if receipt.get('status') in
                ('UNCERTAIN','HTTP_RECEIPT_ONLY') else None,
        failure_category=category if category in allowed else None,
        cleanup_confirmed=receipt.get('cleanup_confirmed') is True)


def replay_endpoint(transaction, samples):
    """Reconstruct successful decisions from original responses, not summaries."""
    review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=samples))
    rows=[[round(s['request_started_monotonic_s']*1e9),
           round(s['response_finished_monotonic_s']*1e9),
           [s['joints_rad'][k] for k in JOINTS]] for s in samples]
    if rows!=transaction['rows']:
        raise ValueError('Recorded rows differ from original feedback')
    saved=transaction['result']
    if not saved:
        raise ValueError('No endpoint verdict to reconstruct')
    kwargs=({'command_target':transaction['command']['rad']}
            if 'desired_endpoint_rad' in transaction else {})
    actual=verify_discrete_endpoint(rows,joint='r',start=transaction['baseline'],
        target=transaction.get('desired_endpoint_rad',transaction['command']['rad']),
        command_finished_ns=saved['command_finished_ns'],
        completion_deadline_ns=saved['completion_deadline_ns'],
        evaluated_ns=saved['evaluated_ns'],**kwargs)
    if actual!=saved or not actual['endpoint_verified']:
        raise ValueError('Endpoint verdict mismatch or not verified')
    return rows


def assess_hold(transaction, samples):
    """Analyze already reconstructed hold samples; exact stability is experimental.

Do not confuse capture success or the broad arrival band with an unchanged hold.
Host response bounds locate observations, not the physical instant of a change.
"""
    if not samples:
        raise ValueError('Nonempty hold required')
    initial=transaction['rows'][-1][2]
    previous_end=transaction['rows'][-1][1]
    desired=transaction.get('desired_endpoint_rad',transaction['command']['rad'])
    poses=[];changes=[]
    for i,sample in enumerate(samples):
        begin=round(sample['request_started_monotonic_s']*1e9)
        end=round(sample['response_finished_monotonic_s']*1e9)
        if not previous_end<=begin<=end:
            raise ValueError('Hold must follow endpoint and remain ordered')
        pose=[sample['joints_rad'][k] for k in JOINTS]
        if pose!=initial:changes.append(i)
        poses.append(pose);previous_end=end
    changed_joints=[k for j,k in enumerate(JOINTS) if any(p[j]!=initial[j] for p in poses)]
    first=changes[0] if changes else None
    return dict(status='UNCHANGED_REPORTED_ENDPOINT' if first is None else 'LATE_REPORTED_ENDPOINT_CHANGE',
        unchanged=first is None,changed_joints=changed_joints,changed_sample_count=len(changes),
        initial_endpoint_deg=math.degrees(initial[4]),
        hold_final_deg=math.degrees(poses[-1][4]),
        hold_final_error_deg=math.degrees(poses[-1][4]-desired),
        maximum_absolute_error_deg=max(math.degrees(abs(p[4]-desired)) for p in poses),
        roll_span_deg=math.degrees(max(p[4] for p in poses)-min(p[4] for p in poses)),
        all_roll_samples_within_arrival_band=all(abs(p[4]-desired)<=TOLERANCE_RAD for p in poses),
        first_changed_sample_index=first,
        first_changed_response_after_dispatch_s=None if first is None else
            samples[first]['response_finished_monotonic_s']-transaction['dispatch_started_ns']/1e9,
        physical_transition_time_known=False)


def incomplete_hold_details(transaction, hold):
    """Describe only the reconstructed successful prefix; never complete a hold.

    The caller first checks original-response reconstruction. Reject samples
    after a fault instead of silently stitching recovery data into the hold.
    """
    prefix=[];failures=[];fault_seen=False
    for i,s in enumerate(hold['samples']):
        if s.get('status')=='SUCCEEDED':
            if fault_seen:raise ValueError('Hold contains samples after fault')
            prefix.append(s)
        else:
            fault_seen=True
            category=s.get('error_category');phase=s.get('failure_phase')
            failures.append(dict(sample_index=i,
                category=category if category in ('TIMEOUT','CONNECTION_RESET','IO_FAILURE','CANCELLED') else 'OTHER_OR_UNAVAILABLE',
                phase=phase if phase in ('REQUEST_SEND','RESPONSE_READ','RESPONSE_HEADERS','CONNECT','IDENTITY_BEFORE','IDENTITY_AFTER') else 'OTHER_OR_UNAVAILABLE'))
    return dict(failure_code='HOLD_INCOMPLETE',hold_completed=False,
        hold_failure_details=failures,successful_prefix_samples=len(prefix),
        partial_hold_assessment=assess_hold(transaction,prefix) if prefix else None,
        # Deliberately omit band qualification and a full-hold verdict.
        full_validation_success=False)


def review(path):
    path=Path(path).resolve()
    if not verify_export(path)['valid']:
        raise ValueError('Export integrity check failed')
    # Read only manifest-listed result attachments; ignore unrelated files.
    manifest=json.loads((path/'manifest.json').read_bytes())
    reports=[]
    for item in manifest['files']:
        name=item['name']
        if name.startswith('attachment-result-') and name.endswith('.json'):
            result=json.loads((path/name).read_bytes())
            reports.extend(s['report'] for s in result.get('steps',[]) if 'report' in s)
    movements=[r for r in reports if 'outcome' in r]
    if len(movements)!=1:
        raise ValueError('Exactly one movement report required')
    report=movements[0];outcome=report['outcome'];tx=outcome['transaction']
    record=dict(export_id=path.name,manifest_file_sha256=hashlib.sha256(
        (path/'manifest.json').read_bytes()).hexdigest(),integrity_verified=True,
        transaction_state=tx['state'],command_attempts=tx['command_attempts'],
        command=tx['command'],baseline_rad=tx['baseline'],
        desired_endpoint_deg=math.degrees(tx.get('desired_endpoint_rad',tx['command']['rad'])),
        candidate=report.get('correction_candidate'),
        characterization=report.get('characterization'),
        command_receipt_summary=receipt_summary(report),
        endpoint_replayed=False,hold_completed=False,full_validation_success=False,
        physical_accuracy_verified=False,motion_authorized=False)
    if tx['state']=='COMMAND_OUTCOME_UNCERTAIN':
        # Preserve the failure, never reinterpret receipt or later recovery as arrival.
        record.update(failure=outcome.get('error'),feedback_failures=[
            dict(status=s.get('status'),category=s.get('error_category'),phase=s.get('failure_phase'))
            for s in outcome['feedback_originals'] if s.get('status')!='SUCCEEDED'])
        return record
    rows=replay_endpoint(tx,outcome['feedback_originals'])
    record.update(endpoint_replayed=True,final_deg=math.degrees(rows[-1][2][4]),
        error_deg=math.degrees(tx['result']['endpoint']['final_error_rad']))
    holds=[r for r in reports if 'samples' in r]
    if len(holds)!=1:
        raise ValueError('One passive hold required')
    hold=holds[0];reconstructed=review_observation(hold)
    if reconstructed!=hold['reconstruction']:
        raise ValueError('Hold summary mismatch')
    record['hold']=reconstructed
    if hold['status'] in ('FAILED','CANCELLED'):
        record.update(incomplete_hold_details(tx,hold))
        return record
    if hold['status']!='SUCCEEDED':raise ValueError('Unknown hold status')
    stability=assess_hold(tx,hold['samples'])
    record.update(endpoint_replayed=True,final_deg=math.degrees(rows[-1][2][4]),
        error_deg=math.degrees(tx['result']['endpoint']['final_error_rad']),hold=reconstructed,
        hold_completed=True,hold_assessment=stability,full_validation_success=stability['unchanged'])
    if report.get('command_receipt'):
        record['trial_timeline']=trial_timeline(tx,hold['samples'],report['command_receipt'])
    # Illustrative sensitivity only: this does not replace the exact hold verdict
    # or adopt an accuracy requirement. Real captures have ~34.8s response spans.
    record['band_sensitivity_examples']=[assess_sustained_band(hold['samples'],
        desired_rad=tx.get('desired_endpoint_rad',tx['command']['rad']),
        band_deg=band,required_duration_s=30.0) for band in (0.05,0.10)]
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports',nargs='+',type=Path)
    args=parser.parse_args()
    records=[review(p) for p in args.exports]
    print(json.dumps(records,indent=2))
    # Preserve nonzero CLI failure while making valid late-change evidence readable.
    if not all(r['full_validation_success'] for r in records):
        raise SystemExit(1)


if __name__=='__main__':main()
