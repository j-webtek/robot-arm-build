"""Fixed commissioning registration checks; not launch or motion authorization."""
import hashlib
from pathlib import Path
import sys

from rocell.application.first_motion_contract import canonical as _canonical
from .first_motion_native_protocol import (
    WORKER_ID,REQUEST_SCHEMA,RESULT_SCHEMA,validate_payload,fixed_budget,_require,
)


def identity_hash(request):
    return hashlib.sha256(_canonical(request.to_dict()['usb_identity'])).hexdigest()


def validate_registration(registration,outer):
    from .owned_worker_process import (WorkerProcessRegistration,OwnedWorkerRequest,
        decode_owned_json,owned_registration_document)
    from .first_motion_native_package import CHILD,expected_archive
    from .owned_arm_feedback_package import _read,MAX_FILE_BYTES
    from rocell.application.first_motion_evidence_snapshot import decode_snapshot,FILENAME,MAX_BYTES
    _require(type(registration) is WorkerProcessRegistration and type(outer) is OwnedWorkerRequest,
             'COMMISSIONING_EXACT_REGISTRATION_TYPES')
    registration.__post_init__()
    outer.__post_init__()
    payload = decode_owned_json(outer.payload_json,maximum=60*1024)
    request = validate_payload(payload)
    body = request.to_dict()
    _require(registration.worker_id==WORKER_ID and registration.composition=='PHYSICAL_UNQUALIFIED'
             and registration.request_schema==REQUEST_SCHEMA and registration.result_schema==RESULT_SCHEMA,
             'COMMISSIONING_REGISTRATION_DOMAIN')
    executable = registration.executable
    _require(executable.path==Path(getattr(sys,'_base_executable',sys.executable))
             and executable.sha256==hashlib.sha256(_read(executable.path,executable.maximum_bytes)).hexdigest(),
             'COMMISSIONING_FIXED_INTERPRETER')
    pins = registration.package_files
    _require(len(pins)==3 and pins[0].path==CHILD
             and pins[1].path==registration.working_directory/'first-motion-native.zip'
             and pins[2].path==registration.working_directory/FILENAME
             and registration.argv==('-I','-S',str(CHILD),str(pins[1].path),pins[1].sha256,'execute-one'),
             'COMMISSIONING_FIXED_COMMAND')
    _require(pins[0].sha256==hashlib.sha256(_read(CHILD,MAX_FILE_BYTES)).hexdigest()
             and pins[1].sha256==hashlib.sha256(expected_archive()).hexdigest(),
             'COMMISSIONING_CURRENT_PACKAGE_SOURCE')
    evidence_raw = _read(pins[2].path,MAX_BYTES)
    _require(hashlib.sha256(evidence_raw).hexdigest()==pins[2].sha256,'COMMISSIONING_EVIDENCE_PIN_CHANGED')
    decode_snapshot(evidence_raw,request)
    _require(registration.budget==fixed_budget(),'COMMISSIONING_FIXED_RESOURCE_BUDGET')
    _require(_canonical(payload['registration'])==_canonical(owned_registration_document(registration)),
             'COMMISSIONING_RUNTIME_ORIGINAL_BINDING')
    _require(outer.attempt_id==body['attempt_id'] and outer.session_id==payload['session_id']
             and outer.source_sha256==body['references']['source_sha256']
             and outer.operation_sha256==request.request_sha256
             and outer.selected_identity_sha256==identity_hash(request)
             and outer.expires_at_ns==body['deadline_monotonic_ns'],'COMMISSIONING_OUTER_CONTEXT_BINDING')
    _require(registration.working_directory==Path(payload['root'])/(outer.attempt_id+'-first-motion-native-child'),
             'COMMISSIONING_ASSIGNED_DIRECTORY')
    return payload
