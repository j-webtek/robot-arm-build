import math
import pytest
from test_compensated_elbow_native import baseline
from rocell.application.ghost_first_step import preview_first_step
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def test_first_step_exact_scope_and_reported_arrival():
    b=baseline(); preview=preview_first_step(b)
    assert math.dist(preview['starting_pose'][:3],preview['target_pose'][:3])==pytest.approx(5)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,ghost_first_step=True)
    command=tx.begin_dispatch(2); tx.acknowledge(3)
    assert command['T']==104 and command['g']==b['joints_rad']['g'] and command['r']==b['joints_rad']['r']
    assert command['spd']==.05
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,preview['target_pose'],preview['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert not tx.snapshot()['physical_accuracy_verified']
    with pytest.raises(ValueError): tx.begin_dispatch(2_000_000_000)


@pytest.mark.parametrize('joint,value',[('s',.1),('e',1.6),('t',0),('r',0)])
def test_different_posture_rejected(joint,value):
    b=baseline(); b['joints_rad'][joint]=value
    with pytest.raises(ValueError): preview_first_step(b)


def test_cannot_mix_compensation_or_elbow_modes():
    with pytest.raises(ValueError): CartesianTransaction(baseline=baseline(),baseline_finished_ns=1,
        completion_budget_ns=3_000_000_000,ghost_first_step=True,elbow_only=True)


def post_wrist_baseline():
    b=baseline(1.563126423)
    b['joints_rad'].update(s=.007669904,t=.007669904,r=.018407769)
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),
        forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    return b


def test_post_wrist_is_distinct_bounded_coordinated_scope():
    b=post_wrist_baseline()
    p=preview_first_step(b,post_wrist=True)
    assert math.dist(p['starting_pose'][:3],p['target_pose'][:3])==pytest.approx(5)
    assert not p['compensation_applied'] and not p['tool_clearance_verified']
    assert max(abs(a-b) for a,b in zip(p['target_joints_rad'],b['joints_rad'].values()))<math.radians(3)
    with pytest.raises(ValueError):preview_first_step(b)
    with pytest.raises(ValueError):preview_first_step(baseline(),post_wrist=True)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,
        completion_budget_ns=3_000_000_000,ghost_first_step='post-wrist')
    command=tx.begin_dispatch(2);tx.acknowledge(3)
    assert command['T']==104 and command['spd']==.05
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['policy']['scope']=='POST_WRIST_GHOST_APPROACH_5MM_UNCOMPENSATED_V2'


@pytest.mark.parametrize('joint',('b','s','e','t','r','g'))
def test_post_wrist_rejects_changed_start(joint):
    b=post_wrist_baseline();b['joints_rad'][joint]+=.001
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),
        forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    with pytest.raises(ValueError):preview_first_step(b,post_wrist=True)
