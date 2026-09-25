"""Synthetic final-confirmation originals; no operator or hardware qualification."""
import base64
import json
import pytest

from rocell.application.first_motion_confirmation import seal_confirmation, confirm_draft
from rocell.application.first_motion_draft import FirstMotionDraft
from rocell.safety.first_motion_review_authority import FirstMotionReviewAuthority, ENGINEERING_CHECKS, OPERATOR_CHECKS
from test_first_motion_contract import request
from test_first_motion_review_authority import originals


@pytest.mark.parametrize('fault', [None, 'unchecked', 'old_request', 'engineering', 'expired', 'context'])
def test_exact_confirmation_or_refusal_before_publication(tmp_path, fault):
    selected = request()
    engineering = {k: v for k, v in originals(selected).items() if k in ENGINEERING_CHECKS}
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', request_sha256=selected.request_sha256)
    if fault == 'unchecked': values['operator_present'] = False
    if fault == 'old_request': values['request_sha256'] = 'c'*64
    if fault == 'engineering': engineering['independent_starting_geometry_review'] = b'{}'
    kwargs = dict(engineering_originals=engineering, authority=FirstMotionReviewAuthority(b'a'*32),
        root=tmp_path, check_current=lambda: True if fault == 'context' else None,
        clock_ns=lambda: 5_000_000_000 if fault == 'expired' else 1_000_000_000)
    if fault:
        with pytest.raises(ValueError): seal_confirmation(selected, values, **kwargs)
        assert not list(tmp_path.iterdir())
    else:
        report = seal_confirmation(selected, values, **kwargs)
        assert report['checks_authenticated'] == 12
        assert not report['motion_authorized']
        raw = (tmp_path/report['filename']).read_bytes()
        bundle = json.loads(raw)
        for name, original in engineering.items():
            assert base64.b64decode(bundle['originals'][name]) == original
        with pytest.raises(Exception): seal_confirmation(selected, values, **kwargs)
        assert (tmp_path/report['filename']).read_bytes() == raw


def test_context_loss_after_publication_retains_consumed_bundle(tmp_path):
    selected = request()
    engineering = {k: v for k, v in originals(selected).items() if k in ENGINEERING_CHECKS}
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', request_sha256=selected.request_sha256)
    calls = 0
    def current():
        nonlocal calls
        calls += 1
        if calls == 3: raise ValueError('Context lost after publication')
    with pytest.raises(ValueError):
        seal_confirmation(selected, values, engineering_originals=engineering,
            authority=FirstMotionReviewAuthority(b'a'*32), root=tmp_path,
            check_current=current, clock_ns=lambda: 1_000_000_000)
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize('fault', [None, 'selection', 'unchecked', 'injected_time', 'engineering'])
def test_final_click_binds_selection_without_browser_time_or_request_hash(tmp_path, fault):
    before = request()
    draft = FirstMotionDraft.from_request(before)
    engineering = {k: v for k, v in originals(before).items() if k in ENGINEERING_CHECKS}
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', selection_sha256=draft.selection_sha256)
    if fault == 'selection': values['selection_sha256'] = 'c'*64
    if fault == 'unchecked': values['operator_present'] = 1
    if fault == 'injected_time': values['issued_monotonic_ns'] = 1
    if fault == 'engineering': engineering['independent_starting_geometry_review'] = b'{}'
    kwargs = dict(attempt_id='operation-'+'d'*32, engineering_originals=engineering,
        authority=FirstMotionReviewAuthority(b'a'*32), root=tmp_path,
        check_current=lambda: None, clock_ns=lambda: 2_000_000_000)
    if fault:
        with pytest.raises(ValueError): confirm_draft(draft, values, **kwargs)
        assert len(list(tmp_path.iterdir())) == (1 if fault == 'engineering' else 0)
    else:
        after, report = confirm_draft(draft, values, **kwargs)
        assert after.selection_sha256 == before.selection_sha256
        assert after.to_dict()['issued_monotonic_ns'] == 2_000_000_000
        assert after.request_sha256 != before.request_sha256
        assert report['request_sha256'] == after.request_sha256
        retained = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        assert len(retained) == 2
        with pytest.raises(Exception): confirm_draft(draft, values, **kwargs)
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == retained


@pytest.mark.parametrize('accepted', [True, 0, 3_000_000_001, 7_000_000_001])
def test_queue_delay_cannot_renew_final_click(tmp_path, accepted):
    before = request()
    draft = FirstMotionDraft.from_request(before)
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', selection_sha256=draft.selection_sha256)
    engineering = {k:v for k,v in originals(before).items() if k in ENGINEERING_CHECKS}
    with pytest.raises(ValueError):
        confirm_draft(draft, values, attempt_id='operation-'+'d'*32,
            engineering_originals=engineering, authority=FirstMotionReviewAuthority(b'a'*32),
            root=tmp_path, check_current=lambda:None, clock_ns=lambda:7_000_000_000,
            accepted_ns=accepted)
    assert not list(tmp_path.iterdir())
