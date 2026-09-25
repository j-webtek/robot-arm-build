"""Fixed observational child composition behind the guarded isolated entry.

Parent fixed-registration/package checks and owned process supervision are
mandatory. This function adds child-side original/key/metadata verification.
"""
from pathlib import Path
from threading import Event
import time

from rocell.application.observational_reference_reader import ObservationalReferenceReader, FrozenObservationalReferences
from rocell.application.observational_worker_claim import claim_observational_worker
from rocell.application.physical_onboarding_durability import safe_root
from rocell.safety.observational_admission import admit_observational
from .observational_native_protocol import decode_request
from .observational_prelaunch import verify_reserved_observational_entry
from .endpoint_child_execution import decode_controller_binding
from .observational_current_context import ObservationalCurrentContextReader, AuthenticatedObservationalReader
from .observational_serial_api import WindowsObservationalSerialApi
from .observational_trial_execution import execute_native_observational_trial
from .bench_review_key import load_host_observational_review_authority
from .controller_metadata import WindowsControllerMetadataAcquirer


def execute_observational_child(workspace, request_raw, *, cancellation, clock_ns=time.monotonic_ns):
    if type(cancellation) is not Event or not callable(clock_ns):
        raise ValueError('Owned cancellation and clock required')
    if cancellation.is_set():
        raise ValueError('Observational child cancelled before preparation')
    wire = decode_request(request_raw)
    payload = wire['payload']
    request = verify_reserved_observational_entry(payload, workspace=workspace, clock_ns=clock_ns)
    root = safe_root(Path(payload['root']))
    references = FrozenObservationalReferences(ObservationalReferenceReader(request, workspace=workspace, root=root))
    current = dict(references())
    binding = decode_controller_binding(references.original('native_controller_review_sha256'), request)
    authority = load_host_observational_review_authority(workspace)
    claim = claim_observational_worker(root, request, launch_sha256=payload['launch_sha256'],
        current_source_sha256=current['source_sha256'], current_runtime_sha256=current['runtime_sha256'], now_ns=clock_ns())
    if cancellation.is_set():
        raise ValueError('Observational child cancelled before metadata/admission')
    connection_id = request.to_dict()['attempt_id']
    metadata = WindowsControllerMetadataAcquirer(deadline_ns=request.to_dict()['deadline_ns']-2_000_000_000,
        cancellation=cancellation, monotonic_ns=clock_ns, maximum_acquisitions=5)
    # One current snapshot each at admission, open claim, native open,
    # baseline binding, and final dispatch. This is not a retry allowance;
    # the same total native-call, buffer, and wall-clock limits still apply.
    context = ObservationalCurrentContextReader(request, binding=binding, connection_id=connection_id,
        metadata_reader=metadata, references_reader=references, clock_ns=clock_ns)
    reader = AuthenticatedObservationalReader(request, root=root, authority=authority,
        context_reader=context, clock_ns=clock_ns)
    permit = admit_observational(request, reader=reader, root=root)
    try:
        if cancellation.is_set():
            raise ValueError('Observational child cancelled before native facade')
        api = WindowsObservationalSerialApi.from_observational_permit(request, permit,
            port_name=binding.identity.port_name, connection_id=connection_id)
        return execute_native_observational_trial(request, permit, api, worker_claim=claim,
            current_source_sha256=current['source_sha256'], current_runtime_sha256=current['runtime_sha256'],
            cancellation=cancellation, clock_ns=clock_ns)
    finally:
        permit.revoke()
