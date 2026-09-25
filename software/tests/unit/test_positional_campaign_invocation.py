"""Observed invocation consistency only; dummy files never execute."""
import hashlib
from dataclasses import asdict

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_reference_reader import ORIGINAL_FILES
from rocell.providers.windows.positional_campaign_invocation import verify_actual_invocation, PINNED_REFERENCES
from rocell.providers.windows import positional_campaign_native_protocol as protocol
from test_positional_campaign_native_protocol import fixture, seal


def prepared(tmp_path):
    wire = fixture(tmp_path)
    body = wire['payload']['campaign_intent']
    directory = tmp_path / (body['campaign_id'] + '-positional-native-child')
    directory.mkdir()
    def pin(path):
        path.write_bytes(b'INCAPABLE FIXTURE: ' + path.name.encode())
        return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), maximum_bytes=8192)
    exe = pin(tmp_path/'python.exe')
    pins = [pin(tmp_path/'_positional_campaign_native_child.py'), pin(directory/'positional-campaign-native.zip')]
    for name in PINNED_REFERENCES:
        item = pin(directory/ORIGINAL_FILES[name])
        body['references'][name] = item['sha256']
        pins.append(item)
    argv = ['-I', '-S', pins[0]['path'], pins[1]['path'], pins[1]['sha256'], 'execute-campaign']
    document = dict(worker_id=protocol.WORKER_ID, executable=exe, argv=argv, package_files=pins,
        working_directory=str(directory), budget=asdict(protocol.fixed_budget()), composition='PHYSICAL_UNQUALIFIED',
        request_schema=protocol.REQUEST_SCHEMA, result_schema=protocol.RESULT_SCHEMA)
    body['references']['runtime_sha256'] = hashlib.sha256(canonical(document)).hexdigest()
    wire['payload']['registration'] = document
    wire['registration_sha256'] = body['references']['runtime_sha256']
    wire['operation_sha256'] = hashlib.sha256(canonical(body)).hexdigest()
    args = dict(entry_path=pins[0]['path'], executable=exe['path'], argv=tuple(argv), working_directory=directory)
    return wire, args, pins


def test_observed_invocation_matches_without_claiming_runtime_authenticity(tmp_path):
    wire, args, _ = prepared(tmp_path)
    assert verify_actual_invocation(seal(wire), **args)['worker_id'] == protocol.WORKER_ID


@pytest.mark.parametrize('fault', ['cwd', 'exe', 'entry', 'argv', 'bytes', 'evidence', 'pin_order', 'budget'])
def test_changed_process_observation_or_resealed_registration_rejected(tmp_path, fault):
    wire, args, pins = prepared(tmp_path)
    if fault == 'cwd': args['working_directory'] = tmp_path
    if fault == 'exe': args['executable'] = tmp_path/'other.exe'
    if fault == 'entry': args['entry_path'] = tmp_path/'other.py'
    if fault == 'argv': args['argv'] = args['argv'][:-1] + ('check-imports',)
    if fault == 'bytes':
        from pathlib import Path
        Path(pins[1]['path']).write_bytes(b'changed')
    if fault == 'evidence': pins[2]['sha256'] = 'a'*64
    if fault == 'pin_order': pins[2], pins[3] = pins[3], pins[2]
    if fault == 'budget': wire['payload']['registration']['budget']['run_timeout_ms'] = 27000
    body = wire['payload']['campaign_intent']
    body['references']['runtime_sha256'] = hashlib.sha256(canonical(wire['payload']['registration'])).hexdigest()
    wire['registration_sha256'] = body['references']['runtime_sha256']
    wire['operation_sha256'] = hashlib.sha256(canonical(body)).hexdigest()
    with pytest.raises(ValueError): verify_actual_invocation(seal(wire), **args)
