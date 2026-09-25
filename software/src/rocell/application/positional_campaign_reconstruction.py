"""Recompute fully evaluated owned campaigns from retained original captures.

Not authentication, native evidence promotion, or recovery permission. Incomplete
captures remain useful diagnostics but cannot pass this completed-result check.
"""
import base64
import hashlib
import math

from .first_motion_contract import canonical
from .positional_campaign_capture import validate_campaign_capture
from rocell.arm.first_motion_analysis import _window
from rocell.arm.campaign_stream_sync import campaign_window, campaign_post_window, FRAMED_SCHEMAS
from rocell.arm.protocol import encode_line
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, require_correction_start, verify_campaign_endpoint, campaign_joint_index


def verify_completed_owned_campaign(request,result):
    if type(request) is not PositionalCampaignIntent or type(result) is not dict:
        raise ValueError('Exact intent and completed result required')
    fields={'schema','basis','status','intent_sha256','legs','errors','cleanup',
        'simulated_write_attempts','physical_write_count','native_execution_released',
        'physical_stop_verified','replay_allowed','skipped_leg_ids'}
    if (set(result) not in (fields,fields|{'reconstruction'}) or len(canonical(result))>2_097_152
            or result['schema']!='rocell.owned_positional_campaign.v1'
            or result['basis']!='SYNTHETIC_WIRE_REHEARSAL' or result['intent_sha256']!=request.sha256
            or result['status'] not in ('SIMULATION_COMPLETE','HELD')
            or type(result['physical_write_count']) is not int or result['physical_write_count']!=0
            or any(result[k] is not False for k in ('native_execution_released','physical_stop_verified','replay_allowed'))
            or type(result['legs']) is not list or not 1<=len(result['legs'])<=request.to_dict()['limits']['maximum_writes']):
        raise ValueError('Bounded completed synthetic campaign required')
    return _verify_completed_campaign_records(request, result,
        complete_status='SIMULATION_COMPLETE', attempts_field='simulated_write_attempts')


def _verify_completed_campaign_records(request, result, *, complete_status, attempts_field):
    """Shared capture mathematics after a domain-specific envelope check.

    Callers preserve their provenance; native data is never relabelled synthetic.
    This routine validates records, not a worker process or a physical position.
    """
    body=request.to_dict()
    previous_sha=request.sha256
    previous_end=body['issued_ns']
    previous_joints=body['start_joints_rad']
    total=0
    final_state=None
    for index,record in enumerate(result['legs']):
        if index>=len(body['legs']): raise ValueError('Unexpected extra command record')
        if final_state=='HELD': raise ValueError('Later leg after failed endpoint')
        leg=body['legs'][index]
        if (type(record) is not dict or set(record)!={'leg_id','baseline','write','post','verification'}
                or record['leg_id']!=leg['leg_id']):
            raise ValueError('Exact ordered leg required')
        baseline,post,write=record['baseline'],record['post'],record['write']
        if type(write) is not dict or set(write)!={'started_ns','finished_ns','confirmed_bytes','uncertain'}:
            raise ValueError('Exact retained write accounting required')
        raw_before=validate_campaign_capture(request,baseline,phase='baseline')
        raw_after=validate_campaign_capture(request,post,phase='post',command_completed_ns=write['finished_ns'])
        rows,issues,_=campaign_window(body,'baseline',raw_before,baseline['read_windows'],baseline['started_ns'],baseline['finished_ns'],
            maximum_bytes=body['limits']['maximum_raw_bytes_per_leg'])
        after,post_issues,framing=campaign_post_window(body,raw_after,post['read_windows'],post['started_ns'],post['finished_ns'],
            baseline_raw=raw_before,baseline_windows=baseline['read_windows'],
            write_started_ns=write['started_ns'],write_finished_ns=write['finished_ns'])
        total+=len(raw_before)+len(raw_after)
        if (issues or post_issues or len(rows)<10 or len(after)<20
                or len(raw_before)+len(raw_after)>body['limits']['maximum_raw_bytes_per_leg']
                or total>body['limits']['maximum_total_raw_bytes']
                or any(type(write[k]) is not int for k in ('started_ns','finished_ns','confirmed_bytes'))
                or type(write['uncertain']) is not bool
                or not previous_end<=baseline['started_ns']<baseline['finished_ns']<=write['started_ns']<=write['finished_ns']<=post['started_ns']
                or post['started_ns']-write['finished_ns']>100_000_000
                or write['started_ns']-rows[-1][1]>250_000_000
                or post['finished_ns']-baseline['started_ns']>body['limits']['maximum_leg_s']*1_000_000_000):
            raise ValueError('Capture/order/budget inconsistency')
        start=rows[-1][2]
        axis=campaign_joint_index(body)
        if (any(max(row[2][i] for row in rows)-min(row[2][i] for row in rows)>math.radians(.1) for i in range(6))
                or any(abs(start[i]-previous_joints[i])>math.radians(.5) for i in range(6))
                or abs(start[axis]-leg['expected_start_rad'])>math.radians(.5)
                or abs(start[axis])>math.radians(10) or abs(start[axis]-leg['target_rad'])>math.radians(5)):
            raise ValueError('Baseline stability/predecessor mismatch')
        for row in rows:
            require_correction_start(body,row[2],leg)
        payload=encode_line(leg['command'])
        saved=record['verification']
        if type(saved) is not dict or type(saved.get('dispatch_claimed_ns')) is not int:
            raise ValueError('Original dispatch boundary timestamp required')
        claimed=saved['dispatch_claimed_ns']
        if not baseline['finished_ns']<=claimed<=write['started_ns']:
            raise ValueError('Dispatch boundary order invalid')
        if not 0<=write['confirmed_bytes']<=len(payload): raise ValueError('Impossible write count')
        clean=(not write['uncertain'] and write['confirmed_bytes']==len(payload)
            and write['finished_ns']-claimed<=1_000_000_000)
        endpoint=verify_campaign_endpoint(body,leg,after,start=start,capture_issues=(),transport_clean=clean,
            write_finished_ns=write['finished_ns'],capture_finished_ns=post['finished_ns'])
        original=dict(raw_base64=base64.b64encode(raw_after).decode(),read_windows=post['read_windows'],
            started_ns=post['started_ns'],finished_ns=post['finished_ns'],raw_sha256=hashlib.sha256(raw_after).hexdigest())
        if body['schema'] in FRAMED_SCHEMAS:
            original['cross_window_framing']=framing
        commit=dict(intent_sha256=request.sha256,leg_id=leg['leg_id'],predecessor_sha256=previous_sha,
            post=original,endpoint=endpoint,confirmed_write_bytes=write['confirmed_bytes'],
            write_uncertain=write['uncertain'],write_finished_ns=write['finished_ns'],
            dispatch_claimed_ns=claimed,replay_allowed=False)
        digest=hashlib.sha256(canonical(commit)).hexdigest()
        final_state=('COMPLETE' if index==len(body['legs'])-1 else 'OPEN_CLAIMED') if endpoint['endpoint_verified'] else 'HELD'
        expected=dict(endpoint=endpoint,state=final_state,committed_sha256=digest,
            dispatch_claimed_ns=claimed,native_execution_released=False)
        if canonical(record['verification'])!=canonical(expected):
            raise ValueError('Saved endpoint decision or commit differs from originals')
        previous_sha,previous_joints,previous_end=digest,after[-1][2],post['finished_ns']
    expected_status=complete_status if final_state=='COMPLETE' else 'HELD'
    cleanup=result['cleanup']
    if (result['status']!=expected_status or final_state=='OPEN_CLAIMED'
            or type(result[attempts_field]) is not int or result[attempts_field]!=len(result['legs'])
            or result['skipped_leg_ids']!=[leg['leg_id'] for leg in body['legs'][len(result['legs']):]]
            or type(cleanup) is not dict or set(cleanup)!={'status','started_ns','finished_ns'}
            or cleanup['status']!='HANDLES_CLOSED'
            or any(type(cleanup[k]) is not int for k in ('started_ns','finished_ns'))
            or not previous_end<=cleanup['started_ns']<=cleanup['finished_ns']<=body['deadline_ns']
            or cleanup['finished_ns']-cleanup['started_ns']>2_000_000_000
            or type(result['errors']) is not list or len(result['errors'])>8
            or (expected_status==complete_status and result['errors'])):
        raise ValueError('Terminal result, skipped legs or cleanup inconsistent')
    verified=dict(valid=True,reconstructed_status=expected_status,legs_verified=len(result['legs']),
        physical_accuracy_verified=False,physical_stop_verified=False,motion_authorized=False)
    if 'reconstruction' in result and canonical(result['reconstruction'])!=canonical(verified):
        raise ValueError('Saved reconstruction summary differs from recomputation')
    return verified
