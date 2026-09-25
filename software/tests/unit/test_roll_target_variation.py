import copy
import math

import pytest

from rocell.arm.roll_target_variation import (
    ANCHOR, OFFSETS, experiment_case, simulate_case, starting_pose_matches, validate_case)


@pytest.mark.parametrize('label', OFFSETS)
@pytest.mark.parametrize('prefix', ['', 'return-'])
def test_enumerated_geometry_and_independent_return(label, prefix):
    case = experiment_case(prefix + label)
    validate_case(case)
    assert case['command_joint'] == 5 and case['selected_joint'] == 'r'
    assert abs(math.degrees(case['target_rad']-case['start_joints_rad'][4])) == pytest.approx(OFFSETS[label])
    result = simulate_case(case)
    assert result['status'] == 'REPORTED_ENDPOINT_PERSISTENT'
    assert result['quality']['next_start_status'] == 'REPORTED_MATCH'
    assert result['simulated_write_attempts'] == 1 and result['physical_writes'] == 0
    assert not result['automatic_next_command_allowed']


@pytest.mark.parametrize('field,value', [('target_rad', float('nan')), ('spd', 21),
    ('acc', 2), ('command_joint', 4), ('observation_s', 5), ('case_id', 'arbitrary'),
    ('motion_authorized', True), ('configuration_sha256', '0'*64)])
def test_modified_case_rejected(field, value):
    case = experiment_case('nominal'); case[field] = value
    with pytest.raises(ValueError):
        simulate_case(case)


@pytest.mark.parametrize('pose', [[0], [0]*5+[float('inf')], [True]*6])
def test_invalid_pose(pose):
    with pytest.raises(ValueError):
        starting_pose_matches(experiment_case('nominal'), pose)


def test_other_axis_start_mismatch_prevents_even_simulated_write():
    start = list(ANCHOR); start[1] += math.radians(.02)
    result = simulate_case(experiment_case('nominal'), observed_start=start)
    assert result['status'] == 'START_MISMATCH'
    assert result['simulated_write_attempts'] == 0 and result['endpoint'] is None


@pytest.mark.parametrize('model,status', [
    ('ideal', 'REPORTED_ENDPOINT_PERSISTENT'), ('bias', 'REPORTED_ENDPOINT_PERSISTENT'),
    ('deadband', 'REPORTED_ENDPOINT_PERSISTENT'), ('quantized', 'REPORTED_ENDPOINT_PERSISTENT'),
    ('delayed', 'ENDPOINT_NOT_VERIFIED'), ('late_departure', 'REPORTED_ENDPOINT_CHANGED'),
    ('stale', 'FEEDBACK_INVALID'), ('partial_write', 'TRANSPORT_FAULT'),
    ('timeout', 'OBSERVATION_INCOMPLETE'), ('other_joint_drift', 'ENDPOINT_NOT_VERIFIED')])
def test_production_evaluator_reports_faults(model, status):
    result = simulate_case(experiment_case('nominal'), model)
    assert result['status'] == status
    assert not result['motion_authorized'] and not result['automatic_next_command_allowed']


def test_biased_return_not_silently_reset_and_no_precision_pass():
    result = simulate_case(experiment_case('return-nominal'), 'bias')
    assert result['quality']['precision_status'] == 'OUTSIDE_DIAGNOSTIC_SCREEN'
    assert result['quality']['next_start_status'] == 'REPORTED_MISMATCH'
    subsequent = simulate_case(experiment_case('nominal'), observed_start=result['final_joints_rad'])
    assert subsequent['simulated_write_attempts'] == 0


def test_deterministic_and_no_mutation():
    case = experiment_case('nominal'); saved = copy.deepcopy(case)
    assert simulate_case(case) == simulate_case(case)
    assert case == saved


def test_unknown_model_rejected():
    with pytest.raises(ValueError):
        simulate_case(experiment_case('nominal'), 'invented')


def test_offline_definition_cannot_be_used_as_native_intent():
    from rocell.safety.positional_campaign_authority import validate_campaign_intent
    with pytest.raises(ValueError):
        validate_campaign_intent(experiment_case('nominal'), 1)


def test_complete_matrix_has_no_implicit_physical_sequence():
    from rocell.arm.roll_target_variation import simulation_matrix
    matrix = simulation_matrix()
    assert len(matrix['results']) == 60
    assert matrix['independent_synthetic_cases'] and not matrix['native_profile_implemented']
    assert matrix['physical_writes'] == 0
    assert len({(r['case']['case_id'], r['model']) for r in matrix['results']}) == 60
    assert all(r['simulated_write_attempts'] == 1 and not r['automatic_next_command_allowed']
               for r in matrix['results'])
    assert all(r['status'] != 'REPORTED_ENDPOINT_PERSISTENT' for r in matrix['results']
               if r['model'] in ('stale', 'partial_write', 'timeout', 'late_departure', 'other_joint_drift', 'delayed'))
