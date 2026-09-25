"""Parent-only reserved-entry recheck; never opens a device or creates a process.

Invoke only after fixed registration/source-package validation. This check does
not replace current native identity, child admission or parent process ownership.
"""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_reference_reader import FirstMotionReferenceReader
from rocell.application.first_motion_worker_claim import _verify_launch
from rocell.application.first_motion_measurements import load_measurement_for_request
from rocell.application.physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file
from rocell.safety.first_motion_review_authority import MAX_BUNDLE_BYTES
from .first_motion_native_protocol import validate_payload
from .bench_review_key import load_host_first_motion_review_authority


def verify_reserved_first_motion_entry(payload, *, workspace, clock_ns):
    """Reconstruct current references and authenticate original reviews afresh.

    Workspace/root/clock come from the trusted parent composition. No implicit
    key provisioning or approval generation occurs. Expiry is never renewed.
    """
    if not callable(clock_ns): raise ValueError('Trusted parent clock required')
    request=validate_payload(payload)
    root=safe_root(Path(payload['root']))
    references=FirstMotionReferenceReader(request,workspace=workspace,reference_root=root)
    current=references()
    runtime_sha=hashlib.sha256(canonical(payload['registration'])).hexdigest()
    started=clock_ns()
    _verify_launch(root,request,payload['launch_sha256'],dict(current)['source_sha256'],runtime_sha,started)
    raw=read_bounded_regular_file(contained_path(root,request.to_dict()['attempt_id']+'-first-motion-reviews.json',
        label='parent commissioning signed reviews'),maximum_bytes=MAX_BUNDLE_BYTES)
    def check_current():
        # The loader invokes this repeatedly around one bounded measurement
        # read. Full reference reconstruction already brackets this entire
        # operation below; repeating disk scans here consumes the parent budget
        # without creating an atomic snapshot. Preserve the deadline checks.
        request.require_start_time(clock_ns())
    # Measure/verify the retained original, not a new timestamped replacement.
    load_measurement_for_request(request,root=root,session_id=payload['session_id'],
        operation_id=payload['measurement_operation_id'],clock_ns=clock_ns,check_current=check_current)
    authority=load_host_first_motion_review_authority(workspace)
    refreshed=references()
    finished=clock_ns()
    if type(finished) is not int or finished<started or refreshed!=current:
        raise ValueError('Parent commissioning references or clock changed')
    request.require_start_time(finished)
    # A second read catches review/launch edits observed during verification;
    # this is not an atomic lock against a malicious process in the same account.
    _verify_launch(root,request,payload['launch_sha256'],dict(refreshed)['source_sha256'],runtime_sha,finished)
    latest=read_bounded_regular_file(contained_path(root,request.to_dict()['attempt_id']+'-first-motion-reviews.json',
        label='parent commissioning signed reviews'),maximum_bytes=MAX_BUNDLE_BYTES)
    if latest!=raw: raise ValueError('Parent commissioning reviews changed')
    verified=clock_ns()
    if type(verified) is not int or verified<finished:
        raise ValueError('Parent commissioning clock changed')
    request.require_start_time(verified)
    authority.verify(request,latest,connection_id=request.to_dict()['attempt_id'],
        current_references=refreshed,now_ns=verified)
