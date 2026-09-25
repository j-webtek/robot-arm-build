import math
import pytest

from rocell.application.wrist_accuracy_analysis import reference_wrist_goal, analyze_wrist_accuracy, STEP_RAD
from rocell.application.first_motion_contract import canonical
from test_absolute_wrist_result_review import fixture


@pytest.mark.parametrize('steps,rounded',[(.5,1),(-.5,-1),(1.5,2),(-1.5,-2),(0,0),(45.51,46),(-45.51,-46)])
def test_cpp_rounding_not_python_bankers_rounding(steps,rounded):
    result=reference_wrist_goal(steps*STEP_RAD)
    assert result['goal_register']==2047+rounded


@pytest.mark.parametrize('degrees,register',[(4,2093),(-4,2001),(0,2047),(100,3071),(-100,1023)])
def test_reference_mapping(degrees,register):
    assert reference_wrist_goal(math.radians(degrees))['goal_register']==register


@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),'0'])
def test_invalid_target_rejected(value):
    with pytest.raises(ValueError): reference_wrist_goal(value)


def test_missing_load_stays_missing_and_miss_is_not_corrected():
    request,trial=fixture(fault='miss')
    result=analyze_wrist_accuracy(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert result['endpoint_status']=='TARGET_MISSED'
    assert result['final_error_to_goal_steps']==pytest.approx(math.radians(-.87)/STEP_RAD+1)
    assert result['load']['observed_count']==0
    assert result['load']['minimum'] is None and result['load']['last'] is None
    assert not result['installed_firmware_verified'] and not result['compensation_recommended']


def test_midpoint_asymmetry_is_not_rounding_or_compensation():
    result=reference_wrist_goal(0)
    assert result['representable_rad']==-STEP_RAD
    assert result['quantization_error_deg']==0
    assert result['reference_feedback_error_deg']==pytest.approx(-.087890625)


def test_corrupt_capture_does_not_supply_accuracy_numbers():
    request,trial=fixture(fault='corrupt')
    result=analyze_wrist_accuracy(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert result['status']=='INSUFFICIENT_EVIDENCE'
    assert result['final_error_to_goal_steps'] is None


def test_changing_load_at_constant_angle_does_not_claim_freshness_or_cause():
    request,trial=fixture(fault='miss',load_values=[49,53])
    result=analyze_wrist_accuracy(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert result['load']['minimum']==49 and result['load']['maximum']==53
    assert result['load']['changed_during_constant_position']
    assert not result['load']['calibrated_torque']
    assert not result['installed_firmware_verified'] and not result['compensation_recommended']


def test_changed_capture_hash_is_rejected_before_comparison():
    request,trial=fixture()
    trial['post']['raw']['sha256']='a'*64
    with pytest.raises(ValueError):
        analyze_wrist_accuracy(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')
