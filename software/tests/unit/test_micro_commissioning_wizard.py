"""Wizard tests replace the native entry point; no physical command is issued."""
import threading
import pytest
from test_arrival_wizard_service import make_service,_ticket,_run,_complete
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows import micro_commissioning_native as native

ACTION='run_micro_commissioning'
VALUES=dict(exclusive_controller_declared=True)


@pytest.mark.parametrize('values',[{},dict(exclusive_controller_declared=False),
                                 dict(exclusive_controller_declared='true')])
def test_declaration_required_without_provider_calls(make_service,monkeypatch,values):
    service,runner,_=make_service(mode='physical')
    def forbidden(**kwargs):raise AssertionError('native called')
    monkeypatch.setattr(native,'run_native_micro_commissioning',forbidden)
    with pytest.raises(WizardError):_ticket(service,ACTION,values)
    assert not runner.calls


@pytest.mark.parametrize('status,expected',[('NO_CORRECTION_NEEDED','SUCCEEDED'),
    ('EXPERIMENT_VERIFIED','SUCCEEDED'),('STOPPED','FAILED')])
def test_preview_execute_export_and_owned_results(make_service,monkeypatch,status,expected):
    service,runner,_=make_service(mode='physical');calls=[]
    def fake(**kwargs):
        calls.append(kwargs);kwargs['check_current']()
        assert kwargs['exclusive_controller_declared'] is True
        assert not kwargs['cancelled']()
        return dict(status=status,reason='TEST',exports=[],final_export_succeeded=True)
    monkeypatch.setattr(native,'run_native_micro_commissioning',fake)
    _ticket(service,ACTION,VALUES)
    assert not calls and not runner.calls
    operation=_run(service,ACTION,VALUES)
    assert operation['status']==expected,operation
    assert len(calls)==1 and not runner.calls
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    with pytest.raises(WizardError):service._validated_result(ACTION,dict(action_id=ACTION,status='SUCCEEDED'))


def test_cancel_reaches_native_coordinator(make_service,monkeypatch):
    service,_,_=make_service(mode='physical');started=threading.Event();observed=[]
    def fake(**kwargs):
        started.set()
        for _ in range(200):
            if kwargs['cancelled']():
                observed.append(True);break
            threading.Event().wait(.005)
        return dict(status='STOPPED',reason='CANCELLED',exports=[])
    monkeypatch.setattr(native,'run_native_micro_commissioning',fake)
    ticket=_ticket(service,ACTION,VALUES);operation=service.execute_action(ticket['ticket_id'])
    assert started.wait(2)
    stop=_ticket(service,'stop_operation',{})
    service.execute_action(stop['ticket_id'])
    _complete(service,operation['operation_id'])
    assert observed
