import math
import pytest
from rocell.arm.micro_endpoint import verify_micro_endpoint

BASE=[0,0,0,0,math.radians(1.40625),0]


def rows(final=1.25):
    pose=[0,0,0,0,math.radians(final),0]
    return [[t-10_000_000,t,list(pose)] for t in
            (600_000_000,1_100_000_000,1_600_000_000,2_100_000_000,2_300_000_000)]


def check(data, **kwargs):
    params=dict(baseline=BASE,dispatch_ns=100_000_000,receipt_ns=200_000_000,
                evaluated_ns=2_300_000_000)
    params.update(kwargs)
    return verify_micro_endpoint(data,**params)


@pytest.mark.parametrize('angle,label,inband',[(1.25,'IN_DESIRED_BAND',True),
    (1.40625,'UNCHANGED_OR_SUBRESOLUTION',False),(1.32,'IMPROVED_OUTSIDE_BAND',False),
    (1.18,'OVERSHOOT',False),(1.45,'NOT_IMPROVED',False)])
def test_settling_is_not_automatically_accuracy(angle,label,inband):
    r=check(rows(angle))
    assert r['status']=='REPORTED_SETTLED' and r['classification']==label
    assert r['desired_band_met']==inband
    assert not r['motion_authorized'] and not r['automatic_next_command_allowed']
    assert r['full_passive_hold_required']


def test_receipt_and_fast_unchanged_prefix_not_arrival():
    assert check([],evaluated_ns=200_000_000)['status']=='NOT_YET_SETTLED'
    assert check(rows()[:3],evaluated_ns=1_600_000_000)['status']=='NOT_YET_SETTLED'


@pytest.mark.parametrize('change,status',[
    ('other','OTHER_JOINT_DRIFT'),('excursion','ROLL_EXCURSION'),
    ('reorder','FEEDBACK_INVALID'),('nan','FEEDBACK_INVALID'),
    ('unstable','NOT_YET_SETTLED')])
def test_bad_capture_never_qualifies(change,status):
    data=rows()
    if change=='other':data[0][2][1]=math.radians(.11)
    if change=='excursion':data[0][2][4]=math.radians(1.0)
    if change=='reorder':data[0][0]=data[0][1]+1
    if change=='nan':data[0][2][4]=float('nan')
    if change=='unstable':data[-2][2][4]=math.radians(1.3)
    assert check(data)['status']==status


def test_late_fault_silence_and_cancellation_override_arrival():
    assert check(rows(),transport_clean=False)['status']=='TRANSPORT_FAULT'
    assert check(rows(),cancelled=True)['status']=='CANCELLED'
    assert check(rows(),evaluated_ns=3_400_000_000)['status']=='FEEDBACK_GAP_EXCEEDED'


def test_completion_deadline_includes_receipt_latency():
    data=rows()
    pose=data[-1][2]
    for t in range(2_800_000_000,10_400_000_000,500_000_000):
        data.append([t-10_000_000,t,pose])
    assert check(data,evaluated_ns=data[-1][1])['status']=='COMPLETION_DEADLINE_EXCEEDED'


def test_invalid_baseline_rejected():
    with pytest.raises(ValueError):check(rows(),baseline=[0]*6)
