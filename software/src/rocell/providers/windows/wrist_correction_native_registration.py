"""Exact correction runtime pins; validation does not launch or qualify IO."""
from pathlib import Path
import sys

from rocell.application.first_motion_contract import canonical
from .wrist_correction_native_protocol import (
    WORKER_ID,REQUEST_SCHEMA,RESULT_SCHEMA,fixed_budget,validate_payload,require,digest)


def validate_registration(registration,outer):
    from .owned_worker_process import WorkerProcessRegistration,OwnedWorkerRequest,decode_owned_json,owned_registration_document
    from .wrist_correction_native_package import CHILD,expected_archive
    from .owned_arm_feedback_package import _read,MAX_FILE_BYTES
    require(type(registration) is WorkerProcessRegistration and type(outer) is OwnedWorkerRequest,
        'Exact correction runtime registration required')
    registration.__post_init__();outer.__post_init__()
    payload=decode_owned_json(outer.payload_json,maximum=60*1024)
    body=validate_payload(payload).to_dict()
    directory=Path(payload['root'])/(body['attempt_id']+'-wrist-correction-native-child')
    require(registration.worker_id==WORKER_ID and registration.composition=='PHYSICAL_UNQUALIFIED'
        and registration.request_schema==REQUEST_SCHEMA and registration.result_schema==RESULT_SCHEMA
        and registration.working_directory==directory,'Correction registration domain mismatch')
    executable=registration.executable
    require(executable.path==Path(getattr(sys,'_base_executable',sys.executable))
        and executable.sha256==digest(_read(executable.path,executable.maximum_bytes)),
        'Correction interpreter changed')
    pins=registration.package_files
    require(len(pins)==4 and pins[0].path==CHILD
        and pins[1].path==directory/'wrist-correction-native.zip'
        and pins[2].path==directory/'controller.original.json'
        and pins[3].path==directory/'protocol.original.json'
        and registration.argv==('-I','-S',str(CHILD),str(pins[1].path),pins[1].sha256,'execute-one'),
        'Fixed correction arguments and pins required')
    require(pins[0].sha256==digest(_read(CHILD,MAX_FILE_BYTES))
        and pins[1].sha256==digest(expected_archive())
        and pins[1].sha256==digest(_read(pins[1].path,pins[1].maximum_bytes)),
        'Correction child/archive differs from current source')
    for pin,ref in ((pins[2],'native_controller_review_sha256'),(pins[3],'protocol_review_sha256')):
        require(pin.sha256==body['references'][ref] and digest(_read(pin.path,128*1024))==pin.sha256,
            'Correction retained original differs')
    require(registration.budget==fixed_budget() and
        canonical(payload['registration'])==canonical(owned_registration_document(registration)),
        'Correction budget/registration differs')
    require(outer.attempt_id==body['attempt_id'] and outer.session_id==body['session_id']
        and outer.source_sha256==body['references']['source_sha256']
        and outer.operation_sha256==digest(canonical(payload))
        and outer.selected_identity_sha256==digest(canonical(body['usb_identity']))
        and outer.expires_at_ns==body['deadline_ns'],'Correction outer operation differs')
    return payload
