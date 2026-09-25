"""Recheck reserved observational entry before parent launch or child admission."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_reference_reader import ObservationalReferenceReader
from rocell.application.observational_worker_claim import _verify_launch
from rocell.application.physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from .observational_native_protocol import validate_payload
from .bench_review_key import load_host_observational_review_authority


def verify_reserved_observational_entry(payload, *, workspace, clock_ns):
    if not callable(clock_ns):
        raise ValueError('Trusted execution clock required')
    request = validate_payload(payload)
    root = safe_root(Path(payload['root']))
    reader = ObservationalReferenceReader(request, workspace=workspace, root=root)
    current = dict(reader())
    runtime_sha = hashlib.sha256(canonical(payload['registration'])).hexdigest()
    started = clock_ns()
    _verify_launch(root, request, payload['launch_sha256'], current['source_sha256'], runtime_sha, started)
    review_path = contained_path(root, request.to_dict()['attempt_id']+'-observational-reviews.json',
                                 label='reserved observational review')
    raw = read_bounded_regular_file(review_path, maximum_bytes=8192)
    authority = load_host_observational_review_authority(workspace)
    refreshed = dict(reader())
    finished = clock_ns()
    if type(finished) is not int or finished < started or refreshed != current:
        raise ValueError('Observational source/reference context changed')
    _verify_launch(root, request, payload['launch_sha256'], current['source_sha256'], runtime_sha, finished)
    if read_bounded_regular_file(review_path, maximum_bytes=8192) != raw:
        raise ValueError('Observational signed review changed during verification')
    authority.verify(raw, expected_intent=request.to_dict(),
        current_usb_identity=request.to_dict()['usb_identity'], current_references=refreshed, now_ns=finished)
    return request
