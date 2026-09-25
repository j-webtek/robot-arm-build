import json
from copy import deepcopy
import pytest
from rocell.application.controller_endpoint_rehearsal import (
    vertical_rehearsal_plan, rehearse_vertical_endpoints)
from test_controller_route_preview import baseline


def test_pair_runs_real_owned_endpoint_workflow_without_hardware(tmp_path):
    feedback = baseline()
    before = deepcopy(feedback)
    result = rehearse_vertical_endpoints(tmp_path,feedback)
    assert feedback == before
    assert result['status'] == 'SIMULATED_PAIR_COMPLETE'
    assert result['controller_model']['reference_ik_status'] == 'REFERENCE_IK_PASS'
    assert not result['physical_authority'] and not result['physical_accuracy_verified']
    assert result['native_device_opens'] == result['physical_motion_commands'] == 0
    assert result['skipped_trial_ids'] == []
    for row,trial in zip(result['trial_results'],result['plan']['trials']):
        assert row['trial']['status'] == 'OBSERVED_ENDPOINT_DWELL'
        assert len(row['simulated_wire_writes']) == 1
        wire = json.loads(row['simulated_wire_writes'][0])
        assert wire['T'] == 104
        assert wire['z'] == trial['target']['z_mm']
        assert wire['r'] == feedback['joints_rad']['r']
        assert wire['g'] == feedback['joints_rad']['g']


@pytest.mark.parametrize('fault',[
    'BASELINE_MISMATCH','SHORT_WRITE','UNCHANGED','CANCEL_AFTER_WRITE','CLEANUP_PENDING'])
def test_failure_prevents_return_and_never_retries(tmp_path,fault):
    result = rehearse_vertical_endpoints(tmp_path,baseline(),first_fault=fault)
    assert result['status'] == 'SIMULATED_PAIR_STOPPED'
    assert len(result['trial_results']) == 1
    assert result['skipped_trial_ids'] == ['return']
    assert len(result['trial_results'][0]['simulated_wire_writes']) <= 1


def test_changed_reference_rejected_before_rehearsal_writes(tmp_path):
    report = baseline()
    report['controller_cartesian']['values']['x'] += 1
    with pytest.raises(ValueError):
        rehearse_vertical_endpoints(tmp_path,report)
    assert not list(tmp_path.iterdir())


def test_plan_is_existing_contract_with_synthetic_labels():
    plan = vertical_rehearsal_plan(baseline()).to_dict()
    assert plan['frame'] == 'R_ctrl'
    assert plan['evidence']['usb_identity'] == 'SYNTHETIC'
    assert plan['trials'][0]['target'] == plan['trials'][1]['start']
    assert plan['trials'][0]['start'] == plan['trials'][1]['target']
