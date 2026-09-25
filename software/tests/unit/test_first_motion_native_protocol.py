"""Synthetic IPC contracts do not admit any process or device execution."""
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import first_motion_native_protocol as module
from rocell.providers.windows.endpoint_native_wire import decode_request as endpoint_decode
from test_first_motion_measurement_binding import setup,SESSION,OPERATION


def signed(wire):
    wire['request_sha256']=hashlib.sha256(canonical({k:v for k,v in wire.items() if k!='request_sha256'})).hexdigest()
    return canonical(wire)


def fixture(tmp_path):
    _,request=setup(tmp_path)
    body=request.to_dict()
    registration={'worker':'synthetic-not-qualified'}
    payload=dict(schema=module.PAYLOAD_SCHEMA,root=str(tmp_path),session_id=SESSION,
        measurement_operation_id=OPERATION,first_motion_request=body,launch_sha256='a'*64,
        registration=registration,review_authority_id='local-first-motion-review-v1')
    return dict(schema=module.REQUEST_SCHEMA,worker_id=module.WORKER_ID,attempt_id=body['attempt_id'],
        session_id=SESSION,source_sha256=body['references']['source_sha256'],operation_sha256=request.request_sha256,
        selected_identity_sha256=hashlib.sha256(canonical(body['usb_identity'])).hexdigest(),
        expires_at_monotonic_ns=body['deadline_monotonic_ns'],parent_deadline_monotonic_ns=body['deadline_monotonic_ns'],
        payload=payload,registration_sha256=hashlib.sha256(canonical(registration)).hexdigest())


def test_exact_separate_domain_roundtrip(tmp_path):
    wire=fixture(tmp_path)
    raw=signed(wire)
    assert module.decode_request(raw)==wire
    with pytest.raises(ValueError): endpoint_decode(raw)
    assert module.fixed_budget().run_timeout_ms==25000


@pytest.mark.parametrize('field,value',[
    ('worker_id','physical-endpoint-trial'),('operation_sha256','f'*64),
    ('selected_identity_sha256','f'*64),('registration_sha256','f'*64),
    ('expires_at_monotonic_ns',True),('parent_deadline_monotonic_ns',1),('extra','field')])
def test_rehashed_wrong_outer_association_refused(tmp_path,field,value):
    wire=fixture(tmp_path); wire[field]=value
    with pytest.raises(ValueError): module.decode_request(signed(wire))


@pytest.mark.parametrize('field,value',[
    ('measurement_operation_id','../file'),('review_authority_id','local-bench-review-v1'),
    ('root','relative-folder'),('extra',True),('registration',{'oversized':'x'*32768})],
    ids=['measurement-path','authority','relative-root','extra','oversized-registration'])
def test_invalid_handoff_refused(tmp_path,field,value):
    wire=fixture(tmp_path); wire['payload'][field]=value
    with pytest.raises(ValueError): module.decode_request(signed(wire))


def test_digest_and_oversized_input_refused(tmp_path):
    wire=fixture(tmp_path); signed(wire); wire['request_sha256']='f'*64
    with pytest.raises(ValueError): module.decode_request(canonical(wire))
    with pytest.raises(ValueError): module.decode_request(b'x'*65537)
