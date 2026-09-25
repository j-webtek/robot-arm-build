"""Explain supported pre-write failures without inventing dispatch evidence."""
import base64

from .servo_acquisition_pair import assess_acquisition_pair
from .servo_baseline_assessment import LIMITS
from .servo_session_plan import freeze_session_plan
from .servo_authorization_record import assess_authorization


def assess_partial_session(snapshot, plan):
    document = plan.to_dict()
    if document.get('schema') != 'rocell.session_plan.v2':
        raise ValueError('Baseline plan required')
    sent = base64.b64decode(document['sent_base64'], validate=True)
    verified = freeze_session_plan(document['command'], document['policy'], sent,
        document['schedule'], origin=document['origin'], baseline_policy=document['baseline_policy'])
    if verified.encoded != plan.encoded:
        raise ValueError('Noncanonical plan')
    start_record=None
    if snapshot['records'] and snapshot['records'][0]['kind']=='authorization':
        start_record=assess_authorization(snapshot['records'][0]['record'],plan,snapshot['records'][1:])
        snapshot=dict(snapshot,records=snapshot['records'][1:])
    status = snapshot['status']
    items = snapshot['records']
    if (status['state'] != 'FAULT' or status['reason'] != 'ADMISSION_REJECTED'
            or status['storage_fault'] or len(items) != 2
            or [item['kind'] for item in items] != ['receipt', 'baseline']):
        raise ValueError('Not a supported partial admission capture')
    receipt, baseline = [item['record'] for item in items]
    command = document['command']
    # Correlate the exact payload and identity, but do not claim a dispatch or
    # complete controller-receipt assessment: neither exists in this prefix.
    if (receipt.get('schema') != 'rocell.controller_receipt.v1'
            or receipt.get('boot_id') != command['boot_id']
            or receipt.get('command_id') != command['command_id']
            or type(receipt.get('payload_utf8')) is not str
            or receipt['payload_utf8'].encode('utf-8') != sent):
        raise ValueError('Uncorrelated partial receipt')
    policy = document['baseline_policy']
    if (set(baseline) != set(LIMITS) | {'schema', 'accepted', 'reason', 'acquisition'}
            or baseline['schema'] != 'rocell.elbow_baseline.v1'
            or baseline['accepted'] is not False
            or any(type(baseline[key]) is not int or baseline[key] != value
                   for key, value in policy.items())):
        raise ValueError('Invalid rejected baseline')
    pair = baseline['acquisition']
    assessed = assess_acquisition_pair(pair, boot_id=command['boot_id'],
        command_id=command['command_id'], servo_id=14, dispatch_us=receipt['received_us'],
        previous_sequence=-1, previous_finished_us=0, maximum_pair_us=policy['maximum_pair_us'])
    if pair['byte_order'] != 'little':
        raise ValueError('Unsupported baseline byte order')
    reason = baseline['reason']
    supported = False
    if assessed['status'] == 'READ_PAIR_INCOMPLETE':
        supported = reason == 'INVALID_BASELINE_READ'
    else:
        feedback = assessed['decoded']['feedback']
        position = feedback['position']['decoded_value']
        target = assessed['decoded']['target']['decoded_value']
        in_profile = 1024 <= position <= 3071 and 1024 <= target <= 3071
        supported = (reason == 'BASELINE_OUTSIDE_PROFILE' and not in_profile) or (
            reason == 'BASELINE_NOT_SETTLED' and in_profile and (
                feedback['moving']['decoded_value'] != 0
                or abs(position-target) > policy['settled_tolerance_counts']))
    if not supported:
        raise ValueError('Partial cause not independently supported')
    result=dict(schema='rocell.partial_session_assessment.v1', category='ADMISSION_REJECTED',
        supported_reason=reason, acquisition=assessed, session_plan_sha256=plan.sha256,
        dispatch_evidence_present=False, no_motion_proven=False,
        progression_authority=False, provenance_verified=False, physical_accuracy_verified=False)
    if start_record is not None:result['start_record']=start_record
    return result
