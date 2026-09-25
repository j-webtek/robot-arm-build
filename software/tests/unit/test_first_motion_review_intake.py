"""Synthetic wizard review recording, explicitly not physical qualification."""
import json
import pytest

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.application.first_motion_draft import FirstMotionDraft
from rocell.application.first_motion_review_intake import parse_decision, record_decision, load_selected_reviews
from rocell.safety.first_motion_review_authority import ENGINEERING_CHECKS
from test_first_motion_contract import request
from test_arrival_wizard_service import make_service, _run


@pytest.mark.parametrize('decision', ['UNKNOWN', 'DENIED', 'APPROVED'])
def test_wizard_retains_explicit_decision_without_hardware(make_service, decision):
    service, runner, _ = make_service(mode='physical')
    body = request().to_dict()
    body['references']['source_sha256'] = service.source_sha256
    draft = FirstMotionDraft.from_request(FirstMotionRequest(canonical(body)))
    values = dict(draft_json=draft.canonical_bytes.decode(), reviewer_id='synthetic-reviewer',
        check='independent_starting_geometry_review', decision=decision,
        detail='Synthetic test only, not an actual physical review.')
    operation = _run(service, 'record_first_motion_engineering_review', values)
    assert operation['status'] == 'SUCCEEDED'
    report = operation['result']['steps'][0]['report']
    assert report['review']['decision'] == decision
    assert report['selection_sha256'] == draft.selection_sha256
    assert not report['physical_authority']
    prefix = operation['operation_id']
    raw = (service._log.root / (prefix+'-first-motion-engineering-review-original.json')).read_bytes()
    assert json.loads(raw) == report['review']
    assert (service._log.root / (prefix+'-first-motion-engineering-draft.json')).read_bytes() == draft.canonical_bytes
    assert not runner.calls
    assert operation['result']['device_open_count'] == 0
    assert operation['result']['motion_command_count'] == 0


@pytest.mark.parametrize('field,value', [('check','operator_present'), ('decision',True),
    ('detail',''), ('reviewer_id','../reviewer'), ('extra',True)])
def test_invalid_decision_refused(field, value):
    values = dict(draft_json=FirstMotionDraft.from_request(request()).canonical_bytes.decode(),
        reviewer_id='synthetic', check='independent_starting_geometry_review',
        decision='UNKNOWN', detail='Synthetic only.')
    values[field] = value
    with pytest.raises(ValueError):
        parse_decision(values, now_ns=1)


@pytest.mark.parametrize('fault', [None, 'denied', 'duplicate_check', 'expired', 'hash', 'context'])
def test_selected_originals_preserve_times_or_fail(tmp_path, fault):
    draft = FirstMotionDraft.from_request(request())
    receipts, expected = [], {}
    checks = sorted(ENGINEERING_CHECKS)
    for index, check in enumerate(checks):
        if fault == 'duplicate_check' and index == 4:
            check = checks[0]
        operation = 'operation-' + format(index, '032x')
        values = dict(draft_json=draft.canonical_bytes.decode(), reviewer_id='synthetic',
            check=check, decision='DENIED' if fault == 'denied' and index == 0 else 'APPROVED',
            detail='Synthetic review only.')
        report = record_decision(values, root=tmp_path, operation_id=operation,
                                 source_sha256='a'*64, now_ns=1)
        receipts.append((operation, 'b'*64 if fault == 'hash' else report['review_sha256']))
        expected[check] = (tmp_path/(operation+'-first-motion-engineering-review-original.json')).read_bytes()
    kwargs = dict(root=tmp_path, draft=draft, selections=tuple(receipts), source_sha256='a'*64,
        check_current=lambda: True if fault == 'context' else None,
        clock_ns=lambda: 300_000_000_001 if fault == 'expired' else 2)
    if fault:
        with pytest.raises(ValueError):
            load_selected_reviews(**kwargs)
    else:
        assert load_selected_reviews(**kwargs) == expected


def test_service_selects_only_same_session_successful_reviews(make_service):
    service, runner, _ = make_service(mode='physical')
    body = request().to_dict()
    body['references']['source_sha256'] = service.source_sha256
    draft = FirstMotionDraft.from_request(FirstMotionRequest(canonical(body)))
    operations = []
    for check in sorted(ENGINEERING_CHECKS):
        result = _run(service, 'record_first_motion_engineering_review',
            dict(draft_json=draft.canonical_bytes.decode(), reviewer_id='synthetic',
                 check=check, decision='APPROVED', detail='Synthetic only.'))
        operations.append(result['operation_id'])
    selected = service.select_first_motion_reviews(draft=draft, review_operation_ids=tuple(operations))
    assert set(selected) == ENGINEERING_CHECKS
    other, _, _ = make_service(mode='physical')
    with pytest.raises(Exception):
        other.select_first_motion_reviews(draft=draft, review_operation_ids=tuple(operations))
    with pytest.raises(Exception):
        service.select_first_motion_reviews(draft=draft, review_operation_ids=(operations[0],)*5)
    assert not runner.calls
