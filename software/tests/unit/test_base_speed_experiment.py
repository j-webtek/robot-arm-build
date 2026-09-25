import math

import pytest

from rocell.application.base_speed_experiment import (
    speed_experiment_spec, summarize_speed_observation,
)


@pytest.mark.parametrize('direction', ['INCREASING', 'DECREASING'])
def test_speed_changes_only_parameter_not_route(direction):
    a = speed_experiment_spec(direction=direction, speed=10)
    b = speed_experiment_spec(direction=direction, speed=20)
    assert {k for k in a if a[k] != b[k]} == {'speed'}
    assert not a['candidate_speed_validated']
    assert not a['motion_authorized']


@pytest.mark.parametrize('speed', [0, -1, 11, 40, True, 10., '10', None])
def test_unsupported_speed_rejected(speed):
    with pytest.raises(ValueError):
        speed_experiment_spec(direction='INCREASING', speed=speed)


@pytest.mark.parametrize('direction', ['INCREASING', 'DECREASING'])
@pytest.mark.parametrize('speed', [10, 20])
def test_speed_dependent_bias_is_not_hidden_by_inverse(direction, speed):
    spec = speed_experiment_spec(direction=direction, speed=speed)
    start = [spec['expected_base_start_rad'], 0, 1.59, .047, 0, 3.14]
    # Deliberately make the unvalidated setting miss despite the same command.
    error = math.radians(.6 if speed == 10 else .05)
    final = start.copy()
    final[0] = spec['desired_rad'] + error
    rows = [(100 + i*20, 110 + i*20, start if i < 5 else final)
            for i in range(30)]
    result = summarize_speed_observation(direction=direction, speed=speed,
        start_joints_rad=start, rows=rows, write_finished_ns=100)
    assert result['signed_endpoint_error_rad'] == pytest.approx(error)
    assert result['final_report_in_quarter_degree_band'] == (speed == 20)
    assert not result['export_verified']
    assert not result['model_validation_evidence']
    assert not result['endpoint_settling_verified']


def test_wrong_start_rejected_before_timing():
    with pytest.raises(ValueError, match='Matched route'):
        summarize_speed_observation(direction='INCREASING', speed=10,
            start_joints_rad=[0.]*6, rows=[], write_finished_ns=0)


def test_other_joint_drift_is_retained():
    start = [.007669904, 0, 1.59, .047, 0, 3.14]
    final = start.copy()
    final[0] = math.radians(1)
    final[3] += .02
    rows = [(100+i*20, 110+i*20, final) for i in range(30)]
    result = summarize_speed_observation(direction='INCREASING', speed=10,
        start_joints_rad=start, rows=rows, write_finished_ns=100)
    assert result['maximum_other_joint_drift_rad'][2] == pytest.approx(.02)
    assert not result['motion_authorized']
