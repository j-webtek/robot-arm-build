"""Staging and original-registration checks only; never process/device launch."""
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.absolute_wrist_worker_preparation import stage_absolute_wrist_runtime
from rocell.application.absolute_wrist_reference_reader import AbsoluteWristReferenceReader, FrozenAbsoluteWristReferences
from rocell.providers.windows.absolute_wrist_native_registration import validate_registration
from rocell.providers.windows import absolute_wrist_native_protocol as protocol
from rocell.providers.windows.owned_worker_process import OwnedWorkerRequest, owned_registration_document
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from test_absolute_wrist_review_authority import intent
from test_endpoint_current_context import fixture as endpoint_fixture


def fixture(tmp_path):
    workspace = Path(__file__).resolve().parents[3]
    binding = endpoint_fixture()[3]
    controller = canonical(binding.to_dict())
    reviewed_protocol = b'{"synthetic":"not a physical protocol qualification"}'
    body = intent()
    staged = stage_absolute_wrist_runtime(workspace, root=tmp_path, attempt_id=body['attempt_id'],
        controller_original=controller, protocol_original=reviewed_protocol)
    body['deadline_ns'] = 31_000_000_000
    body['references'] = dict(source_sha256=staged.source_sha256,
        runtime_sha256=hashlib.sha256(canonical(owned_registration_document(staged.registration))).hexdigest(),
        native_controller_review_sha256=hashlib.sha256(controller).hexdigest(),
        protocol_review_sha256=hashlib.sha256(reviewed_protocol).hexdigest())
    request = AbsoluteWristIntent(canonical(body))
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(tmp_path), absolute_wrist_intent=body,
        launch_sha256='c'*64, registration=owned_registration_document(staged.registration),
        review_authority_id='local-absolute-wrist-review-v1')
    outer = OwnedWorkerRequest(body['attempt_id'], body['session_id'], staged.source_sha256,
        request.request_sha256, hashlib.sha256(canonical(body['usb_identity'])).hexdigest(),
        body['deadline_ns'], canonical(payload))
    return workspace, staged, request, outer


def test_staged_registration_and_reconstructed_originals(tmp_path):
    workspace, staged, request, outer = fixture(tmp_path)
    assert validate_registration(staged.registration, outer)['absolute_wrist_intent'] == request.to_dict()
    reader = AbsoluteWristReferenceReader(request, workspace=workspace, root=tmp_path)
    assert dict(reader()) == request.to_dict()['references']
    frozen = FrozenAbsoluteWristReferences(reader)
    assert frozen() == reader()
    assert frozen.original('runtime_sha256') == reader.original('runtime_sha256')
    with pytest.raises(FileExistsError):
        stage_absolute_wrist_runtime(workspace, root=tmp_path, attempt_id=staged.attempt_id,
            controller_original=reader.original('native_controller_review_sha256'),
            protocol_original=reader.original('protocol_review_sha256'))


@pytest.mark.parametrize('fault', ['controller', 'protocol', 'archive', 'argv', 'budget', 'executable'])
def test_registration_refuses_changed_pins_or_limits(tmp_path, fault):
    _, staged, _, outer = fixture(tmp_path)
    registration = staged.registration
    directory = registration.working_directory
    if fault in ('controller', 'protocol'):
        (directory/(fault+'.original.json')).write_bytes(b'{}')
    if fault == 'archive':
        (directory/'absolute-wrist-native.zip').write_bytes(b'changed')
    if fault == 'argv': registration = replace(registration, argv=(*registration.argv[:-1], 'check-imports'))
    if fault == 'budget': registration = replace(registration, budget=replace(registration.budget, run_timeout_ms=24000))
    if fault == 'executable': registration = replace(registration,
        executable=replace(registration.executable, sha256='f'*64))
    with pytest.raises(ValueError): validate_registration(registration, outer)


@pytest.mark.parametrize('fault', ['runtime', 'protocol', 'controller', 'source'])
def test_reference_reader_rejects_changed_originals(tmp_path, monkeypatch, fault):
    workspace, staged, request, _ = fixture(tmp_path)
    if fault == 'source':
        monkeypatch.setattr('rocell.application.absolute_wrist_reference_reader.source_fingerprint', lambda _: 'f'*64)
    else:
        (staged.registration.working_directory/(fault+'.original.json')).write_bytes(b'{}')
    reader = AbsoluteWristReferenceReader(request, workspace=workspace, root=tmp_path)
    with pytest.raises(ValueError): reader()
    with pytest.raises(ValueError): FrozenAbsoluteWristReferences(reader)
