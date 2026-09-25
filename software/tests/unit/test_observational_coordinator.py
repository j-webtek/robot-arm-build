"""Host pipeline tests: synthetic receipts only, no native process/device APIs."""
import base64
from dataclasses import replace
import hashlib
import json
from threading import Event

import pytest

from rocell.application import wizard_observational_coordinator as coordinator
from rocell.providers.windows.observational_result_publication import publish_supervised_observational_result
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult, owned_request_wire
from test_observational_worker_preparation import fixture
from test_observational_native_registration import registration


def failed_receipt(reg, outer):
    _, digest = owned_request_wire(reg, outer, deadline_ns=outer.expires_at_ns)
    return OwnedWorkerResult('FAILED', 'SYNTHETIC_FAILURE', (), digest, outer.attempt_id,
        False, False, False, None, 0, 0, 0, 0, b'not-json', b'synthetic diagnostic',
        finished_monotonic_ns=2_000_000_000)


def test_rejected_output_retained_exactly_without_promotion_or_overwrite(tmp_path):
    reg, outer, _ = registration(tmp_path)
    result = failed_receipt(reg, outer)
    path, report = publish_supervised_observational_result(tmp_path, registration=reg, request=outer, result=result)
    assert json.loads(path.read_bytes()) == report
    assert report['status'] == 'RESULT_REJECTED'
    assert report['supervisor']['primary_error'] == 'SYNTHETIC_FAILURE'
    assert not report['campaign_advance_allowed'] and not report['claim_receipt_verified']
    for name, expected in [('stdout', result.stdout), ('stderr', result.stderr)]:
        original = report['originals'][name]
        stored = json.loads((tmp_path/original['file']).read_bytes())
        assert base64.b64decode(stored['base64']) == expected
        assert original['sha256'] == hashlib.sha256(expected).hexdigest()
    with pytest.raises(Exception):
        publish_supervised_observational_result(tmp_path, registration=reg, request=outer, result=result)


def test_wrong_receipt_not_published(tmp_path):
    reg, outer, _ = registration(tmp_path)
    result = replace(failed_receipt(reg, outer), request_sha256='f'*64)
    with pytest.raises(ValueError):
        publish_supervised_observational_result(tmp_path, registration=reg, request=outer, result=result)
    assert not list(tmp_path.glob('*-observational-stdout.original.json'))


@pytest.mark.parametrize('fault', [None, 'pid', 'cleanup'])
def test_retention_verifies_real_claim_records_not_just_child_json(tmp_path, monkeypatch, fault):
    import os
    from rocell.application.observational_worker_claim import claim_observational_worker
    from rocell.application.observational_worker_preparation import prepare_observational_worker
    from rocell.providers.windows.observational_native_protocol import decode_request
    from rocell.providers.windows.observational_native_result import encode_result

    workspace, staged, intent, signed, _, _ = fixture(tmp_path, monkeypatch)
    prepared = prepare_observational_worker(workspace, staged, intent,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    raw, digest = owned_request_wire(prepared.registration, prepared.request,
        deadline_ns=prepared.request.expires_at_ns)
    wire = decode_request(raw)
    refs = intent.to_dict()['references']
    claim = claim_observational_worker(tmp_path, intent,
        launch_sha256=wire['payload']['launch_sha256'], current_source_sha256=refs['source_sha256'],
        current_runtime_sha256=refs['runtime_sha256'], now_ns=2_000_000_000)
    # Synthetic process receipt: real claim validation, no real child or hardware.
    lifecycle = dict(schema='rocell.observational_connection_lifecycle.v1', phase='CLOSED',
        request_sha256=intent.request_sha256, connection_id=prepared.request.attempt_id,
        owned_handle_count=0, pending_io_count=0, read_calls=dict(baseline=0, post=0),
        read_bytes=dict(baseline=0, post=0), confirmed_write_bytes=0,
        late_cleanup_read_base64='', errors=[], physical_stop_verified=False)
    child = dict(schema='rocell.observational_native_child_result.v1', claim_sha256=claim.claim_sha256,
        status='HELD_BEFORE_WRITE', trial=None, selection_original=None, lifecycle=lifecycle,
        errors=['Synthetic hold'], physical_authority=False)
    result = replace(failed_receipt(prepared.registration, prepared.request), status='SUCCEEDED',
        primary_error=None, process_created=True, initial_thread_resumed=True, tree_exit_confirmed=True,
        returncode=0, stdout=encode_result(child, wire=wire), stderr=b'',
        owned_process_id=os.getpid()+(1 if fault == 'pid' else 0),
        cleanup_errors=('SYNTHETIC_CLEANUP_ERROR',) if fault == 'cleanup' else ())
    _, report = publish_supervised_observational_result(tmp_path, registration=prepared.registration,
        request=prepared.request, result=result)
    assert report['status'] == ('RESULT_REJECTED' if fault == 'pid' else
        'PROCESS_COMPLETION_UNCONFIRMED' if fault == 'cleanup' else 'RESULT_RETAINED')
    assert report['claim_receipt_verified'] is (fault != 'pid')
    assert report['physical_movement_verified'] is False
    assert report['campaign_advance_allowed'] is False


@pytest.mark.parametrize('fault', [None, 'cancel_before', 'cancel_after', 'export', 'authorization'])
def test_coordinator_retains_once_and_never_retries(tmp_path, monkeypatch, fault):
    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    cancel = Event()
    calls, receipts = [], []

    class IncapableWorker:
        def __init__(self, reg, *, authorizer, _clock):
            self.reg, self.authorizer = reg, authorizer

        def run(self, outer, *, cancellation, deadline_ns):
            calls.append('run')
            _, digest = owned_request_wire(self.reg, outer, deadline_ns=deadline_ns)
            self.authorizer(self.reg, outer, 'f'*64 if fault == 'authorization' else digest)
            receipt = failed_receipt(self.reg, outer)
            receipts.append(receipt)
            if fault == 'cancel_after': cancellation.set()
            return receipt

    monkeypatch.setattr(coordinator, 'OwnedWindowsWorker', IncapableWorker)
    if fault == 'cancel_before': cancel.set()
    if fault == 'export':
        def broken_export(*args, **kwargs): raise OSError('synthetic export failure')
        monkeypatch.setattr(coordinator, 'publish_supervised_observational_result', broken_export)
    outcome = coordinator.run_reviewed_observational(workspace, staged, request,
        review_original=signed, export_root=tmp_path, cancellation=cancel,
        check_current=lambda: None, clock_ns=lambda: 2_000_000_000)
    if fault == 'cancel_before':
        assert calls == [] and outcome.stage == 'PREPARATION_FAILED'
    elif fault == 'authorization':
        assert calls == ['run'] and outcome.stage == 'SUPERVISION_FAILED'
    elif fault == 'export':
        assert outcome.stage == 'RETENTION_FAILED' and outcome.owned is receipts[0]
        assert calls == ['run']
    else:
        assert outcome.stage == 'RETAINED' and outcome.owned is receipts[0]
        assert outcome.report['status'] == 'RESULT_REJECTED' and calls == ['run']
