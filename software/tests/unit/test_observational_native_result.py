from copy import deepcopy
import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import observational_native_result as codec
from test_observational_native_protocol import wire as make_wire, rehash
from test_observational_owned_trial import run


def fixture(tmp_path, monkeypatch):
    import test_observational_current_context as context_fixture
    wire = make_wire(tmp_path)
    body = deepcopy(wire['payload']['observational_intent'])
    monkeypatch.setattr(context_fixture, 'intent', lambda: deepcopy(body))
    request, trial, _ = run(tmp_path)
    wire['payload']['observational_intent'] = request.to_dict()
    wire['operation_sha256'] = request.request_sha256
    rehash(wire)
    # Explicit codec fixture only: synthetic data carries the native expected
    # domain label to exercise parsing, never evidence of physical hardware.
    trial['basis'] = 'RETAINED_PHYSICAL_CAPTURE'
    selection = json.loads((tmp_path/(request.to_dict()['attempt_id']+
        '-observational-command-selection.json')).read_bytes())
    lifecycle = dict(schema='rocell.observational_connection_lifecycle.v1', phase='CLOSED',
        request_sha256=request.request_sha256, connection_id=request.to_dict()['attempt_id'],
        owned_handle_count=0, pending_io_count=0,
        read_calls={phase:trial[phase]['read_calls'] for phase in ('baseline','post')},
        read_bytes={phase:trial[phase]['raw']['bytes'] for phase in ('baseline','post')},
        confirmed_write_bytes=trial['write']['confirmed_write_bytes'],
        late_cleanup_read_base64='', errors=[], physical_stop_verified=False)
    child = dict(schema='rocell.observational_native_child_result.v1', claim_sha256='a'*64,
        status=trial['status'], trial=trial, selection_original=selection, lifecycle=lifecycle,
        errors=[], physical_authority=False)
    return wire, child


def test_complete_data_rebuilt_but_process_and_motion_unverified(tmp_path, monkeypatch):
    wire, child = fixture(tmp_path, monkeypatch)
    raw = codec.encode_result(child, wire=wire)
    result = codec.decode_result(raw, wire=wire)
    review = codec.validate_result(result, wire=wire)
    assert review['status'] == 'COMPLETED_DATA_CONSISTENT'
    assert review['owned_process_receipt_verified'] is False
    assert review['physical_movement_verified'] is False


@pytest.mark.parametrize('fault', ['write_count','read_count','cleanup','selection','basis','late_bytes'])
def test_conflicting_success_refused(tmp_path, monkeypatch, fault):
    wire, child = fixture(tmp_path, monkeypatch)
    if fault == 'write_count': child['lifecycle']['confirmed_write_bytes'] -= 1
    if fault == 'read_count': child['lifecycle']['read_calls']['baseline'] -= 1
    if fault == 'cleanup': child['lifecycle']['pending_io_count'] = 1
    if fault == 'selection': child['selection_original']['preview']['candidate_command']['spd'] = 0
    if fault == 'basis': child['trial']['basis'] = 'SYNTHETIC_WIRE_REHEARSAL'
    if fault == 'late_bytes': child['lifecycle']['late_cleanup_read_base64'] = '!!'
    with pytest.raises(ValueError): codec.encode_result(child, wire=wire)


def test_failed_originals_remain_diagnostic(tmp_path, monkeypatch):
    wire, child = fixture(tmp_path, monkeypatch)
    child['status'] = 'WRITE_UNCERTAIN_NO_RETRY'
    result = codec.decode_result(codec.encode_result(child, wire=wire), wire=wire)
    report = codec.validate_result(result, wire=wire)
    assert report['status'] == 'FAILURE_DIAGNOSTIC_ONLY'
    assert report['rebuilt_trial'] is None
    assert result['child_result']['trial'] == child['trial']
