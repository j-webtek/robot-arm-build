"""Retained synthetic wizard decisions to exact-request reader; no hardware."""

import pytest

from rocell.application.wizard_engineering_review_intake import record_decision, load_engineering_review_reader
from rocell.application.endpoint_engineering_review import ENGINEERING_DRAFT_CHECKS
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from test_endpoint_trial_contract import request


def recorded(tmp_path, *, decision='APPROVED'):
    req = request()
    draft = EndpointTrialDraft.from_request(req)
    selected = []
    for i,check in enumerate(sorted(ENGINEERING_DRAFT_CHECKS)):
        operation = 'operation-'+format(i,'032x')
        report = record_decision({'draft_json':draft.canonical_bytes.decode(),
            'reviewer_id':'synthetic-reviewer','check':check,'decision':decision,
            'detail':'Synthetic test evidence only.'},root=tmp_path,operation_id=operation,
            source_sha256='a'*64,now_ns=500_000_000)
        selected.append((operation,report['review_sha256']))
    kwargs = dict(root=tmp_path,draft=draft,selections=tuple(selected),source_sha256='a'*64,
        check_current=lambda:None,clock_ns=lambda:1_000_000_000)
    return req,kwargs


def test_load_exact_recorded_originals_without_refresh(tmp_path):
    import json,base64
    req,kwargs = recorded(tmp_path)
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    reader = load_engineering_review_reader(**kwargs)
    result = reader(req)
    assert set(result) == ENGINEERING_DRAFT_CHECKS
    for raw in result.values():
        bound = json.loads(raw)
        original = json.loads(base64.b64decode(bound['draft_review_b64']))
        assert original['recorded_ns'] == 500_000_000
    assert before == {p.name:p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('fault',['duplicate','path','hash','source','missing','expired','context'])
def test_selection_rejected(tmp_path,fault):
    _,kwargs = recorded(tmp_path)
    selected = kwargs['selections']
    if fault == 'duplicate': kwargs['selections'] = selected[:-1]+selected[:1]
    if fault == 'path': kwargs['selections'] = (('../outside','a'*64),)+selected[1:]
    if fault == 'hash': kwargs['selections'] = ((selected[0][0],'f'*64),)+selected[1:]
    if fault == 'source': kwargs['source_sha256'] = 'b'*64
    if fault == 'missing': kwargs['selections'] = selected[:-1]
    if fault == 'expired': kwargs['clock_ns'] = lambda:301_000_000_000
    if fault == 'context': kwargs['check_current'] = lambda:'changed'
    with pytest.raises(ValueError): load_engineering_review_reader(**kwargs)


@pytest.mark.parametrize('decision',['UNKNOWN','DENIED'])
def test_recording_success_is_not_approval(tmp_path,decision):
    _,kwargs = recorded(tmp_path,decision=decision)
    with pytest.raises(ValueError): load_engineering_review_reader(**kwargs)


def test_expiry_after_selection_is_rechecked_at_binding(tmp_path):
    req,kwargs = recorded(tmp_path)
    tick = [1_000_000_000]
    kwargs['clock_ns'] = lambda:tick[0]
    reader = load_engineering_review_reader(**kwargs)
    tick[0] = 301_000_000_000
    with pytest.raises(ValueError): reader(req)
