import pytest
from test_compensated_elbow_native import baseline
from rocell.application.local_tip_press import START,preview_local_tip_press
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def source():
    b=baseline()
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),START))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*START[:4])))
    return b


def test_single_tip_press_verifies_reported_arrival_only():
    b=source();p=preview_local_tip_press(b)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
                            ghost_first_step='local-tip-press')
    command=tx.begin_dispatch(2);tx.acknowledge(3)
    assert command['T']==104 and command['spd']==.05
    assert command['r']==START[4] and command['g']==START[5]
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['policy']['scope']=='LOCAL_HYPOTHETICAL_TIP_PRESS_2MM_V1'
    assert not tx.snapshot()['physical_accuracy_verified']
    with pytest.raises(ValueError):tx.begin_dispatch(2_000_000_000)


@pytest.mark.parametrize('joint',('b','s','e','t','r','g'))
def test_changed_start_is_not_admitted(joint):
    b=source();b['joints_rad'][joint]+=.001
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    with pytest.raises(ValueError):preview_local_tip_press(b)


def test_cannot_apply_old_compensation_to_new_press():
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=source(),baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
                              ghost_first_step='local-tip-press',compensated_endpoint=True)


def test_post_transfer_press_is_scoped_and_monitored():
    q=[.001533981,.033747577,1.691980809,-.052155347,.018407769,3.138524692]
    b=source();b['joints_rad']=dict(zip(('b','s','e','t','r','g'),q))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
    p=preview_local_tip_press(b,post_transfer=True)
    assert p['maximum_lateral_drift_mm']<.05
    assert p['maximum_vertical_error_mm']<.02
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        ghost_first_step='post-transfer-tip')
    cmd=tx.begin_dispatch(2);tx.acknowledge(3)
    assert cmd['T']==104 and cmd['spd']==.05
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['observed_hypothetical_tip_displacement_mm']<2.01
    assert tx.snapshot()['policy']['scope']=='POST_TRANSFER_TIP_PRESS_2MM_V1'
    with pytest.raises(ValueError):preview_local_tip_press(source(),post_transfer=True)
    with pytest.raises(ValueError):preview_local_tip_press(b,post_transfer=True,retract=True)
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            ghost_first_step='post-transfer-tip',compensated_endpoint=True)


def test_retract_is_separate_direct_path_and_arrival_scope():
    from rocell.application.local_tip_press import RETRACT_START
    b=source();b['joints_rad']=dict(zip(('b','s','e','t','r','g'),RETRACT_START))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*RETRACT_START[:4])))
    p=preview_local_tip_press(b,retract=True)
    assert p['maximum_vertical_error_mm']<.02 and not p['compensation_applied']
    with pytest.raises(ValueError):preview_local_tip_press(b)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
                            ghost_first_step='local-tip-retract')
    cmd=tx.begin_dispatch(2);tx.acknowledge(3)
    assert cmd['T']==104 and cmd['g']==RETRACT_START[5]
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['policy']['scope']=='LOCAL_HYPOTHETICAL_TIP_RETRACT_2MM_V1'
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
                              ghost_first_step='local-tip-retract',compensated_endpoint=True)
