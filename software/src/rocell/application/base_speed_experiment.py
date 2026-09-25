"""Offline speed-comparison specification and telemetry summary; no device I/O.

Offline descriptors cannot authorize motion. A separately validated v15 template
supports trusted staging; existing speed-20 schemas retain their meaning.
"""
import math
import hashlib
from copy import deepcopy

from .base_reported_timing import summarize_reported_base_timing
from .first_motion_contract import canonical

_ROUTES = {
    'INCREASING': (.007669904, math.radians(1), .04076651868282478),
    'DECREASING': (.018407769, math.radians(.4), -.011952475158143525),
}


def assemble_speed_template(source, proposal):
    """Fixed v15 contract assembly; callers must rebuild the proposal evidence."""
    from rocell.safety.positional_campaign_authority import (
        BASE_SPEED_SCHEMA, PositionalCampaignIntent, fixed_campaign_limits,
    )
    body=deepcopy(source)
    body.pop('base_experiment',None)
    config=dict(schema='rocell.base_speed_configuration.v1',
        specification=speed_experiment_spec(direction=proposal['direction'],speed=10),
        proposal=deepcopy(proposal))
    spec=config['specification']
    body.update(schema=BASE_SPEED_SCHEMA,mode='ATTENDED_ONE_BASE_PROBE',selected_joint='b',
        base_speed=config,limits=fixed_campaign_limits(BASE_SPEED_SCHEMA),
        issued_ns=1,deadline_ns=30_000_000_001,
        legs=[dict(leg_id='leg-01',expected_start_rad=body['start_joints_rad'][0],
            target_rad=spec['desired_rad'],command=dict(T=101,joint=1,
                rad=spec['transmitted_rad'],spd=10,acc=1))])
    body['references']['configuration_sha256']=hashlib.sha256(canonical(config)).hexdigest()
    return PositionalCampaignIntent(canonical(body))


def speed_experiment_spec(*, direction, speed):
    """Return a fresh, fixed route without claiming model validity at a new speed."""
    if type(direction) is not str or direction not in _ROUTES:
        raise ValueError('Known base direction required')
    if type(speed) is not int or speed not in (10, 20):
        raise ValueError('Only enumerated nonzero speed 10 or 20 supported')
    start, desired, transmitted = _ROUTES[direction]
    return dict(schema='rocell.base_speed_experiment_spec.v1', direction=direction,
        speed=speed, acceleration=1, command_type=101, joint=1,
        expected_base_start_rad=start, desired_rad=desired,
        transmitted_rad=transmitted, capture_seconds=5,
        model_training_speed=20, candidate_speed_validated=False,
        protocol_basis='VENDOR_DOCUMENTATION_NOT_INSTALLED_BINARY_VERIFICATION',
        motion_authorized=False)


def summarize_speed_observation(*, direction, speed, start_joints_rad, rows,
                                write_finished_ns):
    """Summarize already-validated acquisition rows, including clean misses.

    This arithmetic layer does not authenticate exports, prove settling, admit a
    next leg, or train a model. A future native/export adapter must supply those
    guarantees. Error is recomputed from actual reports, never from predictions.
    """
    spec = speed_experiment_spec(direction=direction, speed=speed)
    if (type(start_joints_rad) not in (list, tuple) or len(start_joints_rad) != 6
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in start_joints_rad)):
        raise ValueError('Finite six-joint baseline required')
    if abs(start_joints_rad[0] - spec['expected_base_start_rad']) > math.radians(.01):
        raise ValueError('Matched route start required')
    timing = summarize_reported_base_timing(rows, start_rad=start_joints_rad[0],
        desired_rad=spec['desired_rad'], write_finished_ns=write_finished_ns)
    final = list(rows[-1][2])
    signed_error = final[0] - spec['desired_rad']
    drift = [max(abs(row[2][j] - start_joints_rad[j]) for row in rows)
             for j in range(1, 6)]
    return dict(schema='rocell.base_speed_observation.v1', specification=spec,
        start_joints_rad=list(start_joints_rad), final_joints_rad=final,
        signed_endpoint_error_rad=signed_error,
        absolute_endpoint_error_rad=abs(signed_error),
        final_report_in_quarter_degree_band=abs(signed_error) <= math.radians(.25),
        maximum_base_displacement_rad=max(abs(row[2][0] - start_joints_rad[0]) for row in rows),
        maximum_other_joint_drift_rad=drift, reported_timing=timing,
        export_verified=False, endpoint_settling_verified=False,
        model_validation_evidence=False, motion_authorized=False)
