"""Stage immutable runtime first, then prepare one timed reviewed worker request.

Neither phase opens a device or launches a process. Partial files are retained;
an attempt directory is never silently overwritten or reused.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sys
import time

from rocell.safety.observational_review_authority import ObservationalIntent
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .observational_reference_reader import ObservationalReferenceReader
from .observational_worker_claim import reserve_observational_launch
from .physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows import observational_native_package as package
from rocell.providers.windows import observational_native_protocol as protocol
from rocell.providers.windows.observational_native_registration import validate_registration
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile, WorkerProcessRegistration, OwnedWorkerRequest, owned_registration_document,
)


@dataclass(frozen=True)
class StagedObservationalRuntime:
    registration: WorkerProcessRegistration
    source_sha256: str
    attempt_id: str
    root: Path


@dataclass(frozen=True)
class PreparedObservationalWorker:
    registration: WorkerProcessRegistration
    request: OwnedWorkerRequest


def stage_observational_runtime(workspace, *, root, attempt_id, controller_original, protocol_original):
    if type(attempt_id) is not str or not re.fullmatch('operation-[a-f0-9]{32}', attempt_id):
        raise ValueError('Host-selected observational attempt required')
    for raw in (controller_original, protocol_original):
        if type(raw) is not bytes:
            raise ValueError('Immutable structured original bytes required')
        value = decode_diagnostic_json(raw, maximum=128*1024)
        if type(value) is not dict or not value or canonical(value) != raw:
            raise ValueError('Canonical structured controller/protocol originals required')
    root = safe_root(Path(root))
    source = source_fingerprint(Path(workspace))
    directory = contained_path(root, attempt_id+'-observational-native-child', label='observational worker directory')
    directory.mkdir(exist_ok=False)
    for name, raw in (('controller.original.json',controller_original), ('protocol.original.json',protocol_original)):
        publish_reservation_bytes(directory, name, raw, maximum_bytes=128*1024)
    archive = package.prepare(directory)
    def pin(path):
        raw = read_bounded_regular_file(path, maximum_bytes=32*1024*1024)
        return PinnedWorkerFile(path, hashlib.sha256(raw).hexdigest())
    pins = (pin(package.CHILD),pin(archive),pin(directory/'controller.original.json'),pin(directory/'protocol.original.json'))
    reg = WorkerProcessRegistration(protocol.WORKER_ID,
        pin(Path(getattr(sys,'_base_executable',sys.executable))),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),
        pins,directory,protocol.fixed_budget(),'PHYSICAL_UNQUALIFIED',protocol.REQUEST_SCHEMA,protocol.RESULT_SCHEMA)
    publish_reservation_bytes(directory, 'runtime.original.json', canonical(owned_registration_document(reg)), maximum_bytes=32768)
    if source_fingerprint(Path(workspace)) != source:
        raise ValueError('Source changed while staging; staged files retained without approval')
    return StagedObservationalRuntime(reg, source, attempt_id, root)


def prepare_observational_worker(workspace, staged, request, *, review_original, clock_ns=time.monotonic_ns):
    from rocell.providers.windows.bench_review_key import load_host_observational_review_authority
    from rocell.providers.windows.endpoint_child_execution import decode_controller_binding
    if (type(staged) is not StagedObservationalRuntime or type(request) is not ObservationalIntent
            or type(review_original) is not bytes or not callable(clock_ns)):
        raise ValueError('Exact staged runtime, intent and signed review required')
    body = request.to_dict()
    if body['attempt_id'] != staged.attempt_id or body['references']['source_sha256'] != staged.source_sha256:
        raise ValueError('Staged attempt/source differs from reviewed request')
    def now():
        tick = clock_ns()
        request.require_start_time(tick)
        if tick+27_000_000_000 > body['deadline_ns']:
            raise ValueError('Insufficient supervised run/cleanup lifetime')
        return tick
    now()
    refs = ObservationalReferenceReader(request, workspace=workspace, root=staged.root)
    current = dict(refs())
    binding = decode_controller_binding(refs.original('native_controller_review_sha256'), request)
    usb = body['usb_identity']
    if (binding.origin is not EvidenceOrigin.PHYSICAL_OBSERVATION
            or (binding.identity.vid,binding.identity.pid,binding.identity.unit_serial)
               != (f"{usb['vid']:04x}",f"{usb['pid']:04x}",usb['serial_number'])):
        raise ValueError('Reviewed controller does not match observational unit')
    runtime = canonical(owned_registration_document(staged.registration))
    if runtime != refs.original('runtime_sha256'):
        raise ValueError('Staged runtime registration changed')
    authority = load_host_observational_review_authority(workspace)
    authority.verify(review_original, expected_intent=body, current_usb_identity=usb,
        current_references=current, now_ns=now())
    publish_reservation_bytes(staged.root, body['attempt_id']+'-observational-reviews.json',
                              review_original, maximum_bytes=8192)
    launch = reserve_observational_launch(staged.root, request, runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(review_original).hexdigest(), now_ns=now())
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(staged.root), observational_intent=body,
        launch_sha256=launch, registration=owned_registration_document(staged.registration),
        review_authority_id='local-observational-review-v1')
    outer = OwnedWorkerRequest(body['attempt_id'],body['session_id'],current['source_sha256'],
        request.request_sha256,hashlib.sha256(canonical(usb)).hexdigest(),body['deadline_ns'],canonical(payload))
    validate_registration(staged.registration, outer)
    now()
    return PreparedObservationalWorker(staged.registration, outer)
