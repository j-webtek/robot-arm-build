from pathlib import Path
import pytest
from test_arrival_wizard_service import make_service,_run,_ticket
from rocell.application.servo_diagnostic_rehearsal import replay_rehearsal
from rocell.application.wizard_actions import WizardError


@pytest.mark.parametrize('scenario',['arrival','stationary','reboot','paired_arrival','paired_stale_read'])
def test_service_action_exports_without_hardware(make_service,scenario):
    service,runner,_=make_service(mode='physical')
    _ticket(service,'simulate_servo_diagnostics',{'scenario':scenario})
    assert not service.export_directory.exists() and not runner.calls
    result=_run(service,'simulate_servo_diagnostics',{'scenario':scenario})
    assert result['status']=='SUCCEEDED',result
    report=result['result']['steps'][0]['report']
    path=Path(report['export']['path'])
    assert replay_rehearsal(path.parent,path.name)['matches']
    assert not report['progression_authority'] and report['motion_commands']==0
    if scenario=='reboot':assert report['outcome']['status']=='TRACE_REJECTED'
    assert service.view()['arm']['status']=='NOT_CONNECTED'
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert not runner.calls


def test_unknown_scenario_rejected_before_execution(make_service):
    service,runner,_=make_service(mode='physical')
    with pytest.raises(WizardError):_ticket(service,'simulate_servo_diagnostics',{'scenario':'native'})
    assert not runner.calls
