"""Native request syntax never serves as physical approval or a raw command API."""

from dataclasses import FrozenInstanceError
import json

import pytest

from rocell.application.endpoint_trial_contract import (
    EndpointTrialRequest, REFERENCE_NAMES, create_endpoint_request,
)
from rocell.motion.characterization_plan import freeze_campaign
from test_characterization_plan import candidate


def request():
    data = candidate()
    data['frame'] = 'R_ctrl'
    data['evidence']['usb_identity'] = 'A'*32
    plan = freeze_campaign(data)
    return create_endpoint_request(plan, 'out', attempt_id='operation-'+'b'*32,
        references=dict.fromkeys(REFERENCE_NAMES, 'a'*64),
        usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        issued_monotonic_ns=1_000_000_000, deadline_monotonic_ns=21_000_000_000)


def encoded(data):
    return json.dumps(data,sort_keys=True,separators=(',',':')).encode()


def test_request_binds_one_typed_goal_but_grants_no_authority():
    r = request()
    assert r.goal().to_message() == {'T':104,'x':1,'y':0,'z':0,'t':0,'r':0,'g':0,'spd':.05}
    assert not r.to_dict()['physical_authority']
    assert r.to_dict()['limits']['maximum_motion_write_attempts'] == 1
    assert EndpointTrialRequest(r.canonical_bytes).request_sha256 == r.request_sha256
    assert not hasattr(r, 'consume') and not hasattr(r, 'allows')
    detached = r.to_dict()
    detached['trial_id'] = 'back'
    assert r.goal().x_mm == 1
    with pytest.raises(FrozenInstanceError):
        r.canonical_bytes = b'{}'


@pytest.mark.parametrize('field,value', [
    ('purpose','T1041'), ('physical_authority',True), ('trial_id','unknown'),
    ('observation_contract','CONTINUOUS'), ('issued_monotonic_ns',True),
    ('deadline_monotonic_ns',2_000_000_000), ('deadline_monotonic_ns',99_000_000_000),
])
def test_invalid_or_widened_request_rejected(field,value):
    data = request().to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        EndpointTrialRequest(encoded(data))


def test_reference_identity_and_limit_changes_are_not_silently_accepted():
    for group,key,value in [('references','source_sha256','f'*64),
                            ('usb_identity','serial_number','B'*32),
                            ('usb_identity','port','COM7'),
                            ('limits','maximum_retry_count',1),
                            ('limits','maximum_motion_write_attempts',True)]:
        data = request().to_dict()
        data[group][key] = value
        with pytest.raises(ValueError):
            EndpointTrialRequest(encoded(data))


def test_no_raw_command_field_duplicate_json_or_oversized_input():
    data = request().to_dict()
    data['raw_command'] = '{"T":1041}'
    with pytest.raises(ValueError):
        EndpointTrialRequest(encoded(data))
    with pytest.raises(ValueError):
        EndpointTrialRequest(b'{"schema":1,"schema":2}')
    with pytest.raises(ValueError):
        EndpointTrialRequest(b' '*16385)


def test_start_time_reserves_all_io_and_cleanup_budget():
    r = request()
    r.require_start_time(1_000_000_000)
    r.require_start_time(10_000_000_000)
    for now in (999_999_999,10_000_000_001,True,float('nan'),float('inf')):
        with pytest.raises(ValueError):
            r.require_start_time(now)


def test_selected_trial_must_fit_post_capture_time_budget():
    data = request().to_dict()
    data['campaign']['trials'][0]['timeout_s'] = 6
    with pytest.raises(ValueError,match='capture window'):
        EndpointTrialRequest(encoded(data))
