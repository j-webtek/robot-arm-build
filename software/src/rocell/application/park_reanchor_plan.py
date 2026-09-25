"""Inert, evidence-bound plan for returning the first park step.

This does not connect to the controller. The native one-use owner must repeat
all checks on fresh seven-servo feedback immediately before any write.
"""

from __future__ import annotations

from rocell.application.park_step_plan import REFERENCE_GOALS, REFERENCE_POSITIONS, _joints


OFFSET_GOALS = (2047, 2377, 1737, 2907, 1589, 2040, 2047)
OFFSET_POSITIONS = (2047, 2385, 1730, 2904, 1591, 2041, 2047)


def plan_park_reanchor(observation, *, observation_boot, observation_export_id):
    """Describe one possible return, without authorizing or sending it.

    The target is a command goal, not a predicted endpoint. In particular,
    the persistent 8/7-count goal residual must not be treated as travel that
    has already occurred, or as evidence that the gripper is off the board.
    """
    if (observation.get('category') != 'STABLE_SAMPLED_POSE' or
            observation.get('origin') != 'DEVICE_CAPTURE'):
        raise ValueError('Stable device capture required')
    joints = _joints(observation.get('joints'), goal_key='last_goal',
                     position_key='last_position')
    if (tuple(row['last_goal'] for row in joints) != OFFSET_GOALS or
            any(abs(row['last_position'] - expected) > 1 for row, expected in
                zip(joints, OFFSET_POSITIONS)) or
            any(row.get('controls_unchanged') is not True or
                type(row.get('position_span')) is not int or
                not 0 <= row['position_span'] <= 1 for row in joints)):
        raise ValueError('Observation outside measured offset-pose envelope')
    if (type(observation_boot) is not str or len(observation_boot) != 32 or
            any(c not in '0123456789abcdef' for c in observation_boot) or
            type(observation_export_id) is not str or not observation_export_id):
        raise ValueError('Source identity required')
    return {
        'schema': 'rocell.park_reanchor_plan.v1',
        'observation_boot': observation_boot,
        'observation_export_id': observation_export_id,
        'source_goals': list(OFFSET_GOALS),
        'source_positions': [row['last_position'] for row in joints],
        'target_servo_ids': [12, 13],
        'target_goals': [REFERENCE_GOALS[1], REFERENCE_GOALS[2]],
        'reference_positions_are_observations_not_required_targets':
            [REFERENCE_POSITIONS[1], REFERENCE_POSITIONS[2]],
        'maximum_position_excursion_counts_from_prewrite': [8, 8],
        'speed': 20,
        'acceleration': 1,
        'maximum_writes': 1,
        'automatic_retry': False,
        'automatic_follow_on_step': False,
        'fresh_native_prewrite_capture_required': True,
        'fresh_native_postwrite_capture_required': True,
        'durable_success_or_fault_export_required': True,
        'physical_clearance_verified': False,
        'movement_authorized': False,
        'native_route_implemented': False,
    }
