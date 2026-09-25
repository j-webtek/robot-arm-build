"""Synthetic review-to-final-request binding; no physical authority or I/O."""
import json
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_draft import FirstMotionDraft, TIMED_FIELDS
from rocell.safety.first_motion_review_authority import FirstMotionReviewAuthority, ENGINEERING_CHECKS
from test_first_motion_contract import request
from test_first_motion_review_authority import originals


def finalize(draft):
    return draft.create_request(expected_selection_sha256=draft.selection_sha256,
        attempt_id='operation-' + 'c' * 32, issued_monotonic_ns=2_000_000_000,
        deadline_monotonic_ns=32_000_000_000)


def test_final_envelope_preserves_every_reviewed_field():
    before = request()
    draft = FirstMotionDraft.from_request(before)
    after = finalize(draft)
    assert draft.selection_sha256 == before.selection_sha256 == after.selection_sha256
    assert before.request_sha256 != after.request_sha256
    assert {k: v for k, v in before.to_dict().items() if k not in TIMED_FIELDS} == {
        k: v for k, v in after.to_dict().items() if k not in TIMED_FIELDS}
    preview = draft.preview()
    assert not preview['motion_authorized'] and preview['final_request_required']
    preview['selection']['command']['spd'] = 100
    assert draft.preview()['selection']['command']['spd'] == 20


def test_old_operator_attestations_cannot_follow_selection_to_new_request():
    before = request()
    after = finalize(FirstMotionDraft.from_request(before))
    old = originals(before)
    authority = FirstMotionReviewAuthority(b'a' * 32)
    with pytest.raises(ValueError):
        authority.seal(after, old, now_ns=2_000_000_000)
    # Explicit synthetic final-click records replace operator attestations only.
    # Engineering originals retain their actual original bytes and timestamps.
    updated = dict(old)
    for name in updated.keys() - ENGINEERING_CHECKS:
        value = json.loads(updated[name])
        value.update(binding_sha256=after.request_sha256, recorded_ns=2_000_000_000,
                     expires_ns=32_000_000_000)
        updated[name] = canonical(value)
    sealed = authority.seal(after, updated, now_ns=2_000_000_000)
    assert sealed
    assert all(updated[name] == old[name] for name in ENGINEERING_CHECKS)


@pytest.mark.parametrize('field,value', [
    ('attempt_id', 'operation-' + 'a' * 32), ('issued_monotonic_ns', 1),
    ('distal_radius_mm', 201), ('physical_authority', True),
    ('command', {'T': 104}), ('unexpected', False)])
def test_draft_reuses_strict_contract_and_forbids_timed_fields(field, value):
    data = json.loads(FirstMotionDraft.from_request(request()).canonical_bytes)
    data['selection'][field] = value
    with pytest.raises(ValueError):
        FirstMotionDraft(canonical(data))


def test_changed_valid_selection_invalidates_reviewed_digest():
    draft = FirstMotionDraft.from_request(request())
    data = json.loads(draft.canonical_bytes)
    data['selection']['distal_radius_mm'] = 190
    changed = FirstMotionDraft(canonical(data))
    with pytest.raises(ValueError):
        changed.create_request(expected_selection_sha256=draft.selection_sha256,
            attempt_id='operation-' + 'c' * 32, issued_monotonic_ns=2_000_000_000,
            deadline_monotonic_ns=32_000_000_000)


def test_noncanonical_or_wrong_family_refused():
    draft = FirstMotionDraft.from_request(request())
    with pytest.raises(ValueError):
        FirstMotionDraft(json.dumps(json.loads(draft.canonical_bytes)).encode())
    with pytest.raises(ValueError):
        FirstMotionDraft.from_request(draft)
