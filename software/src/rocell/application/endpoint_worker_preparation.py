"""Coordinator preparation of one fixed endpoint worker; never launches it.

All roots, requests and reviews are coordinator-owned. A partial preparation is
retained and cannot be retried with the same attempt ID. Returned registration
data is not a native authorization or evidence that physical checks passed.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sys
import time

from .arm_bench_qualification_contract import _canonical
from .endpoint_trial_contract import EndpointTrialRequest
from .endpoint_evidence_snapshot import prepare_snapshot
from .endpoint_worker_claim import reserve_endpoint_launch
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file
from rocell.safety.bench_review_authority import MAX_BUNDLE_BYTES
from rocell.providers.windows.bench_review_key import load_host_bench_review_authority
from rocell.providers.windows.endpoint_child_execution import load_controller_binding
from .physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows import endpoint_native_package as package
from rocell.providers.windows import endpoint_native_registration as protocol
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,WorkerProcessRegistration,OwnedWorkerRequest,owned_registration_document,
)

# Shared with the coordinator so a review delay is diagnosed before worker
# preparation. This reserves the existing fixed parent run and cleanup budget.
MINIMUM_PREPARATION_REMAINING_NS = 27_000_000_000


@dataclass(frozen=True)
class PreparedEndpointWorker:
    registration: WorkerProcessRegistration
    request: OwnedWorkerRequest


def prepare_endpoint_worker(workspace,request,*,review_root,session_id,clock_ns=time.monotonic_ns):
    if type(request) is not EndpointTrialRequest:
        raise ValueError('Exact endpoint request required')
    if type(session_id) is not str or re.fullmatch(r'wizard-[0-9a-f]{32}',session_id) is None:
        raise ValueError('Exact coordinator session required')
    body = request.to_dict()
    def budget():
        now = clock_ns()
        if type(now) is not int or not body['issued_monotonic_ns']<=now:
            raise ValueError('Invalid preparation clock')
        if now+MINIMUM_PREPARATION_REMAINING_NS>body['deadline_monotonic_ns']:
            raise ValueError('Insufficient fixed parent run/cleanup lifetime')
        return now
    budget()
    root = safe_root(Path(review_root))
    authority = load_host_bench_review_authority(workspace)
    review_path = contained_path(root,body['attempt_id']+'-bench-reviews.json',label='signed bench reviews')
    def authenticate():
        raw = read_bounded_regular_file(review_path,maximum_bytes=MAX_BUNDLE_BYTES)
        authority.verify(request,raw,connection_id=body['attempt_id'],
            current_references=tuple(sorted(body['references'].items())),now_ns=budget())
        return raw
    reviews = authenticate()
    binding = load_controller_binding(root,request)
    usb = body['usb_identity']
    if (binding.origin is not EvidenceOrigin.PHYSICAL_OBSERVATION or
            (binding.identity.vid,binding.identity.pid,binding.identity.unit_serial)!=
            (f"{usb['vid']:04x}",f"{usb['pid']:04x}",usb['serial_number'])):
        raise ValueError('Reviewed physical controller/request mismatch')
    directory = contained_path(root,body['attempt_id']+'-endpoint-native-child',label='endpoint worker directory')
    directory.mkdir(exist_ok=False)
    evidence = prepare_snapshot(workspace,request,reference_root=root,directory=directory)
    archive = package.prepare(directory)
    def pin(path):
        raw = read_bounded_regular_file(path,maximum_bytes=32*1024*1024)
        return PinnedWorkerFile(path,hashlib.sha256(raw).hexdigest())
    pins = (pin(package.CHILD),pin(archive),pin(evidence))
    reg = WorkerProcessRegistration(protocol.WORKER_ID,
        pin(Path(getattr(sys,'_base_executable',sys.executable))),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),
        pins,directory,protocol.fixed_budget(),'PHYSICAL_UNQUALIFIED',
        protocol.REQUEST_SCHEMA,protocol.RESULT_SCHEMA)
    runtime = owned_registration_document(reg)
    if authenticate()!=reviews: raise ValueError('Review originals changed during preparation')
    launch = reserve_endpoint_launch(root,request,runtime_original=_canonical(runtime),
        review_bundle_sha256=hashlib.sha256(reviews).hexdigest(),now_ns=budget())
    payload = {'schema':protocol.PAYLOAD_SCHEMA,'root':str(root),'session_id':session_id,
        'endpoint_request':request.to_dict(),'launch_sha256':launch,'registration':runtime,
        'review_authority_id':'local-bench-review-v1'}
    outer = OwnedWorkerRequest(body['attempt_id'],session_id,body['references']['source_sha256'],
        request.request_sha256,protocol.identity_hash(request),body['deadline_monotonic_ns'],_canonical(payload))
    protocol.validate_registration(reg,outer)
    budget()
    return PreparedEndpointWorker(reg,outer)
