"""Inert plan for the first clearly visible paired-shoulder step.

The plan is derived from the post-r57 device capture.  It contains no
transport and grants no movement authority; the native owner must repeat the
same seven-servo checks immediately before its single write.
"""

from __future__ import annotations

from .park_step_plan import _joints


SOURCE_GOALS = (2047, 2389, 1725, 2907, 1589, 2040, 2047)
SOURCE_POSITIONS = (2047, 2391, 1724, 2904, 1591, 2041, 2047)
TARGET_GOALS = (2413, 1701)
# Preserve the repeatably observed +2/-1 steady-state goal residual.  These
# are encoder expectations, not Cartesian or tool-tip predictions.
EXPECTED_POSITIONS = (2415, 1700)


def plan_visible_shoulder_step(observation, *, observation_boot,
                               observation_export_id):
    if (observation.get('category') != 'STABLE_SAMPLED_POSE' or
            observation.get('origin') != 'DEVICE_CAPTURE'):
        raise ValueError('Stable device capture required')
    joints = _joints(observation.get('joints'), goal_key='last_goal',
                     position_key='last_position')
    if (tuple(row['last_goal'] for row in joints) != SOURCE_GOALS or
            any(abs(row['last_position'] - expected) > 1
                for row, expected in zip(joints, SOURCE_POSITIONS)) or
            any(row.get('controls_unchanged') is not True or
                type(row.get('position_span')) is not int or
                not 0 <= row['position_span'] <= 1 for row in joints)):
        raise ValueError('Observation outside post-return pose envelope')
    if (type(observation_boot) is not str or len(observation_boot) != 32 or
            any(c not in '0123456789abcdef' for c in observation_boot) or
            type(observation_export_id) is not str or not observation_export_id):
        raise ValueError('Source identity required')
    return {
        'schema': 'rocell.visible_shoulder_step_plan.v1',
        'observation_boot': observation_boot,
        'observation_export_id': observation_export_id,
        'source_goals': list(SOURCE_GOALS),
        'source_positions': [row['last_position'] for row in joints],
        'target_servo_ids': [12, 13],
        'target_goals': list(TARGET_GOALS),
        'expected_encoder_positions': list(EXPECTED_POSITIONS),
        'maximum_position_excursion_counts_from_prewrite': [28, 28],
        'speed': 20,
        'acceleration': 1,
        'maximum_writes': 1,
        'automatic_retry': False,
        'automatic_return': False,
        'fresh_native_prewrite_capture_required': True,
        'fresh_native_postwrite_capture_required': True,
        'durable_success_or_fault_export_required': True,
        'physical_clearance_verified': False,
        'movement_authorized': False,
        'native_route_implemented': False,
        'cartesian_motion_predicted': False,
    }

