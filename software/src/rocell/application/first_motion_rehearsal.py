"""Fixed first-motion proposal and synthetic evidence assessment; no I/O.

This cannot mint endpoint evidence, access a device or establish physical truth.
The nominal result deliberately remains review-required, never commissioned.
"""
import math
from .first_motion_contract import fixed_command

SCENARIOS = ('NOMINAL', 'UNCHANGED', 'TELEMETRY_ONLY', 'PHYSICAL_ONLY',
             'WRONG_DIRECTION', 'SHORT_WRITE', 'CLEANUP_UNCERTAIN', 'CANCELLED',
             'OTHER_JOINT_MOVED')


def proposal():
    """Return detached proposed values, not a live command or claimed setup."""
    command = fixed_command()
    return {
        'joint': 'WRIST_PITCH', 'command_family': 'T101', 'joint_number': 4,
        'target_rad': command['rad'], 'target_is_absolute': True,
        'speed_steps_per_second': command['spd'], 'acceleration_parameter': command['acc'],
        'required_independent_start_interval_deg': [-5, 5],
        'required_distal_radius_limit_mm': 200,
        'maximum_requested_travel_given_start_interval_deg': 6,
        'ideal_rigid_point_path_length_bound_mm': 200*math.radians(6),
        'geometry_conditions_established': False,
        'servo_overshoot_and_cables_included_in_bound': False,
        'live_execution_implemented': False,
    }


def assess(*, telemetry, physical, write, cleanup, cancelled, other_joint_moved):
    """Classify already-interpreted observations, never authenticate them.

    A future live analyzer must derive these categories from retained original
    windows and independent observation. They are not browser approval fields.
    """
    if (type(telemetry) is not str or telemetry not in {'EXPECTED', 'UNCHANGED', 'UNEXPECTED', 'UNKNOWN'}
            or type(physical) is not str or physical not in {'EXPECTED', 'UNCHANGED', 'UNEXPECTED', 'UNKNOWN'}
            or type(write) is not str or write not in {'COMPLETE', 'UNCERTAIN', 'NOT_SENT'}
            or any(type(v) is not bool for v in (cleanup, cancelled, other_joint_moved))):
        raise ValueError('Exact bounded observation categories required')
    reasons = []
    if cancelled:
        reasons.append('CANCELLED')
    if write != 'COMPLETE':
        reasons.append('WRITE_'+write)
    if not cleanup:
        reasons.append('CLEANUP_UNCERTAIN')
    if other_joint_moved:
        reasons.append('UNEXPECTED_OTHER_JOINT_MOTION')
    if physical != 'EXPECTED':
        reasons.append('PHYSICAL_'+physical)
    if telemetry != 'EXPECTED':
        reasons.append('TELEMETRY_'+telemetry)
    return {
        'status': 'INCONCLUSIVE_OR_FAILED' if reasons else 'OBSERVATIONS_AGREE_REVIEW_REQUIRED',
        'reasons': reasons,
        'endpoint_baseline_qualified': False,
        'device_sample_freshness_verified': False,
        'physical_authority': False, 'motion_authorized': False,
        'automatic_return_allowed': False, 'automatic_retry_allowed': False,
        'campaign_advance_allowed': False,
    }


def rehearse(scenario):
    """Exercise a finite scenario with explicitly synthetic observation labels."""
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError('Unknown fixed commissioning rehearsal scenario')
    observations = dict(telemetry='EXPECTED', physical='EXPECTED', write='COMPLETE',
                        cleanup=True, cancelled=False, other_joint_moved=False)
    changes = {
        'NOMINAL': {},
        'UNCHANGED': dict(telemetry='UNCHANGED', physical='UNCHANGED'),
        'TELEMETRY_ONLY': dict(physical='UNCHANGED'),
        'PHYSICAL_ONLY': dict(telemetry='UNCHANGED'),
        'WRONG_DIRECTION': dict(telemetry='UNEXPECTED', physical='UNEXPECTED'),
        'SHORT_WRITE': dict(write='UNCERTAIN'),
        'CLEANUP_UNCERTAIN': dict(cleanup=False),
        'CANCELLED': dict(cancelled=True),
        'OTHER_JOINT_MOVED': dict(other_joint_moved=True),
    }
    observations.update(changes[scenario])
    return {'schema': 'rocell.first_motion_rehearsal.v1',
            'basis': 'SYNTHETIC_OBSERVATION_LOGIC_NOT_PHYSICAL_EVIDENCE',
            'scenario': scenario, 'proposal': proposal(),
            'synthetic_observations': observations, 'assessment': assess(**observations),
            'device_open_count': 0, 'serial_write_count': 0, 'motion_command_count': 0,
            'physical_authority': False,
            'limitations': ['No servo dynamics or physical speed is simulated',
                'No source/reference hash or input category authenticates physical observations',
                'Even nominal agreement cannot qualify all joints or subsequent samples']}
