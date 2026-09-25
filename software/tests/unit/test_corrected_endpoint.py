"""No hardware: corrected wire targets must not redefine the desired endpoint."""
import json
import math

import pytest

from rocell.arm.discrete_endpoint import verify_discrete_endpoint
from rocell.arm.discrete_transaction import DiscreteTransaction
from rocell.safety.wifi_dispatch_reservation import WifiDispatchReservation
from test_wifi_discrete_runner import setup


def evaluate(value, *, command=1.45, desired=1.25, other=0):
    rows=[]
    for end in (1_300_000_000,1_600_000_000,1_900_000_000):
        rows.append([end-10_000_000,end,[other,0,1,0,math.radians(value),3]])
    return verify_discrete_endpoint(rows,joint='r',start=[0,0,1,0,0,3],
        target=math.radians(desired),command_target=math.radians(command),
        command_finished_ns=1_000_000_000,completion_deadline_ns=5_000_000_000,
        evaluated_ns=1_900_000_000)


def test_error_is_against_desired_not_command():
    result=evaluate(1.25)
    assert result['endpoint_verified']
    assert result['endpoint']['final_error_rad']==0
    assert result['command_target_rad']==math.radians(1.45)
    # Within .5 degrees of the command, but not the actual endpoint goal.
    assert not evaluate(1.8)['endpoint_verified']


def test_command_path_not_desired_path_and_other_joint_checks():
    # Within the desired arrival band, but beyond command + excursion tolerance.
    assert evaluate(1.7,command=1.05)['status']=='JOINT_EXCURSION'
    assert evaluate(1.25,other=.1)['status']=='OTHER_JOINT_CHANGED'


@pytest.mark.parametrize('desired',[True,float('nan'),float('inf'),-1,3.1,1.96])
def test_invalid_or_excessive_correction_is_rejected(desired):
    with pytest.raises(ValueError):
        DiscreteTransaction(baseline=[0,0,1,0,0,3],baseline_finished_ns=1,
            target=math.radians(1.45),desired_endpoint=desired if isinstance(desired,bool)
            else math.radians(desired),completion_budget_ns=5_000_000_000)


def test_transaction_retains_both_targets_and_reconstructs():
    tx=DiscreteTransaction(baseline=[0,0,1,0,0,3],baseline_finished_ns=1_000_000_000,
        target=math.radians(1.45),desired_endpoint=math.radians(1.25),
        completion_budget_ns=5_000_000_000)
    assert tx.begin_dispatch(1_010_000_000)['rad']==math.radians(1.45)
    tx.acknowledge(1_100_000_000)
    for end in (1_400_000_000,1_700_000_000,2_000_000_000):
        tx.observe([end-10_000_000,end,[0,0,1,0,math.radians(1.25),3]],end)
    snapshot=tx.snapshot()
    result=snapshot['result']
    assert snapshot['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert verify_discrete_endpoint(snapshot['rows'],joint='r',start=snapshot['baseline'],
        target=snapshot['desired_endpoint_rad'],command_target=snapshot['command']['rad'],
        command_finished_ns=result['command_finished_ns'],
        completion_deadline_ns=result['completion_deadline_ns'],
        evaluated_ns=result['evaluated_ns'])==result


def test_durable_record_binds_desired_endpoint(tmp_path):
    _,_,_,_,_,baseline=setup(tmp_path)
    reservation=WifiDispatchReservation(root=tmp_path.resolve(),attempt_id='b'*32,
        baseline=baseline,target=math.radians(1.45),desired_endpoint=math.radians(1.25),
        now_ns=10_000_000_000,completion_budget_ns=5_000_000_000)
    record=json.loads((tmp_path/('b'*32+'-wifi-reserved.json')).read_text())
    assert record['desired_endpoint_rad']==math.radians(1.25)
    assert record['command']==reservation.command()
    assert record['schema']=='rocell.wifi_dispatch_reservation.v2'
