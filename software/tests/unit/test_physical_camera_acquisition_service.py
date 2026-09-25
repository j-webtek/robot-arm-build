"""Real planning/service/export joins; physical-shaped fixtures are not hardware.

The metadata provider below is incapable. No camera helper, OS inventory,
serial endpoint or M1 campaign is executed by these tests.
"""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import threading

import pytest

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_camera_acquisition_service import (
    BASE_HOLDS,
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_selection import selection_from_enrollment
from rocell.application.physical_native_camera_campaign import (
    PhysicalNativeCameraCampaign,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_native_camera_metadata import (
    RehearsalNativeCameraMetadataProvider,
)
from rocell.providers.windows.camera_worker_client import CameraCandidate
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _ticket, _run, _complete
from test_wizard_native_camera_enrollment import generic_review


LAUNCH = "wizard-" + "1" * 32
SOURCE = "a" * 64


def reviewed_enrollment(launch=LAUNCH, *, unicode=False):
    """Inject physical-shaped metadata into the actual pure enrollment codec."""
    provider = RehearsalNativeCameraMetadataProvider("nominal")
    inventory = provider.inventory()
    candidate = CameraCandidate(**inventory["receipt"]["devices"][0])
    identity = provider.identity(candidate)
    descriptor = {"provenance": "WINDOWS_NATIVE_METADATA", "helper_sha256": "b" * 64}
    for packet in (inventory, identity):
        packet.update(descriptor)
    if unicode:
        endpoint = candidate.symbolic_link + "/caméra-測試"
        inventory["receipt"]["devices"][0]["symbolic_link"] = endpoint
        identity["receipt"]["requested_endpoint"] = endpoint
        identity["receipt"]["mapping"]["interface_path"]["value"] = endpoint
    enrollment = WizardNativeCameraEnrollment("physical", launch, SOURCE, descriptor)
    enrollment.ingest_inventory(
        inventory,
        operation_id="injected-physical-shaped-inventory",
        generic_review=generic_review(mode="physical", source=SOURCE, session=launch),
    )
    choice = enrollment.choices()[0]["value"]
    enrollment.retain_identity(choice, identity, operation_id="injected-identity")
    enrollment.review(choice, "réviseur" if unicode else "reviewer")
    return enrollment


def planning_service(tmp_path, mode="physical"):
    return PhysicalCameraAcquisitionService(
        tmp_path, launch_id=LAUNCH, source_sha256=SOURCE, mode=mode
    )


def record(service, enrollment, operation="probe", **changes):
    plan = service.preview_plan(operation, enrollment)
    values = {
        "expected_plan_sha256": digest(canonical(plan)),
        "operator_id": "test-operator",
        "cancellation": threading.Event(),
        **changes,
    }
    return service.record_plan(operation, enrollment, **values)


@pytest.mark.parametrize("unicode", [False, True])
def test_reviewed_selection_composes_actual_native_probe_without_io(
    tmp_path, monkeypatch, unicode
):
    enrollment = reviewed_enrollment(unicode=unicode)
    selected = selection_from_enrollment(
        enrollment, source_sha256=SOURCE, launch_session_id=LAUNCH
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Planning attempted a file, process or device operation")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", forbidden)
        guard.setattr(Path, "stat", forbidden)
        guard.setattr(Path, "mkdir", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(
            "rocell.providers.windows.owned_native_camera_runner.OwnedNativeCameraRunner.run",
            forbidden,
        )
        service = planning_service(tmp_path)
        initial = service.view()
        plan = service.preview_plan("probe", enrollment)
        assert service.view() == initial and service.retained_intent() is None
        assert plan["selected_identity_sha256"] == selected.sha256
        assert plan["reviewed_endpoint"] == selected.safe_summary()
        assert plan["blockers"] == list(BASE_HOLDS)
        assert plan["admitted"] is False
        native = PhysicalNativeCameraCampaign.from_plan(plan["native_campaign_plan"])
        registration = native.registration()
        assert registration.action_id == "physical-native-camera-probe"
        assert plan["native_campaign_plan_sha256"] == digest(canonical(native.plan()))
        assert native.plan()["selection"] == selected.identity_document
        assert native.plan()["cell_id"] == plan["camera_cell_id"]
        assert native.plan()["session_id"] == plan["camera_session_id"]
        assert plan["camera_session_id"] != LAUNCH
        assert registration.budget.timeout_ms == 20000
        assert native.evidence is None
        result = record(service, enrollment)
        assert result["steps"][0]["report"]["intent"] == plan
        assert service.view()["publication"]["status"] == "PENDING"
        service.publication_completed("retained-test-operation")
        assert service.view()["publication"]["status"] == "CURRENT"
        assert service.view()["status"] == "HELD"
        assert service.view()["connected"] is False
        assert service.view()["last_frame"] is None
    assert not service.directory.exists()


@pytest.mark.parametrize("operation", ["probe", "capture"])
def test_unreviewed_plan_names_missing_evidence_without_creating_a_campaign(
    tmp_path, operation
):
    service = planning_service(tmp_path)
    enrollment = WizardNativeCameraEnrollment("physical", LAUNCH, SOURCE, None)
    plan = service.preview_plan(operation, enrollment)
    assert plan["native_campaign_plan"] is None
    assert plan["native_campaign_plan_sha256"] is None
    assert "REVIEWED_PHYSICAL_ENDPOINT_REQUIRED" in plan["blockers"]
    assert plan["required_owned_lifetime_ms"] == (
        12000 if operation == "probe" else 17000
    )
    if operation == "capture":
        assert plan["stage"] == "camera_frame_freshness"
        assert "RETAINED_PHYSICAL_PROBE_REQUIRED" in plan["blockers"]
        assert "REVIEWED_PHYSICAL_SETTINGS_REQUIRED" in plan["blockers"]
    assert not service.directory.exists()


def test_capture_never_guesses_mode_or_controls_from_reviewed_metadata(tmp_path):
    plan = planning_service(tmp_path).preview_plan("capture", reviewed_enrollment())
    assert plan["reviewed_endpoint"] is not None
    assert plan["native_campaign_plan"] is None
    assert "RETAINED_PHYSICAL_PROBE_REQUIRED" in plan["blockers"]
    assert "REVIEWED_PHYSICAL_SETTINGS_REQUIRED" in plan["blockers"]


@pytest.mark.parametrize("operation", ["auto", "connect", False, None])
def test_unknown_operation_cannot_reach_native_preparation(tmp_path, operation):
    with pytest.raises(WizardError):
        planning_service(tmp_path).preview_plan(operation, reviewed_enrollment())


def test_rehearsal_or_foreign_launch_is_not_a_physical_selection(tmp_path):
    with pytest.raises(WizardError):
        planning_service(tmp_path, mode="rehearsal").preview_plan(
            "probe", reviewed_enrollment()
        )
    with pytest.raises(WizardError):
        planning_service(tmp_path).preview_plan(
            "probe", reviewed_enrollment("another-launch")
        )


@pytest.mark.parametrize("cause", ["metadata", "hash", "stop"])
def test_record_revalidates_original_context_and_publishes_nothing_on_change(
    tmp_path, cause
):
    service = planning_service(tmp_path)
    enrollment = reviewed_enrollment()
    plan = service.preview_plan("probe", enrollment)
    expected = digest(canonical(plan))
    cancellation = threading.Event()
    if cause == "metadata":
        enrollment.invalidate_review("CHANGED_AFTER_PREPARE")
    elif cause == "hash":
        expected = "0" * 64
    else:
        cancellation.set()
    with pytest.raises(WizardError, match="context changed or stopped"):
        service.record_plan(
            "probe",
            enrollment,
            expected_plan_sha256=expected,
            operator_id="operator",
            cancellation=cancellation,
        )
    assert service.retained_intent() is None
    assert service.view()["plan"] is None


def test_detached_cached_views_and_invalidation_preserve_original_intent(tmp_path):
    service = planning_service(tmp_path)
    record(service, reviewed_enrollment())
    original = service.retained_intent()
    mutable = service.retained_intent()
    mutable["blockers"].clear()
    projected = service.view()
    projected["runtimes"]["probe"]["dispatch_enabled"] = True
    service.invalidate()
    assert service.retained_intent() == original
    assert service.view()["plan"] is None
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.view()["runtimes"]["probe"]["dispatch_enabled"] is False
    with pytest.raises(WizardError):
        service.publication_completed("late-operation")


@pytest.mark.parametrize("operation", ["probe", "capture"])
def test_public_plan_once_full_export_and_all_physical_stages_pending(
    make_service, operation
):
    service, runner, _ = make_service(mode="physical")
    initial = service.view()
    ticket = _ticket(service, "physical_camera_plan", {"operation": operation})
    assert service.view()["physical_camera"] == initial["physical_camera"]
    assert "planning_context_sha256" in ticket["input"]
    receipt = service.execute_action(ticket["ticket_id"])
    outcome = _complete(service, receipt["operation_id"])
    assert outcome["status"] == "SUCCEEDED", outcome
    assert (
        service.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert not runner.calls
    view = service.view()
    assert view["physical_camera"]["status"] == "HELD"
    assert view["physical_camera"]["publication"]["status"] == "CURRENT"
    assert view["physical_camera"]["last_frame"] is None
    assert view["arm"]["status"] == view["camera"]["status"] == "NOT_CONNECTED"
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in view["stages"])
    assert not service._physical_camera.directory.exists()
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    assert folder.parent == service.export_directory
    assert verify_export(folder)["valid"] is True
    attachments = list(folder.glob("attachment-result-*.json"))
    assert len(attachments) == 1
    retained = json.loads(attachments[0].read_text())
    assert retained == outcome["result"]
    report = retained["steps"][0]["report"]
    assert digest(canonical(report["intent"])) == report["intent_sha256"]
    assert report["intent"]["admitted"] is False


def test_public_reviewed_endpoint_uses_actual_native_campaign_plan(make_service):
    service, runner, _ = make_service(mode="physical")
    # Explicit physical-shaped injection only; no actual metadata lookup.
    service._native_camera = reviewed_enrollment(service.session_id, unicode=True)
    outcome = _run(service, "physical_camera_plan")
    assert outcome["status"] == "SUCCEEDED", outcome
    plan = outcome["result"]["steps"][0]["report"]["intent"]
    assert plan["native_campaign_plan"] is not None
    assert (
        plan["selected_identity_sha256"]
        == service.view()["physical_camera"]["reviewed_endpoint"]["identity_sha256"]
    )
    assert not runner.calls


@pytest.mark.parametrize(
    "action",
    [
        "physical_camera_probe",
        "physical_camera_capture",
        "physical_camera_configuration",
        "camera_connect",
    ],
)
def test_device_actions_remain_held_even_after_planning(make_service, action):
    service, runner, _ = make_service(mode="physical")
    assert _run(service, "physical_camera_plan")["status"] == "SUCCEEDED"
    with pytest.raises(WizardError):
        _ticket(service, action)
    assert not runner.calls


def test_public_caller_cannot_supply_internal_context_or_arbitrary_output(make_service):
    service, runner, _ = make_service(mode="physical")
    for values in (
        {"planning_context_sha256": "a" * 64},
        {"output_directory": "C:\\other"},
        {"selected_identity_sha256": "a" * 64},
    ):
        with pytest.raises(WizardError, match="unsupported field"):
            _ticket(service, "physical_camera_plan", values)
    rehearsal, _, _ = make_service()
    with pytest.raises(WizardError):
        _ticket(rehearsal, "physical_camera_plan")
    assert not runner.calls


@pytest.mark.parametrize("cause", ["stop", "source"])
def test_late_stop_or_source_change_withholds_current_plan_but_retains_intent(
    make_service, monkeypatch, cause
):
    service, runner, source = make_service(mode="physical")
    original = service._physical_camera.record_plan

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if cause == "stop":
            kwargs["cancellation"].set()
        else:
            source["hash"] = "f" * 64
        return result

    monkeypatch.setattr(service._physical_camera, "record_plan", late)
    outcome = _run(service, "physical_camera_plan")
    assert outcome["status"] == ("CANCELLED" if cause == "stop" else "FAILED"), outcome
    assert service.view()["physical_camera"]["plan"] is None
    assert (
        service.view()["physical_camera"]["publication"]["status"] == "HISTORICAL_HELD"
    )
    assert service._physical_camera.retained_intent() is not None
    if cause == "source":
        assert (
            outcome["result"]["retention_meaning"]
            == "RETURNED_CAMERA_INTENT_RETAINED_PUBLICATION_REJECTED"
        )
        assert (
            outcome["result"]["retained_camera_intent"]
            == service._physical_camera.retained_intent()
        )
    assert not runner.calls


@pytest.mark.parametrize("event", ["ACTION_EXECUTED", "ACTION_FINISHED"])
def test_log_failure_never_publishes_a_current_plan(make_service, monkeypatch, event):
    service, runner, _ = make_service(mode="physical")
    original = service._append_event

    def fail(name, data):
        if name == event:
            return False
        return original(name, data)

    monkeypatch.setattr(service, "_append_event", fail)
    outcome = _run(service, "physical_camera_plan")
    assert outcome["status"] == "FAILED", outcome
    assert service.view()["physical_camera"]["plan"] is None
    assert (
        service.view()["physical_camera"]["publication"]["status"] == "HISTORICAL_HELD"
    )
    assert (service._physical_camera.retained_intent() is None) == (
        event == "ACTION_EXECUTED"
    )
    assert not runner.calls


def test_default_export_folder_matches_user_selection():
    workspace = Path(__file__).resolve().parents[3]
    service = ArrivalWizardService(workspace, mode="physical")
    try:
        assert service.export_directory == workspace / "software/runs/wizard-exports"
        assert service.view()["physical_camera"]["connected"] is False
    finally:
        service.shutdown()


def test_redacted_intent_is_retained_as_failed_diagnostic_not_current_exact_plan(
    make_service, tmp_path
):
    service, runner, _ = make_service(mode="physical")
    # The reserved path is not created. Its token-shaped leaf exercises the
    # real diagnostic sanitizer with a benign sentinel, not an actual secret.
    service._physical_camera = PhysicalCameraAcquisitionService(
        tmp_path / "token=example-fixture",
        launch_id=service.session_id,
        source_sha256=SOURCE,
        mode="physical",
    )
    outcome = _run(service, "physical_camera_plan")
    assert outcome["status"] == "FAILED", outcome
    retained = outcome["result"]
    assert retained["code"] == "BOUND_CAMERA_INTENT_REDACTED"
    assert "example-fixture" not in json.dumps(retained)
    assert "[REDACTED]" in json.dumps(retained)
    assert len(retained["original_result_sha256"]) == 64
    report = retained["steps"][0]["report"]
    assert digest(canonical(report["intent"])) != report["intent_sha256"]
    assert (
        digest(canonical(service._physical_camera.retained_intent()))
        == report["intent_sha256"]
    )
    assert service.view()["physical_camera"]["plan"] is None
    assert (
        service.view()["physical_camera"]["publication"]["status"] == "HISTORICAL_HELD"
    )
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"] is True
    attachment = next(folder.glob("attachment-result-*.json"))
    assert json.loads(attachment.read_bytes()) == retained
    assert not runner.calls
