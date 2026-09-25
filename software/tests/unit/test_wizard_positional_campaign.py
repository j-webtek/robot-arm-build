from pathlib import Path
import json
import pytest

from rocell.application.wizard_worker import run
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.positional_campaign_rehearsal import verify_rehearsal_report
from rocell.application.positional_campaign_journal import verify_campaign_journal_export
from test_arrival_wizard_service import make_service, _run, _ticket, WORKSPACE


@pytest.mark.parametrize('mode', ['physical', 'rehearsal'])
def test_campaign_stop_is_delivered_and_cancelled_result_exports_without_replay(make_service, mode):
    """Exercise public ticket/stop/export plumbing, not native servo stopping."""
    from test_arrival_wizard_service import FakeRunner, _complete
    runner = FakeRunner(blocked=True)
    service, _, _ = make_service(mode=mode, runner=runner)
    ticket = _ticket(service, 'positional_campaign_rehearse', {'leg_count': '8'})
    started = service.execute_action(ticket['ticket_id'])
    assert runner.entered.wait(2), 'Registered diagnostic was not entered'
    assert len(runner.calls) == 1
    # A reload/status poll is read-only; the same consumed ticket cannot launch
    # a replacement worker, either while running or after cancellation.
    service.view()
    service.operation(started['operation_id'])
    assert service.execute_action(ticket['ticket_id'])['operation_id'] == started['operation_id']
    stop = _ticket(service, 'stop_operation')
    assert 'not a robot emergency stop' in ' '.join(stop['effects'])
    stopped = service.execute_action(stop['ticket_id'])
    assert _complete(service, stopped['operation_id'])['status'] == 'SUCCEEDED'
    operation = _complete(service, started['operation_id'])
    assert operation['status'] == 'CANCELLED'
    assert operation['result']['physical_authority'] is False
    assert service.execute_action(ticket['ticket_id'])['operation_id'] == started['operation_id']
    exported = _run(service, 'export_logs')
    assert exported['status'] == 'SUCCEEDED'
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained = json.loads((folder / (
        'attachment-result-' + started['operation_id'].removeprefix('operation-') + '.json')).read_bytes())
    assert retained['status'] == 'CANCELLED'
    assert retained['physical_authority'] is False
    assert len(runner.calls) == 1


def test_concurrent_campaign_ticket_submission_dispatches_once(make_service):
    from concurrent.futures import ThreadPoolExecutor
    from test_arrival_wizard_service import FakeRunner, _complete
    runner = FakeRunner(blocked=True)
    service, _, _ = make_service(runner=runner)
    ticket = _ticket(service, 'positional_campaign_rehearse')
    def submit():
        return service.execute_action(ticket['ticket_id'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: submit(), range(2)))
    assert len({receipt['operation_id'] for receipt in receipts}) == 1
    assert runner.entered.wait(2)
    _run(service, 'stop_operation')
    assert _complete(service, receipts[0]['operation_id'])['status'] == 'CANCELLED'
    assert len(runner.calls) == 1


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_public_campaign_and_export_are_simulation_only(make_service,mode):
    service,runner,_ = make_service(mode=mode)
    runner.run = lambda action,values,**kw: run(WORKSPACE,action,values,kw['cell_id'])
    ticket = _ticket(service,'positional_campaign_rehearse')
    assert 'Simulation only' in ' '.join(ticket['effects'])
    operation = _run(service,'positional_campaign_rehearse',dict(leg_count='4',fault='NO_RESPONSE',fault_leg='2'))
    assert operation['status'] == 'SUCCEEDED', operation
    report = operation['result']['steps'][0]['report']
    assert report['status'] == 'SIMULATION_HELD'
    assert report['skipped_leg_ids'] == ['leg-03','leg-04']
    assert operation['result']['motion_command_count'] == 0
    exported = _run(service,'export_logs')
    assert exported['status'] == 'SUCCEEDED', exported
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained = json.loads((folder/f"attachment-result-{operation['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert verify_rehearsal_report(retained['steps'][0]['report'])['valid']
    assert verify_campaign_journal_export(retained['steps'][1]['report']['bundle'],
        retained['steps'][0]['report'])['valid']


@pytest.mark.parametrize('fault,commands,verified', [('NONE', 2, 2), ('NO_RESPONSE', 1, 0)])
def test_two_endpoint_milestone_preview_start_verify_export(make_service, fault, commands, verified):
    """Exact immediate milestone through service actions and real rehearsal worker.

    Does not stand in for the separately required native/physical demonstration.
    """
    from test_arrival_wizard_service import _complete
    service, runner, _ = make_service()
    calls = []
    def actual_worker(action, values, **kwargs):
        calls.append(action)
        return run(WORKSPACE, action, values, kwargs['cell_id'])
    runner.run = actual_worker
    ticket = _ticket(service, 'positional_campaign_rehearse',
        dict(pattern='OUT_AND_BACK', leg_count='2', fault=fault, fault_leg='1'))
    assert len([line for line in ticket['effects'] if line.startswith('leg-')]) == 2
    assert not calls
    receipt = service.execute_action(ticket['ticket_id'])
    assert service.execute_action(ticket['ticket_id'])['operation_id'] == receipt['operation_id']
    operation = _complete(service, receipt['operation_id'])
    assert operation['status'] == 'SUCCEEDED'
    report = operation['result']['steps'][0]['report']
    assert report['simulated_write_count'] == commands
    assert sum(leg['status'] == 'LEG_VERIFIED' for leg in report['legs']) == verified
    assert report['skipped_leg_ids'] == ([] if fault == 'NONE' else ['leg-02'])
    assert all(leg['baseline'] and leg['post'] and leg['endpoint'] for leg in report['legs'])
    assert not report['physical_write_count'] and not report['native_execution_available']
    exported = _run(service, 'export_logs')
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    original = json.loads((folder/f"attachment-result-{receipt['operation_id'].removeprefix('operation-')}.json").read_bytes())
    retained = original['steps'][0]['report']
    assert retained == report
    assert verify_rehearsal_report(retained)['valid']
    assert verify_campaign_journal_export(original['steps'][1]['report']['bundle'], retained)['valid']
    service.view()  # Read-only reload and an old Start ticket cannot replay.
    assert service.execute_action(ticket['ticket_id'])['operation_id'] == receipt['operation_id']
    assert calls.count('positional_campaign_rehearse') == 1


@pytest.mark.parametrize('pattern,count', [
    ('OUT_AND_BACK', '2'), ('OUT_AND_BACK', '8'),
    ('OPPOSITE_APPROACH', '4'), ('OPPOSITE_APPROACH', '8'),
])
def test_preview_enumerates_exact_finite_route_without_execution(make_service, pattern, count):
    from math import degrees
    from rocell.motion.positional_campaign import compile_wrist_campaign
    service, runner, _ = make_service()
    preview = _ticket(service, 'positional_campaign_rehearse',
        dict(pattern=pattern, leg_count=count, fault='NONE', fault_leg='1'))
    plan = compile_wrist_campaign(pattern, int(count))
    effects = preview['effects']
    assert 'Exact plan SHA-256: ' + plan.sha256 in effects
    leg_effects = [line for line in effects if line.startswith('leg-')]
    assert leg_effects == [
        f"{leg['leg_id']}: expected start {degrees(leg['expected_start_rad']):.3f} degrees "
        f"-> absolute target {degrees(leg['target_rad']):.3f} degrees."
        for leg in plan.to_dict()['legs']]
    assert any(f'At most {count} simulated commands' in line and 'physical commands: 0' in line
               for line in effects)
    assert any('0.5 degrees' in line and '200 ms' in line for line in effects)
    assert not runner.calls


@pytest.mark.parametrize('values',[
    {'pattern':'OPPOSITE_APPROACH','leg_count':'2'}, {'fault_leg':'8'},
    {'leg_count':'100'}, {'raw_command':'{}'}, {'mode':'UNATTENDED'},
])
def test_invalid_inputs_cannot_create_ticket(make_service,values):
    service,runner,_ = make_service()
    with pytest.raises(Exception): _ticket(service,'positional_campaign_rehearse',values)
    assert not runner.calls


def test_registered_owned_pipeline_suite_has_no_user_selected_paths(monkeypatch):
    import pytest as runner
    calls=[]
    monkeypatch.setattr(runner,'main',lambda args: calls.append(args) or 0)
    result=run(WORKSPACE,'positional_campaign_boundary_tests',{},'CELL-A')
    assert result['status']=='SUCCEEDED'
    assert result['motion_command_count']==0
    targets=result['steps'][0]['report']['test_files']
    assert 'test_positional_owned_campaign.py' in targets
    assert 'test_positional_campaign_capture.py' in targets
    assert 'test_positional_campaign_native_protocol.py' in targets
    assert 'test_positional_campaign_launch.py' in targets
    assert 'test_positional_campaign_receipt.py' in targets
    assert 'test_positional_campaign_serial_api.py' in targets
    assert 'test_positional_campaign_serial_connection.py' in targets
    assert 'test_positional_campaign_native_capture.py' in targets
    assert 'test_positional_campaign_native_review.py' in targets
    assert 'test_positional_campaign_native_retention.py' in targets
    assert 'test_positional_campaign_native_export.py' in targets
    assert 'test_positional_campaign_child_execution.py' in targets
    assert 'test_positional_campaign_native_package.py' in targets
    assert 'test_positional_campaign_reference_reader.py' in targets
    assert 'test_positional_campaign_invocation.py' in targets
    assert 'test_positional_campaign_native_registration.py' in targets
    assert 'test_positional_campaign_process_codec.py' in targets
    assert 'test_positional_campaign_process_owner.py' in targets
    assert 'test_positional_campaign_bootstrap.py' in targets
    assert 'test_positional_campaign_prelaunch.py' in targets
    assert 'test_positional_stop_assessment.py' in targets
    assert 'test_positional_stop_reconstruction.py' in targets
    assert 'test_positional_campaign_reconstruction.py' in targets
    assert 'test_positional_campaign_export.py' in targets
    assert 'test_servo_freshness_proposal.py' in targets
    assert 'test_wrist_correction_proposal.py' in targets
    assert 'test_wrist_correction_preview.py' in targets
    assert 'test_wrist_correction_review_authority.py' in targets
    assert 'test_wrist_correction_consumption.py' in targets
    assert 'test_wrist_correction_result_review.py' in targets
    assert 'test_wrist_correction_result_publication.py' in targets
    assert 'test_wizard_wrist_correction_rehearsal.py' in targets
    assert 'test_wrist_correction_plan_binding.py' in targets
    assert 'test_wrist_correction_current_context.py' in targets
    assert 'test_wrist_correction_command_binding.py' in targets
    assert 'test_wrist_correction_serial_api.py' in targets
    assert 'test_wrist_correction_serial_connection.py' in targets
    assert 'test_wrist_correction_capture.py' in targets
    assert 'test_wrist_correction_owned_trial.py' in targets
    assert 'test_wrist_correction_native_protocol.py' in targets
    assert 'test_wrist_correction_evidence_store.py' in targets
    assert 'test_wrist_correction_worker_claim.py' in targets
    assert 'test_wrist_correction_trial_execution.py' in targets
    assert 'test_wrist_correction_native_result.py' in targets
    assert 'test_wrist_correction_parent_review.py' in targets
    assert 'test_wrist_correction_native_package.py' in targets
    assert 'test_wrist_correction_native_registration.py' in targets
    assert 'test_wrist_correction_prelaunch.py' in targets
    assert 'test_wrist_correction_child_execution.py' in targets
    assert 'test_wrist_correction_invocation.py' in targets
    assert 'test_wrist_correction_parent_retention.py' in targets
    assert 'test_wrist_correction_process_finalization.py' in targets
    assert 'test_wrist_correction_process_owner.py' in targets
    assert 'test_wrist_correction_worker_preparation.py' in targets
    assert 'test_wrist_correction_export.py' in targets
    assert 'test_wizard_wrist_correction_coordinator.py' in targets
    assert 'test_wrist_correction_saved_sources.py' in targets
    assert 'test_wizard_saved_wrist_correction.py' in targets
    assert 'test_wrist_correction_assessment_binding.py' in targets
    assert 'test_wizard_wrist_correction_http.py' in targets
    assert 'test_wrist_correction_final_readback.py' in targets
    assert 'test_wrist_correction_final_capture.py' in targets
    assert 'test_wrist_correction_owned_final_capture.py' in targets
    assert 'test_wrist_correction_final_review.py' in targets
    assert 'test_wrist_correction_final_consumption.py' in targets
    assert 'test_wrist_correction_final_dispatch.py' in targets
    assert 'test_wrist_correction_final_result_review.py' in targets
    assert 'test_wizard_positional_campaign_native.py' in targets
    assert 'test_wizard_positional_campaign_execution.py' in targets
    assert 'test_arm_controller_metadata_windows.py' in targets
    assert 'test_campaign_pinned_retention.py' in targets
    assert 'test_positional_campaign_capacity_v3.py' in targets
    assert len(targets)==78
    assert calls[0][-3:]==['-q','-p','no:cacheprovider']
    with pytest.raises(ValueError):
        run(WORKSPACE,'positional_campaign_boundary_tests',{'path':'arbitrary.py'},'CELL-A')


def test_full_suite_budget_is_explicit_and_does_not_extend_motion_windows():
    from rocell.application.wizard_actions import ACTION_BY_ID
    from rocell.application.first_motion_contract import fixed_limits
    action=ACTION_BY_ID['positional_campaign_boundary_tests']
    assert action.worker=='positional_boundary_tests' and action.timeout_s==180
    assert not action.fields
    assert fixed_limits()['maximum_write_ms']==1000
    assert fixed_limits()['maximum_post_observation_ms']==5000


def test_public_owned_pipeline_suite_and_export(make_service):
    service,runner,_=make_service()
    # Public ticket execution is tested with the same fake worker used by other
    # service tests; the real subprocess suite is additionally run through HTTP.
    operation=_run(service,'positional_campaign_boundary_tests')
    assert operation['status']=='SUCCEEDED'
    assert len(runner.calls)==1
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
