"""Fixed absolute_wrist child composition behind the guarded isolated entry.

Parent fixed-registration/package checks and owned process supervision are
mandatory. This function adds child-side original/key/metadata verification.
"""
from pathlib import Path
from threading import Event
import time

from rocell.application.absolute_wrist_reference_reader import AbsoluteWristReferenceReader, FrozenAbsoluteWristReferences
from rocell.application.absolute_wrist_worker_claim import claim_absolute_wrist_worker
from rocell.application.physical_onboarding_durability import safe_root
from rocell.safety.absolute_wrist_admission import admit_absolute_wrist
from .absolute_wrist_native_protocol import decode_request
from .absolute_wrist_prelaunch import verify_reserved_absolute_wrist_entry
from .endpoint_child_execution import decode_controller_binding
from .absolute_wrist_current_context import AbsoluteWristCurrentContextReader, AuthenticatedAbsoluteWristReader
from .absolute_wrist_serial_api import WindowsAbsoluteWristSerialApi
from .absolute_wrist_trial_execution import execute_native_absolute_wrist_trial
from .bench_review_key import load_host_absolute_wrist_review_authority
from .controller_metadata import WindowsControllerMetadataAcquirer


def execute_absolute_wrist_child(workspace, request_raw, *, cancellation, clock_ns=time.monotonic_ns):
    if type(cancellation) is not Event or not callable(clock_ns):
        raise ValueError('Owned cancellation and clock required')
    if cancellation.is_set():
        raise ValueError('AbsoluteWrist child cancelled before preparation')
    wire = decode_request(request_raw)
    payload = wire['payload']
    request = verify_reserved_absolute_wrist_entry(payload, workspace=workspace, clock_ns=clock_ns)
    root = safe_root(Path(payload['root']))
    references = FrozenAbsoluteWristReferences(AbsoluteWristReferenceReader(request, workspace=workspace, root=root))
    current = dict(references())
    binding = decode_controller_binding(references.original('native_controller_review_sha256'), request)
    authority = load_host_absolute_wrist_review_authority(workspace)
    claim = claim_absolute_wrist_worker(root, request, launch_sha256=payload['launch_sha256'],
        current_source_sha256=current['source_sha256'], current_runtime_sha256=current['runtime_sha256'], now_ns=clock_ns())
    if cancellation.is_set():
        raise ValueError('AbsoluteWrist child cancelled before metadata/admission')
    connection_id = request.to_dict()['attempt_id']
    metadata = WindowsControllerMetadataAcquirer(deadline_ns=request.to_dict()['deadline_ns']-2_000_000_000,
        cancellation=cancellation, monotonic_ns=clock_ns, maximum_acquisitions=7)
    # Seven bounded snapshots: admission; before/after open reservation;
    # native open; baseline binding; before/after dispatch reservation.
    # No retry allowance: cumulative native-call, byte and time limits remain.
    context = AbsoluteWristCurrentContextReader(request, binding=binding, connection_id=connection_id,
        metadata_reader=metadata, references_reader=references, clock_ns=clock_ns)
    reader = AuthenticatedAbsoluteWristReader(request, root=root, authority=authority,
        context_reader=context, clock_ns=clock_ns)
    permit = admit_absolute_wrist(request, reader=reader, root=root)
    try:
        if cancellation.is_set():
            raise ValueError('AbsoluteWrist child cancelled before native facade')
        api = WindowsAbsoluteWristSerialApi.from_absolute_wrist_permit(request, permit,
            port_name=binding.identity.port_name, connection_id=connection_id)
        return execute_native_absolute_wrist_trial(request, permit, api, worker_claim=claim,
            current_source_sha256=current['source_sha256'], current_runtime_sha256=current['runtime_sha256'],
            cancellation=cancellation, clock_ns=clock_ns)
    finally:
        permit.revoke()
