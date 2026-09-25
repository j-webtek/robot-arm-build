"""Fast source-fixture coverage, with incapable observations and fresh pixels.

These are bounded workflow/fixture checks, not genuine-original admission or
full-history acceptance. Production source validation is never disabled; only
the explicit partial-workspace source observation is modeled by the same helper
used by the long fixture. No device or subprocess can run.
"""

import pytest
from copy import deepcopy

from rocell.application import physical_camera_capture_workflow as workflow
from rocell.application import wizard_diagnostic_coordinator as source
from test_arrival_camera_full_history_ntfs import model_isolated_camera_source, SOURCE
from test_camera_activation_application_handoff import (
    accept,
    no_device_calls,
    workflow_fixture,
    write_pixels,
)
from test_native_camera_activation_supervisor import no_physical_owner
import test_arrival_camera_full_history_ntfs as full_history


def test_full_history_source_roster_covers_ingestion_without_patching_shared_checker(
    tmp_path, monkeypatch
):
    actual = source.source_fingerprint
    # Remove the other workflow fixture's model so it cannot mask this omission.
    monkeypatch.setattr(workflow, "source_fingerprint", actual)
    model_isolated_camera_source(monkeypatch)
    assert workflow.source_fingerprint(tmp_path) == SOURCE
    assert source.source_fingerprint is actual


@pytest.mark.parametrize("changed_source", [False, True])
def test_capture_ingestion_keeps_real_source_comparison_and_rejects_changes(
    tmp_path, monkeypatch, changed_source
):
    case = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(case)
    monkeypatch.setattr(workflow, "source_fingerprint", source.source_fingerprint)
    model_isolated_camera_source(monkeypatch)
    if changed_source:
        monkeypatch.setattr(workflow, "source_fingerprint", lambda _: "f" * 64)
        with pytest.raises(
            workflow.PhysicalCameraCaptureWorkflowError,
            match="WORKSPACE_SOURCE_CHANGED",
        ):
            accept(case, configuration_verification=True)
        assert case.workflow.view()["physical_authority"] is False
    else:
        result = accept(case, configuration_verification=True)
        assert result is not None and result.verification.content_verified
        view = case.workflow.view()
        assert view["status"] == "CONTENT_VERIFIED"
        assert view["physical_authority"] is view["hardware_qualified"] is False


@pytest.mark.parametrize("condition", ["unchanged", "changed", "unreadable"])
def test_terminal_checkout_audit_cannot_promote_drift_or_unreadable_source(
    tmp_path, monkeypatch, condition
):
    actual_shared_checker = source.source_fingerprint

    def observed(workspace):
        assert workspace == tmp_path
        if condition == "unreadable":
            raise OSError("MODELED concurrent source read failure")
        return SOURCE if condition == "unchanged" else "f" * 64

    # Only the test module's real-checkout observation is injected here; neither
    # production checks nor the isolated fixture's source roster are changed.
    monkeypatch.setattr(full_history, "source_fingerprint", observed)
    audit = full_history.observe_executing_source(tmp_path, SOURCE)
    assert source.source_fingerprint is actual_shared_checker
    assert audit["expected"] == SOURCE
    if condition == "unchanged":
        full_history.require_unchanged_execution_source(audit)
        assert audit["observed"] == SOURCE and audit["error_type"] is None
    else:
        with pytest.raises(AssertionError, match="Fixed-source acceptance"):
            full_history.require_unchanged_execution_source(audit)
        if condition == "unreadable":
            assert audit["status"] == "SOURCE_AUDIT_ERROR"
            assert audit["observed"] is None and audit["error_type"] == "OSError"
        else:
            assert audit["status"] == "SOURCE_CHANGED"
            assert audit["observed"] == "f" * 64 and audit["error_type"] is None


def test_absent_terminal_checkout_audit_is_not_acceptance():
    with pytest.raises(AssertionError, match="Fixed-source acceptance"):
        full_history.require_unchanged_execution_source(None)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "authority",
        "camera-status",
        "arm-status",
        "image",
        "connected",
        "settings",
        "export",
        "attempts",
    ],
)
def test_restart_assertions_reject_live_or_restored_capture_state(fault):
    # Pure assertion-helper coverage; the slow test supplies the actual new app.
    view = dict(
        physical_authority=False,
        camera=dict(status="NOT_CONNECTED", image_id=None),
        arm=dict(status="NOT_CONNECTED"),
        physical_camera=dict(connected=False),
        camera_configuration_attempt=dict(
            settings_reference_retained=False,
            export_available=False,
            attempts=[],
        ),
    )
    before = deepcopy(view)
    if fault == "authority":
        view["physical_authority"] = True
    elif fault in {"camera-status", "arm-status"}:
        view[fault.split("-")[0]]["status"] = "CONNECTED"
    elif fault == "image":
        view["camera"]["image_id"] = "MODELED old preview"
    elif fault == "connected":
        view["physical_camera"]["connected"] = True
    elif fault:
        key = {
            "settings": "settings_reference_retained",
            "export": "export_available",
            "attempts": "attempts",
        }[fault]
        view["camera_configuration_attempt"][key] = (
            ["MODELED old attempt"] if fault == "attempts" else True
        )
    if fault is None:
        full_history.require_disconnected_camera_restart(view)
        assert view == before
    else:
        with pytest.raises(AssertionError):
            full_history.require_disconnected_camera_restart(view)
