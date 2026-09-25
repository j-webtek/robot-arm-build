import pytest
from rocell.providers.windows.arm_wifi_feedback import sample_feedback
from test_arm_wifi_feedback import Connection, run
from test_arrival_wizard_service import make_service, _run, _ticket


def test_eight_only_and_no_movement():
    calls=[]
    def sample(**kw):
        calls.append(1)
        return run(Connection())
    r=sample_feedback(run_probe=sample)
    assert r['status']=='SUCCEEDED' and len(calls)==8
    assert r['request_attempts']==8 and len(r['response_completion_gaps_ms'])==7
    assert all(v==0 for v in r['reported_joint_span_rad'].values())
    assert not r['freshness_verified'] and not r['movement_ready']


@pytest.mark.parametrize('fault_index',[0,3,7])
def test_fault_stops_without_retry(fault_index):
    calls=[]
    def sample(**kw):
        i=len(calls);calls.append(i)
        return run(Connection(status=500 if i==fault_index else 200))
    r=sample_feedback(run_probe=sample)
    assert r['stop_reason']=='FIRST_FAULT'
    assert len(calls)==fault_index+1 and r['failed_samples']==1


def test_cancel_and_budget_prevent_dispatch():
    def forbidden(**kw):raise AssertionError('must not dispatch')
    assert sample_feedback(run_probe=forbidden,cancelled=lambda:True)['stop_reason']=='CANCELLED'
    ticks=iter([0,31,32])
    assert sample_feedback(run_probe=forbidden,clock=lambda:next(ticks))['stop_reason']=='SESSION_BUDGET_EXCEEDED'


def test_wizard_preview_is_inert_and_export_succeeds(make_service,monkeypatch):
    calls=[]
    def sample(**kw):
        calls.append(1)
        return sample_feedback(run_probe=lambda **kw:run(Connection()))
    monkeypatch.setattr('rocell.providers.windows.arm_wifi_feedback.sample_feedback',sample)
    service,runner,_=make_service(mode='physical')
    _ticket(service,'sample_arm_wifi_feedback',{})
    assert not calls
    result=_run(service,'sample_arm_wifi_feedback')
    assert result['status']=='SUCCEEDED',result
    assert len(calls)==1 and not runner.calls
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
