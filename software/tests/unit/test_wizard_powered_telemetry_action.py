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


@pytest.fixture(autouse=True)
def no_actual_worker(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No live worker may start in these tests")
    monkeypatch.setattr(OwnedWindowsWorker, "run", forbidden)


@pytest.mark.parametrize("empty", [False, True])
def test_public_capture_export_and_shared_attempt_limit(setup, captured, monkeypatch, empty):
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
        obs["acquisition_started_monotonic_ns"] -= offset
        obs["observation_finished_monotonic_ns"] = obs["started_monotonic_ns"] + duration
        obs["finished_monotonic_ns"] = obs["observation_finished_monotonic_ns"]
        for row in obs["read_windows"]:
            row[2] -= offset
            row[3] -= offset
        obs["origin"] = "PHYSICAL_OBSERVATION"
        obs["request_sha256"] = request.operation_sha256
        obs["lifecycle"]["composition"] = "WINDOWS_POWERED_FEEDBACK_ENGINEERING"
        if empty:
            obs["capture"] = compact_capture(TelemetryStream().finish())
            obs["read_windows"] = []
            obs["read_calls"] = 0
        parsed = {"schema": "rocell.owned_powered_feedback_native_result.v1",
            "attempt_id": request.attempt_id, "request_sha256": request_sha,
            "connected": False, "physical_authority": False,
            "child_result": {"schema": "rocell.powered_feedback_native_child_result.v1",
                "claim_sha256": "e"*64, "fresh_snapshot": native["snapshot"],
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
    assert completed["status"] == ("FAILED" if empty else "SUCCEEDED"), completed
    report = completed["result"]["steps"][0]["report"]
    assert report["pose_sample_count"] == (0 if empty else 1)
    assert report["confirmed_write_bytes"] == 0
    assert report["motion_authorized"] is report["sample_freshness_verified"] is False
    for name in (ACTION, "run_powered_arm_feedback"):
        with pytest.raises(WizardError): ticket(service, name, firmware_unchanged=True)
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    logs = json.loads((folder / "attachment-powered-feedback-native-logs.json").read_bytes())
    assert b"".join(base64.b64decode(c) for c in logs["stdout_base64_chunks"]) == saved[0]


def test_setup_and_physical_mode_required(setup):
    service, _, _, _ = ready(setup)
    with pytest.raises(WizardError): ticket(service, ACTION, firmware_unchanged=True)
    other, _, _, _ = setup("rehearsal")
    with pytest.raises(WizardError): ticket(other, ACTION, firmware_unchanged=True)
