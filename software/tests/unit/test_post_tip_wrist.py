import math
import pytest
from test_post_tip_elbow import source
from rocell.application.coordinated_wrist_probe import preview_post_tip_wrist
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def transaction(b, **kwargs):
    return CartesianTransaction(baseline=b,baseline_finished_ns=1,
        completion_budget_ns=3_000_000_000,wrist_probe='post-tip',**kwargs)


def test_command_arc_and_reported_arrival():
    b=source(); p=preview_post_tip_wrist(b)
    assert p['hypothetical_tip_sweep_mm']<6
    assert not p['compensation_applied']
    for s in p['samples']:
        assert all(s['joints_rad'][i]==v for i,v in enumerate(b['joints_rad'].values()) if i!=3)
    tx=transaction(b)
    assert tx.begin_dispatch(2)==dict(T=101,joint=4,rad=b['joints_rad']['t']-math.radians(1.5),spd=20,acc=1)
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'


@pytest.mark.parametrize('key',('b','s','e','t','r','g'))
def test_changed_start_rejected(key):
    b=source();b['joints_rad'][key]+=.001
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    with pytest.raises(ValueError):transaction(b)


@pytest.mark.parametrize('options',[{'wrist_candidate':True},{'wrist_prepare':True},{'compensated_endpoint':True}])
def test_no_old_corrections(options):
    with pytest.raises(ValueError):transaction(source(),**options)


def test_reverse_has_separate_exact_start_and_no_correction():
    b=source();b['joints_rad']['t']=-.072097097
    q=list(b['joints_rad'].values())
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
    p=preview_post_tip_wrist(b,reverse=True)
    assert p['hypothetical_tip_sweep_mm']<6
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-tip-reverse')
    assert tx.begin_dispatch(2)==dict(T=101,joint=4,rad=q[3]+math.radians(1.5),spd=20,acc=1)
    assert tx.snapshot()['local_candidate'] is None
    with pytest.raises(ValueError):preview_post_tip_wrist(source(),reverse=True)
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            wrist_probe='post-tip-reverse',wrist_candidate=True)


def post_overshoot_source():
    b=source();b['joints_rad']['e']=1.691980809
    q=[b['joints_rad'][k] for k in ('b','s','e','t','r','g')]
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
    return b


def test_post_overshoot_is_separate_uncompensated_trial():
    b=post_overshoot_source()
    p=preview_post_tip_wrist(b,post_overshoot=True)
    assert p['hypothetical_tip_sweep_mm']<6
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,
        completion_budget_ns=3_000_000_000,wrist_probe='post-overshoot')
    assert tx.begin_dispatch(2)==dict(T=101,joint=4,rad=b['joints_rad']['t']-math.radians(1.5),spd=20,acc=1)
    assert tx.snapshot()['local_candidate'] is None
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['observed_hypothetical_tip_displacement_mm']<6
    with pytest.raises(ValueError):preview_post_tip_wrist(b)
    with pytest.raises(ValueError):preview_post_tip_wrist(source(),post_overshoot=True)


@pytest.mark.parametrize('options',[{'wrist_candidate':True},{'wrist_prepare':True},{'compensated_endpoint':True}])
def test_post_overshoot_rejects_old_compensation(options):
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=post_overshoot_source(),baseline_finished_ns=1,
            completion_budget_ns=3_000_000_000,wrist_probe='post-overshoot',**options)
