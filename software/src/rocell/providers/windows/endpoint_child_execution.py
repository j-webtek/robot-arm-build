"""Fixed one-trial child composition; CLI activation remains separately held."""

from dataclasses import fields
import hashlib
from pathlib import Path
from threading import Event
import time

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_reference_reader import EndpointReferenceReader
from rocell.application.endpoint_evidence_snapshot import FrozenEndpointReferences,FILENAME,MAX_BYTES
from rocell.application.endpoint_worker_claim import claim_endpoint_worker
from rocell.application.physical_onboarding_durability import contained_path, safe_root, read_bounded_regular_file
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.physical_connection_contracts import EvidenceOrigin, RoArmUsbSerialIdentity, UsbDriverIdentity
from rocell.safety.bench_review_authority import AuthenticatedBenchReviewReader
from rocell.safety.bench_endpoint import authorize_bench_endpoint
from .arm_feedback_worker import ReviewedControllerBinding
from .bench_review_key import load_host_bench_review_authority
from .controller_metadata import WindowsControllerMetadataAcquirer
from .endpoint_current_context import EndpointCurrentContextReader
from .endpoint_native_wire import decode_request
from .endpoint_native_registration import validate_payload
from .endpoint_serial_api import WindowsEndpointSerialApi
from .endpoint_trial_execution import execute_native_endpoint_trial


def load_controller_binding(root,request):
    name = request.to_dict()['attempt_id']+'-native_controller_review_sha256.original.json'
    raw = read_bounded_regular_file(contained_path(safe_root(Path(root)),name,label='controller original'),
                                    maximum_bytes=128*1024)
    return decode_controller_binding(raw,request)


def decode_controller_binding(raw,request):
    expected = request.to_dict()['references']['native_controller_review_sha256']
    return decode_reviewed_controller_binding(raw, expected_sha256=expected)


def decode_reviewed_controller_binding(raw, *, expected_sha256):
    """Restore an exact reviewed controller original without inventing an intent."""
    expected = expected_sha256
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Controller original hash changed')
    document = decode_diagnostic_json(raw,maximum=128*1024)
    if type(document) is not dict or set(document)!={f.name for f in fields(ReviewedControllerBinding)}:
        raise ValueError('Exact reviewed controller document required')
    identity = document['identity']
    if type(identity) is not dict or type(identity.get('driver')) is not dict:
        raise ValueError('Controller identity and driver required')
    try:
        driver = UsbDriverIdentity(**identity['driver'])
        restored_identity = RoArmUsbSerialIdentity(**{f.name:identity[f.name]
            for f in fields(RoArmUsbSerialIdentity) if f.init and f.name!='driver'},driver=driver)
        binding = ReviewedControllerBinding(**{k:v for k,v in document.items() if k not in {'identity','origin'}},
            identity=restored_identity,origin=EvidenceOrigin(document['origin']))
    except (KeyError,TypeError) as error:
        raise ValueError('Invalid retained controller document') from error
    if binding.binding_sha256!=expected or binding.to_dict()!=document:
        raise ValueError('Retained controller fields changed during reconstruction')
    return binding


def execute_endpoint_child(workspace,request_raw,*,cancellation,clock_ns=time.monotonic_ns):
    """Called only by the source-pinned isolated entry, never the generic wizard.

    The parent must own/contain this process and bind workspace to its registered
    source. Errors before execution propagate for raw diagnostic retention.
    """
    if type(cancellation) is not Event: raise ValueError('Owned cancellation event required')
    if cancellation.is_set(): raise ValueError('Endpoint child cancelled before preparation')
    wire = decode_request(request_raw)
    request = validate_payload(wire['payload'])
    root = safe_root(Path(wire['payload']['root']))
    references = EndpointReferenceReader(request,workspace=workspace,reference_root=root)
    current = dict(references())
    pins = wire['payload']['registration'].get('package_files')
    expected_path = root/(request.to_dict()['attempt_id']+'-endpoint-native-child')/FILENAME
    if type(pins) is not list or len(pins)!=3 or pins[2].get('path')!=str(expected_path):
        raise ValueError('Exact registered evidence snapshot required')
    snapshot_raw = read_bounded_regular_file(expected_path,maximum_bytes=MAX_BYTES)
    references = FrozenEndpointReferences(snapshot_raw,request)
    if references.snapshot_sha256!=pins[2].get('sha256'):
        raise ValueError('Registered evidence snapshot hash changed')
    binding = decode_controller_binding(references.original('native_controller_review_sha256'),request)
    authority = load_host_bench_review_authority(workspace)
    runtime_sha = hashlib.sha256(_canonical(wire['payload']['registration'])).hexdigest()
    claim = claim_endpoint_worker(root,request,launch_sha256=wire['payload']['launch_sha256'],
        current_source_sha256=current['source_sha256'],current_runtime_sha256=runtime_sha,now_ns=clock_ns())
    connection_id = request.to_dict()['attempt_id']
    metadata = WindowsControllerMetadataAcquirer(
        deadline_ns=request.to_dict()['deadline_monotonic_ns']-2_000_000_000,
        cancellation=cancellation,monotonic_ns=clock_ns)
    context = EndpointCurrentContextReader(request,binding=binding,connection_id=connection_id,
        metadata_reader=metadata,references_reader=references,clock_ns=clock_ns)
    reviews = AuthenticatedBenchReviewReader(request,authority=authority,review_root=root,
        connection_id=connection_id,context_reader=context,clock_ns=clock_ns)
    if cancellation.is_set(): raise ValueError('Endpoint child cancelled before admission')
    permit = authorize_bench_endpoint(request,connection_id=connection_id,evidence_reader=reviews,
                                     attempt_root=root,clock=clock_ns)
    try:
        if cancellation.is_set(): raise ValueError('Endpoint child cancelled before native facade')
        api = WindowsEndpointSerialApi.from_bench_permit(request,permit,
            port_name=binding.identity.port_name,connection_id=connection_id)
        result = execute_native_endpoint_trial(request,permit,api,cancellation=cancellation,
            presence_expiry_reader=reviews.presence_expiry,worker_claim=claim,
            current_source_sha256=current['source_sha256'],current_runtime_sha256=runtime_sha,
            clock_ns=clock_ns)
        return {'schema':'rocell.endpoint_native_child_result.v1','claim_sha256':claim.claim_sha256,
                'execution':result,'physical_authority':False}
    finally:
        permit.revoke()
