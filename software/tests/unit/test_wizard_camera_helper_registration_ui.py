"""Helper inspection/review presentation: no file inspection or process launch."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from test_arrival_wizard_device_selection_ui import browser as metadata_browser
from test_arrival_wizard_terminal import Service, action, dispatched, run


def helper_view(status="METADATA_HELPER_REGISTERED", mode="rehearsal"):
    data = {
        "schema": "rocell.wizard_camera_helper_registration.v1",
        "status": status,
        "provenance": {
            "mode": mode,
            "session_id": "helper-session",
            "source_sha256": "a" * 64,
            "scope": "CAMERA_HELPER_METADATA_ONLY",
        },
        "inspection": {
            "catalog_id": "fixed-metadata-helper",
            "display_name": "Fixed development metadata helper",
            "catalog_sha256": "b" * 64,
            "inspection_sha256": "c" * 64,
            "operation_id": "inspect-operation",
            "operator_id": "named-operator",
            "inspection_status": "MATCHED_METADATA_CATALOG",
            "inspection_provenance": (
                "INCAPABLE_FIXTURE"
                if mode == "rehearsal"
                else "WORKSPACE_FILE_INSPECTION"
            ),
            "helper_sha256": "d" * 64,
            "eligible_for_metadata_registration": True,
            "blockers": [],
        },
        "review": {
            "reviewer_id": "named-reviewer",
            "review_operation_id": "review-operation",
            "status": "METADATA_ONLY_REGISTERED",
            "registration_sha256": "e" * 64,
            "distinct_operator_labels": True,
            "physical_authority": False,
        },
        "blockers": [
            "DEVELOPMENT_METADATA_ONLY_NOT_TRUSTED_RELEASE",
            "DRIVER_AND_PROCESS_CONTAINMENT_NOT_QUALIFIED",
        ],
        "allowed_operations": ["inventory", "identity"],
        "probe_allowed": False,
        "capture_allowed": False,
        "connected": False,
        "qualified": False,
        "physical_authority": False,
        "invalidation_reason": None,
    }
    if status in ("NO_INSPECTION", "INVALIDATED"):
        data.update(inspection=None, review=None)
        if status == "INVALIDATED":
            data["invalidation_reason"] = "SOURCE_CHANGED"
    elif status == "INSPECTION_RETAINED":
        data["review"] = None
    elif status == "REVIEW_HELD":
        data["inspection"].update(
            inspection_status="MISSING_FILES",
            helper_sha256=None,
            eligible_for_metadata_registration=False,
            blockers=["HELPER_FILE_MISSING"],
        )
        data["review"].update(status="ACKNOWLEDGED_BUT_HELD", registration_sha256=None)
    return data


def helper_action(name):
    field_name = "operator_id" if name == "camera_helper_inspect" else "reviewer_id"
    result = action(
        name,
        fields=[
            {"name": field_name, "type": "text", "label": field_name, "required": True},
            {
                "name": "metadata_only",
                "type": "checkbox",
                "label": "Metadata only",
                "required": True,
                "default": False,
            },
        ],
    )
    result["section"] = "camera"
    return result


class HelperService(Service):
    def __init__(self, data):
        super().__init__(
            [
                helper_action("camera_helper_inspect"),
                helper_action("camera_helper_review"),
            ]
        )
        self.data = data

    def view(self):
        result = super().view()
        result.update(
            camera={},
            arm={},
            stages=[],
            operations=[],
            camera_helper_registration=deepcopy(self.data),
        )
        return result


def browser(data, page="camera", **options):
    return metadata_browser(None, page, snapshot=HelperService(data).view(), **options)


def render(data):
    result = browser(data)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    service = HelperService(data)
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and service.calls == [("view",), ("view",)]
    assert not service.shutdown_count
    page = (
        result["text"]
        .split("Camera metadata helper inspection & review", 1)[1]
        .split("Native camera endpoint enrollment", 1)[0]
    )
    return page, "\n".join(output)


def assert_holds(page, console):
    assert "CAMERA NOT CONNECTED" in page and "CAMERA NOT QUALIFIED" in page
    assert "NOT_CONNECTED" in console and "NOT_QUALIFIED" in console
    for text in (page, console):
        assert (
            "does not permit probe or capture; separate purpose-specific runtime gates apply"
            in text
        )
        assert (
            "does not qualify a camera unit, driver, process containment or a trusted release"
            in text
        )
        assert "does not establish current full-build provenance" in text
        assert (
            "no discovery, file hashing, helper installation or process launch" in text
        )
        assert (
            "No source activation, probe, capture, power, motion or contact authority"
            in text
        )


@pytest.mark.parametrize(
    "status",
    [
        "NO_INSPECTION",
        "INSPECTION_RETAINED",
        "METADATA_HELPER_REGISTERED",
        "REVIEW_HELD",
        "INVALIDATED",
    ],
)
@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_helper_states_are_readable_and_never_qualify_camera_or_capture(status, mode):
    data = helper_view(status, mode)
    page, console = render(data)
    assert_holds(page, console)
    for text in (page, console):
        assert "Helper registration metadata is inconsistent" not in text
        for code in data["blockers"]:
            assert code in text
        if mode == "rehearsal":
            assert "INCAPABLE FIXTURE: rehearsal inspection is synthetic" in text
        else:
            assert "rehearsal inspection is synthetic" not in page
        if status == "METADATA_HELPER_REGISTERED":
            assert "Exact helper report reviewed for metadata only" in text
            assert "not proof of authenticated independent people" in text
            assert "e" * 64 in text
        elif status == "REVIEW_HELD":
            assert "Helper review remains held" in text
            assert "acknowledgment does not repair or install them" in text
            assert "HELPER_FILE_MISSING" in text
        elif status == "INVALIDATED":
            assert "No prior registration is restored or operation replayed" in text
            assert "named-reviewer" not in text


def test_helper_card_is_camera_only_and_has_no_catalog_path_or_automatic_consent():
    data = helper_view()
    assert (
        "Camera metadata helper inspection & review" not in browser(data, "arm")["text"]
    )
    controls = browser(data)["controls"]
    assert not any(row["checked"] for row in controls)
    assert not any(row["tag"] == "SELECT" for row in controls)
    assert {row["id"] for row in controls} == {
        "field-camera_helper_inspect-operator_id",
        "field-camera_helper_inspect-metadata_only",
        "field-camera_helper_review-reviewer_id",
        "field-camera_helper_review-metadata_only",
    }


@pytest.mark.parametrize("value", [None, False, {}, [], "invalid"])
def test_missing_and_malformed_helper_snapshot_never_infers_registration(value):
    page, console = render(value)
    assert_holds(page, console)
    phrase = (
        "No helper inspection snapshot"
        if value is None
        else "Helper registration metadata is inconsistent"
    )
    assert phrase in page and phrase in console
    assert "Exact helper report reviewed" not in page


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "unknown"),
        (("status",), "READY_FOR_CAPTURE"),
        (("connected",), True),
        (("qualified",), True),
        (("physical_authority",), True),
        (("probe_allowed",), True),
        (("capture_allowed",), True),
        (("allowed_operations",), ["inventory", "capture"]),
        (("allowed_operations",), ["inventory", "identity", "probe"]),
        (("provenance", "scope"), "NATIVE_ACTIVATION"),
        (("provenance", "source_sha256"), "unbound"),
        (("inspection", "inspection_status"), "PASS"),
        (("inspection", "inspection_sha256"), None),
        (("inspection", "catalog_sha256"), "unbound"),
        (("inspection", "display_name"), "x" * 129),
        (("inspection", "display_name"), "\ud800"),
        (("inspection", "operator_id"), "unsafe\x1b[2J"),
        (("inspection", "inspection_provenance"), "WORKSPACE_FILE_INSPECTION"),
        (("inspection", "helper_sha256"), None),
        (("inspection", "eligible_for_metadata_registration"), 1),
        (("inspection", "eligible_for_metadata_registration"), False),
        (("inspection", "blockers"), ["BAD CODE"]),
        (("review", "reviewer_id"), "named-operator"),
        (("review", "review_operation_id"), ""),
        (("review", "registration_sha256"), None),
        (("review", "distinct_operator_labels"), False),
        (("review", "physical_authority"), True),
        (("review", "status"), "TRUSTED_RELEASE"),
    ],
)
def test_inconsistent_or_authority_bearing_helper_projection_is_not_rendered_as_reviewed(
    path, value
):
    data = helper_view()
    selected = data
    for key in path[:-1]:
        selected = selected[key]
    selected[path[-1]] = value
    page, console = render(data)
    assert_holds(page, console)
    assert (
        "Helper registration metadata is inconsistent" in page
        and "Helper registration metadata is inconsistent" in console
    )
    assert "Exact helper report reviewed for metadata only" not in page


@pytest.mark.parametrize(
    "status", ["MISSING_FILES", "HASH_DRIFT", "UNSAFE_OR_UNREADABLE"]
)
def test_failure_inspections_remain_reviewable_holds_not_file_repairs(status):
    data = helper_view("REVIEW_HELD")
    data["inspection"]["inspection_status"] = status
    page, console = render(data)
    for text in (page, console):
        assert "Helper review remains held" in text
        assert "This inspection cannot register the metadata helper" in text
        assert "Helper registration metadata is inconsistent" not in text
        assert "d" * 64 not in text


def test_partial_review_reset_retains_inspection_but_does_not_restore_old_review():
    data = helper_view("INSPECTION_RETAINED")
    data["invalidation_reason"] = "HELPER_REVIEW_REFRESH_STARTED"
    page, console = render(data)
    for text in (page, console):
        assert "HELPER_REVIEW_REFRESH_STARTED" in text
        assert "inspect-operation" in text
        assert "named-reviewer" not in text
        assert "Helper registration metadata is inconsistent" not in text


@pytest.mark.parametrize(
    "variant", ["unknown-path", "33-blockers", "duplicate-blocker", "held-hash"]
)
def test_unknown_fields_and_budgets_are_rejected_without_silent_truncation(variant):
    data = helper_view("REVIEW_HELD")
    if variant == "unknown-path":
        data["inspection"]["helper_path"] = "NEVER_RENDER_RAW_HELPER_PATH"
    elif variant == "33-blockers":
        data["blockers"] = [f"BLOCKER_{index}" for index in range(33)]
    elif variant == "duplicate-blocker":
        data["blockers"] *= 2
    else:
        data["inspection"]["helper_sha256"] = "d" * 64
    page, console = render(data)
    assert (
        "Helper registration metadata is inconsistent" in page
        and "Helper registration metadata is inconsistent" in console
    )
    assert (
        "NEVER_RENDER_RAW_HELPER_PATH" not in page
        and "NEVER_RENDER_RAW_HELPER_PATH" not in console
    )


@pytest.mark.parametrize("action_id", ["camera_helper_inspect", "camera_helper_review"])
def test_helper_browser_actions_require_identity_label_and_explicit_consent(action_id):
    label = "operator_id" if action_id.endswith("inspect") else "reviewer_id"
    values = {label: "explicit-label", "metadata_only": False}
    result = browser(helper_view(), prepare=True, action=action_id, values=values)
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    values["metadata_only"] = True
    result = browser(helper_view(), prepare=True, action=action_id, values=values)
    assert [row["path"] for row in result["requests"]] == ["/api/view", "/api/prepare"]
    assert result["requests"][1]["body"]["input"] == values
    assert result["dialogOpen"]


@pytest.mark.parametrize("confirmation", ["", "no", "yes to all hardware"])
def test_helper_terminal_preview_never_means_execute(confirmation):
    service = HelperService(helper_view())
    code, _, _ = run(
        service, ["camera_helper_review", "reviewer", "yes", confirmation, "quit"]
    )
    assert code == 0 and len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")


def test_helper_terminal_enter_does_not_acknowledge_inspection_consent():
    service = HelperService(helper_view())
    code, _, _ = run(service, ["camera_helper_inspect", "operator", "", "quit"])
    assert (
        code == 0
        and not dispatched(service, "prepare")
        and not dispatched(service, "execute")
    )


@pytest.fixture
def actual_service(tmp_path, monkeypatch):
    from rocell.application import arrival_wizard_service as service_module
    from rocell.application import physical_device_inventory as inventory
    from rocell.arm.serial_transport import SerialTransport
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.vision.usb_opencv import UsbOpenCvCamera
    from test_wizard_device_selection_integration import InventoryRunner

    def forbidden(*args, **kwargs):
        pytest.fail("Helper presentation attempted a native/device operation")

    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(WindowsCameraWorkerClient, "_registered_arguments", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    monkeypatch.setattr(service_module, "source_fingerprint", lambda _: "a" * 64)
    instances = []

    def create(mode="rehearsal", **options):
        runner = InventoryRunner()
        service = service_module.ArrivalWizardService(
            Path(__file__).resolve().parents[3],
            mode=mode,
            runner=runner,
            log_directory=tmp_path / f"logs-{mode}",
            export_directory=tmp_path / f"exports-{mode}",
            **options,
        )
        instances.append(service)
        return service, runner

    yield create
    for service in instances:
        service.shutdown()


@pytest.mark.parametrize("scenario", ["nominal", "missing-helper", "hash-drift"])
def test_actual_inspector_registry_and_arrival_review_render_substantive_results(
    actual_service, scenario
):
    from rocell.application import wizard_camera_helper_inspection as inspection
    from rocell.application.wizard_actions import WizardError
    from test_wizard_device_selection_integration import action as invoke, ticket

    calls = []

    def tracked(*args, **kwargs):
        calls.append(kwargs)
        return inspection.inspect_camera_helper(*args, **kwargs)

    service, runner = actual_service(helper_inspector=tracked)
    assert service.view()["camera_helper_registration"]["status"] == "NO_INSPECTION"
    assert not calls
    inspected = invoke(
        service,
        "camera_helper_inspect",
        operator_id="named-inspection-operator",
        metadata_only=True,
        scenario=scenario,
    )
    assert inspected["status"] == "SUCCEEDED", inspected.get("error")
    retained = service.view()["camera_helper_registration"]
    assert (
        len(calls) == 1
        and retained["inspection"]["inspection_provenance"] == "INCAPABLE_FIXTURE"
    )
    assert retained["review"] is None
    with pytest.raises(WizardError):
        ticket(
            service,
            "camera_helper_review",
            reviewer_id="named-inspection-operator",
            metadata_only=True,
        )
    assert service.view()["camera_helper_registration"]["review"] is None
    reviewed = invoke(
        service,
        "camera_helper_review",
        reviewer_id="distinct-review-label",
        metadata_only=True,
    )
    assert reviewed["status"] == "SUCCEEDED", reviewed.get("error")
    snapshot = service.view()
    state = snapshot["camera_helper_registration"]
    if scenario == "nominal":
        assert state["status"] == "METADATA_HELPER_REGISTERED"
        assert state["inspection"]["inspection_status"] == "MATCHED_METADATA_CATALOG"
        assert state["inspection"]["eligible_for_metadata_registration"] is True
        assert state["review"]["registration_sha256"] is not None
    else:
        assert state["status"] == "REVIEW_HELD"
        assert state["inspection"]["eligible_for_metadata_registration"] is False
        assert state["inspection"]["helper_sha256"] is None
        assert state["review"]["registration_sha256"] is None
        assert state["inspection"]["inspection_status"] == (
            "MISSING_FILES" if scenario == "missing-helper" else "HASH_DRIFT"
        )
    assert state["review"]["distinct_operator_labels"] is True
    assert state["review"]["review_operation_id"] == reviewed["operation_id"]
    assert state["allowed_operations"] == ["inventory", "identity"]
    assert all(
        state[key] is False
        for key in (
            "probe_allowed",
            "capture_allowed",
            "connected",
            "qualified",
            "physical_authority",
        )
    )
    assert all(row["state"] == "PHYSICAL_PENDING" for row in snapshot["stages"])
    result = metadata_browser(None, "camera", snapshot=snapshot)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    page = (
        result["text"]
        .split("Camera metadata helper inspection & review", 1)[1]
        .split("Native camera endpoint enrollment", 1)[0]
    )
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and not runner.calls and len(calls) == 1
    console = "\n".join(output)
    assert_holds(page, console)
    for text in (page, console):
        assert "Helper registration metadata is inconsistent" not in text
        assert state["inspection"]["inspection_sha256"] in text
        assert state["inspection"]["catalog_sha256"] in text
        assert "distinct-review-label" in text
        assert "not proof of authenticated independent people" in text
        for blocker in state["inspection"]["blockers"]:
            assert blocker in text
    controls = [
        row
        for row in result["controls"]
        if row["id"].startswith("field-camera_helper_")
    ]
    assert controls and not any(row["checked"] for row in controls)
    assert all(
        row["value"] == ""
        for row in controls
        if row["id"].endswith(("-operator_id", "-reviewer_id"))
    )


def test_actual_physical_startup_and_views_do_not_inspect_hash_or_register_helpers(
    actual_service,
):
    def forbidden(*args, **kwargs):
        pytest.fail("Startup/view inspected files or constructed a metadata provider")

    service, runner = actual_service(
        "physical", helper_inspector=forbidden, helper_provider_factory=forbidden
    )
    snapshot = service.view()
    assert snapshot["camera_helper_registration"]["status"] == "NO_INSPECTION"
    assert snapshot["native_camera_enrollment"]["status"] == "PROVIDER_UNAVAILABLE"
    result = metadata_browser(None, "camera", snapshot=snapshot)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0 and not runner.calls
    assert "Default physical startup is unregistered" in result["text"]
    assert "Default physical startup is unregistered" in "\n".join(output)
