"""Fixed observational registration checks; neither launch nor motion approval."""
import hashlib
from pathlib import Path
import sys

from rocell.application.first_motion_contract import canonical
from .observational_native_protocol import (
    WORKER_ID, REQUEST_SCHEMA, RESULT_SCHEMA, fixed_budget, validate_payload, _require,
)


def validate_registration(registration, outer):
    from .owned_worker_process import WorkerProcessRegistration, OwnedWorkerRequest, decode_owned_json, owned_registration_document
    from .observational_native_package import CHILD, expected_archive
    from .owned_arm_feedback_package import _read, MAX_FILE_BYTES
    _require(type(registration) is WorkerProcessRegistration and type(outer) is OwnedWorkerRequest,
             'Exact observational worker registration types required')
    registration.__post_init__()
    outer.__post_init__()
    payload = decode_owned_json(outer.payload_json, maximum=60*1024)
    request = validate_payload(payload)
    body = request.to_dict()
    directory = Path(payload['root'])/(body['attempt_id']+'-observational-native-child')
    _require(registration.worker_id == WORKER_ID and registration.composition == 'PHYSICAL_UNQUALIFIED'
        and registration.request_schema == REQUEST_SCHEMA and registration.result_schema == RESULT_SCHEMA
        and registration.working_directory == directory, 'Observational registration domain/directory mismatch')
    executable = registration.executable
    _require(executable.path == Path(getattr(sys, '_base_executable', sys.executable))
        and executable.sha256 == hashlib.sha256(_read(executable.path, executable.maximum_bytes)).hexdigest(),
        'Observational interpreter changed')
    pins = registration.package_files
    _require(len(pins) == 4 and pins[0].path == CHILD
        and pins[1].path == directory/'observational-native.zip'
        and pins[2].path == directory/'controller.original.json'
        and pins[3].path == directory/'protocol.original.json'
        and registration.argv == ('-I','-S',str(CHILD),str(pins[1].path),pins[1].sha256,'execute-one'),
        'Fixed observational command and original pins required')
    _require(pins[0].sha256 == hashlib.sha256(_read(CHILD, MAX_FILE_BYTES)).hexdigest()
        and pins[1].sha256 == hashlib.sha256(expected_archive()).hexdigest(),
        'Observational child/archive differs from current package')
    for pin, reference in ((pins[2],'native_controller_review_sha256'), (pins[3],'protocol_review_sha256')):
        _require(pin.sha256 == body['references'][reference]
            and hashlib.sha256(_read(pin.path, 128*1024)).hexdigest() == pin.sha256,
            'Observational retained original differs from signed reference')
    _require(hashlib.sha256(_read(pins[1].path, pins[1].maximum_bytes)).hexdigest() == pins[1].sha256,
             'Retained observational archive changed')
    _require(registration.budget == fixed_budget(), 'Observational resource budget cannot be widened')
    _require(canonical(payload['registration']) == canonical(owned_registration_document(registration)),
             'Observational registration original mismatch')
    _require(outer.attempt_id == body['attempt_id'] and outer.session_id == body['session_id']
        and outer.source_sha256 == body['references']['source_sha256']
        and outer.operation_sha256 == request.request_sha256
        and outer.selected_identity_sha256 == hashlib.sha256(canonical(body['usb_identity'])).hexdigest()
        and outer.expires_at_ns == body['deadline_ns'], 'Observational outer request mismatch')
    return payload
