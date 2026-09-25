"""Exact synthetic measurement/request associations do not authorize motion."""
import hashlib
import json

import pytest

from rocell.application.first_motion_contract import (
    REFERENCES, FirstMotionRequest, canonical, create_first_motion_request,
)
from rocell.application.first_motion_measurements import (
    record_measurements, load_measurement_for_request, validate_original_for_request,
)
from test_first_motion_measurements import values

SESSION='wizard-'+'a'*32
OPERATION='operation-'+'c'*32


def setup(tmp_path, *, issued=2_000_000_000):
    report=record_measurements(values(),root=tmp_path,session_id=SESSION,
        operation_id=OPERATION,source_sha256='a'*64,now_ns=1_000_000_000)
    raw=(tmp_path/report['filename']).read_bytes()
    refs=dict.fromkeys(REFERENCES,'a'*64)
    refs['independent_posture_review_sha256']=hashlib.sha256(raw).hexdigest()
    request=create_first_motion_request(attempt_id='operation-'+'d'*32,
        usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        references=refs,independent_start_interval_deg=[-1,1],distal_radius_mm=175,
        issued_monotonic_ns=issued,deadline_monotonic_ns=issued+30_000_000_000)
    return raw,request


def check(raw,request,**kwargs):
    arguments=dict(session_id=SESSION,operation_id=OPERATION,now_ns=2_000_000_000)
    arguments.update(kwargs)
    return validate_original_for_request(raw,request,**arguments)


def test_selected_original_matches_without_retiming_or_approving(tmp_path):
    raw,request=setup(tmp_path)
    captured,result=load_measurement_for_request(request,root=tmp_path,
        session_id=SESSION,operation_id=OPERATION,check_current=lambda:None,
        clock_ns=lambda:2_000_000_000)
    assert captured==raw
    assert result['status']=='ORIGINAL_MATCHES_REQUEST_NOT_APPROVED'
    assert result['original_recorded_monotonic_ns']==1_000_000_000
    assert result['record_age_ns']==1_000_000_000
    assert not result['motion_authorized']
    assert not result['measurement_time_independently_verified']


@pytest.mark.parametrize('change',[
    {'independent_start_interval_deg':[-.5,.5]},
    {'independent_start_interval_deg':[-2,2]}, {'distal_radius_mm':170},
    {'distal_radius_mm':180},
    {'usb_identity':{'vid':0x10c4,'pid':0xea60,'serial_number':'B'*32}},
])
def test_request_cannot_substitute_geometry_or_unit(tmp_path,change):
    raw,request=setup(tmp_path)
    body=request.to_dict(); body.update(change)
    with pytest.raises(ValueError): check(raw,FirstMotionRequest(canonical(body)))


@pytest.mark.parametrize('change',[
    {'measurement_accuracy_independently_verified':True},
    {'measured_monotonic_ns':1_000_000_000}, {'physical_authority':True},
    {'angle_reference':'WORLD_HORIZONTAL'}, {'extra':False},
    {'derived':{'reported_wrist_interval_deg':[-.5,.5],
                'reported_distal_radius_upper_bound_mm':175,'within_proposal_numeric_bounds':True}},
])
def test_changed_flags_and_derivations_fail_even_with_updated_digest(tmp_path,change):
    raw,request=setup(tmp_path)
    original=json.loads(raw); original.update(change); changed=canonical(original)
    body=request.to_dict()
    body['references']['independent_posture_review_sha256']=hashlib.sha256(changed).hexdigest()
    with pytest.raises(ValueError): check(changed,FirstMotionRequest(canonical(body)))


def test_digest_session_operation_source_and_time_are_checked(tmp_path):
    raw,request=setup(tmp_path)
    for kwargs in ({'session_id':'wizard-'+'b'*32},
                   {'operation_id':'operation-'+'e'*32}, {'now_ns':True},
                   {'now_ns':1}, {'now_ns':32_000_000_000}):
        with pytest.raises(ValueError): check(raw,request,**kwargs)
    with pytest.raises(ValueError): check(raw+b' ',request)
    body=request.to_dict(); body['references']['source_sha256']='b'*64
    with pytest.raises(ValueError): check(raw,FirstMotionRequest(canonical(body)))


def test_old_record_not_renewed_by_new_request(tmp_path):
    raw,request=setup(tmp_path,issued=301_000_000_000)
    with pytest.raises(ValueError): check(raw,request,now_ns=301_000_000_000)


@pytest.mark.parametrize('fail_at',[1,2,3])
def test_context_change_aborts_selection(tmp_path,fail_at):
    _,request=setup(tmp_path)
    calls=[]
    def current():
        calls.append(1)
        if len(calls)==fail_at: raise ValueError('cancelled/source changed')
    with pytest.raises(ValueError):
        load_measurement_for_request(request,root=tmp_path,session_id=SESSION,
            operation_id=OPERATION,check_current=current,clock_ns=lambda:2_000_000_000)


def test_no_arbitrary_path_or_late_result(tmp_path):
    _,request=setup(tmp_path)
    with pytest.raises(ValueError):
        load_measurement_for_request(request,root=tmp_path,session_id=SESSION,
            operation_id='../other',check_current=lambda:None,clock_ns=lambda:2_000_000_000)
    clock=iter((2_000_000_000,2_000_000_000,32_000_000_000))
    with pytest.raises(ValueError):
        load_measurement_for_request(request,root=tmp_path,session_id=SESSION,
            operation_id=OPERATION,check_current=lambda:None,clock_ns=lambda:next(clock))
