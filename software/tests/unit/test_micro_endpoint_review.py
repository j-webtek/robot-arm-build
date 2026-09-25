import base64
import hashlib
import json
import pytest
from test_micro_endpoint import BASE,rows
from rocell.application.micro_endpoint_review import review_micro_feedback,JOINTS


def originals():
    samples=[]
    for begin,end,pose in rows():
        joints=dict(zip(JOINTS,pose))
        raw=json.dumps(dict(T=1051,x=0,y=0,z=0,tit=0,**joints)).encode()
        samples.append(dict(status='SUCCEEDED',response_base64=base64.b64encode(raw).decode(),
            response_sha256=hashlib.sha256(raw).hexdigest(),response_bytes=len(raw),
            joints_rad=joints,request_started_monotonic_s=begin/1e9,
            response_finished_monotonic_s=end/1e9))
    return samples


def review(samples):
    return review_micro_feedback(samples,baseline=BASE,dispatch_ns=100_000_000,
        receipt_ns=200_000_000,evaluated_ns=2_300_000_000)


def test_originals_reconstruct_settling():
    assert review(originals())['reported_settled']


@pytest.mark.parametrize('field,value',[('response_sha256','0'*64),
                                      ('response_base64','e30='),('response_bytes',1)])
def test_corrupted_original_rejected(field,value):
    samples=originals();samples[0][field]=value
    with pytest.raises(ValueError):review(samples)


def test_derived_pose_cannot_override_original():
    samples=originals();samples[0]['joints_rad']['r']=0
    with pytest.raises(ValueError):review(samples)


def test_failed_read_overrides_settling_even_if_later_reads_succeed():
    samples=originals();samples.insert(2,dict(status='FAILED'))
    assert review(samples)['status']=='TRANSPORT_FAULT'
    assert review([dict(status='FAILED')])['status']=='TRANSPORT_FAULT'


def test_empty_capture_never_settles():
    assert not review([])['reported_settled']
