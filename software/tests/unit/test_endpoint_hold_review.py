from copy import deepcopy
import pytest
from rocell.application.endpoint_hold_review import review_endpoint_hold
from rocell.kinematics.firmware_reference import forward


def evidence():
    q=[.001533981,.033747577,1.691980809,-.052155347,.018407769,3.138524692]
    pose=list(forward(*q[:4]))
    trial=dict(run=dict(error=None,transaction=dict(state='COMPENSATED_REPORTED_ENDPOINT_VERIFIED',
        desired_endpoint_result=dict(desired_xyz_pitch=pose),rows=[[1,2,pose,q]])))
    sample=dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
        joints_rad=dict(zip(('b','s','e','t','r','g'),q)),timing_clock='HOST_PERF_COUNTER',
        controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),pose))))
    samples=[]
    for i in range(5):
        s=deepcopy(sample);s.update(request_started_monotonic_s=1+i*.3,response_finished_monotonic_s=1.1+i*.3)
        samples.append(s)
    return trial,dict(status='SUCCEEDED',samples=samples)


def test_stable_hold_is_not_motion_authority():
    t,o=evidence();r=review_endpoint_hold(t,o)
    assert r['status']=='REPORTED_HOLD_VERIFIED'
    assert not r['motion_authorized'] and not r['encoder_freshness_verified']
    assert not r['changed_since_completion']


@pytest.mark.parametrize('fault',['gap','old','identity','left_band','unfinished'])
def test_invalid_hold_cannot_pass(fault):
    t,o=evidence()
    if fault=='gap':o['samples'][-1]['response_finished_monotonic_s']+=2
    if fault=='old':t['run']['transaction']['rows'][-1][1]=10_000_000_000
    if fault=='identity':o['samples'][-1]['identity_after_matched']=False
    if fault=='left_band':t['run']['transaction']['desired_endpoint_result']['desired_xyz_pitch'][0]+=1
    if fault=='unfinished':t['run']['error']='UNCERTAIN'
    if fault=='identity':
        with pytest.raises(ValueError):review_endpoint_hold(t,o)
    else:assert review_endpoint_hold(t,o)['status']!='REPORTED_HOLD_VERIFIED'
