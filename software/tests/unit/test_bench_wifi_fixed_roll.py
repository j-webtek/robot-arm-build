"""Bench display tests use no physical service or hardware."""
import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('bench_roll',
    Path(__file__).resolve().parents[2]/'scripts'/'bench_wifi_fixed_roll.py')
bench=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


@pytest.mark.parametrize('result',[None,{},dict(steps=[]),dict(steps=[dict(report={})])])
def test_absent_report_is_not_endpoint_success(result):
    summary=bench.summarize_operation(dict(operation_id='test',action_id='test',status='FAILED',result=result))
    assert summary['status']=='FAILED'
    assert summary['final_deg'] is None and summary['error_deg'] is None


def test_uncertain_first_feedback_has_no_endpoint():
    outcome=dict(command_send_attempted=True,error='TRANSACTION_INTERRUPTED_OR_UNCERTAIN',
        transaction=dict(state='COMMAND_OUTCOME_UNCERTAIN',result=None,rows=[]))
    summary=bench.summarize_operation(dict(operation_id='test',action_id='test',status='FAILED',
        result=dict(steps=[dict(report=dict(outcome=outcome))])))
    assert summary['transaction_state']=='COMMAND_OUTCOME_UNCERTAIN'
    assert summary['command_send_attempted'] is True
    assert summary['final_deg'] is None and summary['error_deg'] is None


def test_failed_move_only_exports_and_shuts_down(monkeypatch,capsys):
    calls=[]
    class Service:
        def __init__(self,*a,**k):pass
        def view(self):return dict(revision=1)
        def prepare_action(self,name,*a):calls.append(name);return dict(ticket_id=name)
        def execute_action(self,ticket):return dict(operation_id=ticket)
        def operation(self,name):
            return dict(operation_id=name,action_id=name,status='SUCCEEDED' if name=='export_logs' else 'FAILED',
                result=dict(receipt=dict(path='test')) if name=='export_logs' else
                dict(steps=[dict(report=dict(outcome=dict(transaction=dict(result=None,rows=[]))))]))
        def shutdown(self):calls.append('shutdown')
    monkeypatch.setattr(bench,'ArrivalWizardService',Service)
    monkeypatch.setattr('sys.argv',['bench','high'])
    bench.main()
    assert calls==['run_wifi_roll_high_trial','export_logs','shutdown']
    assert 'FAILED' in capsys.readouterr().out
