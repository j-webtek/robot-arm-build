import pytest
from test_arm_wifi_observation import simulation
from test_arrival_wizard_service import make_service,_run,_ticket
from rocell.providers.windows.arm_wifi_observation import review_observation


def test_distinct_profile_and_pacing():
    old,_=simulation();fast,calls=simulation(fast=True)
    assert old['schema']=='rocell.arm_wifi_observation.v1' and old['maximum_samples']==200
    assert fast['schema']=='rocell.arm_wifi_observation.v2' and fast['maximum_samples']==400
    assert fast['status']=='SUCCEEDED' and len(calls)==350
    assert fast['elapsed_s']==pytest.approx(35)
    assert fast['reconstruction']['maximum_response_gap_ms']==pytest.approx(100)
    assert not fast['reconstruction']['movement_ready']
    assert review_observation(old)==old['reconstruction']


@pytest.mark.parametrize('at',[0,20,349])
def test_fast_first_fault_no_retry(at):
    report,calls=simulation(fault_at=at,fast=True)
    assert len(calls)==at+1 and report['status']=='FAILED'


def test_cancel_no_further_request():
    report,calls=simulation(cancel_at=4,fast=True)
    assert len(calls)==4 and report['stop_reason']=='CANCELLED'


def test_fast_export_and_inert_preview(make_service,monkeypatch):
    calls=[]
    prepared=simulation(fast=True)[0]
    def run(**kw):
        calls.append(1)
        return prepared
    monkeypatch.setattr('rocell.providers.windows.arm_wifi_observation.observe_fast',run)
    service,runner,_=make_service(mode='physical')
    _ticket(service,'observe_arm_wifi_feedback_fast',{})
    assert not calls
    result=_run(service,'observe_arm_wifi_feedback_fast')
    assert result['status']=='SUCCEEDED',str(result.get('error'))+str(result.get('result'))
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert len(calls)==1 and not runner.calls
