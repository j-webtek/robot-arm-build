"""Wire association tests use inert registrations, not native launch approval."""
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from rocell.providers.windows import absolute_wrist_native_protocol as protocol
from rocell.providers.windows import observational_native_protocol as relative_protocol
from test_absolute_wrist_review_authority import intent
from test_observational_native_protocol import rehash


def wire(tmp_path):
    registration = {'synthetic': 'NOT_A_LAUNCH_REGISTRATION'}
    runtime = hashlib.sha256(canonical(registration)).hexdigest()
    body = intent()
    body['deadline_ns'] = body['issued_ns'] + 30_000_000_000
    body['references']['runtime_sha256'] = runtime
    request = AbsoluteWristIntent(canonical(body))
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(tmp_path),
        absolute_wrist_intent=body, launch_sha256='c'*64, registration=registration,
        review_authority_id='local-absolute-wrist-review-v1')
    return rehash(dict(schema=protocol.REQUEST_SCHEMA, worker_id=protocol.WORKER_ID,
        attempt_id=body['attempt_id'], session_id=body['session_id'],
        source_sha256=body['references']['source_sha256'], operation_sha256=request.request_sha256,
        selected_identity_sha256=hashlib.sha256(canonical(body['usb_identity'])).hexdigest(),
        expires_at_monotonic_ns=body['deadline_ns'], parent_deadline_monotonic_ns=body['deadline_ns'],
        payload=payload, registration_sha256=runtime))


def test_exact_closed_absolute_handoff(tmp_path):
    value = wire(tmp_path)
    assert protocol.decode_request(canonical(value)+b'\n') == value
    assert 'command' not in value['payload']
    assert protocol.fixed_budget().process_count == 1
    assert protocol.validate_payload(value['payload']).to_dict()['draft']['target_deg'] == 0
    with pytest.raises(ValueError): relative_protocol.decode_request(canonical(value))


@pytest.mark.parametrize('fault', ['session', 'attempt', 'identity', 'source', 'deadline',
    'parent_deadline', 'registration', 'command', 'authority', 'worker', 'hash',
    'short_lifetime', 'target', 'start', 'bool_deadline', 'relative_root', 'extra', 'bytes_budget'])
def test_even_rehashed_mutations_rejected(tmp_path, fault):
    value = wire(tmp_path)
    if fault == 'session': value['session_id'] = 'wizard-'+'f'*32
    if fault == 'attempt': value['attempt_id'] = 'operation-'+'f'*32
    if fault == 'identity': value['selected_identity_sha256'] = 'f'*64
    if fault == 'source': value['source_sha256'] = 'f'*64
    if fault == 'deadline': value['expires_at_monotonic_ns'] += 1
    if fault == 'parent_deadline': value['parent_deadline_monotonic_ns'] += 1
    if fault == 'registration': value['payload']['registration']['changed'] = True
    if fault == 'command': value['payload']['command'] = dict(T=100)
    if fault == 'authority': value['payload']['review_authority_id'] = 'local-observational-review-v1'
    if fault == 'worker': value['worker_id'] = relative_protocol.WORKER_ID
    if fault == 'short_lifetime': value['payload']['absolute_wrist_intent']['deadline_ns'] = 21_000_000_000
    if fault == 'target': value['payload']['absolute_wrist_intent']['draft']['target_deg'] = 4
    if fault == 'start': value['payload']['absolute_wrist_intent']['draft']['expected_start_joints_rad']['t'] += .001
    if fault == 'bool_deadline': value['expires_at_monotonic_ns'] = True
    if fault == 'relative_root': value['payload']['root'] = 'relative/path'
    if fault == 'extra': value['approved'] = True
    if fault == 'bytes_budget': value['payload']['registration']['padding'] = 'x'*65536
    if fault == 'hash': value['request_sha256'] = 'f'*64
    else: rehash(value)
    with pytest.raises(ValueError): protocol.decode_request(canonical(value))
