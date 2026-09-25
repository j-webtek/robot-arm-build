"""Closed endpoint handoff and fixed registration; no activation decision.

The owned process supervisor still holds this physical composition. Accepting
its data format is not permission to launch or to load a review authority key.
"""

import hashlib
from pathlib import Path
import re
import sys

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_trial_contract import EndpointTrialRequest

PAYLOAD_SCHEMA = 'rocell.endpoint_native_handoff.v1'
REQUEST_SCHEMA = 'rocell.owned_endpoint_native_request.v1'
RESULT_SCHEMA = 'rocell.owned_endpoint_native_result.v1'
WORKER_ID = 'physical-endpoint-trial'


def _require(value,code):
    if not value: raise ValueError(code)


def validate_payload(value):
    from .owned_worker_process import _path, _hash
    _require(type(value) is dict and set(value)=={'schema','root','session_id','endpoint_request',
             'launch_sha256','registration','review_authority_id'},'ENDPOINT_HANDOFF_FIELDS')
    _require(value['schema']==PAYLOAD_SCHEMA and type(value['root']) is str
             and type(value['registration']) is dict
             and value['review_authority_id']=='local-bench-review-v1','ENDPOINT_HANDOFF_DOMAIN')
    _path(Path(value['root']))
    _hash(value['launch_sha256'])
    _require(type(value['session_id']) is str and re.fullmatch(r'wizard-[a-f0-9]{32}',value['session_id']) is not None,
             'ENDPOINT_SESSION_REQUIRED')
    request = EndpointTrialRequest(_canonical(value['endpoint_request']))
    body = request.to_dict()
    _require(body['deadline_monotonic_ns']-body['issued_monotonic_ns'] >= 27_000_000_000,
             'ENDPOINT_PARENT_RUN_AND_CLEANUP_BUDGET_REQUIRED')
    return request


def fixed_budget():
    from .owned_worker_process import WorkerProcessBudget
    return WorkerProcessBudget(run_timeout_ms=25000,cleanup_timeout_ms=2000,
        stdin_bytes=65536,stdout_bytes=256*1024,stderr_bytes=8192,process_count=1)


def identity_hash(request):
    return hashlib.sha256(_canonical(request.to_dict()['usb_identity'])).hexdigest()


def verify_reserved_entry(payload,*,clock_ns):
    """Parent-only verification before create/resume; no device or permit access."""
    from .endpoint_native_package import CHILD
    from .bench_review_key import load_host_bench_review_authority
    from rocell.application.endpoint_reference_reader import EndpointReferenceReader
    from rocell.application.endpoint_worker_claim import _verify_launch
    from rocell.application.physical_onboarding_durability import read_bounded_regular_file,contained_path,safe_root
    from rocell.safety.bench_review_authority import MAX_BUNDLE_BYTES
    request = validate_payload(payload)
    workspace = CHILD.parents[5]
    refs = dict(EndpointReferenceReader(request,workspace=workspace,reference_root=payload['root'])())
    runtime_sha = hashlib.sha256(_canonical(payload['registration'])).hexdigest()
    _verify_launch(payload['root'],request,payload['launch_sha256'],refs['source_sha256'],runtime_sha,clock_ns())
    raw = read_bounded_regular_file(contained_path(safe_root(Path(payload['root'])),
        request.to_dict()['attempt_id']+'-bench-reviews.json',label='parent signed reviews'),maximum_bytes=MAX_BUNDLE_BYTES)
    authority = load_host_bench_review_authority(workspace)
    authority.verify(request,raw,connection_id=request.to_dict()['attempt_id'],
                     current_references=tuple(sorted(refs.items())),now_ns=clock_ns())


def validate_registration(registration,outer):
    from .owned_worker_process import (WorkerProcessRegistration,OwnedWorkerRequest,
        decode_owned_json,owned_registration_document)
    from .endpoint_native_package import CHILD,expected_archive
    from .owned_arm_feedback_package import _read,MAX_FILE_BYTES
    from rocell.application.endpoint_evidence_snapshot import decode_snapshot,FILENAME,MAX_BYTES
    _require(type(registration) is WorkerProcessRegistration and type(outer) is OwnedWorkerRequest,
             'ENDPOINT_EXACT_REGISTRATION_TYPES')
    registration.__post_init__()
    outer.__post_init__()
    payload = decode_owned_json(outer.payload_json,maximum=60*1024)
    request = validate_payload(payload)
    body = request.to_dict()
    _require(registration.worker_id==WORKER_ID and registration.composition=='PHYSICAL_UNQUALIFIED'
             and registration.request_schema==REQUEST_SCHEMA and registration.result_schema==RESULT_SCHEMA,
             'ENDPOINT_REGISTRATION_DOMAIN')
    executable = registration.executable
    _require(executable.path==Path(getattr(sys,'_base_executable',sys.executable))
             and executable.sha256==hashlib.sha256(_read(executable.path,executable.maximum_bytes)).hexdigest(),
             'ENDPOINT_FIXED_INTERPRETER')
    pins = registration.package_files
    _require(len(pins)==3 and pins[0].path==CHILD
             and pins[1].path==registration.working_directory/'endpoint-native.zip'
             and pins[2].path==registration.working_directory/FILENAME
             and registration.argv==('-I','-S',str(CHILD),str(pins[1].path),pins[1].sha256,'execute-one'),
             'ENDPOINT_FIXED_COMMAND')
    _require(pins[0].sha256==hashlib.sha256(_read(CHILD,MAX_FILE_BYTES)).hexdigest()
             and pins[1].sha256==hashlib.sha256(expected_archive()).hexdigest(),
             'ENDPOINT_CURRENT_PACKAGE_SOURCE')
    evidence_raw = _read(pins[2].path,MAX_BYTES)
    _require(hashlib.sha256(evidence_raw).hexdigest()==pins[2].sha256,'ENDPOINT_EVIDENCE_PIN_CHANGED')
    decode_snapshot(evidence_raw,request)
    _require(registration.budget==fixed_budget(),'ENDPOINT_FIXED_RESOURCE_BUDGET')
    _require(_canonical(payload['registration'])==_canonical(owned_registration_document(registration)),
             'ENDPOINT_RUNTIME_ORIGINAL_BINDING')
    _require(outer.attempt_id==body['attempt_id'] and outer.session_id==payload['session_id']
             and outer.source_sha256==body['references']['source_sha256']
             and outer.operation_sha256==request.request_sha256
             and outer.selected_identity_sha256==identity_hash(request)
             and outer.expires_at_ns==body['deadline_monotonic_ns'],'ENDPOINT_OUTER_CONTEXT_BINDING')
    _require(registration.working_directory==Path(payload['root'])/(outer.attempt_id+'-endpoint-native-child'),
             'ENDPOINT_ASSIGNED_DIRECTORY')
    return payload
