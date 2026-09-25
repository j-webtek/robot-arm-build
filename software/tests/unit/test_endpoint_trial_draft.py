import json

import pytest

from rocell.application.endpoint_trial_contract import _canonical
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from test_endpoint_trial_contract import request


def test_draft_preserves_selection_but_not_old_clock_or_attempt():
    original = request()
    draft = EndpointTrialDraft.from_request(original)
    updated = draft.create_request(expected_draft_sha256=draft.draft_sha256,
        attempt_id='operation-'+'c'*32, issued_monotonic_ns=40_000_000_000,
        deadline_monotonic_ns=70_000_000_000)
    before, after = original.to_dict(), updated.to_dict()
    for field in ('attempt_id', 'issued_monotonic_ns', 'deadline_monotonic_ns'):
        assert before.pop(field) != after.pop(field)
    assert before == after
    assert updated.request_sha256 != original.request_sha256
    assert after['physical_authority'] is False
    assert EndpointTrialDraft.from_request(updated) == draft


def test_changed_review_digest_refused():
    draft = EndpointTrialDraft.from_request(request())
    with pytest.raises(ValueError, match='selection changed'):
        draft.create_request(expected_draft_sha256='f'*64,
            attempt_id='operation-'+'b'*32, issued_monotonic_ns=1,
            deadline_monotonic_ns=30_000_000_001)


@pytest.mark.parametrize('field,value', [
    ('physical_authority', True), ('issued_monotonic_ns', 1),
    ('limits', {}), ('usb_identity', {}), ('unexpected', True),
])
def test_draft_reuses_strict_request_validation(field, value):
    raw = json.loads(EndpointTrialDraft.from_request(request()).canonical_bytes)
    raw['selection'][field] = value
    with pytest.raises(ValueError):
        EndpointTrialDraft(_canonical(raw))


def test_request_deadline_limits_still_apply():
    draft = EndpointTrialDraft.from_request(request())
    with pytest.raises(ValueError):
        draft.create_request(expected_draft_sha256=draft.draft_sha256,
            attempt_id='operation-'+'b'*32, issued_monotonic_ns=1,
            deadline_monotonic_ns=60_000_000_001)
