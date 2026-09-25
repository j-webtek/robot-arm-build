import copy

import pytest

from rocell.application.visible_shoulder_step_plan import (
    SOURCE_GOALS, SOURCE_POSITIONS, TARGET_GOALS,
    plan_visible_shoulder_step,
)


def observation():
    return {
        'category': 'STABLE_SAMPLED_POSE', 'origin': 'DEVICE_CAPTURE',
        'joints': [
            {'servo_id': 11 + index, 'last_goal': goal,
             'last_position': position, 'torque': 1,
             'controls_unchanged': True, 'position_span': 0}
            for index, (goal, position) in enumerate(zip(SOURCE_GOALS,
                                                         SOURCE_POSITIONS))
        ],
    }


def plan(sample=None):
    return plan_visible_shoulder_step(
        observation() if sample is None else sample,
        observation_boot='ab' * 16, observation_export_id='wizard-valid')


def test_plan_is_inert_and_fixed():
    result = plan()
    assert result['target_goals'] == list(TARGET_GOALS)
    assert result['source_positions'] == list(SOURCE_POSITIONS)
    assert result['maximum_position_excursion_counts_from_prewrite'] == [28, 28]
    assert result['movement_authorized'] is False
    assert result['automatic_retry'] is False
    assert result['automatic_return'] is False
    assert result['cartesian_motion_predicted'] is False


@pytest.mark.parametrize('field,value', [
    ('last_goal', 2400), ('last_position', 2400),
    ('controls_unchanged', False), ('position_span', 2),
])
def test_changed_source_is_rejected(field, value):
    sample = copy.deepcopy(observation())
    sample['joints'][1][field] = value
    with pytest.raises(ValueError, match='outside'):
        plan(sample)


def test_nondevice_capture_is_rejected():
    sample = observation()
    sample['origin'] = 'SIMULATION'
    with pytest.raises(ValueError, match='Stable device'):
        plan(sample)

