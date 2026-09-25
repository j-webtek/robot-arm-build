"""Public Arrival/export join with actual evidence, injected acquisition/storage.

The commissioning control flow and fault projection are real. Worker/coordinator
and M1 storage are explicit fixtures: these tests prove neither acquisition nor
durability qualification. Only diagnostic logs/exports are written to tmp_path.
"""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import threading

import pytest

from rocell.application.camera_fault_diagnostics import camera_fault_diagnostic
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import (
    _complete,
    _run,
    _ticket,
    make_service,
)
from test_camera_fault_service import ACTION, installed_service


def _assert_safe_fault(report, artifact):
    fault = report["camera_fault_diagnostic"]
    assert fault == camera_fault_diagnostic(artifact)
    assert fault["reason_category"] == "CONTROL_READBACK_MISMATCH_REPORTED"
    assert fault["evidence_sha256"] == artifact.evidence_sha256
    assert report["retained_campaign_sha256"] == artifact.evidence_sha256
    assert report["attempt_result"]["state"] == "SEALED_UNCERTAIN"
    assert report["attempt_result"]["quarantine_latched"] is True
    assert report["camera_process"]["native"] is None
    for field in (
        "retry_this_attempt_allowed",
        "automatic_retry_allowed",
        "clear_quarantine_allowed",
        "physical_authority",
        "qualified",
    ):
        assert fault[field] is False
    text = json.dumps(report)
    for raw_field in (
        '"stdout":',
        '"stderr":',
        '"payload_base64":',
        '"native_receipt":',
        '"symbolic_link":',
    ):
        assert raw_field not in text
    assert "incapable://" not in text


@pytest.mark.parametrize("failure", ["publication", "stop", "final-source"])
def test_arrival_late_failure_exports_exact_retained_camera_fault(
    make_service, monkeypatch, tmp_path, failure
):
    arrival, runner, source = make_service()
    commissioning, artifact, _, _, calls = installed_service(
        monkeypatch, tmp_path, failure="uncertain"
    )
    original_payload = artifact.payload
    monkeypatch.setattr(arrival, "_commissioning", commissioning)

    def no_process(*args, **kwargs):
        pytest.fail("This integration fixture must not start a native/device process")

    monkeypatch.setattr(subprocess, "Popen", no_process)
    retained = threading.Event()
    reached_cancellation = []
    original_execute = commissioning._execute_camera_worker
    original_refresh = commissioning._refresh

    def execute(worker, registration, cancellation, **kwargs):
        reached_cancellation.append(cancellation)
        return original_execute(worker, registration, cancellation, **kwargs)

    def refresh(**kwargs):
        original_refresh(**kwargs)
        # The exact artifact has passed the real retained-evidence projection
        # before this injected late boundary refuses current publication.
        assert commissioning.retained_camera_diagnostics() is not None
        retained.set()
        if failure == "publication":
            raise OSError("Injected late diagnostic publication failure")
        if failure == "stop":
            assert reached_cancellation[0].wait(3), "Explicit Stop did not arrive"
            commissioning._check_cancelled(
                reached_cancellation[0], "injected diagnostic publication boundary"
            )
        if failure == "final-source":
            # No file changes: the Arrival fixture's final source recheck sees
            # drift after the actual service has retained its failed result.
            source["hash"] = "b" * 64

    monkeypatch.setattr(commissioning, "_execute_camera_worker", execute)
    monkeypatch.setattr(commissioning, "_refresh", refresh)
    ticket = _ticket(arrival, ACTION, {"frame_count": 1, "fault": "none"})
    receipt = arrival.execute_action(ticket["ticket_id"])
    assert retained.wait(3)
    if failure == "stop":
        stop = _run(arrival, "stop_operation")
        assert stop["status"] == "SUCCEEDED"
        assert stop["result"]["target_operation_id"] == receipt["operation_id"]

    operation = _complete(arrival, receipt["operation_id"])
    assert operation["status"] == "FAILED"
    assert (
        operation["result"]["code"]
        == {
            "publication": "DIAGNOSTIC_FAILED",
            "stop": "REHEARSAL_CANCELLED_BEFORE_PUBLICATION",
            "final-source": "SOURCE_CHANGED",
        }[failure]
    )
    assert operation["completion_log_persisted"] is True
    assert operation["result_retention"] == "FULL_JSON_RETAINED"
    history = operation["result"]["retained_camera_diagnostics"]
    _assert_safe_fault(history, artifact)
    assert history == commissioning.retained_camera_diagnostics()
    assert commissioning._receipt_reference is None
    assert commissioning.latest_preview() is None
    assert arrival.view()["camera"]["image_id"] is None
    assert all(s["state"] == "PHYSICAL_PENDING" for s in arrival.view()["stages"])
    assert artifact.payload == original_payload

    # Reusing the exact ticket is an idempotent historical lookup, not a retry.
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    with pytest.raises(WizardError):
        _ticket(arrival, ACTION, {"frame_count": 1, "fault": "none"})
    returned = deepcopy(operation)
    returned["result"]["retained_camera_diagnostics"]["camera_fault_diagnostic"][
        "automatic_retry_allowed"
    ] = True
    assert arrival.operation(receipt["operation_id"]) == operation

    exported = _run(arrival, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    assert directory.is_relative_to(tmp_path / "exports")
    assert verify_export(directory)["status"] == "VERIFIED_DIAGNOSTIC_EXPORT"
    attachment = directory / (
        "attachment-result-"
        + receipt["operation_id"].removeprefix("operation-")
        + ".json"
    )
    saved = json.loads(attachment.read_text(encoding="utf-8"))
    assert saved == operation["result"]
    _assert_safe_fault(saved["retained_camera_diagnostics"], artifact)
    snapshot = json.loads((directory / "report.json").read_text(encoding="utf-8"))[
        "snapshot"
    ]
    assert (
        snapshot["commissioning_rehearsal"]["camera_fault_diagnostic"]
        == history["camera_fault_diagnostic"]
    )
    assert snapshot["camera"]["image_id"] is None
    assert calls.count("execute") == 1
    assert "publish" not in calls
    assert not runner.calls
    assert not commissioning.directory.exists()
