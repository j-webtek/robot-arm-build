"""Review post-completion feedback; in-band arrival is not a settled-start claim."""
import math

from .controller_route_preview import _baseline
from rocell.kinematics.firmware_reference import forward


def review_endpoint_hold(trial, observation):
    result=dict(schema='rocell.endpoint_hold_review.v1',status='HOLD_NOT_VERIFIED',
        motion_authorized=False,physical_accuracy_verified=False,
        encoder_freshness_verified=False,automatic_retry_allowed=False)
    run=trial.get('run') or {};tx=run.get('transaction') or {}
    if run.get('error') is not None or tx.get('state')!='COMPENSATED_REPORTED_ENDPOINT_VERIFIED':
        return dict(result,reason='CLEAN_COMPENSATED_COMPLETION_REQUIRED')
    desired=(tx.get('desired_endpoint_result') or {}).get('desired_xyz_pitch')
    samples=observation.get('samples') or []
    if observation.get('status')!='SUCCEEDED' or len(samples)<3 or not desired:
        return dict(result,reason='COMPLETE_HOLD_OBSERVATIONS_REQUIRED')
    last_end=None;first_end=None;previous=None;stable_since=None;errors=[];final=None
    for sample in samples:
        pose,joints,consistent=_baseline(sample)
        begin=sample.get('request_started_monotonic_s');end=sample.get('response_finished_monotonic_s')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (begin,end)):
            raise ValueError('Finite observation timestamps required')
        if begin>end or (last_end is not None and (begin<last_end or end-last_end>1)):
            return dict(result,reason='OBSERVATION_TIMING_INVALID')
        if sample.get('timing_clock')!='HOST_PERF_COUNTER' or begin<tx['rows'][-1][1]/1e9:
            return dict(result,reason='OBSERVATION_NOT_AFTER_COMPLETION')
        if not consistent:return dict(result,reason='MODEL_MISMATCH')
        commanded_index=(tx.get('command') or {}).get('joint',4)-1
        if any(abs(a-b)>1e-8 for i,(a,b) in enumerate(zip(joints,tx['rows'][-1][3])) if i!=commanded_index):
            return dict(result,reason='OTHER_JOINT_CHANGED_DURING_HOLD')
        if first_end is None:first_end=end
        if previous is None or any(abs(a-b)>1e-8 for a,b in zip(previous,joints)):
            stable_since=end
        error=math.dist(pose[:3],desired[:3]);errors.append(error)
        if error>.5 or abs(pose[3]-desired[3])>.02:
            return dict(result,reason='LEFT_DESIRED_ENDPOINT_BAND',position_error_mm=error)
        previous=joints;final=joints;last_end=end
    stable_s=last_end-stable_since
    return dict(result,status='REPORTED_HOLD_VERIFIED' if stable_s>=1 else 'HOLD_NOT_VERIFIED',
        sample_count=len(samples),observation_span_s=last_end-first_end,
        unchanged_tail_s=stable_s,maximum_desired_error_mm=max(errors),
        final_desired_error_mm=errors[-1],final_joints_rad=final,
        changed_since_completion=any(abs(a-b)>1e-8 for a,b in zip(final,tx['rows'][-1][3])),
        final_modeled_pose=list(forward(*final[:4])))
