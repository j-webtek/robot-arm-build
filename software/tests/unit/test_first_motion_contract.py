"""Synthetic contract tests; no fake measurements qualify an actual robot."""
from dataclasses import FrozenInstanceError
import json

import pytest

from rocell.application.first_motion_contract import (
    FirstMotionRequest, REFERENCES, canonical, create_first_motion_request,
    review_first_motion_request,
)
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.wizard_actions import ACTION_BY_ID, validate_action_input, WizardError
from rocell.application.wizard_worker import run


def request():
    return create_first_motion_request(attempt_id='operation-'+'b'*32,
        usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        references=dict.fromkeys(REFERENCES,'a'*64),
        independent_start_interval_deg=[-5,5],distal_radius_mm=200,
        issued_monotonic_ns=1_000_000_000,deadline_monotonic_ns=31_000_000_000)


def test_fixed_command_immutable_unknown_freshness_and_no_authority():
    r = request()
    data = r.to_dict()
    assert data['command']['T']==101 and data['command']['joint']==4
    assert data['command']['spd']==20 and data['command']['acc']==1
    assert data['feedback_freshness_at_entry']=='UNKNOWN'
    assert r.preview()['maximum_requested_travel_given_interval_deg']==6
    assert r.preview()['conditional_ideal_path_length_mm']==pytest.approx(20.943951)
    assert not r.preview()['motion_authorized']
    data['command']['joint']=2
    assert r.to_dict()['command']['joint']==4
    with pytest.raises(FrozenInstanceError):
        r.canonical_bytes=b'{}'


@pytest.mark.parametrize('field,value', [('T',104),('joint',0),('joint',2),
    ('joint',5),('rad',0),('rad',1),('spd',0),('spd',21),('acc',0),('acc',True)])
def test_command_cannot_be_substituted_or_widened(field,value):
    data=request().to_dict()
    data['command'][field]=value
    with pytest.raises(ValueError): FirstMotionRequest(canonical(data))


@pytest.mark.parametrize('field,value', [('independent_start_interval_deg',[-6,5]),
    ('independent_start_interval_deg',[-5,6]),('independent_start_interval_deg',[0,0]),
    ('independent_start_interval_deg',[True,5]),('independent_start_interval_deg',[-5,10**400]),
    ('distal_radius_mm',201),('distal_radius_mm',0),('distal_radius_mm',True),
    ('feedback_freshness_at_entry','VERIFIED'),('physical_authority',True),
    ('issued_monotonic_ns',True),('deadline_monotonic_ns',32_000_000_000)])
def test_invalid_geometry_time_or_claims_refused(field,value):
    data=request().to_dict()
    data[field]=value
    with pytest.raises(ValueError): FirstMotionRequest(canonical(data))


def test_deadlines_and_identity_reference_mutations():
    r=request()
    r.require_start_time(1_000_000_000)
    for now in (True,0,999_999_999,20_000_000_001):
        with pytest.raises(ValueError): r.require_start_time(now)
    for section,key,value in [('usb_identity','port','COM7'),
        ('usb_identity','serial_number',''),('references','source_sha256','0'*64),
        ('references','extra','a'*64),('limits','maximum_retry_count',1)]:
        data=r.to_dict(); data[section][key]=value
        with pytest.raises(ValueError): FirstMotionRequest(canonical(data))


def test_endpoint_request_rejects_commissioning_format():
    with pytest.raises(ValueError): EndpointTrialRequest(request().canonical_bytes)


def test_noncanonical_duplicate_and_oversized_input_refused():
    data=request().to_dict()
    with pytest.raises(ValueError): FirstMotionRequest(json.dumps(data).encode())
    raw=request().canonical_bytes.decode().replace('"physical_authority":false',
        '"physical_authority":false,"physical_authority":false')
    with pytest.raises(ValueError): review_first_motion_request(raw)
    with pytest.raises(ValueError): review_first_motion_request(' '*12001+'{}')


def test_review_worker_is_read_only_and_keeps_conditions_unverified(tmp_path):
    values={'request_json':request().canonical_bytes.decode()}
    result=run(tmp_path,'first_motion_review',values,'test')
    report=result['steps'][0]['report']
    assert not report['motion_authorized']
    assert not report['independent_measurements_authenticated']
    assert not report['physical_clearance_verified']
    assert not report['live_execution_implemented']
    with pytest.raises(WizardError):
        validate_action_input(ACTION_BY_ID['first_motion_review'],dict(values,execute=True))
