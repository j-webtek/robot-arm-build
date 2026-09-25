import math
import pytest
from rocell.arm.discrete_endpoint import verify_discrete_endpoint, assess_stationary_timing
from rocell.arm.endpoint_persistence import MAX_GAP_NS
from test_arm_wifi_spaced import simulate

START=[0.,0.,1.,0.,0.,3.]
TARGET=math.radians(2)


def check(times=(.3,.6,.9,1.2), *, values=None, evaluated=1.2, deadline=5, **kw):
    rows=[]
    for i,t in enumerate(times):
        pose=START.copy();pose[4]=TARGET if values is None else values[i]
        end=1_000_000_000+round(t*1e9)
        rows.append((end-10_000_000,end,pose))
    return verify_discrete_endpoint(rows,joint='r',start=START,target=TARGET,
        command_finished_ns=1_000_000_000,completion_deadline_ns=1_000_000_000+round(deadline*1e9),
        evaluated_ns=1_000_000_000+round(evaluated*1e9),**kw)


def test_slower_feedback_preserves_position_checks_and_old_policy():
    r=check()
    assert r['endpoint_verified']
    assert r['policy']['maximum_feedback_gap_ns']==1_000_000_000
    assert MAX_GAP_NS==250_000_000
    assert not r['automatic_next_command_allowed'] and not r['physical_accuracy_verified']


@pytest.mark.parametrize('kw',[dict(times=(1.01,1.3,1.6),evaluated=1.6),
    dict(times=(.3,.6,1.7),evaluated=1.7),dict(evaluated=2.21)])
def test_first_internal_and_tail_gaps(kw):
    assert check(**kw)['status']=='FEEDBACK_GAP_EXCEEDED'


def test_reset_after_arrival_never_permits_retry():
    r=check(transport_clean=False)
    assert r['status']=='TRANSPORT_FAULT' and r['outcome_uncertain']
    assert not r['endpoint_verified'] and not r['automatic_retry_allowed']


def test_deadline_and_consecutive_and_missed_target():
    assert check(deadline=1)['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert not check(times=(.3,.9),evaluated=.9)['endpoint_verified']
    assert not check(values=[0,0,0,0])['endpoint_verified']
    assert not check(values=[TARGET,TARGET,TARGET,0])['endpoint_verified']
    assert check(cancelled=True)['status']=='CANCELLED'


def test_stationary_assessment_does_not_claim_endpoint():
    report,_=simulate(intermediate=True)
    r=assess_stationary_timing(report)
    assert r['status']=='WITHIN_PROVISIONAL_GAP_ALLOWANCE'
    assert not r['endpoint_verified'] and not r['movement_ready']
    failed,_=simulate(fault_at=2,intermediate=True)
    assert assess_stationary_timing(failed)['status']=='TRANSPORT_FAULT'


def test_excursion_is_terminal_and_not_merely_waiting():
    r=check(values=[TARGET*3,TARGET,TARGET,TARGET])
    assert r['status']=='JOINT_EXCURSION' and not r['endpoint_verified']


def test_other_joint_drift_and_bad_rows():
    pose=START.copy();pose[0]=.1;pose[4]=TARGET
    kw=dict(joint='r',start=START,target=TARGET,command_finished_ns=1_000_000_000,
        completion_deadline_ns=6_000_000_000,evaluated_ns=1_500_000_000)
    assert verify_discrete_endpoint([(1_200_000_000,1_300_000_000,pose)],**kw)['status']=='OTHER_JOINT_CHANGED'
    assert verify_discrete_endpoint([(0,1,[])],**kw)['status']=='FEEDBACK_INVALID'
