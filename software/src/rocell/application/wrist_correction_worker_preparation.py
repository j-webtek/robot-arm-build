"""Stage immutable correction runtime, then bind a reviewed one-use launch.

No review is invented and no process is launched. Staging precedes the short
review lifetime; preparation rechecks source, controller and signed evidence.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import time
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root,contained_path,publish_reservation_bytes,read_bounded_regular_file
from .wizard_diagnostic_coordinator import source_fingerprint,decode_diagnostic_json
from .physical_connection_contracts import EvidenceOrigin
from .wrist_correction_reference_reader import WristCorrectionReferenceReader
from .wrist_correction_worker_claim import reserve_correction_launch
from rocell.providers.windows import wrist_correction_native_package as package
from rocell.providers.windows import wrist_correction_native_protocol as protocol
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.providers.windows.wrist_correction_evidence_store import stage_evidence
from rocell.providers.windows.wrist_correction_native_registration import validate_registration
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,WorkerProcessRegistration,OwnedWorkerRequest,owned_registration_document)


@dataclass(frozen=True)
class StagedCorrectionRuntime:
    registration: WorkerProcessRegistration
    source_sha256: str
    attempt_id: str
    root: Path


@dataclass(frozen=True)
class PreparedCorrectionWorker:
    registration: WorkerProcessRegistration
    request: OwnedWorkerRequest


def stage_correction_runtime(workspace,*,root,attempt_id,controller_original,protocol_original):
    protocol.require(type(attempt_id) is str and re.fullmatch('operation-[a-f0-9]{32}',attempt_id),
        'Host-selected correction attempt required')
    for raw in (controller_original,protocol_original):
        value=decode_diagnostic_json(raw,maximum=128*1024)
        protocol.require(type(raw) is bytes and type(value) is dict and bool(value) and canonical(value)==raw,
            'Canonical controller/protocol originals required')
    root=safe_root(Path(root));workspace=safe_root(Path(workspace))
    source=source_fingerprint(workspace)
    directory=contained_path(root,attempt_id+'-wrist-correction-native-child',label='correction runtime')
    directory.mkdir(exist_ok=False)
    for name,raw in (('controller.original.json',controller_original),('protocol.original.json',protocol_original)):
        publish_reservation_bytes(directory,name,raw,maximum_bytes=128*1024)
    archive=package.prepare(directory)
    def pin(path):
        return PinnedWorkerFile(path,protocol.digest(read_bounded_regular_file(path,maximum_bytes=32*1024*1024)))
    pins=tuple(pin(path) for path in (package.CHILD,archive,directory/'controller.original.json',directory/'protocol.original.json'))
    registration=WorkerProcessRegistration(protocol.WORKER_ID,pin(Path(getattr(sys,'_base_executable',sys.executable))),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),pins,directory,
        protocol.fixed_budget(),'PHYSICAL_UNQUALIFIED',protocol.REQUEST_SCHEMA,protocol.RESULT_SCHEMA)
    publish_reservation_bytes(directory,'runtime.original.json',canonical(owned_registration_document(registration)),maximum_bytes=32768)
    protocol.require(source_fingerprint(workspace)==source,'Source changed during correction staging')
    return StagedCorrectionRuntime(registration,source,attempt_id,root)


def prepare_correction_worker(workspace,staged,request,*,plan_original,originals,clock_ns=time.monotonic_ns):
    from rocell.providers.windows.bench_review_key import load_host_wrist_correction_review_authority
    from rocell.providers.windows.endpoint_child_execution import decode_controller_binding
    protocol.require(type(staged) is StagedCorrectionRuntime and type(request) is WristCorrectionContextRequest
        and type(plan_original) is bytes and callable(clock_ns),'Exact correction preparation inputs required')
    body=request.to_dict();last=None
    protocol.require(body['attempt_id']==staged.attempt_id and body['references']['source_sha256']==staged.source_sha256,
        'Staged correction attempt/source differs')
    def now():
        nonlocal last
        tick=clock_ns();request.require_start_time(tick)
        protocol.require((last is None or tick>=last) and tick+27_000_000_000<=body['deadline_ns'],
            'Correction preparation clock/lifetime invalid')
        last=tick;return tick
    now()
    refs=WristCorrectionReferenceReader(request,workspace=workspace,root=staged.root)
    current=dict(refs());controller=decode_controller_binding(refs.original('native_controller_review_sha256'),request)
    usb=body['usb_identity']
    protocol.require(controller.origin is EvidenceOrigin.PHYSICAL_OBSERVATION and
        (controller.identity.vid,controller.identity.pid,controller.identity.unit_serial)==
        (f"{usb['vid']:04x}",f"{usb['pid']:04x}",usb['serial_number']), 'Correction controller unit differs')
    registration=owned_registration_document(staged.registration)
    protocol.require(canonical(registration)==refs.original('runtime_sha256'),'Staged correction runtime changed')
    authority=load_host_wrist_correction_review_authority(workspace)
    authority.verify_plan(plan_original,context=body,originals=originals,now_ns=now(),expected_basis='RETAINED_PHYSICAL_CAPTURE')
    payload=dict(schema=protocol.PAYLOAD_SCHEMA,root=str(staged.root),context=body,registration=registration,
        launch_sha256='0'*64,review_authority_id='local-wrist-correction-review-v1',
        plan_sha256=protocol.digest(plan_original),originals=protocol.evidence_manifest(originals),expected_basis='RETAINED_PHYSICAL_CAPTURE')
    stage_evidence(payload,assigned_root=staged.root,originals=originals,plan_raw=plan_original)
    protocol.require(dict(refs())==current,'Correction references changed before reservation')
    payload['launch_sha256']=reserve_correction_launch(payload,root=staged.root,authority=authority,now_ns=now())
    outer=OwnedWorkerRequest(body['attempt_id'],body['session_id'],current['source_sha256'],
        protocol.digest(canonical(payload)),protocol.digest(canonical(usb)),body['deadline_ns'],canonical(payload))
    validate_registration(staged.registration,outer)
    now()
    return PreparedCorrectionWorker(staged.registration,outer)
