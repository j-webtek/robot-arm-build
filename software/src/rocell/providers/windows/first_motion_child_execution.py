"""Fixed commissioning child composition, not registered for CLI/live launch.

The parent must validate source/runtime/evidence pins and own/contain the process.
This function never substitutes synthetic reviews or inferred physical geometry.
"""
import hashlib
from pathlib import Path
from threading import Event
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_reference_reader import FirstMotionReferenceReader
from rocell.application.first_motion_evidence_snapshot import FrozenFirstMotionReferences,FILENAME,MAX_BYTES
from rocell.application.first_motion_worker_claim import claim_first_motion_worker
from rocell.application.physical_onboarding_durability import safe_root,read_bounded_regular_file
from rocell.safety.first_motion_review_authority import AuthenticatedFirstMotionReviewReader
from rocell.safety.first_motion_admission import authorize_first_motion
from .first_motion_native_protocol import decode_request,validate_payload
from .endpoint_child_execution import decode_controller_binding
from .first_motion_current_context import FirstMotionCurrentContextReader
from .first_motion_serial_api import WindowsFirstMotionSerialApi
from .first_motion_trial_execution import execute_native_first_motion_trial
from .bench_review_key import load_host_first_motion_review_authority
from .controller_metadata import WindowsControllerMetadataAcquirer


def execute_first_motion_child(workspace,request_raw,*,cancellation,clock_ns=time.monotonic_ns):
    if type(cancellation) is not Event or not callable(clock_ns):
        raise ValueError('Owned cancellation event and clock required')
    if cancellation.is_set(): raise ValueError('Commissioning child cancelled before preparation')
    wire=decode_request(request_raw)
    payload=wire['payload']
    request=validate_payload(payload)
    root=safe_root(Path(payload['root']))
    references=FirstMotionReferenceReader(request,workspace=workspace,reference_root=root)
    current=dict(references())
    pins=payload['registration'].get('package_files')
    path=root/(request.to_dict()['attempt_id']+'-first-motion-native-child')/FILENAME
    if (type(pins) is not list or len(pins)!=3 or type(pins[2]) is not dict
            or pins[2].get('path')!=str(path)):
        raise ValueError('Exact registered commissioning snapshot required')
    references=FrozenFirstMotionReferences(read_bounded_regular_file(path,maximum_bytes=MAX_BYTES),request)
    if references.snapshot_sha256!=pins[2].get('sha256'):
        raise ValueError('Registered commissioning snapshot changed')
    binding=decode_controller_binding(references.original('native_controller_review_sha256'),request)
    authority=load_host_first_motion_review_authority(workspace)
    runtime_sha=hashlib.sha256(canonical(payload['registration'])).hexdigest()
    claim=claim_first_motion_worker(root,request,launch_sha256=payload['launch_sha256'],
        current_source_sha256=current['source_sha256'],current_runtime_sha256=runtime_sha,now_ns=clock_ns())
    connection_id=request.to_dict()['attempt_id']
    metadata=WindowsControllerMetadataAcquirer(deadline_ns=request.to_dict()['deadline_monotonic_ns']-2_000_000_000,
        cancellation=cancellation,monotonic_ns=clock_ns)
    context=FirstMotionCurrentContextReader(request,binding=binding,connection_id=connection_id,
        metadata_reader=metadata,references_reader=references,clock_ns=clock_ns)
    reviews=AuthenticatedFirstMotionReviewReader(request,authority=authority,root=root,
        measurement_session_id=payload['session_id'],measurement_operation_id=payload['measurement_operation_id'],
        context_reader=context,clock_ns=clock_ns)
    if cancellation.is_set(): raise ValueError('Commissioning child cancelled before admission')
    permit=authorize_first_motion(request,evidence_reader=reviews,attempt_root=root,clock=clock_ns)
    try:
        if cancellation.is_set(): raise ValueError('Commissioning child cancelled before native facade')
        api=WindowsFirstMotionSerialApi.from_first_motion_permit(request,permit,
            port_name=binding.identity.port_name,connection_id=connection_id)
        execution=execute_native_first_motion_trial(request,permit,api,cancellation=cancellation,
            worker_claim=claim,current_source_sha256=current['source_sha256'],
            current_runtime_sha256=runtime_sha,clock_ns=clock_ns)
        return dict(schema='rocell.first_motion_native_child_result.v1',claim_sha256=claim.claim_sha256,
            execution=execution,physical_authority=False)
    finally:
        permit.revoke()
