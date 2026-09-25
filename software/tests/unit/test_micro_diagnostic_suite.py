from rocell.application.micro_diagnostic_suite import run_suite
from test_arrival_wizard_service import make_service, _run, _ticket


def test_suite_has_no_native_authority():
    report=run_suite()
    assert report['status']=='SUCCEEDED' and len(report['checks'])==17
    assert all(check['passed'] for check in report['checks'])
    assert not report['hardware_access'] and report['motion_commands']==0
    assert not report['native_micro_enabled']


def test_wizard_preview_execute_and_export_without_runner(make_service):
    service,runner,_=make_service(mode='physical')
    _ticket(service,'simulate_micro_correction',{})
    assert not runner.calls
    result=_run(service,'simulate_micro_correction')
    assert result['status']=='SUCCEEDED',result
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED',exported
    assert not runner.calls
