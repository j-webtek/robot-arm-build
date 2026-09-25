"""Offline first-rise contract from a measured seven-servo checkpoint.

Planning is intentionally inert: it does not open a transport or authorize a
servo write. A future native owner must repeat the prewrite checks on fresh
hardware samples and enforce its own one-write, fault-stop record contract.
"""

from __future__ import annotations


REFERENCE_GOALS = (2047, 2389, 1725, 2907, 1589, 2040, 2047)
REFERENCE_POSITIONS = (2047, 2390, 1724, 2904, 1591, 2041, 2047)
FIRST_TARGET = (2377, 1737)
SELECTED_INDEXES = (1, 2)


def _joints(rows, *, goal_key, position_key):
    if type(rows) is not list or len(rows) != 7:
        raise ValueError('Complete seven-servo evidence required')
    if [row.get('servo_id') for row in rows] != list(range(11, 18)):
        raise ValueError('Servo identities or order changed')
    if any(type(row.get(goal_key)) is not int or type(row.get(position_key)) is not int
           or not (0 <= row[goal_key] <= 4095 and 0 <= row[position_key] <= 4095)
           or type(row.get('torque')) is not int or row['torque'] != 1 for row in rows):
        raise ValueError('Invalid joint controls or readings')
    return rows


def plan_first_park_step(reference, observation, *, observation_boot,
                         observation_export_id):
    """Prepare one bounded paired target, not a general home or live command.

    The caller must replay/verify the exported reference and fresh device
    observation independently. A sampled pose alone cannot prove clearance.
    """
    if (reference.get('schema') != 'rocell.standard_start_encoder_reference.v1'
            or reference.get('label') != 'REFERENCE_A'
            or reference.get('encoder_reference_verified') is not True
            or reference.get('physical_park_verified') is not False
            or reference.get('safe_to_replay_without_fresh_capture') is not False):
        raise ValueError('Measured non-park reference required')
    baseline = _joints(reference.get('joints'), goal_key='goal', position_key='position')
    if (tuple(row['goal'] for row in baseline) != REFERENCE_GOALS or
            any(abs(row['position'] - expected) > 2 for row, expected in
                zip(baseline, REFERENCE_POSITIONS))):
        raise ValueError('Reference differs from frozen measured checkpoint')
    if (observation.get('category') != 'STABLE_SAMPLED_POSE' or
            observation.get('origin') != 'DEVICE_CAPTURE'):
        raise ValueError('Fresh stable device observation required')
    current = _joints(observation.get('joints'), goal_key='last_goal',
                      position_key='last_position')
    if any(row.get('controls_unchanged') is not True or
           type(row.get('position_span')) is not int or not 0 <= row['position_span'] <= 1
           for row in current):
        raise ValueError('Changing servo state')
    if (tuple(row['last_goal'] for row in current) != REFERENCE_GOALS or
            any(abs(row['last_position'] - expected) > 2 for row, expected in
                zip(current, REFERENCE_POSITIONS))):
        raise ValueError('Fresh pose drifted from reference')
    if (type(observation_boot) is not str or len(observation_boot) != 32 or
            any(c not in '0123456789abcdef' for c in observation_boot) or
            type(observation_export_id) is not str or not observation_export_id):
        raise ValueError('Source identity required')
    return {
        'schema': 'rocell.first_park_step_plan.v1',
        'reference_label': 'REFERENCE_A',
        'observation_boot': observation_boot,
        'observation_export_id': observation_export_id,
        'source_goals': list(REFERENCE_GOALS),
        'source_positions': [row['last_position'] for row in current],
        'target_servo_ids': [12, 13],
        'target_goals': list(FIRST_TARGET),
        'speed': 20,
        'acceleration': 1,
        'maximum_writes': 1,
        'automatic_retry': False,
        'automatic_return': False,
        'fresh_native_prewrite_capture_required': True,
        'fresh_native_postwrite_capture_required': True,
        'durable_result_export_required': True,
        'physical_rise_observation_required_for_next_step': True,
        'physical_clearance_verified': False,
        'movement_authorized': False,
        'firmware_support_installed': False,
    }
