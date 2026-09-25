"""Pure producer -> browser/terminal presentation; never physical acquisition.

The native-shaped producer fixture uses modeled process/driver observations.
It proves schema integration, not a received camera or a qualified runtime.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from rocell.ui.terminal import _PhysicalCameraDisplay, _TerminalWizard, _camera_fault
from test_arrival_wizard_device_selection_ui import (
    _HARNESS,
    MetadataService,
    browser as metadata_browser,
    selection,
)
from test_arrival_wizard_terminal import Service, action, run


def physical():
    return {
        "schema": "rocell.wizard_physical_camera.v1",
        "status": "NOT_STARTED",
        "source_sha256": "a" * 64,
        "session_id": "session-unit",
        "reviewed_endpoint": None,
        "runtimes": {"probe": None, "capture": None},
        "configuration": {"capabilities": None, "candidate": None, "readback": None},
        "plan": None,
        "last_frame": None,
        "fault": None,
        "publication": {"status": "NOT_PUBLISHED", "operation_id": None},
        "blockers": ["PHYSICAL_RUNTIME_QUALIFICATION_REQUIRED"],
        "physical_authority": False,
        "hardware_qualified": False,
        "connected": False,
        "meaning": "Source-bound physical planning only. No device has been opened.",
    }


def snapshot(projection, *, fault=None):
    view = MetadataService(selection()).view()
    view.update(mode="physical", physical_camera=projection)
    if fault is not None:
        view["commissioning_rehearsal"] = {
            "status": "HELD",
            "stages": [],
            "camera_fault_diagnostic": fault,
        }
    # Generic action controls are server-owned; display cannot enable these.
    view["actions"] = []
    for name in ("physical_camera_probe", "physical_camera_capture"):
        row = action(name)
        row.update(
            section="camera",
            enabled=False,
            blockers=["PHYSICAL_RUNTIME_QUALIFICATION_REQUIRED"],
        )
        view["actions"].append(row)
    return view


def render(projection, *, fault=None, page="camera"):
    view = snapshot(projection, fault=fault)
    result = metadata_browser(selection(), page, snapshot=view)
    assert result["status"] == "Local service connected", result["error"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    service = MetadataService(selection())
    original = service.view

    def status():
        original()  # Preserve fake call accounting, with no provider calls.
        return deepcopy(view)

    service.view = status
    code, lines, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)]
    return result["text"], "\n".join(lines)


@pytest.mark.parametrize("projection", [None, physical()])
def test_initial_view_has_no_activation_or_inferred_connection(projection):
    page, console = render(projection)
    for output in (page, console):
        assert "Physical camera acquisition" in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "Metadata review is not runtime admission" in output
        assert (
            "No physical camera plan" in output
            or "No separately verified physical frame" in output
        )


def test_prepared_plan_is_held_and_runtime_purposes_are_separate():
    data = physical()
    data.update(
        status="HELD",
        plan={
            "plan_sha256": "1" * 64,
            "operation": "probe",
            "stage": "camera_mode_controls",
            "status": "PREPARED_NOT_ADMITTED",
        },
    )
    data["runtimes"]["probe"] = {
        "purpose": "FINITE_NATIVE_CAMERA_PROBE",
        "registration_sha256": "2" * 64,
        "helper_sha256": "3" * 64,
        "build_record_sha256": "4" * 64,
        "status": "DORMANT_REVIEW_REQUIRED",
        "dispatch_enabled": False,
        "driver_qualified": False,
    }
    page, console = render(data)
    for output in (page, console):
        assert "NOT ADMITTED" in output
        assert "PHYSICAL_RUNTIME_QUALIFICATION_REQUIRED" in output
        assert "Purpose-specific runtime not registered" in output
        assert "a" * 64 in output and "1" * 64 in output


@pytest.fixture
def actual_projection(tmp_path):
    from test_physical_camera_configuration import physical_configuration_fixture

    parts = physical_configuration_fixture(tmp_path)
    caps, candidate, readback = parts[2], parts[3], parts[6]
    data = physical()
    data.update(
        status="OBSERVATION_RETAINED",
        configuration={
            "capabilities": caps.view(),
            "candidate": candidate.view(),
            "readback": readback.view(),
        },
    )
    data["reviewed_endpoint"] = {
        "endpoint_sha256": caps.view()["binding"]["endpoint_sha256"],
        "identity_sha256": "b" * 64,
        "metadata_review_binding_sha256": "c" * 64,
        "generic_candidate_sha256": "d" * 64,
    }
    return data


def test_actual_distinct_physical_producers_render_both_frontends(actual_projection):
    data = actual_projection
    assert (
        data["configuration"]["readback"]["status"]
        == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
    )
    assert _PhysicalCameraDisplay.physical(data) == data
    page, console = render(data)
    for output in (page, console):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in output
        assert "NOT APPLIED" in output
        assert "not pixel or power proof" in output
        assert "No separately verified physical frame" in output
        assert data["configuration"]["candidate"]["settings_epoch"] in output
        assert data["configuration"]["readback"]["readback_sha256"] in output
    assert "brightness: requested 4 (manual); observed 4" in page
    assert "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in console


@pytest.mark.parametrize(
    "path,value",
    [
        (("extra",), "RAW_SENTINEL"),
        (("connected",), True),
        (("physical_authority",), 0),
        (("hardware_qualified",), True),
        (("status",), "CONNECTED"),
        (("blockers",), ["raw/device/path"]),
        (("configuration", "capabilities", "schema"), "rocell.camera_capabilities.v1"),
        (("configuration", "capabilities", "controls", 0, "flags"), "2"),
        (("configuration", "capabilities", "controls", 0, "capability_flags"), 4),
        (("configuration", "capabilities", "binding", "source_sha256"), "e" * 64),
        (("configuration", "capabilities", "modes", 0, "mode", "width"), True),
        (("configuration", "candidate", "applied"), True),
        (("configuration", "candidate", "controls", 0, "value"), 3),
        (("configuration", "readback", "frame_content_verified"), True),
        (("configuration", "readback", "native_cleanup_confirmed"), False),
        (("configuration", "readback", "controls", 0, "observed", "value"), 2),
        (("configuration", "readback", "final_power_state"), "DEENERGIZED"),
    ],
)
def test_malformed_or_coerced_physical_projection_is_withheld(
    actual_projection, path, value
):
    data = deepcopy(actual_projection)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert _PhysicalCameraDisplay.physical(data) is None
    page, console = render(data)
    for output in (page, console):
        assert "PHYSICAL_CAMERA_NOT_VERIFIED" in output
        assert "RAW_SENTINEL" not in output
        assert data["configuration"]["candidate"]["settings_epoch"] not in output


def test_unsupported_mode_and_ambiguous_current_flags_are_not_auto_selected(tmp_path):
    from test_physical_camera_configuration import capabilities_fixture

    _, _, caps = capabilities_fixture(tmp_path, probe_fault="unsupported")
    data = physical()
    view = caps.view()
    view["controls"][0][
        "flags"
    ] = 3  # Explicit display mutation, not producer evidence.
    data.update(status="OBSERVATION_RETAINED")
    data["configuration"]["capabilities"] = view
    data["reviewed_endpoint"] = {
        "endpoint_sha256": view["binding"]["endpoint_sha256"],
        "identity_sha256": "b" * 64,
        "metadata_review_binding_sha256": "c" * 64,
        "generic_candidate_sha256": "d" * 64,
    }
    page, console = render(data)
    assert "UNSUPPORTED_PIXEL_FORMAT" in page and "UNSUPPORTED_PIXEL_FORMAT" in console
    assert "AMBIGUOUS" in page and "AMBIGUOUS_NO_MODE_INFERRED" in console
    assert "NOT SELECTED" in page and "SUPPORTED_LAYOUT_ONLY_NOT_SELECTED" in console


def frame(data, *, published=False):
    data["last_frame"] = {
        "image_id": "retained-physical-image" if published else None,
        "attempt_id": data["configuration"]["readback"]["capture_binding"][
            "attempt_id"
        ],
        "frame_index": 0,
        "preview_sha256": "1" * 64,
        "native_frame_sha256": "2" * 64,
        "manifest_sha256": "3" * 64,
        "settings_epoch": data["configuration"]["candidate"]["settings_epoch"],
        "endpoint_sha256": data["reviewed_endpoint"]["endpoint_sha256"],
        "capture_evidence_sha256": data["configuration"]["readback"][
            "capture_evidence_sha256"
        ],
        "provenance": "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2",
        "frame_content_verified": True,
        "live": False,
    }
    data["publication"] = {
        "status": "CURRENT" if published else "HISTORICAL_HELD",
        "operation_id": "capture-operation",
    }
    return data


def test_historical_frame_is_not_live_or_implicitly_refetched(actual_projection):
    data = frame(actual_projection)
    data["status"] = "HELD"
    page, console = render(data)
    for output in (page, console):
        assert "NOT LIVE" in output and "Historical frame references only" in output
        assert "2" * 64 in output and "3" * 64 in output


@pytest.mark.parametrize("change", ["pending", "held", "epoch", "live", "pixels"])
def test_frame_publication_requires_separate_current_verified_binding(
    actual_projection, change
):
    data = frame(actual_projection, published=True)
    if change == "pending":
        data["publication"]["status"] = "PENDING"
    if change == "held":
        data["status"] = "HELD"
    if change == "epoch":
        data["last_frame"]["settings_epoch"] = "9" * 64
    if change == "live":
        data["last_frame"]["live"] = True
    if change == "pixels":
        data["last_frame"]["frame_content_verified"] = False
    assert _PhysicalCameraDisplay.physical(data) is None
    page, console = render(data)
    assert (
        "PHYSICAL_CAMERA_NOT_VERIFIED" in page
        and "PHYSICAL_CAMERA_NOT_VERIFIED" in console
    )


def fault_projection():
    from rocell.application.camera_fault_diagnostics import camera_fault_diagnostic
    from rocell.application.rehearsal_owned_camera_evidence import (
        retain_owned_camera_evidence,
    )
    from test_camera_fault_diagnostics import rejection_inputs

    return camera_fault_diagnostic(retain_owned_camera_evidence(**rejection_inputs()))


def test_actual_fault_producer_is_historical_and_never_invents_observed_values():
    fault = fault_projection()
    assert _camera_fault(fault) == fault
    data = physical()
    data.update(status="HELD", fault=fault)
    page, console = render(data)
    for output in (page, console):
        assert "Retained camera fault explanation" in output
        assert "Historical retained explanation" in output
        assert "does not establish observed control values" in output
        assert fault["evidence_sha256"] in output


def test_actual_fault_cached_rehearsal_sibling_uses_dedicated_card():
    fault = fault_projection()
    page, console = render(None, fault=fault, page="commissioning")
    assert (
        "Retained camera fault explanation" in page
        and "Retained camera fault explanation" in console
    )
    assert (
        "CAMERA_FAULT_NOT_VERIFIED" not in page
        and "CAMERA_FAULT_NOT_VERIFIED" not in console
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("automatic_retry_allowed", True),
        ("reported_code", "RAW_SENTINEL"),
        ("reason_category", "UNKNOWN"),
        ("basis", "NONE"),
        ("physical_authority", 0),
        ("extra", "RAW_SENTINEL"),
    ],
)
def test_malformed_fault_is_not_forwarded_as_raw_data(key, value):
    fault = fault_projection()
    fault[key] = value
    assert _camera_fault(fault) is None
    page, console = render(None, fault=fault, page="commissioning")
    for output in (page, console):
        assert "CAMERA_FAULT_NOT_VERIFIED" in output
        assert "RAW_SENTINEL" not in output


def browser_transport(view, operation=None):
    """DOM/HTTP fixture only. Image bytes are a local memory Blob, not capture."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node runtime unavailable")
    harness = _HARNESS.replace(
        "throw new Error('Unexpected request: '+path);",
        "if(path.startsWith('/api/images/'))return{ok:true,blob:async()=>new Blob(['fixture'],{type:'image/png'})};"
        "if(path.startsWith('/api/operations/'))return{ok:true,json:async()=>input.operation};"
        "throw new Error('Unexpected request: '+path);",
    ).replace(
        "if(input.prepare){",
        "if(input.operation)await nodes.filter(node=>node.textContent==='Load latest full result').at(-1).listeners.click(); if(input.prepare){",
    )
    path = Path(__file__).resolve().parents[3] / "software/src/rocell/ui/static/app.js"
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": path.read_text(encoding="utf-8"),
                "snapshot": view,
                "page": "camera",
                "operation": operation,
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("current", [True, False])
def test_physical_image_is_cached_get_only_with_exact_current_publication(
    actual_projection, current
):
    data = frame(actual_projection, published=True)
    if not current:
        data["publication"]["status"] = "PENDING"
    view = snapshot(data)
    view["camera"] = {
        "image_id": data["last_frame"]["image_id"],
        "image_provenance": "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2",
    }
    result = browser_transport(view)
    assert result["status"] == "Local service connected", result["error"]
    assert all(item["method"] == "GET" for item in result["requests"])
    images = [
        item for item in result["requests"] if item["path"].startswith("/api/images/")
    ]
    assert len(images) == (1 if current else 0)
    assert (
        "LAST CAPTURED \u00b7 NOT LIVE"
        if current
        else "PHYSICAL IMAGE PUBLICATION HELD"
    ) in result["text"]


@pytest.mark.parametrize("malformed", [False, True])
def test_explicit_result_load_and_terminal_poll_render_only_named_fault_sidecar(
    malformed,
):
    fault = fault_projection()
    if malformed:
        fault["reported_code"] = "RAW_SENTINEL"
    operation = {
        "operation_id": "known-operation",
        # Public operation responses retain their action identity. The shared
        # result viewer must reject mismatched responses rather than guess it.
        "action_id": "rehearsal_owned_camera_campaign",
        "status": "FAILED",
        "result": {
            "steps": [
                {
                    "name": "retained-incapable-owned-camera-diagnostics",
                    "report": {
                        "camera_fault_diagnostic": fault,
                        "retained_reference": "original-evidence",
                    },
                }
            ]
        },
    }
    original = deepcopy(operation)
    view = snapshot(None)
    view["operations"] = [
        {
            "operation_id": "known-operation",
            "status": "FAILED",
            "action_id": "rehearsal_owned_camera_campaign",
        }
    ]
    result = browser_transport(view, operation)
    assert result["requests"] == [
        {"path": "/api/view", "method": "GET", "body": None},
        {"path": "/api/operations/known-operation", "method": "GET", "body": None},
    ]
    output = []
    service = Service([])

    def retained(identifier):
        service.calls.append(("operation", identifier))
        return operation

    service.operation = retained
    terminal = _TerminalWizard(
        service, lambda prompt: "back", output.append, lambda seconds: None
    )
    terminal.monitor("known-operation")
    assert service.calls == [("operation", "known-operation")]
    assert operation == original  # Display redaction cannot mutate retained evidence.
    for text in (result["text"], "\n".join(output)):
        assert "original-evidence" in text
        assert "RAW_SENTINEL" not in text
        assert (
            "CAMERA_FAULT_NOT_VERIFIED"
            if malformed
            else "Historical retained explanation"
        ) in text


def test_actual_service_initial_pending_published_intent_and_invalidation_are_device_inert(
    tmp_path, monkeypatch
):
    from rocell.application.physical_camera_acquisition_service import (
        PhysicalCameraAcquisitionService,
    )
    from rocell.application.wizard_native_camera_enrollment import (
        WizardNativeCameraEnrollment,
    )
    from rocell.providers.windows.native_camera_protocol import canonical, digest

    def forbidden(*args, **kwargs):
        pytest.fail("cached physical planning attempted file/process/device I/O")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", forbidden)
        guard.setattr(Path, "stat", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        launch = "wizard-" + "1" * 32
        service = PhysicalCameraAcquisitionService(
            tmp_path, launch_id=launch, source_sha256="a" * 64, mode="physical"
        )
        enrollment = WizardNativeCameraEnrollment("physical", launch, "a" * 64, None)
        initial = service.view()
        plan = service.preview_plan("probe", enrollment)
        assert service.view() == initial and service.retained_intent() is None
        service.record_plan(
            "probe",
            enrollment,
            expected_plan_sha256=digest(canonical(plan)),
            operator_id="operator",
            cancellation=threading.Event(),
        )
        pending = service.view()
        service.publication_completed("retained-operation")
        published = service.view()
        original_intent = service.retained_intent()
        service.invalidate()
        historical = service.view()
        assert service.retained_intent() == original_intent
    assert pending["publication"]["status"] == "PENDING"
    assert published["publication"]["status"] == "CURRENT"
    assert published["status"] == "HELD" and published["last_frame"] is None
    assert historical["publication"]["status"] == "HISTORICAL_HELD"
    for data in (initial, pending, published, historical):
        assert _PhysicalCameraDisplay.physical(data) == data
        page, console = render(data)
        for text in (page, console):
            assert "PHYSICAL_CAMERA_NOT_VERIFIED" not in text
            assert "CURRENT publication describes the retained plan/report" in text
            assert "not current-file inspection or runtime approval" in text
