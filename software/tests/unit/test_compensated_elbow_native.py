from contextlib import contextmanager
import pytest
from rocell.providers.windows import compensated_elbow_native as native
from rocell.kinematics.firmware_reference import forward


def baseline(elbow=1.529378846):
    joints=[.001533981,0,elbow,.053689328,.01994175,3.138524692]
    return dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
        joints_rad=dict(zip(('b','s','e','t','r','g'),joints)),
        controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),forward(*joints[:4])))))


def test_tested_posture_and_continuity():
    assert native.validate_cycle_baseline(baseline(),3)['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    b=baseline(1.552388557); previous=list(b['joints_rad'].values())
    assert native.validate_cycle_baseline(b,-6,previous)['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    previous[2]+=.001
    with pytest.raises(ValueError): native.validate_cycle_baseline(b,-6,previous)
    b=baseline(); b['joints_rad']['r']+=.01
    with pytest.raises(ValueError): native.validate_cycle_baseline(b,3)


def test_native_rejection_is_published_under_lock_without_send(monkeypatch,tmp_path):
    events=[]
    @contextmanager
    def lock():
        events.append('lock')
        yield
        events.append('unlock')
    monkeypatch.setattr(native,'arm_transport_lock',lock)
    monkeypatch.setattr(native,'bounded_probe',lambda **kw:baseline(1.6))
    def forbidden(**kw): raise AssertionError('No reservation after rejected baseline')
    monkeypatch.setattr(native,'WifiCartesianReservation',forbidden)
    def publish(**kw):
        assert events==['lock']
        assert kw['report']['status']=='HELD_BEFORE_DISPATCH'
        events.append('publish')
        return dict(export='rejected-leg',verified=True)
    result=native.run_native_cycle(root=tmp_path,publish_leg=publish)
    assert result['status']=='LEG_NOT_VERIFIED'
    assert events==['lock','publish','unlock']


def test_native_cancellation_prevents_probe(monkeypatch,tmp_path):
    from contextlib import nullcontext
    monkeypatch.setattr(native,'arm_transport_lock',nullcontext)
    def forbidden(**kw): raise AssertionError('No probe after cancellation')
    monkeypatch.setattr(native,'bounded_probe',forbidden)
    result=native.run_native_cycle(root=tmp_path,publish_leg=forbidden,cancelled=lambda:True)
    assert result['status']=='CANCELLED_BEFORE_NEXT_LEG'
