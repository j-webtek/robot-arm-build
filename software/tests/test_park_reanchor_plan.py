import pytest

from rocell.application.park_reanchor_plan import (
    OFFSET_GOALS, OFFSET_POSITIONS, plan_park_reanchor,
)


BOOT = '03137a0ed96846b69056b502bdfd8e29'


def observation():
    return {
        'category': 'STABLE_SAMPLED_POSE',
        'origin': 'DEVICE_CAPTURE',
        'joints': [
            {'servo_id': 11 + i, 'last_goal': goal, 'last_position': position,
             'torque': 1, 'controls_unchanged': True, 'position_span': 0}
            for i, (goal, position) in enumerate(zip(OFFSET_GOALS, OFFSET_POSITIONS))
        ],
    }


def plan(sample=None):
    return plan_park_reanchor(observation() if sample is None else sample,
                              observation_boot=BOOT,
                              observation_export_id='export-1')


def test_plan_is_inert_and_not_a_position_claim():
    result = plan()
    assert result['target_goals'] == [2389, 1725]
    assert result['source_positions'][1:3] == [2385, 1730]
    assert result['movement_authorized'] is False
    assert result['physical_clearance_verified'] is False
    assert result['native_route_implemented'] is False
    assert result['maximum_writes'] == 1


@pytest.mark.parametrize('index,field,value', [
    (1, 'last_goal', 2376),
    (2, 'last_position', 1728),
    (0, 'torque', 0),
    (1, 'position_span', 2),
    (2, 'controls_unchanged', False),
    (4, 'servo_id', 99),
])
def test_rejects_changed_or_invalid_joint(index, field, value):
    sample = observation()
    sample['joints'][index][field] = value
    with pytest.raises(ValueError):
        plan(sample)


def test_rejects_unstable_or_unidentified_capture():
    sample = observation()
    sample['category'] = 'UNKNOWN'
    with pytest.raises(ValueError):
        plan(sample)
    with pytest.raises(ValueError):
        plan_park_reanchor(observation(), observation_boot='bad',
                           observation_export_id='export-1')
