"""Host pipeline tests: synthetic receipts only, no native process/device APIs."""
import base64
from dataclasses import replace
import hashlib
import json
from threading import Event

import pytest

from rocell.application import wizard_absolute_wrist_coordinator as coordinator
from rocell.providers.windows.absolute_wrist_result_publication import publish_supervised_absolute_wrist_result
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult, owned_request_wire
from test_absolute_wrist_timed_preparation import fixture
from test_absolute_wrist_worker_preparation import fixture as staging_fixture

def registration(tmp_path):
    workspace, staged, request, outer = staging_fixture(tmp_path)
    return staged.registration, outer, request


def failed_receipt(reg, outer):
    _, digest = owned_request_wire(reg, outer, deadline_ns=outer.expires_at_ns)
    return OwnedWorkerResult('FAILED', 'SYNTHETIC_FAILURE', (), digest, outer.attempt_id,
        False, False, False, None, 0, 0, 0, 0, b'not-json', b'synthetic diagnostic',
        finished_monotonic_ns=2_000_000_000)


def test_rejected_output_retained_exactly_without_promotion_or_overwrite(tmp_path):
    reg, outer, _ = registration(tmp_path)
    result = failed_receipt(reg, outer)
    path, report = publish_supervised_absolute_wrist_result(tmp_path, registration=reg, request=outer, result=result)
    assert json.loads(path.read_bytes()) == report
    assert report['status'] == 'RESULT_REJECTED'
    assert report['supervisor']['primary_error'] == 'SYNTHETIC_FAILURE'
    assert not report['campaign_advance_allowed'] and not report['claim_receipt_verified']
    assert not any(report['verification_layers'].values())
    for name, expected in [('stdout', result.stdout), ('stderr', result.stderr)]:
        original = report['originals'][name]
        stored = json.loads((tmp_path/original['file']).read_bytes())
        assert base64.b64decode(stored['base64']) == expected
        assert original['sha256'] == hashlib.sha256(expected).hexdigest()
    with pytest.raises(Exception):
        publish_supervised_absolute_wrist_result(tmp_path, registration=reg, request=outer, result=result)


def test_wrong_receipt_not_published(tmp_path):
    reg, outer, _ = registration(tmp_path)
    result = replace(failed_receipt(reg, outer), request_sha256='f'*64)
    with pytest.raises(ValueError):
        publish_supervised_absolute_wrist_result(tmp_path, registration=reg, request=outer, result=result)
    assert not list(tmp_path.glob('*-absolute_wrist-stdout.original.json'))


def test_display_report_does_not_duplicate_large_parsed_child_tree(tmp_path):
    from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
    reg, outer, _ = registration(tmp_path)
    # Real streams have hundreds of read windows and nested capture summaries.
    # Retain bytes once; do not expand the wizard's depth/item safety budget.
    result = replace(failed_receipt(reg, outer),
        parsed_result={'nested_capture': [[0, 1, 2, 3] for _ in range(2000)]})
    _, report = publish_supervised_absolute_wrist_result(tmp_path,
        registration=reg, request=outer, result=result)
    assert 'parsed_result' not in report['supervisor']
    assert report['supervisor']['stdout_sha256'] == hashlib.sha256(result.stdout).hexdigest()
    assert sanitize_diagnostic_record({'steps': [{'report': report}]}, maximum_bytes=1048576)
    stored = json.loads((tmp_path/report['originals']['stdout']['file']).read_bytes())
    assert base64.b64decode(stored['base64']) == result.stdout


@pytest.mark.parametrize('fault', [None, 'pid', 'cleanup'])
def test_retention_verifies_real_claim_records_not_just_child_json(tmp_path, monkeypatch, fault):
    import os
    from rocell.application.absolute_wrist_worker_claim import claim_absolute_wrist_worker
    from rocell.application.absolute_wrist_worker_preparation import prepare_absolute_wrist_worker
    from rocell.providers.windows.absolute_wrist_native_protocol import decode_request
    from rocell.providers.windows.absolute_wrist_native_result import encode_result

    workspace, staged, intent, signed, _, _ = fixture(tmp_path, monkeypatch)
    prepared = prepare_absolute_wrist_worker(workspace, staged, intent,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    raw, digest = owned_request_wire(prepared.registration, prepared.request,
        deadline_ns=prepared.request.expires_at_ns)
    wire = decode_request(raw)
    refs = intent.to_dict()['references']
    claim = claim_absolute_wrist_worker(tmp_path, intent,
        launch_sha256=wire['payload']['launch_sha256'], current_source_sha256=refs['source_sha256'],
        current_runtime_sha256=refs['runtime_sha256'], now_ns=2_000_000_000)
    # Synthetic process receipt: real claim validation, no real child or hardware.
    lifecycle = dict(schema='rocell.absolute_wrist_connection_lifecycle.v1', phase='CLOSED',
        request_sha256=intent.request_sha256, connection_id=prepared.request.attempt_id,
        owned_handle_count=0, pending_io_count=0, read_calls=dict(baseline=0, post=0),
        read_bytes=dict(baseline=0, post=0), confirmed_write_bytes=0,
        late_cleanup_read_base64='', errors=[], physical_stop_verified=False)
    child = dict(schema='rocell.absolute_wrist_native_child_result.v1', claim_sha256=claim.claim_sha256,
        status='CANCELLED_BEFORE_OPEN', result=None, lifecycle=lifecycle,
        errors=['Synthetic hold'], physical_authority=False)
    result = replace(failed_receipt(prepared.registration, prepared.request), status='SUCCEEDED',
        primary_error=None, process_created=True, initial_thread_resumed=True, tree_exit_confirmed=True,
        returncode=0, stdout=encode_result(child, wire=wire), stderr=b'',
        owned_process_id=os.getpid()+(1 if fault == 'pid' else 0),
        cleanup_errors=('SYNTHETIC_CLEANUP_ERROR',) if fault == 'cleanup' else ())
    _, report = publish_supervised_absolute_wrist_result(tmp_path, registration=prepared.registration,
        request=prepared.request, result=result)
    assert report['status'] == ('RESULT_REJECTED' if fault == 'pid' else
        'PROCESS_COMPLETION_UNCONFIRMED' if fault == 'cleanup' else 'RESULT_RETAINED')
    assert report['claim_receipt_verified'] is (fault != 'pid')
    assert report['physical_movement_verified'] is False
    assert report['campaign_advance_allowed'] is False
    assert report['endpoint_status'] is None and not report['endpoint_reported_settled']
    layers = report['verification_layers']
    assert layers['worker_claim_verified'] is (fault != 'pid')
    assert layers['owned_process_completion_verified'] is (fault is None)
    assert not layers['reported_joint_destination_verified']


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
        monkeypatch.setattr(coordinator, 'publish_supervised_absolute_wrist_result', broken_export)
    outcome = coordinator.run_reviewed_absolute_wrist(workspace, staged, request,
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


@pytest.mark.parametrize('delay_ns', [1_000_000_000, 4_000_000_000])
def test_confirmation_binds_exact_draft_and_does_not_renew_old_click(tmp_path, monkeypatch, delay_ns):
    from rocell.application.first_motion_contract import canonical
    from rocell.motion.absolute_wrist_diagnostic import AbsoluteWristDiagnosticDraft
    from test_absolute_wrist_review_authority import review
    workspace, staged, request, _, _, _ = fixture(tmp_path, monkeypatch)
    body = request.to_dict()
    accepted = body['issued_ns']
    values = review()
    params = dict(session_id=body['session_id'], usb_identity=body['usb_identity'],
        draft=AbsoluteWristDiagnosticDraft(canonical(body['draft'])), operator_id=values['operator_id'],
        checks=values['checks'], accepted_ns=accepted, now_ns=accepted+delay_ns)
    if delay_ns > 3_000_000_000:
        with pytest.raises(ValueError, match='too old'):
            coordinator.confirm_absolute_wrist_run(workspace, staged, **params)
    else:
        confirmed, signed = coordinator.confirm_absolute_wrist_run(workspace, staged, **params)
        assert confirmed.to_dict()['draft'] == body['draft']
        assert confirmed.to_dict()['issued_ns'] == accepted
        assert confirmed.to_dict()['deadline_ns'] == accepted+30_000_000_000
        assert signed


def test_zero_digest_preflight_failure_is_retained_without_claiming_process(tmp_path):
    reg, outer, _ = registration(tmp_path)
    receipt = replace(failed_receipt(reg, outer), request_sha256='0'*64, stdout=b'', stderr=b'')
    _, report = publish_supervised_absolute_wrist_result(tmp_path, registration=reg, request=outer, result=receipt)
    assert report['status'] == 'RESULT_REJECTED'
    assert not report['claim_receipt_verified'] and not report['endpoint_reported_settled']


@pytest.mark.parametrize('fault', [None, 'miss'])
@pytest.mark.parametrize('process_clean', [True, False])
def test_retained_report_distinguishes_endpoint_pass_from_saved_miss(tmp_path, monkeypatch, fault, process_clean):
    import os
    import test_absolute_wrist_native_result as result_fixture
    from rocell.application.absolute_wrist_worker_claim import claim_absolute_wrist_worker
    from rocell.providers.windows.absolute_wrist_native_protocol import decode_request
    from rocell.providers.windows.absolute_wrist_native_result import encode_result
    workspace, staged, intent, signed, _, _ = fixture(tmp_path, monkeypatch)
    prepared = coordinator.prepare_absolute_wrist_worker(workspace, staged, intent,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    raw, _ = owned_request_wire(prepared.registration, prepared.request,
        deadline_ns=prepared.request.expires_at_ns)
    wire = decode_request(raw)
    monkeypatch.setattr(result_fixture, 'wire', lambda _: wire)
    child, _ = result_fixture.fixture(tmp_path, monkeypatch, fault)
    refs = intent.to_dict()['references']
    claim = claim_absolute_wrist_worker(tmp_path, intent, launch_sha256=wire['payload']['launch_sha256'],
        current_source_sha256=refs['source_sha256'], current_runtime_sha256=refs['runtime_sha256'],
        now_ns=2_000_000_000)
    child['claim_sha256'] = claim.claim_sha256
    receipt = replace(failed_receipt(prepared.registration, prepared.request), status='SUCCEEDED',
        primary_error=None, process_created=True, initial_thread_resumed=True, tree_exit_confirmed=True,
        returncode=0, stdout=encode_result(child, wire=wire), stderr=b'', owned_process_id=os.getpid(),
        finished_monotonic_ns=10_000_000_000)
    if not process_clean:
        receipt = replace(receipt, cleanup_errors=('SYNTHETIC_CLEANUP_ERROR',))
    _, report = publish_supervised_absolute_wrist_result(tmp_path, registration=prepared.registration,
        request=prepared.request, result=receipt)
    assert report['status'] == ('RESULT_RETAINED' if process_clean else 'PROCESS_COMPLETION_UNCONFIRMED')
    assert report['endpoint_status'] == ('REPORTED_SETTLED' if fault is None else 'TARGET_MISSED')
    assert report['endpoint_reported_settled'] is (fault is None and process_clean)
    assert report['verification_layers'] == dict(
        worker_claim_verified=True,
        owned_process_completion_verified=process_clean,
        serial_cleanup_reported_closed=True,
        reported_joint_destination_verified=fault is None and process_clean,
        device_sample_freshness_verified=False,
        independent_tool_position_verified=False,
        physical_stop_verified=False)
    assert not report['summary']['owned_process_receipt_verified']
    assert not report['summary']['rebuilt_trial']['owned_process_verified']
    assert not report['campaign_advance_allowed'] and not report['physical_movement_verified']
    trace = report['trace_diagnostic']
    assert trace['endpoint_status'] == report['endpoint_status']
    assert trace['trial_sha256'] == report['summary']['rebuilt_trial']['trial_sha256']
    assert report['accuracy_diagnostic']['trial_sha256'] == trace['trial_sha256']
    assert report['accuracy_diagnostic']['endpoint_status'] == report['endpoint_status']
    assert not report['accuracy_diagnostic']['compensation_recommended']
    assert trace['status'] == 'REPORTED_TRACE_AVAILABLE'
    assert not trace['campaign_advance_allowed'] and not trace['sample_freshness_verified']
    assert 'parsed_result' not in report['supervisor']
    from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
    # Exercise the same nesting and budget used by the public wizard result.
    assert sanitize_diagnostic_record(dict(steps=[dict(report=report)]), maximum_bytes=1048576)
