from copy import deepcopy
import pytest
from test_wrist_shared_pair import baseline
from rocell.application.compensated_wrist_cycle import CompensatedWristCycle
from rocell.application.wrist_shared_pair import pair_candidate
from rocell.providers.windows.compensated_wrist_native import validate_cycle_baseline
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def adapters(fault=None):
    events=[]
    def leg(*,index,mode,previous_joints,cancelled):
        events.append(('run',index));b=baseline(mode);c=pair_candidate(mode)
        validate_cycle_baseline(b,mode,previous_joints)
        tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            wrist_probe='post-coordinated-ascending' if mode=='up' else 'post-coordinated',
            wrist_candidate='pair-'+mode,compensated_endpoint=True)
        tx.begin_dispatch(2);tx.acknowledge(3)
        q=list(b['joints_rad'].values());q[3]=c['desired_rad']
        for i in range(1,5):
            end=i*250_000_000;tx.observe((end-1,end,forward(*q[:4]),q),end)
        snap=tx.snapshot()
        if fault=='command':snap['command']['joint']=3
        if fault=='candidate':snap['local_candidate']['desired_rad']+=.001
        run=dict(status=snap['state'],transaction=snap,error='FAULT' if fault=='feedback' else None,
            command_send_attempted=True,acknowledgment_received=True,
            move_request=dict(configuration=dict(compensated_candidate=deepcopy(c))),
            feedback_originals=[dict(status='SUCCEEDED',cleanup_confirmed=True,
                identity_before_matched=True,identity_after_matched=True) for _ in range(4)])
        return dict(status=run['status'],run=run,receipt=dict(cleanup_confirmed=fault!='cleanup'))
    def publish(*,index,report):
        events.append(('publish',index))
        return dict(verified=fault!='export',export='leg-'+str(index))
    return leg,publish,events


def test_pair_publication_precedes_next_send_and_cycle_is_one_use():
    leg,publish,events=adapters();cycle=CompensatedWristCycle()
    assert cycle.run(run_leg=leg,publish_leg=publish)['status']=='LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED'
    assert events==[('run',0),('publish',0),('run',1),('publish',1)]
    assert cycle.run(run_leg=leg,publish_leg=publish)['status']=='CYCLE_ALREADY_USED'


@pytest.mark.parametrize('fault',['feedback','command','candidate','cleanup','export'])
def test_first_leg_failure_stops_pair(fault):
    leg,publish,events=adapters(fault)
    r=CompensatedWristCycle().run(run_leg=leg,publish_leg=publish)
    assert r['status'] in ('LEG_NOT_VERIFIED','EXPORT_NOT_VERIFIED')
    assert ('run',1) not in events


def test_cancellation_after_export_stops_pair():
    leg,publish,events=adapters()
    r=CompensatedWristCycle().run(run_leg=leg,publish_leg=publish,cancelled=lambda:('publish',0) in events)
    assert r['status']=='CANCELLED_BEFORE_NEXT_LEG'


def test_fresh_pose_continuity_rejects_drift():
    b=baseline('up');q=list(b['joints_rad'].values());q[3]+=.001
    with pytest.raises(ValueError):validate_cycle_baseline(b,'up',q)


def test_native_rejects_and_publishes_under_lock_without_send(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from rocell.providers.windows import compensated_wrist_native as native
    events=[]
    @contextmanager
    def lock():
        events.append('lock');yield;events.append('unlock')
    b=baseline('up')  # Wrong first-leg posture.
    monkeypatch.setattr(native,'arm_transport_lock',lock)
    monkeypatch.setattr(native,'bounded_probe',lambda **kw:b)
    def forbidden(**kw):raise AssertionError('No dispatch after rejected posture')
    monkeypatch.setattr(native,'WifiCartesianReservation',forbidden)
    def publish(**kw):
        assert events==['lock'];events.append('publish')
        return dict(verified=True,export='rejected')
    assert native.run_native_cycle(root=tmp_path,publish_leg=publish)['status']=='LEG_NOT_VERIFIED'
    assert events==['lock','publish','unlock']


def test_native_cancel_does_not_probe(monkeypatch,tmp_path):
    from contextlib import nullcontext
    from rocell.providers.windows import compensated_wrist_native as native
    monkeypatch.setattr(native,'arm_transport_lock',nullcontext)
    def forbidden(**kw):raise AssertionError('No I/O after cancellation')
    monkeypatch.setattr(native,'bounded_probe',forbidden)
    assert native.run_native_cycle(root=tmp_path,publish_leg=forbidden,cancelled=lambda:True)['status']=='CANCELLED_BEFORE_NEXT_LEG'
