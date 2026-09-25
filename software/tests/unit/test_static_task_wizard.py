"""Exercise the actual static task parent branch, UI card and exported evidence."""
import json
from pathlib import Path

import pytest
from test_arrival_wizard_service import make_service, _run, _ticket
from test_wizard_activity_ui import render, view, operation
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_actions import WizardError


@pytest.mark.parametrize('mode,device', [('rehearsal','keyboard'), ('physical','phone')])
def test_real_static_route_through_wizard_and_export(make_service, mode, device):
    service, runner, _ = make_service(mode=mode)
    values = dict(device=device, text='a', park='overlay_290_40')
    ticket = _ticket(service, 'rehearse_static_task', values)
    assert not runner.calls
    # This exercises real numerical IK, not a mocked fast diagnostic. Allow
    # computation time without changing any production or motion deadline.
    result = _run(service, 'rehearse_static_task', values, timeout_s=30)
    assert result['status'] == 'SUCCEEDED', result
    report = result['result']['steps'][0]['report']
    assert report['dense_route']['all_waypoints_accepted']
    assert not report['physical_authority'] and not report['hardware_access']
    exported = _run(service, 'export_logs')
    assert exported['status'] == 'SUCCEEDED'
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    saved = [json.loads(path.read_text()) for path in folder.glob('attachment-result-*.json')]
    assert any(item == result['result'] for item in saved)
    assert not runner.calls


def test_static_nominal_failure_is_not_worker_success(make_service):
    service, _, _ = make_service()
    result = _run(service, 'rehearse_static_task', dict(device='keyboard', text='a', park='nominal'))
    assert result['status'] == 'FAILED'
    assert result['result']['steps'][0]['report']['status'] == 'DENSE_ROUTE_FAILED'


def test_invalid_input_rejected_before_dispatch(make_service):
    service, runner, _ = make_service()
    with pytest.raises(WizardError):
        _ticket(service, 'rehearse_static_task', dict(device='keyboard', text='a'*9, park='overlay_290_40'))
    with pytest.raises(WizardError):
        _ticket(service, 'rehearse_static_task', dict(device='keyboard', text='a', park='arbitrary_live_pose'))
    assert not runner.calls


@pytest.mark.parametrize('passed', [True, False])
def test_result_card_shows_pass_and_first_failure_without_authority(passed):
    report = dict(status='DENSE_SAMPLES_PASS_NOT_EXECUTABLE' if passed else 'DENSE_ROUTE_FAILED',
        architecture='static_overhead_eye_to_hand', device='keyboard',
        park_selection=dict(xy_board_mm=[290,40]),
        task_summary=dict(requested_target_count=2, requested_targets=['H','H'],
            first_failure=None if passed else dict(target='keyboard:H',phase='HOVER')),
        dense_route=dict(round=dict(waypoint_count=38, evaluated_waypoint_count=38 if passed else 1,
            all_waypoints_accepted=passed, failure_reason=None if passed else 'IK_NO_CONVERGED_SOLUTION')))
    op = operation(action_id='rehearse_static_task', result=dict(steps=[dict(report=report)]))
    page = render(view([op]), steps=[dict(load='op-0')], results={'op-0':op})
    rendered = json.dumps(page)
    for label in ('Static-camera task rehearsal', report['status'], 'waypoints evaluated',
                  'physical motion authorized', 'Inspect full static route evidence'):
        assert label in rendered
    if not passed:
        assert 'IK_NO_CONVERGED_SOLUTION' in rendered
        assert 'keyboard:H / HOVER' in rendered
    assert 'requested targets (including repeats)' in rendered
