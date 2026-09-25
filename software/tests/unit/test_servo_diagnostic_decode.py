import hashlib
import json
import pytest
from test_servo_diagnostic_contract import trace
from rocell.application.servo_diagnostic_decode import decode_trace,MAX_TRACE_BYTES


def test_roundtrip_hash_and_assessment(trace):
    raw=json.dumps(trace).encode()
    result=decode_trace(raw)
    assert result['trace']==trace
    assert result['raw_sha256']==hashlib.sha256(raw).hexdigest()
    assert result['assessment']['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
    assert not result['provenance_verified'] and not result['motion_authorized']


@pytest.mark.parametrize('raw',[b'',b'[]',b'null',b'{}',b'\xff',
    b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'['*2000+b']'*2000,
    b' '* (MAX_TRACE_BYTES+1)],ids=['empty','array','null','missing-fields','utf8',
        'duplicate','nan','infinity','deep','oversize'])
def test_bad_json_is_bounded_and_rejected(raw):
    with pytest.raises(ValueError):decode_trace(raw)


@pytest.mark.parametrize('section',[None,'command','dispatch','policy','sample'])
def test_unknown_fields_fail_closed(trace,section):
    value=trace if section is None else trace['samples'][0] if section=='sample' else trace[section]
    value['unexpected_secret']='do-not-log'
    with pytest.raises(ValueError) as caught:decode_trace(json.dumps(trace).encode())
    assert 'do-not-log' not in str(caught.value)


def test_excess_samples_rejected(trace):
    trace['samples']=[trace['samples'][0]]*2001
    with pytest.raises(ValueError):decode_trace(json.dumps(trace).encode())


def test_device_label_does_not_authenticate_record(trace):
    trace['origin']='DEVICE_CAPTURE'
    result=decode_trace(json.dumps(trace).encode())
    assert not result['provenance_verified']
    assert not result['assessment']['progression_authority']
