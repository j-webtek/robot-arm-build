"""Associate actual child-process observations with the reviewed runtime pins.

This validates bytes and invocation, not trust in a supplied registration.
The bootstrap must also authenticate review/source and reserve the attempt.
No device access or process launch is performed here.
"""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.positional_campaign_reference_reader import ORIGINAL_FILES
from .owned_worker_process import PinnedWorkerFile, WorkerProcessBudget, WorkerProcessRegistration, owned_registration_document
from .positional_campaign_native_protocol import decode_request, fixed_budget, WORKER_ID, REQUEST_SCHEMA, RESULT_SCHEMA

# Keep the process owner's bounded pin roster for code and connection evidence.
# All other originals are checked by PositionalCampaignReferenceReader during
# bootstrap. Runtime itself cannot pin its own registration (a circular hash).
PINNED_REFERENCES = ('native_controller_review_sha256', 'protocol_review_sha256')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_actual_invocation(request_raw, *, entry_path, executable, argv, working_directory):
    wire = decode_request(request_raw)
    payload = wire['payload']
    document = payload['registration']
    _require(set(document) == {'worker_id', 'executable', 'argv', 'package_files',
        'working_directory', 'budget', 'composition', 'request_schema', 'result_schema'},
        'Exact campaign runtime registration required')
    def pin(value):
        _require(type(value) is dict and set(value) == {'path', 'sha256', 'maximum_bytes'},
            'Exact campaign file pin required')
        return PinnedWorkerFile(Path(value['path']), value['sha256'], value['maximum_bytes'])
    _require(type(document['argv']) is list and type(document['package_files']) is list
        and type(document['budget']) is dict, 'Exact runtime collections required')
    registration = WorkerProcessRegistration(document['worker_id'], pin(document['executable']),
        tuple(document['argv']), tuple(pin(value) for value in document['package_files']),
        Path(document['working_directory']), WorkerProcessBudget(**document['budget']),
        document['composition'], document['request_schema'], document['result_schema'])
    _require(canonical(owned_registration_document(registration)) == canonical(document),
        'Campaign runtime changed during decoding')
    directory = Path(payload['root']) / (wire['attempt_id'] + '-positional-native-child')
    pins = registration.package_files
    _require(registration.worker_id == WORKER_ID and registration.request_schema == REQUEST_SCHEMA
        and registration.result_schema == RESULT_SCHEMA and registration.composition == 'PHYSICAL_UNQUALIFIED'
        and registration.budget == fixed_budget(payload['campaign_intent']['schema']) and registration.working_directory == directory
        and Path(working_directory) == directory and registration.executable.path == Path(executable)
        and len(pins) == 2 + len(PINNED_REFERENCES), 'Actual campaign runtime/domain differs')
    _require(pins[0].path == Path(entry_path) and pins[0].path.name == '_positional_campaign_native_child.py'
        and pins[1].path == directory / 'positional-campaign-native.zip'
        and registration.argv == ('-I', '-S', str(entry_path), str(pins[1].path), pins[1].sha256, 'execute-campaign')
        and tuple(argv) == registration.argv, 'Actual campaign arguments differ')
    for item, reference in zip(pins[2:], PINNED_REFERENCES):
        _require(item.path == directory / ORIGINAL_FILES[reference]
            and item.sha256 == payload['campaign_intent']['references'][reference],
            'Campaign evidence pin differs')
    limits = (32*1024*1024, 2*1024*1024, 8*1024*1024) + tuple(
        2_097_152 if name == 'owned_baseline_sha256' else 131072 for name in PINNED_REFERENCES)
    for item, limit in zip((registration.executable,) + pins, limits):
        raw = read_bounded_regular_file(item.path, maximum_bytes=min(limit, item.maximum_bytes))
        _require(hashlib.sha256(raw).hexdigest() == item.sha256, 'Actual campaign pinned bytes changed')
    return wire
