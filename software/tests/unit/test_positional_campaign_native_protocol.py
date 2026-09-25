"""Campaign IPC association without a native registration, launch or device."""
import hashlib
from dataclasses import asdict

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import positional_campaign_native_protocol as protocol
from test_positional_campaign_authority import body


def seal(wire):
    wire.pop('request_sha256', None)
    wire['request_sha256'] = hashlib.sha256(canonical(wire)).hexdigest()
    return canonical(wire)


def fixture(tmp_path):
    intent = body()
    registration = dict(fixture_only=True, budget=asdict(protocol.fixed_budget()))
    intent['references']['runtime_sha256'] = hashlib.sha256(canonical(registration)).hexdigest()
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(tmp_path), campaign_intent=intent,
        launch_sha256='d'*64, registration=registration,
        review_authority_id='local-positional-campaign-review-v1')
    return dict(schema=protocol.REQUEST_SCHEMA, worker_id=protocol.WORKER_ID,
        attempt_id=intent['campaign_id'], session_id=intent['session_id'],
        source_sha256=intent['references']['source_sha256'],
        operation_sha256=hashlib.sha256(canonical(intent)).hexdigest(),
        selected_identity_sha256=hashlib.sha256(canonical(intent['usb_identity'])).hexdigest(),
        expires_at_monotonic_ns=intent['deadline_ns'], parent_deadline_monotonic_ns=intent['deadline_ns'],
        payload=payload, registration_sha256=intent['references']['runtime_sha256'])


def test_exact_handoff_retains_both_commands_without_granting_authority(tmp_path):
    wire = fixture(tmp_path)
    decoded = protocol.decode_request(seal(wire))
    intent = protocol.validate_payload(decoded['payload'])
    assert intent.to_dict()['legs'] == body()['legs']
    assert decoded['operation_sha256'] == intent.sha256
    budget = protocol.fixed_budget()
    assert budget.process_count == 1
    assert budget.run_timeout_ms + budget.cleanup_timeout_ms == 30000


def test_campaign_wire_is_rejected_by_single_move_decoder(tmp_path):
    from rocell.providers.windows.absolute_wrist_native_protocol import decode_request
    with pytest.raises(ValueError):
        decode_request(seal(fixture(tmp_path)))


@pytest.mark.parametrize('fault', ['duplicate', 'oversize', 'changed_hash'])
def test_untrusted_wire_bytes_rejected(tmp_path, fault):
    raw = seal(fixture(tmp_path))
    if fault == 'duplicate': raw = b'{"worker_id":"duplicate",' + raw[1:]
    if fault == 'oversize': raw = b' ' * 65537
    if fault == 'changed_hash': raw = raw.replace(b'"launch_sha256":"d', b'"launch_sha256":"e')
    with pytest.raises(ValueError):
        protocol.decode_request(raw)


@pytest.mark.parametrize('field', ['schema', 'worker_id', 'attempt_id', 'session_id',
    'source_sha256', 'operation_sha256', 'selected_identity_sha256', 'registration_sha256',
    'expires_at_monotonic_ns', 'parent_deadline_monotonic_ns'])
def test_rehashed_cross_request_association_rejected(tmp_path, field):
    wire = fixture(tmp_path)
    wire[field] = wire[field] + 1 if type(wire[field]) is int else 'wrong-domain-or-reference'
    with pytest.raises(ValueError):
        protocol.decode_request(seal(wire))


@pytest.mark.parametrize('fault', ['unattended', 'command_override', 'single_move_domain',
    'runtime', 'stop_reference', 'extra_leg', 'deadline_bool', 'zero_launch_hash'])
def test_rehashed_payload_cannot_expand_reviewed_route(tmp_path, fault):
    wire = fixture(tmp_path)
    payload = wire['payload']
    if fault == 'unattended': payload['campaign_intent']['mode'] = 'UNATTENDED'
    if fault == 'command_override': payload['command'] = dict(T=101, joint=4, rad=1)
    if fault == 'single_move_domain': payload['schema'] = 'rocell.absolute_wrist_native_handoff.v1'
    if fault == 'runtime': payload['registration']['fixture_only'] = False
    if fault == 'stop_reference': del payload['campaign_intent']['references']['stop_qualification_sha256']
    if fault == 'extra_leg': payload['campaign_intent']['legs'].append(payload['campaign_intent']['legs'][0])
    if fault == 'deadline_bool': wire['parent_deadline_monotonic_ns'] = True
    if fault == 'zero_launch_hash': payload['launch_sha256'] = '0'*64
    with pytest.raises(ValueError):
        protocol.decode_request(seal(wire))
