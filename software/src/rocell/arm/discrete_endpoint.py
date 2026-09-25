"""Discrete move/wait/verify policy. No transport access or movement authority.

Host timing bounds are not device timestamps. A verified reported endpoint does
not establish external tool-tip accuracy or authorize another command.
"""
import math

from .joint_endpoint_verification import JOINT_KEYS, verify_reported_joint
from .first_motion_analysis import TOLERANCE_RAD

POLICY_ID = 'rocell.discrete_endpoint_policy.v1'
MAX_FEEDBACK_GAP_NS = 1_000_000_000
POST_RESPONSE_QUIET_S = .15
REQUIRED_CONSECUTIVE = 3


def policy():
    return dict(schema=POLICY_ID, provisional=True,
        maximum_feedback_gap_ns=MAX_FEEDBACK_GAP_NS,
        post_response_quiet_s=POST_RESPONSE_QUIET_S,
        required_consecutive=REQUIRED_CONSECUTIVE,
        arrival_tolerance_rad=TOLERANCE_RAD,
        scope='DISCRETE_SINGLE_JOINT_ONLY', automatic_retry=False)


def verify_discrete_endpoint(rows, *, joint, start, target, command_finished_ns,
                             completion_deadline_ns, evaluated_ns,
                             transport_clean=True, cancelled=False, command_target=None):
    """Evaluate a bounded capture using existing position/dwell/drift checks.

The caller must supply a deadline selected BEFORE dispatch from expected movement
duration plus settling margin. We do not infer travel time from servo speed units.
Check first response, all completion gaps and the trailing silence independently
of the movement deadline. A later failure always invalidates earlier arrival.
"""
    if (joint not in JOINT_KEYS or any(type(v) is not int for v in
            (command_finished_ns, completion_deadline_ns, evaluated_ns))
            or not 0 < command_finished_ns <= evaluated_ns
            or not command_finished_ns < completion_deadline_ns <= command_finished_ns+120_000_000_000
            or type(transport_clean) is not bool or type(cancelled) is not bool):
        raise ValueError('Explicit bounded command timing and status required')
    # Shared checker validates the pose configuration even for an empty capture.
    verify_reported_joint([],joint=joint,start=start,target=target,path_target=command_target)
    records=[];previous=command_finished_ns;largest=0;consecutive=0;invalid=False
    index=JOINT_KEYS.index(joint)
    for row in rows:
        try:
            begin,end,pose=row
            if (len(records)>=4096 or type(begin) is not int or type(end) is not int
                    or not previous<=begin<=end<=evaluated_ns
                    or type(pose) not in (list,tuple) or len(pose)!=6
                    or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in pose)):
                raise ValueError('Invalid observation')
        except (TypeError,ValueError):
            invalid=True
            break
        largest=max(largest,end-previous)
        previous=end
        records.append((begin,end,tuple(pose)))
        consecutive=consecutive+1 if abs(pose[index]-target)<=TOLERANCE_RAD else 0
    largest=max(largest,evaluated_ns-previous)
    endpoint=verify_reported_joint(records,joint=joint,start=start,target=target,
        capture_issues=['INVALID_ROWS'] if invalid else (),transport_clean=transport_clean,
        path_target=command_target)
    if cancelled: status='CANCELLED'
    elif not transport_clean: status='TRANSPORT_FAULT'
    elif invalid: status='FEEDBACK_INVALID'
    elif endpoint['status'] in ('OTHER_JOINT_CHANGED','JOINT_EXCURSION'):
        status=endpoint['status']
    elif largest>MAX_FEEDBACK_GAP_NS: status='FEEDBACK_GAP_EXCEEDED'
    elif evaluated_ns>completion_deadline_ns: status='COMPLETION_DEADLINE_EXCEEDED'
    elif endpoint['endpoint_verified'] and consecutive>=REQUIRED_CONSECUTIVE:
        status='REPORTED_ENDPOINT_VERIFIED'
    elif evaluated_ns>=completion_deadline_ns: status='COMPLETION_DEADLINE_EXCEEDED'
    else: status='NOT_YET_VERIFIED'
    result = dict(schema='rocell.discrete_endpoint_result.v1',policy=policy(),status=status,
        endpoint=endpoint,endpoint_verified=status=='REPORTED_ENDPOINT_VERIFIED',
        consecutive_in_band=consecutive,maximum_feedback_gap_ns=largest,
        command_finished_ns=command_finished_ns,completion_deadline_ns=completion_deadline_ns,
        evaluated_ns=evaluated_ns,outcome_uncertain=status in
        ('TRANSPORT_FAULT','FEEDBACK_GAP_EXCEEDED','FEEDBACK_INVALID','CANCELLED'),
        automatic_next_command_allowed=False,automatic_retry_allowed=False,
        physical_accuracy_verified=False,motion_authorized=False)
    if command_target is not None:
        result.update(schema='rocell.discrete_endpoint_result.v2',
            desired_endpoint_rad=target,command_target_rad=command_target)
    return result


def assess_stationary_timing(report):
    """Project a saved observation onto the new allowance, not an endpoint test.

Caller first verifies original responses. Keep historical 250-ms counts intact.
No command, target, or motion is present, so endpoint verification is impossible.
"""
    samples=report['samples']
    previous=None;largest=0.
    for sample in samples:
        if sample['status']!='SUCCEEDED':
            return dict(policy=policy(),status='TRANSPORT_FAULT',movement_ready=False)
        begin=sample['request_started_monotonic_s'];end=sample['response_finished_monotonic_s']
        largest=max(largest,end-(begin if previous is None else previous))
        previous=end
    return dict(policy=policy(),status='NO_SAMPLES' if not samples else
        'INCOMPLETE_OBSERVATION' if report['status']!='SUCCEEDED' else
        'WITHIN_PROVISIONAL_GAP_ALLOWANCE' if largest<=1 else 'FEEDBACK_GAP_EXCEEDED',
        maximum_observed_gap_s=largest,scope='STATIONARY_RESPONSE_TIMING_ONLY',
        endpoint_verified=False,movement_ready=False)
