"""Record explicit engineering decisions; no authentication or hardware access."""
import hashlib
import re
import time
from pathlib import Path

from .first_motion_contract import canonical
from .first_motion_draft import FirstMotionDraft
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import publish_reservation_bytes, safe_root, contained_path, read_bounded_regular_file
from rocell.safety.first_motion_review_authority import ENGINEERING_CHECKS, MAX_ENGINEERING_LIFETIME_NS


def parse_decision(values, *, now_ns):
    if type(values) is not dict or set(values) != {'draft_json','reviewer_id','check','decision','detail'}:
        raise ValueError('Exact commissioning review fields required')
    if type(values['draft_json']) is not str:
        raise ValueError('Commissioning draft JSON required')
    draft = FirstMotionDraft(canonical(decode_diagnostic_json(
        values['draft_json'].encode('utf-8'), maximum=16384)))
    if (type(values['reviewer_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', values['reviewer_id'])
            or type(values['check']) is not str or values['check'] not in ENGINEERING_CHECKS
            or type(values['decision']) is not str or values['decision'] not in ('UNKNOWN','DENIED','APPROVED')
            or type(values['detail']) is not str or not 1 <= len(values['detail'].strip()) <= 1024
            or type(now_ns) is not int or not 0 < now_ns < 2**63-MAX_ENGINEERING_LIFETIME_NS):
        raise ValueError('Explicit bounded reviewer, check, decision, rationale and host time required')
    review = dict(schema='rocell.first_motion_review.v1',
        scope='ONE_WRIST_RESPONSE_EXPERIMENT', check=values['check'],
        actor_id=values['reviewer_id'], decision=values['decision'],
        evidence_kind='ENGINEERING_SELECTION_REVIEW', binding_sha256=draft.selection_sha256,
        recorded_ns=now_ns, expires_ns=now_ns+MAX_ENGINEERING_LIFETIME_NS,
        detail=values['detail'])
    raw = canonical(review)
    if len(raw) > 4096:
        raise ValueError('Encoded review exceeds original byte budget')
    return draft, raw


def record_decision(values, *, root, operation_id, source_sha256, now_ns):
    draft, raw = parse_decision(values, now_ns=now_ns)
    if (type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation_id)
            or draft.preview()['selection']['references']['source_sha256'] != source_sha256):
        raise ValueError('Current wizard source and exact operation identity required')
    # Failure keeps any partially published attempt; never replace or retime it.
    publish_reservation_bytes(root, operation_id+'-first-motion-engineering-draft.json',
                              draft.canonical_bytes, maximum_bytes=16384)
    publish_reservation_bytes(root, operation_id+'-first-motion-engineering-review-original.json',
                              raw, maximum_bytes=4096)
    return dict(status='ENGINEERING_DECISION_RECORDED_NOT_AUTHORIZED',
                selection_sha256=draft.selection_sha256,
                review=decode_diagnostic_json(raw, maximum=4096),
                review_sha256=hashlib.sha256(raw).hexdigest(),
                physical_authority=False, reviewer_identity_independently_verified=False)


def load_selected_reviews(*, root, draft, selections, source_sha256,
                          check_current, clock_ns=time.monotonic_ns):
    """Read exact host-selected receipts; preserve original bytes and times.

    This is not authentication or admission. Final sealing rechecks these
    originals against the timed request. No latest-file discovery or renewal.
    """
    if (type(draft) is not FirstMotionDraft or type(selections) is not tuple
            or len(selections) != len(ENGINEERING_CHECKS)
            or not callable(check_current) or not callable(clock_ns)
            or any(type(row) is not tuple or len(row) != 2
                or type(row[0]) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', row[0])
                or type(row[1]) is not str or not re.fullmatch(r'[a-f0-9]{64}', row[1])
                for row in selections)
            or len({row[0] for row in selections}) != len(ENGINEERING_CHECKS)):
        raise ValueError('Five distinct host-selected review receipts required')
    if draft.preview()['selection']['references']['source_sha256'] != source_sha256:
        raise ValueError('Selected commissioning source changed')
    directory = safe_root(Path(root))
    originals, times = {}, []
    def current():
        if check_current() is not None:
            raise ValueError('Commissioning review context changed')
    current()
    for operation_id, digest in selections:
        retained = read_bounded_regular_file(contained_path(directory,
            operation_id+'-first-motion-engineering-draft.json', label='commissioning draft'), maximum_bytes=16384)
        raw = read_bounded_regular_file(contained_path(directory,
            operation_id+'-first-motion-engineering-review-original.json', label='commissioning review'), maximum_bytes=4096)
        if retained != draft.canonical_bytes or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Selected commissioning original changed')
        value = decode_diagnostic_json(raw, maximum=4096)
        try:
            # Rebuild with the ORIGINAL host timestamp, never the selection time.
            _, rebuilt = parse_decision(dict(draft_json=retained.decode('ascii'),
                reviewer_id=value['actor_id'], check=value['check'],
                decision=value['decision'], detail=value['detail']), now_ns=value['recorded_ns'])
        except (KeyError, TypeError) as error:
            raise ValueError('Malformed commissioning review') from error
        if rebuilt != raw or value['decision'] != 'APPROVED' or value['check'] in originals:
            raise ValueError('Distinct unchanged approvals required')
        originals[value['check']] = raw
        times.append((value['recorded_ns'], value['expires_ns']))
        current()
    current()
    now = clock_ns()
    if (type(now) is not int or not 0 < now < 2**63 or set(originals) != ENGINEERING_CHECKS
            or any(not recorded <= now < expiry for recorded, expiry in times)):
        raise ValueError('Complete current commissioning approvals required')
    return originals
