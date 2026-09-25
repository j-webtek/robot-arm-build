from pathlib import Path

from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render
from test_startup_command_contract import fixture, BOOT
from rocell.application.startup_command_contract import freeze_startup_plan
from rocell.application.startup_planned_run import collect_startup_run


def test_wizard_replays_failed_collection_without_qualifying_hardware(make_service):
    service, runner, _ = make_service(mode='physical')
    normal, policy, _ = fixture()
    def failed_reader(path, **kwargs): raise TimeoutError()
    saved = collect_startup_run(service.export_directory, failed_reader,
        freeze_startup_plan(normal, policy), boot_id=BOOT, approved_policy=policy)
    operation = _run(service, 'review_startup_servo_run',
        {'export_id': Path(saved['export_path']).name})
    assert operation['status'] == 'SUCCEEDED', operation
    report = operation['result']['steps'][0]['report']
    assert report['schema'] == 'rocell.startup_run_review.v1'
    assert report['replay_verified'] and report['outcome']['status'] == 'INCONCLUSIVE'
    page = render(operation)
    assert 'Startup command and endpoint' in page
    assert 'Inconclusive' in page and 'endpoint not verified' in page and 'NOT QUALIFIED' in page
    assert not runner.calls and service.view()['arm']['status'] == 'NOT_CONNECTED'


def test_missing_startup_export_fails_review(make_service):
    service, runner, _ = make_service(mode='physical')
    operation = _run(service, 'review_startup_servo_run', {'export_id': 'wizard-missing'})
    assert operation['status'] != 'SUCCEEDED'
    assert not runner.calls


def test_linked_startup_review_keeps_delivery_distinct(make_service,monkeypatch):
    from test_startup_prepared_start import inputs,fake_socket
    from test_startup_command_contract import KEY
    from rocell.application.startup_prepared_start import StartupStartSender,send_prepared_startup
    from rocell.application.startup_started_run import collect_started_startup
    service,runner,_=make_service(mode='physical')
    calls,_=fake_socket(monkeypatch,lost=True)
    plan,policy,challenge,_=inputs()
    prepared=send_prepared_startup(service.export_directory,StartupStartSender('127.0.0.1',8081,policy),
        plan,challenge,KEY,approved_policy=policy)
    def reader(*args,**kwargs):raise TimeoutError()
    linked=collect_started_startup(service.export_directory,Path(prepared['export_path']).name,reader)
    operation=_run(service,'review_started_startup_run',{'export_id':Path(linked['export_path']).name})
    assert operation['status']=='SUCCEEDED',operation
    page=render(operation)
    assert 'DELIVERY_UNCERTAIN' in page and 'INCONCLUSIVE' in page and 'NOT QUALIFIED' in page
    assert 'Controller acceptance does not verify arrival' in page
    assert calls.count('send')==1 and not runner.calls


def test_startup_assessment_rendering_separates_arrival_from_qualification():
    assessment = dict(schema='rocell.startup_session_assessment.v1',
        category='DIAGNOSTIC_ENDPOINT_CRITERIA_MET', progression_authority=False,
        provenance_verified=False, physical_accuracy_verified=False,
        startup_evidence_verified=True, initial_elbow_position=2128, command_delta_counts=4,
        startup_plan_sha256='a'*64)
    report = dict(schema='rocell.startup_run_review.v1', export_id='test-render-only',
        replay_verified=True, hardware_access=False, progression_authority=False,
        outcome=dict(status='ASSESSED', assessment=assessment))
    operation = dict(action_id='review_startup_servo_run', result=dict(steps=[dict(report=report)]))
    page = render(operation)
    assert 'DIAGNOSTIC_ENDPOINT_CRITERIA_MET' in page and 'NOT QUALIFIED' in page
    assert '2128' in page and 'Not measured' in page
    assessment['progression_authority'] = True
    assert 'unavailable or inconsistent' in render(operation)
