"""Parent validation with real interpreter/archive pins; no process launch."""
import hashlib
from dataclasses import replace
from pathlib import Path
import sys

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import positional_campaign_native_package as package
from rocell.providers.windows import positional_campaign_native_protocol as protocol
from rocell.providers.windows.owned_worker_process import PinnedWorkerFile, WorkerProcessRegistration, owned_registration_document
from rocell.providers.windows.positional_campaign_native_registration import validate_registration
from test_positional_campaign_native_protocol import fixture, seal


def prepared(tmp_path):
    wire = fixture(tmp_path)
    body = wire['payload']['campaign_intent']
    directory = tmp_path / (body['campaign_id'] + '-positional-native-child')
    directory.mkdir()
    archive = package.prepare(directory)
    controller = directory/'controller.original.json'
    controller.write_bytes(b'{"fixture_only":"controller"}')
    protocol_file = directory/'protocol.original.json'
    protocol_file.write_bytes(b'{"fixture_only":"protocol"}')
    def pin(path):
        return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())
    pins = tuple(map(pin, (package.CHILD, archive, controller, protocol_file)))
    registration = WorkerProcessRegistration(protocol.WORKER_ID,
        pin(Path(getattr(sys, '_base_executable', sys.executable))),
        ('-I', '-S', str(package.CHILD), str(archive), pins[1].sha256, 'execute-campaign'),
        pins, directory, budget=protocol.fixed_budget(), request_schema=protocol.REQUEST_SCHEMA,
        result_schema=protocol.RESULT_SCHEMA)
    body['references']['native_controller_review_sha256'] = pins[2].sha256
    body['references']['protocol_review_sha256'] = pins[3].sha256
    return registration, reseal(wire, registration)


def reseal(wire, registration):
    body = wire['payload']['campaign_intent']
    wire['payload']['registration'] = owned_registration_document(registration)
    body['references']['runtime_sha256'] = hashlib.sha256(canonical(wire['payload']['registration'])).hexdigest()
    wire['registration_sha256'] = body['references']['runtime_sha256']
    wire['operation_sha256'] = hashlib.sha256(canonical(body)).hexdigest()
    return seal(wire)


def test_current_runtime_validates_without_launch(tmp_path):
    registration, raw = prepared(tmp_path)
    assert validate_registration(registration, raw)['worker_id'] == protocol.WORKER_ID


@pytest.mark.parametrize('fault', ['argv', 'budget', 'domain', 'archive', 'controller', 'entry_hash', 'untyped'])
def test_altered_registration_or_files_rejected(tmp_path, fault):
    reg, raw = prepared(tmp_path)
    if fault == 'argv': reg = replace(reg, argv=reg.argv[:-1] + ('check-imports',))
    if fault == 'budget': reg = replace(reg, budget=replace(reg.budget, run_timeout_ms=27000))
    if fault == 'domain': reg = replace(reg, composition='INCAPABLE_PROCESS_FIXTURE')
    if fault in ('archive', 'controller'):
        reg.package_files[1 if fault == 'archive' else 2].path.write_bytes(b'changed')
    if fault == 'entry_hash': reg = replace(reg, package_files=(replace(reg.package_files[0], sha256='f'*64),) + reg.package_files[1:])
    if fault == 'untyped': reg = {}
    with pytest.raises(ValueError): validate_registration(reg, raw)


def test_rehashed_archive_still_must_match_current_source(tmp_path):
    reg, raw = prepared(tmp_path)
    wire = protocol.decode_request(raw)
    pin = reg.package_files[1]
    pin.path.write_bytes(b'Not the current source archive')
    changed = replace(pin, sha256=hashlib.sha256(pin.path.read_bytes()).hexdigest())
    reg = replace(reg, package_files=(reg.package_files[0], changed) + reg.package_files[2:],
        argv=reg.argv[:4] + (changed.sha256, 'execute-campaign'))
    with pytest.raises(ValueError, match='current source'):
        validate_registration(reg, reseal(wire, reg))
