"""Stage exact host-selected commissioning originals; never sign or launch."""
import hashlib
from pathlib import Path
import time

from .first_motion_contract import FirstMotionRequest
from .first_motion_measurements import validate_original_for_request
from .first_motion_reference_reader import ORIGINAL_REFERENCES,FirstMotionReferenceReader
from .endpoint_reference_reader import MAX_ORIGINAL_BYTES
from .wizard_diagnostic_coordinator import decode_diagnostic_json,source_fingerprint
from .physical_onboarding_durability import safe_root,publish_reservation_bytes
from rocell.rc03.importer import import_build_snapshot


def stage_first_motion_originals(workspace,request,*,root,reference_originals,
                                 measurement_raw,session_id,operation_id,
                                 check_current,clock_ns=time.monotonic_ns):
    """Reserve the exact request before immutable publication; no retries.

    All originals and selection IDs come from the trusted host. The selected
    measurement keeps its original timestamp/bytes. Source/build and each digest
    are verified before publication and again afterward; integrity is not approval.
    """
    if (type(request) is not FirstMotionRequest or type(reference_originals) is not dict
            or set(reference_originals)!=ORIGINAL_REFERENCES or not callable(check_current)
            or not callable(clock_ns)):
        raise ValueError('Exact request and complete trusted originals required')
    root=safe_root(Path(root))
    originals=dict(reference_originals)
    refs=request.to_dict()['references']
    def current():
        if check_current() is not None: raise ValueError('Host staging context changed')
        request.require_start_time(clock_ns())
    current()
    validate_original_for_request(measurement_raw,request,session_id=session_id,
        operation_id=operation_id,now_ns=clock_ns())
    if originals['independent_posture_review_sha256']!=measurement_raw:
        raise ValueError('Selected measurement differs from posture original')
    for name,raw in originals.items():
        if type(raw) is not bytes or not 0<len(raw)<=MAX_ORIGINAL_BYTES:
            raise ValueError('Bounded original reference bytes required')
        document=decode_diagnostic_json(raw,maximum=MAX_ORIGINAL_BYTES)
        if type(document) is not dict or not document or hashlib.sha256(raw).hexdigest()!=refs[name]:
            raise ValueError('Commissioning original digest or structure mismatch')
    current()
    # No publication occurred during the in-memory validation above. Rebuild
    # source/build now, immediately before reserving the immutable originals.
    if source_fingerprint(workspace)!=refs['source_sha256'] or import_build_snapshot(workspace).snapshot_hash!=refs['build_snapshot_sha256']:
        raise ValueError('Source/build changed before commissioning staging')
    attempt=request.to_dict()['attempt_id']
    publish_reservation_bytes(root,attempt+'-first-motion-staged-request.json',request.canonical_bytes,maximum_bytes=16384)
    for name,raw in sorted(originals.items()):
        publish_reservation_bytes(root,attempt+'-'+name+'.original.json',raw,maximum_bytes=MAX_ORIGINAL_BYTES)
    # Perform the external context callback BEFORE final reconstruction so its
    # side effects cannot invalidate a source scan that just completed. The
    # reader freshly checks source/build and all published original bytes; no
    # additional full scan or cached fingerprint is needed in this stage.
    current()
    FirstMotionReferenceReader(request,workspace=workspace,reference_root=root)()
    request.require_start_time(clock_ns())
    return dict(schema='rocell.first_motion_staging.v1',request_sha256=request.request_sha256,
        measurement_operation_id=operation_id,original_count=len(originals),
        reviews_authenticated=False,physical_authority=False,motion_authorized=False,replay_allowed=False)
