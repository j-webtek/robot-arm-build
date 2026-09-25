"""Actual public service/coordinator with a simulated owned-worker result."""

import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.powered_feedback_attempt_store import attempt_path
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker, OwnedWorkerResult, owned_request_wire
from rocell.providers.windows.powered_feedback_native_wire import validate_result
from rocell.arm.telemetry_stream import TelemetryStream, compact_capture
from rocell.application.wizard_actions import WizardError
from test_wizard_native_arm_integration import setup, action, ticket
from test_wizard_passive_arm_setup import ready
from test_wizard_powered_arm_setup import ACTION as SETUP, VALUES
from test_powered_telemetry_wire import captured

ACTION = "capture_powered_arm_telemetry"


def test_capture_select_run_export(setup, captured, monkeypatch):
    service, _, _, _ = ready(setup)
    assert action(service, SETUP, **VALUES)["status"] == "SUCCEEDED"
    saved = []

    def worker(self, request, *, cancellation, deadline_ns):
        payload = json.loads(request.payload_json)
        assert payload["intent"]["purpose"] == "POWERED_UNSOLICITED_TELEMETRY_ZERO_WRITE"
        assert payload["intent"]["limits"]["maximum_write_attempts"] == 0
        request_raw, request_sha = owned_request_wire(self.registration, request, deadline_ns=deadline_ns)
        self._authorizer(self.registration, request, request_sha)
        prepared = json.loads(attempt_path(Path(payload["root"]), request.attempt_id, "prepared").read_bytes())
        native = json.loads(base64.b64decode(prepared["body"]["originals_base64"]["native_identity_original_sha256"]))
        obs = deepcopy(captured)
        # Synthetic timestamps are associated with this synthetic worker run.
        duration = obs["observation_finished_monotonic_ns"] - obs["started_monotonic_ns"]
        offset = obs["started_monotonic_ns"] - payload["intent"]["startup_recorded_monotonic_ns"]
        obs["started_monotonic_ns"] = payload["intent"]["startup_recorded_monotonic_ns"]
        obs["observation_finished_monotonic_ns"] = obs["started_monotonic_ns"] + duration
        obs["finished_monotonic_ns"] = obs["observation_finished_monotonic_ns"]
        for row in obs["read_windows"]:
            row[2] -= offset
            row[3] -= offset
        obs["origin"] = "PHYSICAL_OBSERVATION"
        obs["request_sha256"] = request.operation_sha256
        obs["lifecycle"]["composition"] = "WINDOWS_POWERED_FEEDBACK_ENGINEERING"
        from test_first_motion_analysis import wire as sample_wire
        from rocell.application.powered_feedback_attempt_store import _publish
        sample_bytes, sample_windows = sample_wire([.02]*100, obs['started_monotonic_ns'])
        # This replacement stream begins immediately in the modeled epoch.
        obs['acquisition_started_monotonic_ns'] = obs['started_monotonic_ns']
        parser = TelemetryStream()
        parser.feed(sample_bytes)
        obs['capture'] = compact_capture(parser.finish())
        obs['read_windows'], obs['read_calls'] = sample_windows, len(sample_windows)
        obs['observation_finished_monotonic_ns'] = obs['started_monotonic_ns']+5_000_000_000
        obs['finished_monotonic_ns'] = obs['observation_finished_monotonic_ns']
        obs['stop_reason'] = 'OBSERVATION_WINDOW_COMPLETE'
        claim_sha = _publish(Path(payload['root']), request.attempt_id, 'claimed',
            dict(consumption_sha256=payload['consumption_sha256'], request_sha256=request.operation_sha256))
        parsed = {"schema": "rocell.owned_powered_feedback_native_result.v1",
            "attempt_id": request.attempt_id, "request_sha256": request_sha,
            "connected": False, "physical_authority": False,
            "child_result": {"schema": "rocell.powered_feedback_native_child_result.v1",
                "claim_sha256": claim_sha, "fresh_snapshot": native["snapshot"],
                "observation": obs, "connected": False, "physical_authority": False}}
        validate_result(parsed, wire=json.loads(request_raw))
        raw = _canonical(parsed)
        saved.append(raw)
        return OwnedWorkerResult(status="SUCCEEDED", primary_error=None, cleanup_errors=(),
            request_sha256=request_sha, attempt_id=request.attempt_id, process_created=True,
            initial_thread_resumed=True, tree_exit_confirmed=True, returncode=0, elapsed_ns=1,
            stdin_bytes_written=len(request_raw), peak_observed_handles=0, peak_active_processes=1,
            stdout=raw, stderr=b"synthetic worker", parsed_result=parsed)

    monkeypatch.setattr(OwnedWindowsWorker, "run", worker)
    completed = action(service, ACTION, firmware_unchanged=True)
    assert completed["status"] == "SUCCEEDED", completed
    report = completed["result"]["steps"][0]["report"]
    assert report["pose_sample_count"] == 100
    assert report["confirmed_write_bytes"] == 0
    assert report["motion_authorized"] is report["sample_freshness_verified"] is False
    for name in (ACTION, "run_powered_arm_feedback"):
        with pytest.raises(WizardError): ticket(service, name, firmware_unchanged=True)

    onboard = action(service, 'use_current_arm_for_observational_test',
        operator_id='FixtureOperator', confirm_model=True, firmware_unchanged=True)
    assert onboard['status'] == 'SUCCEEDED', json.dumps(onboard, indent=2)
    choices = service._absolute_wrist_capture_choices
    assert choices is not None and choices['choices']
    selected = next(item for item in choices['choices'] if item['draft']['target_deg'] == 0)
    source_id = next(iter(service._observational_sources))
    staged = action(service, 'setup_observational_movement', source_id=source_id,
        direction='1', degrees='5', absolute_draft=selected['draft_sha256'])
    assert staged['status'] == 'SUCCEEDED', staged
    assert service._observational_configuration['absolute_draft'].to_dict() == selected['draft']

    from rocell.application import wizard_absolute_wrist_coordinator as coordinator
    from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
    from rocell.safety.observational_review_authority import CHECKS
    from test_absolute_wrist_review_authority import intent
    body = intent()
    body.update(session_id=service.session_id,
        attempt_id=service._observational_configuration['staged'].attempt_id, draft=selected['draft'])
    request = AbsoluteWristIntent(_canonical(body))
    calls = []
    def confirm(*args, **kwargs):
        assert kwargs['draft'].sha256 == selected['draft_sha256']
        calls.append('confirm')
        return request, b'SYNTHETIC_SIGNED_RECORD'
    receipt = OwnedWorkerResult('FAILED', 'SYNTHETIC', (), 'a'*64, body['attempt_id'],
        False, False, False, None, 1, 0, 0, 0, b'absolute-original-stdout', b'absolute-original-stderr')
    def run(*args, **kwargs):
        kwargs['check_current']()
        calls.append('run')
        return coordinator.AbsoluteWristRunOutcome('RETAINED', receipt, None,
            dict(status='RESULT_RETAINED', endpoint_status='TARGET_MISSED',
                 endpoint_reported_settled=False), None)
    monkeypatch.setattr(coordinator, 'confirm_absolute_wrist_run', confirm)
    monkeypatch.setattr(coordinator, 'run_reviewed_absolute_wrist', run)
    movement = action(service, 'run_observational_movement', operator_id='Fixture operator',
        **dict.fromkeys(CHECKS, True))
    assert movement['status'] == 'FAILED', movement
    assert 'TARGET_MISSED' in movement['result']['message']
    assert calls == ['confirm', 'run']
    with pytest.raises(WizardError):
        ticket(service, 'run_observational_movement', operator_id='Fixture operator',
            **dict.fromkeys(CHECKS, True))
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    logs = json.loads((folder / "attachment-powered-feedback-native-logs.json").read_bytes())
    assert b"".join(base64.b64decode(c) for c in logs["stdout_base64_chunks"]) == saved[0]

    absolute_logs = json.loads((folder/'attachment-absolute-wrist-native-logs.json').read_bytes())
    assert absolute_logs['schema'] == 'rocell.absolute_wrist_native_logs.v1'
    assert b''.join(base64.b64decode(c) for c in absolute_logs['stdout_base64_chunks']) == receipt.stdout
