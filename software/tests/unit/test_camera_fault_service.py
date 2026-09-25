"""Actual service control flow, injected worker/store; no M1 or process claims."""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from rocell.application import commissioning_rehearsal_service as module
from rocell.application import owned_camera_rehearsal_campaign as campaign
from rocell.application.camera_fault_diagnostics import camera_fault_diagnostic
from rocell.application.camera_rehearsal_campaign import camera_settings
from rocell.application.cell_commissioning_coordinator import AttemptResult
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.rehearsal_owned_camera_evidence import (
    retain_owned_camera_evidence,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter,
    verify_export,
)
from test_camera_fault_diagnostics import rejection_inputs
from test_rehearsal_owned_camera_evidence import complete_inputs

ACTION = "rehearsal_owned_camera_campaign"


def installed_service(monkeypatch, tmp_path, failure="uncertain"):
    """Fixture responses are explicitly injected, not real durability/acquisition."""
    inputs = (
        complete_inputs()
        if failure in {"known", "stop", "publication"}
        else rejection_inputs()
    )
    artifact = retain_owned_camera_evidence(**inputs)
    state = (
        AttemptState.SEALED_KNOWN
        if failure in {"known", "stop", "publication"}
        else AttemptState.SEALED_UNCERTAIN
    )
    result = AttemptResult(
        inputs["binding"]["attempt_id"],
        state,
        inputs["binding"]["permit_sha256"],
        () if state is AttemptState.SEALED_KNOWN else ("EFFECT_UNCERTAIN",),
        None,
        state is AttemptState.SEALED_UNCERTAIN,
    )
    service = module.CommissioningRehearsalService(
        Path(__file__).resolve().parents[3],
        tmp_path / "never-created-store",
        source_sha256="a" * 64,
    )
    cancellation = threading.Event()
    calls = []
    stage = STAGE_ORDER[4]
    service._store = SimpleNamespace(
        snapshot=lambda _: SimpleNamespace(next_action=SimpleNamespace(stage=stage))
    )
    service._selected = {"endpoint": "incapable-fixture-only"}
    service._operator = "injected-operator"
    service._camera_settings = {
        "settings": camera_settings(0),
        "settings_epoch": "e" * 64,
    }
    service._cached.update(
        stage=stage.value, stage_state="WAITING_OPERATOR", status="ACTIVE_REHEARSAL"
    )
    capture = (
        SimpleNamespace(
            to_dict=lambda: {"schema": "test.metadata.only"},
            latest_preview=SimpleNamespace(png_bytes=b"test-only-image-not-camera"),
        )
        if state is AttemptState.SEALED_KNOWN
        else None
    )

    class Worker:
        def __init__(self, *args, **kwargs):
            self.evidence = None
            self.capture = capture
            calls.append("construct")

        def plan(self):
            return {"process_backend": "OWNED_INCAPABLE_CAMERA_PROCESS"}

        def registration(self, _stage):
            return SimpleNamespace()

    def execute(worker, *args, **kwargs):
        calls.append("execute")
        worker.evidence = artifact
        if failure == "execution":
            raise OSError("injected coordinator exit/retention failure")
        if failure == "stop":
            cancellation.set()
        return result

    def refresh(**kwargs):
        calls.append("refresh")
        if failure == "source":
            raise WizardError("SOURCE_CHANGED", "injected late source drift")
        service._cached.update(
            status="HELD" if service._failed else "ACTIVE_REHEARSAL",
            camera_process=deepcopy(service._camera_process),
            capture_dataset=deepcopy(service._latest_capture),
        )

    @contextmanager
    def transaction():
        calls.append("transaction")
        yield object()

    def publish(*args):
        calls.append("publish")
        if failure == "publication":
            raise OSError("injected stage publication failure")
        return "injected-reference-not-M1"

    monkeypatch.setattr(campaign, "OwnedBinaryCameraWorker", Worker)
    monkeypatch.setattr(service, "_execute_camera_worker", execute)
    monkeypatch.setattr(service, "_refresh", refresh)
    monkeypatch.setattr(service, "_transaction", transaction)
    monkeypatch.setattr(service, "_store_json", publish)
    return service, artifact, result, cancellation, calls


def perform(service, cancellation):
    return service.perform(
        ACTION,
        {
            "frame_count": 1,
            "fault": "none",
            "_view_sha256": module._hash(service.view()),
        },
        cancellation=cancellation,
        progress=lambda _: None,
    )


def test_fault_is_in_cached_view_and_full_operation_step(monkeypatch, tmp_path):
    service, artifact, result, cancel, calls = installed_service(monkeypatch, tmp_path)
    operation = perform(service, cancel)
    assert operation["status"] == "FAILED"
    fault = camera_fault_diagnostic(artifact)
    assert service.view()["camera_fault_diagnostic"] == fault
    report = operation["steps"][-1]["report"]
    assert (
        operation["steps"][-1]["name"] == "retained-incapable-owned-camera-diagnostics"
    )
    assert report["camera_fault_diagnostic"] == fault
    assert report["retained_campaign_sha256"] == fault["evidence_sha256"]
    assert report["attempt_result"]["state"] == "SEALED_UNCERTAIN"
    assert report["attempt_result"]["quarantine_latched"] is True
    assert service.latest_preview() is None
    assert "publish" not in calls
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert service.retained_camera_diagnostics() == report
    assert "camera_fault_diagnostic" not in service._receipt


@pytest.mark.parametrize("failure", ["source", "execution", "stop", "publication"])
def test_late_failure_preserves_history_not_current_preview(
    monkeypatch, tmp_path, failure
):
    service, artifact, result, cancel, calls = installed_service(
        monkeypatch, tmp_path, failure
    )
    with pytest.raises((WizardError, OSError)):
        perform(service, cancel)
    retained = service.retained_camera_diagnostics()
    assert retained["camera_fault_diagnostic"] == camera_fault_diagnostic(artifact)
    assert (
        service.view()["camera_fault_diagnostic"] == retained["camera_fault_diagnostic"]
    )
    assert service.view()["status"] == "HELD"
    assert service.latest_preview() is None
    assert service.view()["camera_process"] is None
    assert service._receipt_reference is None
    if failure == "execution":
        assert retained["attempt_result"] is None
        assert (
            retained["raw_evidence_location"]
            == "CAMPAIGN_WORKER_EVIDENCE_DURABLE_RETENTION_UNCONFIRMED"
        )
    else:
        assert retained["attempt_result"]["state"] == result.state.value
    # Clearing a display and rereading history cannot reopen or clear a hold.
    service._clear_preview()
    assert service.retained_camera_diagnostics() == retained
    cancel.clear()
    with pytest.raises(WizardError, match="held"):
        perform(service, cancel)
    assert calls.count("execute") == 1
    assert not service.directory.exists()


def test_history_reads_are_detached_and_inert(monkeypatch, tmp_path):
    service, _, _, cancel, _ = installed_service(monkeypatch, tmp_path)
    perform(service, cancel)
    original = service.retained_camera_diagnostics()

    def forbidden(*args, **kwargs):
        pytest.fail("Cached status must not read storage or dispatch")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(service, "_execute_camera_worker", forbidden)
    monkeypatch.setattr(service, "_refresh", forbidden)
    returned = service.retained_camera_diagnostics()
    returned["camera_fault_diagnostic"]["clear_quarantine_allowed"] = True
    assert service.retained_camera_diagnostics() == original
    assert (
        service.view()["camera_fault_diagnostic"]["clear_quarantine_allowed"] is False
    )
    service._clear_camera_diagnostics()
    assert service.view()["camera_fault_diagnostic"] is None
    assert service.retained_camera_diagnostics() is None


def test_actual_export_retains_actionable_fault_without_raw_packet(
    monkeypatch, tmp_path
):
    service, artifact, _, cancel, _ = installed_service(monkeypatch, tmp_path)
    operation = perform(service, cancel)
    exporter = WizardDiagnosticExporter(tmp_path / "exports")
    exporter.prepare(create=True)
    receipt = exporter.export(
        {
            "session_id": "wizard-fault-test",
            "mode": "rehearsal",
            "source_sha256": "a" * 64,
            "commissioning_rehearsal": service.view(),
            "physical_authority": False,
        },
        [],
        attachments={"camera-operation.json": json.dumps(operation).encode()},
    )
    exported = Path(receipt["path"])
    assert verify_export(exported)["status"] == "VERIFIED_DIAGNOSTIC_EXPORT"
    text = (exported / "attachment-camera-operation.json").read_text(encoding="utf-8")
    assert "CONTROL_READBACK_MISMATCH_REPORTED" in text
    assert artifact.evidence_sha256 in text
    assert '"clear_quarantine_allowed": false' in text
    assert "payload_base64" not in text and '"stdout":' not in text
    assert "incapable://" not in text


def test_new_service_status_has_no_fault_or_io(tmp_path):
    service = module.CommissioningRehearsalService(
        tmp_path, tmp_path / "absent", source_sha256="a" * 64
    )
    assert service.view()["camera_fault_diagnostic"] is None
    assert service.retained_camera_diagnostics() is None
    assert not service.directory.exists()
