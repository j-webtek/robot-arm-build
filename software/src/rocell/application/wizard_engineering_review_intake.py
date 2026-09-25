"""Parent-only recording of an explicit engineering decision; no device access."""

import hashlib
import re
import time
from pathlib import Path
from .endpoint_engineering_review import (
    EngineeringDraftReview, EngineeringDraftReviewReader, MAX_REVIEW_LIFETIME_NS,
    ENGINEERING_DRAFT_CHECKS,
)
from .endpoint_trial_draft import EndpointTrialDraft
from .endpoint_trial_contract import _canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import (
    publish_reservation_bytes, safe_root, contained_path, read_bounded_regular_file,
)


def parse_decision(values, *, now_ns):
    draft = EndpointTrialDraft(_canonical(decode_diagnostic_json(
        values['draft_json'].encode('utf-8'),maximum=16384)))
    review = EngineeringDraftReview(_canonical({
        'schema':'rocell.engineering_draft_review.v1', 'draft_sha256':draft.draft_sha256,
        'check':values['check'], 'actor_id':values['reviewer_id'],
        'decision':values['decision'], 'detail':values['detail'],
        'recorded_ns':now_ns, 'expires_ns':now_ns+MAX_REVIEW_LIFETIME_NS,
    }))
    return draft, review


def record_decision(values, *, root, operation_id, source_sha256, now_ns):
    draft,review = parse_decision(values,now_ns=now_ns)
    if decode_diagnostic_json(draft.canonical_bytes,maximum=16384)['selection']['references']['source_sha256'] != source_sha256:
        raise ValueError('Draft source differs from current wizard source')
    # Retain both exact material and explicit decision under this operation.
    # A partial publication is retained; neither file can be overwritten.
    publish_reservation_bytes(root,operation_id+'-engineering-draft.json',
        draft.canonical_bytes,maximum_bytes=16384)
    publish_reservation_bytes(root,operation_id+'-engineering-review-original.json',
        review.canonical_bytes,maximum_bytes=2048)
    return {'status':'ENGINEERING_DECISION_RECORDED_NOT_AUTHORIZED',
        'draft':decode_diagnostic_json(draft.canonical_bytes,maximum=16384),
        'draft_sha256':draft.draft_sha256, 'review':review.to_dict(),
        'review_sha256':hashlib.sha256(review.canonical_bytes).hexdigest(),
        'physical_authority':False, 'reviewer_identity_independently_verified':False}


def load_engineering_review_reader(*, root, draft, selections, source_sha256,
                                   check_current, clock_ns=time.monotonic_ns):
    """Load five explicit host-selected receipts, never discover 'latest approval'.

    selections is a tuple of (operation ID, expected review SHA-256) pairs from
    the service's retained results. Hashes establish byte integrity, not reviewer
    identity. The caller owns the log root, receipt selection and current-source
    check; browser-supplied paths or claimed approval digests are not authority.
    This reads only, signs nothing and cannot install a wizard motion binding.
    """
    if (type(draft) is not EndpointTrialDraft or type(selections) is not tuple
            or len(selections) != len(ENGINEERING_DRAFT_CHECKS) or not callable(check_current) or not callable(clock_ns)
            or any(type(row) is not tuple or len(row) != 2
                   or type(row[0]) is not str or re.fullmatch(r'operation-[0-9a-f]{32}',row[0]) is None
                   or type(row[1]) is not str or re.fullmatch(r'[0-9a-f]{64}',row[1]) is None
                   for row in selections)
            or len({row[0] for row in selections}) != len(ENGINEERING_DRAFT_CHECKS)):
        raise ValueError('Five unique bounded host review receipts required')
    expected_source = decode_diagnostic_json(draft.canonical_bytes,maximum=16384)['selection']['references']['source_sha256']
    if source_sha256 != expected_source:
        raise ValueError('Selected draft source is not current')
    directory = safe_root(Path(root))
    originals = []
    decisions = []
    def current():
        if check_current() is not None:
            raise ValueError('Review selection context changed')
    current()
    for operation_id, expected_hash in selections:
        current()
        retained_draft = read_bounded_regular_file(contained_path(directory,
            operation_id+'-engineering-draft.json',label='retained engineering draft'),maximum_bytes=16384)
        raw = read_bounded_regular_file(contained_path(directory,
            operation_id+'-engineering-review-original.json',label='retained engineering review'),maximum_bytes=2048)
        if retained_draft != draft.canonical_bytes or hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError('Selected engineering original changed')
        review = EngineeringDraftReview(raw).to_dict()
        if review['draft_sha256'] != draft.draft_sha256 or review['decision'] != 'APPROVED':
            raise ValueError('Selected engineering decision is not approval of this draft')
        originals.append(raw)
        decisions.append(review)
    current()
    now = clock_ns()
    if type(now) is not int or not 0 < now < 2**63:
        raise ValueError('Current host monotonic time required')
    if any(not review['recorded_ns'] <= now < review['expires_ns'] for review in decisions):
        raise ValueError('Selected engineering reviews expired or from a future clock')
    # The reader revalidates material and expiry when the actual request arrives.
    # No new timestamp is assigned to any original during loading.
    return EngineeringDraftReviewReader(tuple(originals),clock_ns=clock_ns)
