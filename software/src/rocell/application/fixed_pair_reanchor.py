"""Offline contract for one exact shoulder-pair start-goal correction.

This module has no transport, controller access, or movement authority. A future
native one-shot owner must independently enforce the same checks using fresh
servo reads before and after its sole paired target write.
"""
from __future__ import annotations

from pathlib import Path

from .pose_observation_export import replay_pose_observation


SOURCE_GOALS = (2386, 1728)
SOURCE_POSITIONS = (2390, 1725)
TARGET_GOALS = (2389, 1725)
TARGET_POSITIONS = (2391, 1724)
SELECTED_IDS = (12, 13)


def _selected(assessment):
    if assessment.get('category') != 'STABLE_SAMPLED_POSE' or assessment.get('origin') != 'DEVICE_CAPTURE':
        raise ValueError('Fresh stable device evidence required')
    joints = assessment.get('joints')
    if type(joints) is not list or len(joints) != 7:
        raise ValueError('Complete seven-servo evidence required')
    if [j.get('servo_id') for j in joints] != list(range(11, 18)):
        raise ValueError('Unexpected servo identity or order')
    if any(j.get('controls_unchanged') is not True or
           type(j.get('position_span')) is not int or j['position_span'] > 1
           or j.get('torque') != 1 for j in joints):
        raise ValueError('Changing or disabled servo state')
    return joints


def plan_fixed_pair_reanchor(root, export_id):
    """Bind a reviewed capture to the sole permissible target; never send it."""
    replay = replay_pose_observation(Path(root).resolve(), export_id)
    if replay.get('replay_verified') is not True:
        raise ValueError('Pose export did not replay')
    assessment = replay['assessment']
    joints = _selected(assessment)
    goals = tuple(joints[i]['last_goal'] for i in (1, 2))
    positions = tuple(joints[i]['last_position'] for i in (1, 2))
    if goals != SOURCE_GOALS or any(abs(a-b) > 1 for a, b in zip(positions, SOURCE_POSITIONS)):
        raise ValueError('Measured pair outside exact reanchor start gate')
    if sum(goals) != sum(TARGET_GOALS) or any(abs(a-b) > 3 for a, b in zip(goals, TARGET_GOALS)):
        raise ValueError('Target exceeds paired three-count envelope')
    return {
        'schema': 'rocell.fixed_pair_reanchor_plan.v1',
        'source_export_id': export_id,
        'source_raw_sha256': replay['raw_bundle_sha256'],
        'source_goals': list(goals),
        'source_positions': list(positions),
        'target_servo_ids': list(SELECTED_IDS),
        'target_goals': list(TARGET_GOALS),
        'expected_positions': list(TARGET_POSITIONS),
        'maximum_endpoint_error_counts': 1,
        'maximum_selected_excursion_counts': 3,
        'maximum_neighbor_excursion_counts': 2,
        'maximum_writes': 1,
        'automatic_retry': False,
        'automatic_return': False,
        'fresh_native_prewrite_capture_required': True,
        'fresh_native_postwrite_capture_required': True,
        'durable_result_export_required': True,
        'movement_authorized': False,
        'firmware_support_installed': False,
        'physical_motion_proven': False,
    }


def verify_reanchor_endpoint(plan, baseline, endpoint):
    """Offline mirror of the proposed native readback gate.

    A successful goal correction can be smaller than one position count and
    therefore does not, by itself, prove visible physical motion.
    """
    if plan.get('schema') != 'rocell.fixed_pair_reanchor_plan.v1':
        raise ValueError('Unexpected reanchor plan')
    if (plan.get('target_goals') != list(TARGET_GOALS) or
            plan.get('expected_positions') != list(TARGET_POSITIONS)):
        raise ValueError('Reanchor plan target changed')
    before, after = _selected(baseline), _selected(endpoint)
    if any(before[i]['last_goal'] != after[i]['last_goal'] for i in (0, 3, 4, 5, 6)):
        raise ValueError('Neighbor goal changed')
    if any(abs(after[i]['last_position']-before[i]['last_position']) > 2
           for i in (0, 3, 4, 5, 6)):
        raise ValueError('Neighbor moved outside envelope')
    initial = tuple(before[i]['last_position'] for i in (1, 2))
    final = tuple(after[i]['last_position'] for i in (1, 2))
    if any(abs(a-b) > 1 for a, b in zip(initial, SOURCE_POSITIONS)):
        raise ValueError('Prewrite position changed')
    if tuple(before[i]['last_goal'] for i in (1, 2)) != SOURCE_GOALS:
        raise ValueError('Prewrite goals changed')
    if tuple(after[i]['last_goal'] for i in (1, 2)) != TARGET_GOALS:
        raise ValueError('Target goal readback failed')
    if any(abs(a-b) > 3 for a, b in zip(initial, final)):
        raise ValueError('Selected servo excursion exceeded')
    if any(abs(a-b) > 1 for a, b in zip(final, TARGET_POSITIONS)):
        raise ValueError('Reanchor endpoint outside frozen gate')
    return {
        'status': 'GOAL_AND_ENDPOINT_VERIFIED',
        'position_delta': [b-a for a, b in zip(initial, final)],
        'encoder_displacement_observed': any(a != b for a, b in zip(initial, final)),
        'physical_motion_proven': False,
        'ghost_campaign_authorized': False,
    }
