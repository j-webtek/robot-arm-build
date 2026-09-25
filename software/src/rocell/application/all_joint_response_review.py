"""Offline post-command count comparison; no fitted correction or motion authority."""
import math
from rocell.arm.all_joint_command import JOINT_FIELDS, all_joint_command
from rocell.kinematics.firmware_reference import joint_response_comparison, REFERENCE_SHA256
from rocell.safety.wifi_all_joint_reservation import verify_sample
from .controller_route_preview import _baseline


def review_all_joint_response(trial, observation):
    tx=trial['transaction']
    if trial.get('command_send_attempted') is not True:
        raise ValueError('A retained send attempt is required')
    command=tx['command']
    target=[command[k] for k in JOINT_FIELDS]
    if command != all_joint_command(target,speed=command['spd'],acceleration=command['acc']):
        raise ValueError('Exact T102 command required')
    verify_sample(tx['baseline'])
    _,start,consistent=_baseline(tx['baseline'])
    if not consistent:raise ValueError('Baseline model mismatch')
    samples=observation.get('samples',[])
    if observation.get('status')!='SUCCEEDED' or len(samples)<3:
        raise ValueError('Complete passive observation required')
    previous=tx['dispatch_s'];rows=[]
    for sample in samples:
        verify_sample(sample)
        begin=sample['request_started_monotonic_s'];end=sample['response_finished_monotonic_s']
        if begin<previous:raise ValueError('Post-dispatch ordered feedback required')
        _,q,consistent=_baseline(sample)
        if not consistent:raise ValueError('Observation model mismatch')
        rows.append(q);previous=end
    comparisons=joint_response_comparison(start,target,rows[-1])
    spans=[max(q[i] for q in rows)-min(q[i] for q in rows) for i in range(6)]
    return dict(schema='rocell.all_joint_response_review.v1',
        status='POST_COMMAND_COMPARISON_NOT_TRAJECTORY_VERIFICATION',
        reference_sha256=REFERENCE_SHA256,command=command,
        baseline_joints_rad=start,final_joints_rad=rows[-1],joint_comparisons=comparisons,
        passive_sample_count=len(rows),reported_joint_spans_rad=spans,
        passive_span_s=samples[-1]['response_finished_monotonic_s']-
            samples[0]['response_finished_monotonic_s'],
        first_passive_response_after_dispatch_s=samples[0]['response_finished_monotonic_s']-tx['dispatch_s'],
        nominal_encoder_step_rad=2*math.pi/4096,
        nominal_count_mismatches=[r['joint'] for r in comparisons if r['count_error']!=0],
        rounding_alone_matches_reference_counts=all(r['count_error']==0 for r in comparisons),
        installed_firmware_verified=False,trajectory_verified=False,
        physical_accuracy_verified=False,motion_authorized=False,compensation_generated=False)
