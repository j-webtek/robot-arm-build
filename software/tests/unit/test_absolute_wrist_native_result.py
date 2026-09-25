"""Parent result reconstruction from synthetic original captures, no hardware."""
import copy
import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.absolute_wrist_result_review import review_absolute_wrist_result
from rocell.providers.windows import absolute_wrist_native_result as module
from test_absolute_wrist_native_protocol import wire
import test_absolute_wrist_result_review as capture_fixture


def fixture(tmp_path, monkeypatch, fault=None):
    request_wire = wire(tmp_path)
    body = request_wire['payload']['absolute_wrist_intent']
    monkeypatch.setattr(capture_fixture, 'intent', lambda: copy.deepcopy(body))
    request, trial = capture_fixture.fixture(fault=fault)
    trial['basis'] = 'RETAINED_PHYSICAL_CAPTURE'  # Fixture label, never hardware evidence.
    review = review_absolute_wrist_result(request, canonical(trial), expected_basis=trial['basis'])
    endpoint = review['endpoint']['status']
    status = endpoint if endpoint == 'REPORTED_SETTLED' else 'HELD_'+endpoint
    owned = dict(schema='rocell.owned_absolute_wrist_trial.v1', status=status, trial=trial,
        review=review, errors=[], motion_authorized=False, physical_movement_verified=False,
        physical_stop_verified=False, campaign_advance_allowed=False, replay_allowed=False)
    lifecycle = dict(schema='rocell.absolute_wrist_connection_lifecycle.v1', phase='CLOSED',
        request_sha256=request.request_sha256, connection_id=body['attempt_id'],
        owned_handle_count=0, pending_io_count=0, confirmed_write_bytes=trial['write']['confirmed_bytes'],
        read_calls={p: trial[p]['read_calls'] for p in ('baseline', 'post')},
        read_bytes={p: trial[p]['raw']['bytes'] for p in ('baseline', 'post')},
        late_cleanup_read_base64='', errors=[], physical_stop_verified=False)
    child = dict(schema='rocell.absolute_wrist_native_child_result.v1', claim_sha256='f'*64,
        status=status, result=owned, lifecycle=lifecycle, errors=[], physical_authority=False)
    return child, request_wire


@pytest.mark.parametrize('fault', [None, 'miss', 'no_response', 'corrupt', 'other_joint'])
def test_parent_rebuilds_pass_and_held_endpoints(tmp_path, monkeypatch, fault):
    child, request = fixture(tmp_path, monkeypatch, fault)
    raw = module.encode_result(child, wire=request)
    value = module.decode_result(raw, wire=request)
    result = module.validate_result(value, wire=request)
    assert result['rebuilt_trial'] == child['result']['review']
    assert not result['campaign_advance_allowed'] and not result['owned_process_receipt_verified']
    assert len(raw) < module.MAX_BYTES


@pytest.mark.parametrize('fault', ['summary', 'status', 'authority', 'capture_count', 'write_count',
    'handles', 'errors', 'schema', 'request', 'missing_review', 'budget'])
def test_changed_child_claims_refused(tmp_path, monkeypatch, fault):
    child, request = fixture(tmp_path, monkeypatch)
    if fault == 'summary': child['result']['review']['endpoint']['final_error_rad'] = 1.
    if fault == 'status': child['status'] = 'HELD_TARGET_MISSED'
    if fault == 'authority': child['result']['campaign_advance_allowed'] = True
    if fault == 'capture_count': child['lifecycle']['read_calls']['post'] -= 1
    if fault == 'write_count': child['lifecycle']['confirmed_write_bytes'] -= 1
    if fault == 'handles': child['lifecycle']['owned_handle_count'] = 1
    if fault == 'errors': child['lifecycle']['errors'] = ['unresolved']
    if fault == 'schema': child['schema'] = 'rocell.observational_native_child_result.v1'
    if fault == 'request': child['lifecycle']['request_sha256'] = 'a'*64
    if fault == 'missing_review': child['result']['review'] = None
    if fault == 'budget': child['errors'] = ['x'*module.MAX_BYTES]
    with pytest.raises(ValueError): module.encode_result(child, wire=request)


def test_cleanup_override_cannot_become_endpoint_pass(tmp_path, monkeypatch):
    child, request = fixture(tmp_path, monkeypatch)
    child['status'] = 'CLEANUP_UNCONFIRMED'
    child['lifecycle']['phase'] = 'CLEANUP_UNCONFIRMED'
    child['lifecycle']['owned_handle_count'] = 1
    raw = module.encode_result(child, wire=request)
    result = module.validate_result(json.loads(raw), wire=request)
    assert not result['cleanup_reported_closed'] and not result['campaign_advance_allowed']
    assert result['status'] == 'FAILURE_DIAGNOSTIC_ONLY'


def test_failure_without_trial_remains_diagnostic_only(tmp_path, monkeypatch):
    child, request = fixture(tmp_path, monkeypatch)
    child.update(status='CANCELLED_BEFORE_OPEN', result=None)
    child['lifecycle'].update(confirmed_write_bytes=0, read_calls=dict(baseline=0, post=0),
                              read_bytes=dict(baseline=0, post=0))
    result = module.validate_result(json.loads(module.encode_result(child, wire=request)), wire=request)
    assert result['status'] == 'FAILURE_DIAGNOSTIC_ONLY' and result['rebuilt_trial'] is None


def test_unopened_label_cannot_hide_recorded_io(tmp_path, monkeypatch):
    child, request = fixture(tmp_path, monkeypatch)
    child.update(status='CANCELLED_BEFORE_OPEN', result=None)
    with pytest.raises(ValueError, match='Unopened outcome'):
        module.encode_result(child, wire=request)
