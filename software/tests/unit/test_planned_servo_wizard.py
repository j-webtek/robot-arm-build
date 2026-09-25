from pathlib import Path
from test_arrival_wizard_service import make_service,_run
from test_movement_campaign_ui import render
from test_servo_planned_run import inputs,idle
from rocell.application.servo_planned_run import collect_planned_run


def test_saved_rejection_review_is_not_hardware_pass(make_service):
    service,runner,_=make_service(mode='physical')
    run=collect_planned_run(service.export_directory,idle,*inputs(),origin='SIMULATION')
    operation=_run(service,'review_planned_servo_run',{'export_id':Path(run['export_path']).name})
    assert operation['status']=='SUCCEEDED',operation
    report=operation['result']['steps'][0]['report']
    assert report['replay_verified'] and report['outcome']['status']=='EVIDENCE_REJECTED'
    page=render(operation)
    assert 'Planned servo run' in page and 'NOT QUALIFIED' in page and 'Evidence rejected' in page
    assert not runner.calls
    assert service.view()['arm']['status']=='NOT_CONNECTED'


def test_missing_export_does_not_claim_review_success(make_service):
    service,runner,_=make_service(mode='physical')
    operation=_run(service,'review_planned_servo_run',{'export_id':'wizard-missing'})
    assert operation['status']!='SUCCEEDED'
    assert not runner.calls
