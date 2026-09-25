"""Trusted coordinator assembly of original reviews; no browser signing API.

Operator and engineering readers are distinct host dependencies. They must
return already-recorded canonical reviews for this exact request. This function
does not generate approvals, infer readiness, or refresh review timestamps.
"""

import hashlib
from pathlib import Path
import time
from .endpoint_trial_contract import EndpointTrialRequest
from .physical_onboarding_durability import publish_reservation_bytes, read_bounded_regular_file
from rocell.safety.bench_endpoint import REQUIRED_CHECKS
from rocell.safety.bench_review_authority import OPERATOR_CHECKS, MAX_BUNDLE_BYTES, AuthenticatedBenchReviewReader
from rocell.providers.windows.bench_review_key import load_host_bench_review_authority


def issue_bench_reviews(workspace, request, *, review_root, connection_id,
                        operator_reader, engineering_reader, context_reader,
                        clock_ns=time.monotonic_ns):
    """Publish once; a partial/stale publication is retained, never retried.

    Readers and roots are wired by the coordinator, not action payload fields.
    Successful issuance is not a permit and does not open any device.
    """
    if type(request) is not EndpointTrialRequest:
        raise ValueError('Exact endpoint request required')
    request.require_start_time(clock_ns())
    operator = operator_reader(request)
    engineering = engineering_reader(request)
    if (type(operator) is not dict or set(operator)!=OPERATOR_CHECKS
            or type(engineering) is not dict or set(engineering)!=REQUIRED_CHECKS-OPERATOR_CHECKS):
        raise ValueError('Separate complete operator and engineering originals required')
    originals = {**operator,**engineering}
    authority = load_host_bench_review_authority(workspace)
    now = clock_ns()
    request.require_start_time(now)
    raw = authority.seal(request,originals,now_ns=now)
    filename = request.to_dict()['attempt_id']+'-bench-reviews.json'
    publish_reservation_bytes(Path(review_root),filename,raw,maximum_bytes=MAX_BUNDLE_BYTES)
    stored = read_bounded_regular_file(Path(review_root)/filename,maximum_bytes=MAX_BUNDLE_BYTES)
    if stored!=raw: raise ValueError('Published review originals changed')
    # Fresh identity, references and original expiry are checked after disk I/O.
    reader = AuthenticatedBenchReviewReader(request,authority=authority,review_root=review_root,
        connection_id=connection_id,context_reader=context_reader,clock_ns=clock_ns)
    evidence = reader()
    request.require_start_time(clock_ns())
    return {'schema':'rocell.bench_review_issuance.v1','request_sha256':request.request_sha256,
            'review_bundle_sha256':hashlib.sha256(raw).hexdigest(),
            'expires_ns':evidence.expires_at_ns,'physical_authority':False,'replay_allowed':False}
