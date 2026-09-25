import pytest
from rocell.providers.windows.arm_wifi_observation import observe_spaced, observe_intermediate, review_observation
from rocell.providers.windows.arm_wifi_feedback import probe, MAC
from test_arm_wifi_feedback import Connection, run
from test_arrival_wizard_service import make_service, _run, _ticket


def simulate(fault_at=None, cancel_at=None, intermediate=False):
    now=[0.]; starts=[]
    def sample(**kw):
        starts.append(now[0])
        now[0]+=.3  # Slow responses must still be followed by the full cooldown.
        return probe(identity=lambda:MAC, clock=lambda:now[0],
            connection_factory=lambda *a,**k:Connection(status=500 if len(starts)==fault_at else 200),**kw)
    result=(observe_intermediate if intermediate else observe_spaced)(run_probe=sample, clock=lambda:now[0],
        wait=lambda seconds:now.__setitem__(0,now[0]+seconds),
        cancelled=lambda:cancel_at is not None and len(starts)>=cancel_at)
    return result,starts


def test_completion_cooldown_and_reconstruction():
    report,starts=simulate()
    assert report['status']=='SUCCEEDED' and report['schema']=='rocell.arm_wifi_observation.v3'
    assert report['elapsed_s']==pytest.approx(35)
    assert all(b-a==pytest.approx(.8) for a,b in zip(starts,starts[1:]))
    assert len(starts)<=70 and report['post_completion_quiet_s']==.5
    assert review_observation(report)==report['reconstruction']
    assert not report['reconstruction']['movement_ready']


@pytest.mark.parametrize('intermediate',[False,True])
def test_fault_and_cancellation_stop_without_retry(intermediate):
    report,starts=simulate(fault_at=3,intermediate=intermediate)
    assert len(starts)==3 and report['stop_reason']=='FIRST_FAULT'
    report,starts=simulate(cancel_at=3,intermediate=intermediate)
    assert len(starts)==3 and report['stop_reason']=='CANCELLED'


@pytest.mark.parametrize('body',[{'ok':1},{'error':'Queue full'}])
def test_acknowledgment_is_not_feedback(body):
    result=run(Connection(body))
    assert result['status']=='FAILED' and 'joints_rad' not in result


@pytest.mark.parametrize('intermediate',[False,True])
def test_wizard_preview_inert_and_export(make_service,monkeypatch,intermediate):
    prepared,_=simulate(intermediate=intermediate); calls=[]
    suffix='intermediate' if intermediate else 'spaced'
    def observe(**kw):
        calls.append(1)
        return prepared
    monkeypatch.setattr('rocell.providers.windows.arm_wifi_observation.observe_'+suffix,observe)
    service,runner,_=make_service(mode='physical')
    _ticket(service,'observe_arm_wifi_feedback_'+suffix,{})
    assert not calls
    result=_run(service,'observe_arm_wifi_feedback_'+suffix)
    assert result['status']=='SUCCEEDED',result
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert calls==[1] and not runner.calls


def test_intermediate_is_separate_and_waits_after_slow_response():
    report,starts=simulate(intermediate=True)
    assert report['schema']=='rocell.arm_wifi_observation.v4'
    assert report['status']=='SUCCEEDED' and len(starts)<=234
    assert report['post_completion_quiet_s']==.15
    assert all(b-a==pytest.approx(.45) for a,b in zip(starts,starts[1:]))
    assert review_observation(report)==report['reconstruction']
    assert report['motion_commands']==0 and not report['reconstruction']['movement_ready']
