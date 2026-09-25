"""Public action/preview join with an injected incapable commissioning boundary.

These tests exercise Arrival, its log and action registry; the fake perform call
does not prove M1 durability, process containment, native output or pixel content.
"""

from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from test_arrival_wizard_service import make_service, _complete, _run, _ticket


ACTION = "rehearsal_owned_camera_campaign"
CAMPAIGNS = ["rehearsal_camera_campaign", ACTION]


def worker_result(action_id, status="SUCCEEDED"):
    if status in {"CANCELLED", "TIMED_OUT"}:
        return {
            "schema": "rocell.wizard_diagnostic_completion.v1",
            "action_id": action_id,
            "status": status,
            "message": "Injected completion; no child or device was run.",
            "elapsed_s": 0.0,
            "output_limit_exceeded": False,
            "physical_authority": False,
        }
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": action_id,
        "status": status,
        "steps": [
            {
                "name": action_id,
                "exit_code": 0 if status == "SUCCEEDED" else 1,
                "report": {
                    "status": "INJECTED_BOUNDARY_ONLY",
                    "physical_authority": False,
                },
            }
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }


def prior_preview(service):
    service._images = {"old-image": b"old synthetic image"}
    service._camera.update(
        image_id="old-image",
        image_capture={"campaign_id": "old-campaign"},
        image_provenance="SYNTHETIC_DATASET_DERIVED_PREVIEW_NOT_PHYSICAL",
    )


def install_boundary(service, monkeypatch, *, status="SUCCEEDED", hook=None):
    calls = []
    preview_reads = []
    monkeypatch.setattr(service._commissioning, "blocked_reason", lambda _: None)
    monkeypatch.setattr(
        service._commissioning, "bind", lambda action_id, values: values
    )
    original_view = service._commissioning.view
    capture = {
        "verification": {
            "plan": {
                "binding": {"campaign_id": "new-campaign", "settings_epoch": "b" * 64}
            }
        },
        "dataset": {"manifest_sha256": "c" * 64},
    }
    monkeypatch.setattr(
        service._commissioning,
        "view",
        lambda: {**original_view(), "capture_dataset": deepcopy(capture)},
    )

    def perform(action_id, values, *, cancellation, progress):
        assert service.view()["camera"]["image_id"] is None
        assert service.view()["camera"]["image_capture"] is None
        calls.append((action_id, deepcopy(values)))
        if hook:
            hook(cancellation)
        return worker_result(action_id, status)

    def preview():
        preview_reads.append(True)
        return b"injected-current-synthetic-preview"

    monkeypatch.setattr(service._commissioning, "perform", perform)
    monkeypatch.setattr(service._commissioning, "latest_preview", preview)
    return calls, preview_reads


@pytest.mark.parametrize("count", [1, 2, 3, 4])
@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "identity-mismatch",
        "cleanup-uncertain",
        "child-timeout",
        "malformed-result",
    ],
)
def test_closed_owned_action_accepts_only_its_bounded_semantic_plan(count, fault):
    action = ACTION_BY_ID[ACTION]
    assert action.worker == "commissioning" and action.mode == "rehearsal"
    assert action.view(mode="physical", busy=False)["enabled"] is False
    assert validate_action_input(action, {"frame_count": count, "fault": fault}) == {
        "frame_count": count,
        "fault": fault,
    }
    assert "contained incapable" in action.label
    assert (
        "85 MB" in action.description
        and "synthetic native camera cleanup" in action.description
    )


@pytest.mark.parametrize(
    "values",
    [
        {"frame_count": 0},
        {"frame_count": 5},
        {"frame_count": True},
        {"frame_count": "1"},
        {"frame_count": 1.0},
        {"frame_count": 1.5},
        {"frame_count": float("nan")},
        {"fault": "arbitrary"},
        {"fault": None},
        {"command": "run"},
        {"path": "C:/camera"},
        {"allow_hardware": True},
        {"port": "COM3"},
    ],
)
def test_owned_action_rejects_noninteger_counts_and_unregistered_fields(values):
    with pytest.raises(WizardError):
        validate_action_input(ACTION_BY_ID[ACTION], values)


def test_original_binary_campaign_stays_a_separate_three_scenario_action():
    original = ACTION_BY_ID["rehearsal_camera_campaign"]
    values = [row["value"] for row in original.fields[1]["options"]]
    assert values == ["none", "identity-mismatch", "cleanup-uncertain"]
    with pytest.raises(WizardError):
        validate_action_input(original, {"fault": "child-timeout"})


def test_public_owned_action_is_held_until_due_stage_and_never_physical(
    make_service, monkeypatch
):
    service, runner, _ = make_service()
    assert not next(
        item for item in service.view()["actions"] if item["action_id"] == ACTION
    )["enabled"]
    with pytest.raises(WizardError):
        _ticket(service, ACTION)
    physical, physical_runner, _ = make_service(mode="physical")
    monkeypatch.setattr(physical._commissioning, "blocked_reason", lambda _: None)
    with pytest.raises(WizardError):
        _ticket(physical, ACTION)
    assert not runner.calls and not physical_runner.calls
    assert not service._commissioning.directory.exists()
    assert not physical._commissioning.directory.exists()


def test_prepare_preserves_prior_image_and_does_not_dispatch_or_create_files(
    make_service, monkeypatch, tmp_path
):
    service, runner, _ = make_service()
    calls, preview_reads = install_boundary(service, monkeypatch)
    prior_preview(service)
    prepared = _ticket(service, ACTION, {"frame_count": 4, "fault": "malformed-result"})
    effects = " ".join(prepared["effects"])
    assert "one-use coordinator permit" in effects and "85 MB per frame" in effects
    assert (
        "actual child" in effects and "separately from the synthetic native" in effects
    )
    assert "Failure, Stop, source drift or log loss" in effects
    assert prepared["physical_authority"] is False
    assert prepared["input"] == {"frame_count": 4, "fault": "malformed-result"}
    assert service.view()["camera"]["image_id"] == "old-image"
    assert not calls and not preview_reads and not runner.calls
    assert not (tmp_path / "diagnostics").exists()


@pytest.mark.parametrize("action_id", CAMPAIGNS)
def test_exact_execution_retires_old_image_and_publishes_only_after_completion_log(
    make_service, monkeypatch, action_id
):
    service, runner, _ = make_service()
    calls, preview_reads = install_boundary(service, monkeypatch)
    prior_preview(service)
    append = service._log.append

    def checked_log(kind, details):
        if kind in {"ACTION_EXECUTED", "ACTION_FINISHED"}:
            assert service.view()["camera"]["image_id"] is None
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", checked_log)
    prepared = _ticket(service, action_id)
    receipt = service.execute_action(prepared["ticket_id"])
    completed = _complete(service, receipt["operation_id"])
    assert completed["status"] == "SUCCEEDED" and completed["completion_log_persisted"]
    camera = service.view()["camera"]
    assert camera["image_id"] != "old-image"
    assert (
        camera["image_provenance"] == "SYNTHETIC_DATASET_DERIVED_PREVIEW_NOT_PHYSICAL"
    )
    assert camera["image_capture"] == {
        "meaning": "LAST_SUCCESSFUL_REHEARSAL_CAPTURE_NOT_LIVE",
        "campaign_id": "new-campaign",
        "settings_epoch": "b" * 64,
        "manifest_sha256": "c" * 64,
    }
    assert service.image(camera["image_id"])[0] == b"injected-current-synthetic-preview"
    with pytest.raises(WizardError):
        service.image("old-image")
    assert (
        service.execute_action(prepared["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert len(calls) == 1 and len(preview_reads) == 1 and not runner.calls
    assert all(
        stage["state"] == "PHYSICAL_PENDING" for stage in service.view()["stages"]
    )


@pytest.mark.parametrize("action_id", CAMPAIGNS)
@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_unsuccessful_campaign_never_publishes_or_fetches_preview(
    make_service, monkeypatch, action_id, status
):
    service, _, _ = make_service()
    calls, preview_reads = install_boundary(service, monkeypatch, status=status)
    prior_preview(service)
    completed = _run(service, action_id)
    assert completed["status"] == status
    assert len(calls) == 1 and not preview_reads
    assert service.view()["camera"]["image_id"] is None
    assert service.view()["camera"]["image_capture"] is None
    with pytest.raises(WizardError):
        service.image("old-image")


@pytest.mark.parametrize("action_id", CAMPAIGNS)
@pytest.mark.parametrize("failed_kind", ["ACTION_EXECUTED", "ACTION_FINISHED"])
def test_intent_or_completion_log_loss_never_leaves_an_image_current(
    make_service, monkeypatch, action_id, failed_kind
):
    service, _, _ = make_service()
    calls, _ = install_boundary(service, monkeypatch)
    prior_preview(service)
    append = service._log.append

    def fail_log(kind, details):
        if kind == failed_kind:
            raise OSError("Injected diagnostic log loss")
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", fail_log)
    completed = _run(service, action_id)
    assert completed["status"] == "FAILED"
    assert len(calls) == (1 if failed_kind == "ACTION_FINISHED" else 0)
    assert service.view()["camera"]["image_id"] is None
    assert service.view()["camera"]["image_capture"] is None
    with pytest.raises(WizardError):
        service.image("old-image")
    if failed_kind == "ACTION_FINISHED":
        assert completed["action_outcome_before_log_failure"] == "SUCCEEDED"


@pytest.mark.parametrize("action_id", CAMPAIGNS)
def test_source_drift_after_result_prevents_any_preview_promotion(
    make_service, monkeypatch, action_id
):
    service, _, source = make_service()
    calls, preview_reads = install_boundary(
        service, monkeypatch, hook=lambda _: source.update(hash="f" * 64)
    )
    prior_preview(service)
    completed = _run(service, action_id)
    assert (
        completed["status"] == "FAILED"
        and completed["result"]["code"] == "SOURCE_CHANGED"
    )
    assert len(calls) == 1 and not preview_reads
    assert service.view()["camera"]["image_id"] is None


@pytest.mark.parametrize("action_id", CAMPAIGNS)
def test_late_stop_preserves_known_result_but_never_promotes_or_replays_preview(
    make_service, monkeypatch, action_id
):
    service, _, _ = make_service()
    entered = threading.Event()
    release = threading.Event()

    def hold(cancel):
        entered.set()
        assert release.wait(5)
        assert cancel.is_set()

    calls, preview_reads = install_boundary(service, monkeypatch, hook=hold)
    prior_preview(service)
    prepared = _ticket(service, action_id)
    receipt = service.execute_action(prepared["ticket_id"])
    try:
        assert entered.wait(3)
        assert service.view()["camera"]["image_id"] is None
        stopped = _run(service, "stop_operation")
        assert stopped["status"] == "SUCCEEDED"
    finally:
        release.set()
    completed = _complete(service, receipt["operation_id"])
    assert completed["status"] == "SUCCEEDED"
    assert "cancellation cannot undo evidence" in completed["result"]["message"]
    assert service.view()["camera"]["image_id"] is None
    assert not preview_reads and len(calls) == 1
    assert (
        service.execute_action(prepared["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert len(calls) == 1


def test_owned_public_result_exports_safe_producer_projection_without_raw_or_image_io(
    make_service, monkeypatch, tmp_path
):
    from test_rehearsal_owned_camera_evidence import complete_inputs
    from rocell.application.rehearsal_owned_camera_evidence import (
        retain_owned_camera_evidence,
        verify_owned_camera_evidence,
    )
    from rocell.application.wizard_diagnostic_export import verify_export
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker

    def forbidden(*args, **kwargs):
        raise AssertionError("Export or cached image read attempted a provider call")

    monkeypatch.setattr(OwnedWindowsWorker, "run", forbidden)
    monkeypatch.setattr(WindowsCameraWorkerClient, "capture", forbidden)
    # This actual producer/verifier receives typed metadata fixtures. Its
    # successful metadata join does not mean this test ran or contained a child.
    inputs = complete_inputs(2)
    artifact = retain_owned_camera_evidence(**inputs)
    safe = verify_owned_camera_evidence(artifact.payload, inputs["binding"]).view()
    assert safe["status"] == "RETAINED_COMPLETE_REHEARSAL"
    assert len(json.dumps(safe).encode("utf-8")) < 16 * 1024
    private = artifact.to_dict()
    assert private["stdout"]["data"]

    service, runner, _ = make_service()
    _, preview_reads = install_boundary(service, monkeypatch)
    original_view = service._commissioning.view
    monkeypatch.setattr(
        service._commissioning,
        "view",
        lambda: {**original_view(), "camera_process": deepcopy(safe)},
    )
    performed = []

    def delegate(action_id, values, *, cancellation, progress):
        performed.append(action_id)
        result = worker_result(action_id)
        # Same public step separation as the service: cached view plus bounded
        # diagnostics/retrieval reference. Private evidence is deliberately not
        # passed to Arrival; the M1-owned producer integration is tested elsewhere.
        result["steps"] = [
            {
                "name": "durable-commissioning-rehearsal",
                "exit_code": 0,
                "report": {
                    "camera_process": deepcopy(safe),
                    "physical_authority": False,
                },
            },
            {
                "name": "retained-incapable-owned-camera-diagnostics",
                "exit_code": 0,
                "report": {
                    "camera_process": deepcopy(safe),
                    "retained_campaign_sha256": artifact.evidence_sha256,
                    "attempt_result": {
                        "attempt_id": safe["binding"]["attempt_id"],
                        "status": "SEALED_KNOWN",
                    },
                    "raw_evidence_location": "ORIGINAL_M1_CAMPAIGN_RECORD_NOT_PUBLIC_STATUS",
                    "physical_authority": False,
                },
            },
        ]
        return result

    monkeypatch.setattr(service._commissioning, "perform", delegate)
    completed = _run(service, ACTION, {"frame_count": 2, "fault": "none"})
    assert completed["status"] == "SUCCEEDED", completed
    assert performed == [ACTION] and len(preview_reads) == 1 and not runner.calls
    image_id = service.view()["camera"]["image_id"]
    assert image_id is not None
    # Refresh, cached image reads and export must not re-request even a fixture
    # preview or return to a commissioning/provider execution seam.
    monkeypatch.setattr(service._commissioning, "latest_preview", forbidden)
    monkeypatch.setattr(service._commissioning, "perform", forbidden)
    assert service.image(image_id) == (
        b"injected-current-synthetic-preview",
        "image/png",
    )
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    assert folder.parent == tmp_path / "exports"
    assert verify_export(folder)["valid"]
    attachments = list(folder.glob("attachment-result-*.json"))
    assert len(attachments) == 1
    retained = json.loads(attachments[0].read_text(encoding="utf-8"))
    assert retained == completed["result"]
    diagnostics = retained["steps"][1]["report"]
    assert diagnostics["camera_process"] == safe
    assert diagnostics["retained_campaign_sha256"] == artifact.evidence_sha256
    assert attachments[0].stat().st_size < 32 * 1024
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert report["snapshot"]["commissioning_rehearsal"]["camera_process"] == safe
    assert report["snapshot"]["result_export_policy"]["included_full_results"] == 1
    assert all("result" not in row for row in report["snapshot"]["operations"])

    public_text = attachments[0].read_text(encoding="utf-8") + json.dumps(report)
    assert private["stdout"]["data"] not in public_text
    assert "incapable-owned-camera-evidence-fixture" not in public_text
    assert "injected-current-synthetic-preview" not in public_text

    def assert_no_private_payload(value):
        if type(value) is dict:
            assert not {
                "activation_request",
                "process_result",
                "stdout",
                "stderr",
                "native_receipt",
                "capture_envelope",
                "source_contract",
            }.intersection(value)
            for child in value.values():
                assert_no_private_payload(child)
        elif type(value) is list:
            for child in value:
                assert_no_private_payload(child)

    assert_no_private_payload(retained)
    assert_no_private_payload(report)
    assert service.image(image_id)[0] == b"injected-current-synthetic-preview"
    assert performed == [ACTION] and len(preview_reads) == 1 and not runner.calls
