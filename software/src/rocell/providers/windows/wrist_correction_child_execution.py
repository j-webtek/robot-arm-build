"""Fixed correction child composition, still behind an unregistered entry.

The parent must separately validate/contain the executable and retain failures.
No arbitrary transport factory or command override crosses this boundary.
"""
from pathlib import Path
from threading import Event
import time
from rocell.application.wrist_correction_reference_reader import WristCorrectionReferenceReader,FrozenWristCorrectionReferences
from rocell.application.wrist_correction_worker_claim import claim_correction_worker
from rocell.application.physical_onboarding_durability import safe_root
from rocell.safety.wrist_correction_admission import admit_wrist_correction
from .wrist_correction_native_protocol import decode_request,require
from .wrist_correction_prelaunch import verify_reserved_correction_entry
from .wrist_correction_evidence_store import load_evidence
from .wrist_correction_current_context import WristCorrectionCurrentContextReader,AuthenticatedWristCorrectionReader
from .wrist_correction_serial_api import WindowsWristCorrectionSerialApi
from .wrist_correction_trial_execution import _execute_claimed_correction_trial
from .bench_review_key import load_host_wrist_correction_review_authority
from .endpoint_child_execution import decode_controller_binding
from .controller_metadata import WindowsControllerMetadataAcquirer


def execute_correction_child(workspace,request_raw,*,cancellation,clock_ns=time.monotonic_ns):
    require(type(cancellation) is Event and callable(clock_ns),'Owned correction cancellation and clock required')
    require(not cancellation.is_set(),'Correction cancelled before preparation')
    payload=decode_request(request_raw)['payload']
    request=verify_reserved_correction_entry(payload,workspace=workspace,clock_ns=clock_ns)
    root=safe_root(Path(payload['root']))
    references=FrozenWristCorrectionReferences(WristCorrectionReferenceReader(request,workspace=workspace,root=root))
    current=dict(references())
    controller=decode_controller_binding(references.original('native_controller_review_sha256'),request)
    evidence=load_evidence(payload,assigned_root=root)
    authority=load_host_wrist_correction_review_authority(workspace)
    claim=claim_correction_worker(payload,root=root,authority=authority,
        current_source_sha256=current['source_sha256'],current_runtime_sha256=current['runtime_sha256'],now_ns=clock_ns())
    require(not cancellation.is_set(),'Correction cancelled before metadata/admission')
    # Eight checks: admission; two open-claim checks; native open; two
    # baseline-binding checks; two dispatch checks. No retries are allotted.
    metadata=WindowsControllerMetadataAcquirer(deadline_ns=request.to_dict()['deadline_ns']-2_000_000_000,
        cancellation=cancellation,monotonic_ns=clock_ns,maximum_acquisitions=8)
    connection_id=request.to_dict()['attempt_id']
    context=WristCorrectionCurrentContextReader(request,binding=controller,connection_id=connection_id,
        metadata_reader=metadata,references_reader=references,clock_ns=clock_ns)
    reader=AuthenticatedWristCorrectionReader(request,root=root,authority=authority,context_reader=context,
        originals=list(evidence.originals),expected_basis=payload['expected_basis'],clock_ns=clock_ns)
    permit=admit_wrist_correction(request,reader=reader,root=root,cancellation=cancellation)
    try:
        require(not cancellation.is_set(),'Correction cancelled before native facade')
        api=WindowsWristCorrectionSerialApi.from_correction_permit(request,permit,
            port_name=controller.identity.port_name,connection_id=connection_id)
        return _execute_claimed_correction_trial(payload,permit,api,worker_claim=claim,
            current_source_sha256=current['source_sha256'],current_runtime_sha256=current['runtime_sha256'],
            cancellation=cancellation,clock_ns=clock_ns)
    finally:
        permit.revoke()
