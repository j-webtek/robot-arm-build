from pathlib import Path
import json
import pytest
from test_arrival_wizard_service import make_service,_run,_ticket
from test_wrist_correction_saved_sources import saved
from rocell.application.wizard_diagnostic_export import verify_export


def test_saved_assessment_action_and_log_export(make_service,monkeypatch):
    service,runner,_=make_service()
    service.export_directory.mkdir(exist_ok=True)
    attempts=saved(service.export_directory,monkeypatch)
    values=dict(attempt_ids='\n'.join(attempts))
    ticket=_ticket(service,'assess_saved_wrist_correction',values)
    assert 'no device' in ' '.join(ticket['effects'])
    operation=_run(service,'assess_saved_wrist_correction',values)
    assert operation['status']=='SUCCEEDED',operation
    assert operation['result']['motion_command_count']==0 and not runner.calls
    report=operation['result']['steps'][0]['report']
    assert not report['motion_authorized']
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED',exported
    assert verify_export(Path(exported['result']['receipt']['path']))['valid']


def test_match_retained_assessment_to_reviewed_controller(make_service,monkeypatch):
    service,runner,matched,controller,source,attempts=matched_fixture(make_service,monkeypatch)
    binding=matched['result']['steps'][0]['report']['binding']
    assert binding['controller_sha256']==controller.binding_sha256
    assert not binding['current_connection_verified'] and matched['result']['motion_command_count']==0
    assert not runner.calls


def matched_fixture(make_service,monkeypatch):
    from test_endpoint_current_context import fixture
    from rocell.application.first_motion_contract import canonical
    service,runner,_=make_service(mode='physical')
    service.export_directory.mkdir(exist_ok=True)
    _,_,_,controller=fixture()
    source=service.retain_reviewed_observational_sources(controller_binding=controller,
        protocol_original=canonical({'fixture':'protocol'}),label='Fixture controller')
    attempts=saved(service.export_directory,monkeypatch,fault='miss')
    assessed=_run(service,'assess_saved_wrist_correction',dict(attempt_ids='\n'.join(attempts)))
    assert assessed['status']=='SUCCEEDED',assessed
    matched=_run(service,'bind_saved_wrist_correction',dict(assessment_operation_id=assessed['operation_id'],source_id=source['source_id']))
    assert matched['status']=='SUCCEEDED',matched
    return service,runner,matched,controller,source,attempts


def test_stage_runtime_from_binding_without_hardware(make_service,monkeypatch):
    service,runner,matched,_,_,_=matched_fixture(make_service,monkeypatch)
    operation=_run(service,'stage_wrist_correction',dict(binding_operation_id=matched['operation_id']))
    assert operation['status']=='SUCCEEDED',operation
    report=operation['result']['steps'][0]['report']
    config=service._wrist_correction_configuration
    assert config['staged'].attempt_id==report['attempt_id']
    assert report['attempt_id']!=operation['operation_id']  # execution must not overwrite setup history
    assert (config['staged'].registration.working_directory/'runtime.original.json').is_file()
    assert not report['motion_authorized'] and not report['execution_enabled']
    assert report['final_review_required'] and report['fresh_baseline_required']
    assert operation['result']['device_open_count']==operation['result']['motion_command_count']==0
    assert not list(service._log.root.glob('*-launch.json')) and not runner.calls
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED',exported
    assert verify_export(Path(exported['result']['receipt']['path']))['valid']


@pytest.mark.parametrize('fault',['binding','assessment','controller','protocol','trial'])
def test_stage_rejects_changed_evidence_and_clears_prior_setup(make_service,monkeypatch,fault):
    service,runner,matched,_,source,attempts=matched_fixture(make_service,monkeypatch)
    values=dict(binding_operation_id=matched['operation_id'])
    assert _run(service,'stage_wrist_correction',values)['status']=='SUCCEEDED'
    report=matched['result']['steps'][0]['report']
    paths=dict(binding=service._log.root/(matched['operation_id']+'-bound-wrist-correction.json'),
        assessment=service._log.root/(report['assessment_operation_id']+'-saved-wrist-correction-assessment.json'),
        controller=service._log.root/(source['source_id']+'-controller.json'),
        protocol=service._log.root/(source['source_id']+'-protocol.json'),
        trial=service.export_directory/(attempts[0]+'-absolute-wrist-stdout.original.json'))
    paths[fault].write_bytes(b'{}')
    failed=_run(service,'stage_wrist_correction',values)
    assert failed['status']=='FAILED',failed
    assert service._wrist_correction_configuration is None and not runner.calls


def test_stage_rechecks_evidence_after_package_creation(make_service,monkeypatch):
    from rocell.application import wrist_correction_worker_preparation as preparation
    service,runner,matched,_,source,_=matched_fixture(make_service,monkeypatch)
    original=preparation.stage_correction_runtime
    def changed(*args,**kwargs):
        staged=original(*args,**kwargs)
        (service._log.root/(source['source_id']+'-protocol.json')).write_bytes(b'{}')
        return staged
    monkeypatch.setattr(preparation,'stage_correction_runtime',changed)
    failed=_run(service,'stage_wrist_correction',dict(binding_operation_id=matched['operation_id']))
    assert failed['status']=='FAILED',failed
    assert service._wrist_correction_configuration is None and not runner.calls
    assert not list(service._log.root.glob('*-launch.json'))


def ready_correction(make_service,monkeypatch):
    from rocell.safety.observational_review_authority import CHECKS
    service,runner,matched,_,source,attempts=matched_fixture(make_service,monkeypatch)
    staged=_run(service,'stage_wrist_correction',dict(binding_operation_id=matched['operation_id']))
    assert staged['status']=='SUCCEEDED',staged
    monkeypatch.setattr(service,'_powered_setup_context',lambda:{'fixture':'powered'})
    values=dict(operator_id='fixture-operator',**{name:True for name in CHECKS})
    return service,runner,staged,values,source,attempts


@pytest.mark.parametrize('endpoint,stage,expected',[
    ('REPORTED_SETTLED','EXPORTED','SUCCEEDED'),
    ('TARGET_MISSED','EXPORTED','FAILED'),
    ('HELD_PROCESS_OR_CLEANUP','EXPORTED','FAILED'),
    ('REPORTED_SETTLED','EXPORT_FAILED','FAILED'),
    (None,'EXPORTED','FAILED')])
def test_reviewed_correction_one_use_and_endpoint_status(make_service,monkeypatch,endpoint,stage,expected):
    from types import SimpleNamespace
    from rocell.application import wizard_wrist_correction_coordinator as coordinator
    from rocell.application.wizard_actions import WizardError
    service,runner,staged,values,_,_=ready_correction(make_service,monkeypatch)
    calls=[]
    def confirm(workspace,runtime,**kwargs):
        confirmation=service._wrist_correction_confirmation
        assert kwargs['accepted_ns']==confirmation[2]<=kwargs['now_ns']
        assert tuple(kwargs['originals'])==confirmation[1]['bound'].originals
        calls.append('confirm')
        return object(),b'fixture-only'
    def run(workspace,runtime,request,**kwargs):
        kwargs['check_current']()
        calls.append('run')
        verdict=None if endpoint is None else dict(schema='rocell.wrist_correction_process_finalization.v1',status=endpoint)
        return SimpleNamespace(stage=stage,owned=SimpleNamespace(parsed_result=verdict),report={'fixture':True},error_type=None)
    monkeypatch.setattr(coordinator,'confirm_correction_run',confirm)
    monkeypatch.setattr(coordinator,'run_reviewed_correction',run)
    operation=_run(service,'run_wrist_correction',values)
    assert operation['status']==expected,operation
    assert calls==['confirm','run'] and not runner.calls
    assert operation['operation_id']==staged['result']['steps'][0]['report']['attempt_id']
    assert service.operation(staged['operation_id'])['action_id']=='stage_wrist_correction'
    with pytest.raises(WizardError):
        _ticket(service,'run_wrist_correction',values)


def test_correction_changed_after_preview_is_not_accepted(make_service,monkeypatch):
    from rocell.application.wizard_actions import WizardError
    service,runner,_,values,_,attempts=ready_correction(make_service,monkeypatch)
    ticket=_ticket(service,'run_wrist_correction',values)
    (service.export_directory/(attempts[0]+'-absolute-wrist-stdout.original.json')).write_bytes(b'{}')
    with pytest.raises((WizardError,ValueError)):
        service.execute_action(ticket['ticket_id'])
    assert service._wrist_correction_confirmation is None and not runner.calls


@pytest.mark.parametrize('valid',[True,False])
def test_correction_dom_shows_separate_targets_or_missing_preview(valid):
    from test_arrival_wizard_reopen_ui import browser,commissioning,ReopenService
    from test_arrival_wizard_terminal import action
    preview=dict(schema='rocell.wizard_wrist_correction_runtime.v1',nominal_target_deg=0,
        experimental_motor_target_deg=-0.966796875,binding_sha256='a'*64,runtime_sha256='b'*64,
        spd=20,acc=1,fresh_baseline_required=True,return_motion=False,retry_allowed=False)
    selected=action('run_wrist_correction',fields=[])
    selected.update(section='commissioning',correction_preview=preview if valid else None)
    snapshot=ReopenService(commissioning()).view()
    snapshot.update(camera={},arm={},stages=[],operations=[],actions=[selected])
    result=browser(commissioning(),snapshot=snapshot)
    assert 'Experimental correction' in result['allText']
    if valid:
        assert 'Desired endpoint: 0 degrees. Experimental motor command: -0.966796875 degrees.' in result['allText']
    else:
        assert 'No valid prepared correction preview' in result['allText']
    assert all(item['method']=='GET' for item in result['requests'])
