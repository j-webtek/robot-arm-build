"""Wizard service/result/export integration for incapable endpoint trials."""

import json
from pathlib import Path
import pytest

from rocell.application.wizard_worker import run
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket


@pytest.mark.parametrize('mode', ['physical','rehearsal'])
def test_public_endpoint_rehearsal_and_export(make_service, tmp_path, mode):
    service, runner, _ = make_service(mode=mode)
    runner.run = lambda action, values, **kw: run(tmp_path, action, values, kw['cell_id'])
    _ticket(service, 'movement_endpoint_rehearse')
    operation = _run(service, 'movement_endpoint_rehearse')
    assert operation['status'] == 'SUCCEEDED', operation
    report = operation['result']['steps'][0]['report']
    assert report['trial']['status'] == 'OBSERVED_ENDPOINT_DWELL'
    assert report['native_device_opens'] == report['physical_motion_commands'] == 0
    assert len(report['simulated_wire_writes']) == 1
    assert not report['physical_authority'] and not report['physical_ready']
    exported = _run(service, 'export_logs')
    assert exported['status'] == 'SUCCEEDED', exported
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained = json.loads((folder/f"attachment-result-{operation['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert retained['steps'][0]['report'] == report
    assert service.view()['arm']['status'] == 'NOT_CONNECTED'


@pytest.mark.parametrize('fault,expected', [
    ('BASELINE_MISMATCH','HELD_BEFORE_WRITE'),('SHORT_WRITE','WRITE_UNCERTAIN_NO_RETRY'),
    ('UNCHANGED','INSUFFICIENT_ENDPOINT_EVIDENCE'),('CLEANUP_PENDING','CLEANUP_UNCERTAIN'),
])
def test_worker_fault_results_are_not_hardware_success(tmp_path, fault, expected):
    result = run(tmp_path, 'movement_endpoint_rehearse', {'fault':fault}, 'synthetic')
    report = result['steps'][0]['report']
    assert report['trial']['status'] == expected
    assert result['motion_command_count'] == 0


def test_unknown_target_and_extra_command_rejected_before_ticket(make_service):
    service, _, _ = make_service()
    for values in ({'trial_id':'not-a-trial'}, {'raw_command':'{"T":104}'}, {'fault':'LIVE'}):
        with pytest.raises(WizardError):
            _ticket(service, 'movement_endpoint_rehearse', values)
