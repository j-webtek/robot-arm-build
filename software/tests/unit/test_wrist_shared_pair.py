import pytest
from test_coordinated_wrist_probe import posture
from rocell.application.wrist_shared_pair import pair_candidate,preview_pair_leg
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def baseline(leg):
    b=posture();b['joints_rad'].update(s=.033747577,e=1.636757501,r=.018407769,t=pair_candidate(leg)['start_center_rad'])
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    return b


@pytest.mark.parametrize('leg',['down','up'])
def test_pair_desired_arrival_and_fixed_bias(leg):
    b=baseline(leg);c=pair_candidate(leg);p=preview_pair_leg(b,leg)
    assert len(p['samples'])==82
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-coordinated-ascending' if leg=='up' else 'post-coordinated',
        wrist_candidate='pair-'+leg,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['rad']==c['command_rad'];tx.acknowledge(3)
    q=list(b['joints_rad'].values());q[3]=c['desired_rad']
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,forward(*q[:4]),q),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert not tx.snapshot()['result']['endpoint_verified']


@pytest.mark.parametrize('leg',['down','up'])
def test_pair_rejects_wrong_start_and_other_joints(leg):
    b=baseline('down' if leg=='up' else 'up')
    with pytest.raises(ValueError):preview_pair_leg(b,leg)
    b=baseline(leg);b['joints_rad']['s']+=.001
    with pytest.raises(ValueError):preview_pair_leg(b,leg)
