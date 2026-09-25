import pytest
from rocell.kinematics.shoulder_clearance_recovery import preview_recovery

POSITIONS = [2047,2448,1667,2905,1589,2040,2047]
GOALS = [2047,2443,1671,2907,1589,2040,2047]


def test_preserves_commanded_pair_relationship_and_rises():
    result = preview_recovery(POSITIONS, GOALS)
    assert result['proposed_goals'] == [2047,2419,1695,2907,1589,2040,2047]
    assert result['actual_to_target_counts'] == [-29,28]
    assert result['preserved_commanded_pair_sum'] == 4114
    assert result['sample_count'] == 30
    assert result['minimum_nominal_increment_mm'] > 0
    assert result['nominal_endpoint_rise_mm'] > 0
    assert result['movement_authorized'] is False
    assert result['physical_clearance_verified'] is False


@pytest.mark.parametrize('index', range(7))
def test_changed_goals_or_pose_require_new_review(index):
    goals = GOALS.copy(); goals[index] += 1
    with pytest.raises(ValueError): preview_recovery(POSITIONS, goals)
    positions = POSITIONS.copy(); positions[index] += 3
    with pytest.raises(ValueError): preview_recovery(positions, GOALS)


@pytest.mark.parametrize('value', [True, 2448.0, -1, 4096, None])
def test_invalid_counts_never_admitted(value):
    positions = POSITIONS.copy(); positions[1] = value
    with pytest.raises(ValueError): preview_recovery(positions, GOALS)


def test_wrong_direction_residual_rejected():
    positions = POSITIONS.copy(); positions[2] = 1672
    with pytest.raises(ValueError): preview_recovery(positions, GOALS)
