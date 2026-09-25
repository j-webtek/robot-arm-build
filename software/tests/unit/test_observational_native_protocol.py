import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.providers.windows import observational_native_protocol as protocol
from test_observational_review_authority import intent


def wire(tmp_path):
    # Inert registration dictionary tests association only, not launch approval.
    registration = {'synthetic': 'NOT_A_LAUNCH_REGISTRATION'}
    runtime = hashlib.sha256(canonical(registration)).hexdigest()
    body = intent()
    body['deadline_ns'] = body['issued_ns'] + 30_000_000_000
    body['references']['runtime_sha256'] = runtime
    request = ObservationalIntent(canonical(body))
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(tmp_path),
        observational_intent=body, launch_sha256='c'*64, registration=registration,
        review_authority_id='local-observational-review-v1')
    result = dict(schema=protocol.REQUEST_SCHEMA, worker_id=protocol.WORKER_ID,
        attempt_id=body['attempt_id'], session_id=body['session_id'],
        source_sha256=body['references']['source_sha256'], operation_sha256=request.request_sha256,
        selected_identity_sha256=hashlib.sha256(canonical(body['usb_identity'])).hexdigest(),
        expires_at_monotonic_ns=body['deadline_ns'], parent_deadline_monotonic_ns=body['deadline_ns'],
        payload=payload, registration_sha256=runtime)
    return rehash(result)


def rehash(value):
    value.pop('request_sha256', None)
    value['request_sha256'] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def test_closed_handoff_without_measurements_or_command(tmp_path):
    value = wire(tmp_path)
    assert protocol.decode_request(canonical(value)) == value
    assert 'command' not in value['payload']
    assert protocol.fixed_budget().process_count == 1


@pytest.mark.parametrize('fault', ['session','attempt','identity','source','deadline',
    'registration','command','authority','worker','hash','short_lifetime'])
def test_rehashed_mismatch_still_rejected(tmp_path, fault):
    value = wire(tmp_path)
    if fault == 'session': value['session_id'] = 'wizard-'+'f'*32
    if fault == 'attempt': value['attempt_id'] = 'operation-'+'f'*32
    if fault == 'identity': value['selected_identity_sha256'] = 'f'*64
    if fault == 'source': value['source_sha256'] = 'f'*64
    if fault == 'deadline': value['expires_at_monotonic_ns'] += 1
    if fault == 'registration': value['payload']['registration']['changed'] = True
    if fault == 'command': value['payload']['command'] = dict(T=100)
    if fault == 'authority': value['payload']['review_authority_id'] = 'local-first-motion-review-v1'
    if fault == 'worker': value['worker_id'] = 'physical-first-motion-trial'
    if fault == 'short_lifetime':
        value['payload']['observational_intent']['deadline_ns'] = 21_000_000_000
    if fault != 'hash': rehash(value)
    else: value['request_sha256'] = 'f'*64
    with pytest.raises(ValueError): protocol.decode_request(canonical(value))
