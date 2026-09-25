"""Actual public queues/logs/settings/M1/ingest; incapable native owners only.

Metadata provenance and predecessor setup semantic authentication are explicitly
MODELED by the imported fixtures. This is not a complete received-hardware or
full original-history qualification lane. No real camera/serial access occurs.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application.camera_configuration_attempt_export import (
    restore_configuration_attempt_export,
)
from rocell.application.camera_configuration_wizard_contract import (
    CAPTURE_ACTION_ID as CAPTURE,
    EXPORT_ACTION_ID as EXPORT,
)
from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _ticket
from test_camera_original_probe_arrival import (
    joined,
    complete,
    PROBE,
    VALUES as PROBE_VALUES,
)
from test_camera_configuration_originals import install_modeled_configuration_setup
from test_camera_activation_dispatch_handoff import install_owner
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner
from test_commissioning_camera_persistence import WINDOWS

VALUES = dict(
    operator_id="MODELED capture operator",
    arm_actuator_supply_disconnected=True,
    bounded_configuration_capture_consent=True,
)


def act(app, action, values=None):
    ticket = _ticket(app, action, values or {})
    return complete(app, app.execute_action(ticket["ticket_id"])["operation_id"])


def settings_values(service):
    fields = service.configuration_fields()
    values = {f["name"]: f["default"] for f in fields if "default" in f}
    values.update(
        mode_choice_id=fields[0]["options"][0]["value"],
        operator_id="MODELED-settings-operator",
    )
    return values


@pytest.fixture
def configured(joined, tmp_path, monkeypatch):
    c = joined
    install_owner(tmp_path, monkeypatch, purpose="probe")
    result = act(c.app, PROBE, PROBE_VALUES)
    assert result["status"] == "SUCCEEDED", result
    result = act(c.app, "physical_camera_configuration", settings_values(c.service))
    assert result["status"] == "SUCCEEDED", json.dumps(result, indent=2)
    assert c.app._configuration_wizard.view()["settings_reference_retained"]
    install_modeled_configuration_setup(c, tmp_path, monkeypatch)
    c.capture_owners = install_owner(
        tmp_path, monkeypatch, purpose="capture", pixels=True
    )
    return c


def exported(app, operation_id):
    result = act(app, EXPORT, {"attempt_choice_id": operation_id})
    assert result["status"] == "SUCCEEDED", result
    root = Path(result["result"]["steps"][0]["report"]["receipt"]["path"])
    assert root.parent == app.export_directory and verify_export(root)["valid"]
    snapshot = json.loads((root / "report.json").read_bytes())["snapshot"]
    parts = {
        p.name.removeprefix("attachment-"): p.read_bytes()
        for p in root.glob("attachment-*.json")
    }
    return restore_configuration_attempt_export(snapshot, parts)


@WINDOWS
def test_public_logged_settings_capture_then_second_request_preserves_probe_and_export(
    configured,
):
    c, app = configured, configured.app
    original_probe = deepcopy(app._probe_attempt_packet())
    context = app._configuration_wizard.preview_context()
    ticket = _ticket(app, CAPTURE, VALUES)
    assert ticket["input"] == VALUES
    assert context["expected_capture_plan_sha256"] in " ".join(ticket["effects"])
    assert not c.capture_owners
    receipt = app.execute_action(ticket["ticket_id"])
    result = complete(app, receipt["operation_id"])
    assert result["status"] == "SUCCEEDED", json.dumps(result, indent=2)
    assert result["result"]["action_id"] == CAPTURE
    assert len(c.capture_owners) == 1 and c.capture_owners[0].cleaned
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    image_id = app.view()["camera"]["image_id"]
    assert app.image(image_id)[0].startswith(b"\x89PNG")
    first = exported(app, receipt["operation_id"])
    assert first == app._configuration_wizard.packet(receipt["operation_id"])
    assert first["queue"]["claimed"] is True
    assert first["completion"]["completion_log_persisted"] is True
    assert (
        first["admission"]["logged_settings_reference"]["completion_log_persisted"]
        is True
    )
    assert first["admission"]["current_operator_request"] == VALUES
    assert first["dispatch"]["transaction"]["attempt_state"] == "SEALED_KNOWN"
    from rocell.providers.windows.native_camera_protocol import canonical, digest

    original = first["dispatch"]["original_evidence"]
    assert original["schema"] == "rocell.camera_activation_observation_with_checksum.v1"
    assert original["capture_checksum"]["status"] == "CAPTURE_BYTES_HASHED"
    assert original["capture_checksum"]["request_key"] == receipt["operation_id"]
    assert original["capture_checksum_sha256"] == digest(
        canonical(original["capture_checksum"])
    )
    assert (
        first["dispatch"]["original_admission"]["hazard_assessment"]["schema"]
        == "rocell.camera_configuration_limited_hazard_assessment.v2"
    )
    assert app._configuration_wizard.preview_context() == context
    second = act(app, CAPTURE, VALUES)
    assert second["status"] == "SUCCEEDED", second
    assert len(c.capture_owners) == 2
    assert app._probe_attempt_packet() == original_probe
    assert exported(app, receipt["operation_id"]) == first
    assert app.view()["physical_camera"]["connected"] is False
    assert (
        not c.runner.calls
        and not c.runtime.verify(c.service.session_id).active_lease_owners
    )


@WINDOWS
@pytest.mark.parametrize(
    "fault",
    ["intent-log", "completion-log", "late-stop", "publication", "admission-deadline"],
)
def test_failures_withhold_preview_and_keep_selected_export(
    configured, tmp_path, monkeypatch, fault
):
    c, app = configured, configured.app
    original_probe = deepcopy(app._probe_attempt_packet())
    if fault.endswith("log"):
        append = app._append_event
        event = "ACTION_EXECUTED" if fault == "intent-log" else "ACTION_FINISHED"
        monkeypatch.setattr(
            app,
            "_append_event",
            lambda kind, data: (
                False
                if kind == event and data["action_id"] == CAPTURE
                else append(kind, data)
            ),
        )
    elif fault == "late-stop":
        finish = app._finish

        def stopped(op, status, result):
            if app._operations[op]["action_id"] == CAPTURE and app._cancel is not None:
                app._cancel.set()
            return finish(op, status, result)

        monkeypatch.setattr(app, "_finish", stopped)
    elif fault == "admission-deadline":
        c.capture_owners = install_owner(
            tmp_path, monkeypatch, purpose="capture", fault="admission-deadline"
        )
    else:

        def refused(*a, **k):
            raise WizardError(
                "MODELED_PUBLICATION_FAULT", "Injected preview publication failure"
            )

        monkeypatch.setattr(c.service, "cache_published_preview", refused)
    result = act(app, CAPTURE, VALUES)
    assert result["status"] == "FAILED", result
    saved = exported(app, result["operation_id"])
    assert saved["completion"]["status"] == "FAILED"
    assert saved["queue"]["claimed"] is (fault != "intent-log")
    assert len(c.capture_owners) == (0 if fault == "intent-log" else 1)
    assert app.view()["camera"]["image_id"] is None
    assert app._probe_attempt_packet() == original_probe
    assert not c.runner.calls
    if fault == "admission-deadline":
        summary = result["result"]["camera_attempt_failure"]
        assert summary["reported_primary_error"] == "ADMISSION_DEADLINE_EXPIRED"
        assert summary["reported_primary_error"] in result["error"]["message"]
        assert summary["operation"] == "capture"
        assert summary["release_check_passed"] is False
        assert summary["native_accounting_available"] is False
        assert summary["quarantine_latched"] is True
        assert summary["physical_authority"] is summary["automatic_replay"] is False
        assert saved["completion"]["result"]["camera_attempt_failure"] == summary
        assert (
            saved["dispatch"]["original_evidence"]["supervision"]["primary_error"]
            == summary["reported_primary_error"]
        )
        assert c.capture_owners[0].phase == "ready"


@WINDOWS
def test_current_settings_owner_and_ticket_drift_are_rejected_before_queue(
    configured, monkeypatch
):
    c, app = configured, configured.app
    ticket = _ticket(app, CAPTURE, VALUES)
    original = app._native_camera
    app._native_camera = original.staged_copy()
    with pytest.raises(WizardError):
        app.execute_action(ticket["ticket_id"])
    assert not c.capture_owners and not app._configuration_wizard.view()["attempts"]
    app._native_camera = original
    # Each check uses the actual publication comparator, not a replaced guard.
    for fault in ("probe-log", "metadata-log", "settings", "session", "source", "log"):
        ticket = _ticket(app, CAPTURE, VALUES)
        with monkeypatch.context() as patch:
            if fault == "probe-log":
                patch.setitem(
                    app._probe_attempt_completion, "completion_log_persisted", False
                )
            elif fault == "metadata-log":
                op = next(iter(app._probe_metadata_publication["operations"]))
                patch.setitem(app._operations[op], "completion_log_persisted", False)
            elif fault == "settings":
                reference = json.loads(app._configuration_wizard._settings)
                reference["intent"]["settings_epoch"] = "f" * 64
                from rocell.providers.windows.native_camera_protocol import canonical

                patch.setattr(
                    app._configuration_wizard, "_settings", canonical(reference)
                )
            elif fault == "session":
                patch.setattr(app._physical_camera_setup, "session", object())
            elif fault == "source":
                patch.setattr(app, "_source_changed", True)
            else:
                patch.setattr(
                    app,
                    "_log_error",
                    {"code": "MODELED", "message": "Changed log status"},
                )
            with pytest.raises(WizardError):
                app.execute_action(ticket["ticket_id"])
        assert not c.capture_owners and not app._configuration_wizard.view()["attempts"]
    app._configuration_wizard.withdraw_settings()
    with pytest.raises(WizardError):
        _ticket(app, CAPTURE, VALUES)


@WINDOWS
def test_new_settings_intent_withdraws_reference_even_if_intent_log_fails(
    configured, monkeypatch
):
    c, app = configured, configured.app
    append = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda kind, data: (
            False
            if kind == "ACTION_EXECUTED"
            and data["action_id"] == "physical_camera_configuration"
            else append(kind, data)
        ),
    )
    result = act(app, "physical_camera_configuration", settings_values(c.service))
    assert result["status"] == "FAILED"
    assert app._configuration_wizard.view()["settings_reference_retained"] is False
    with pytest.raises(WizardError):
        _ticket(app, CAPTURE, VALUES)
    assert not c.capture_owners and app.view()["camera"]["image_id"] is None


@WINDOWS
@pytest.mark.parametrize("fault", ["source", "stop", "owner", "cleanup"])
def test_current_guard_and_native_cleanup_faults_remain_exportable(
    configured, tmp_path, monkeypatch, fault
):
    c, app = configured, configured.app
    if fault == "cleanup":
        c.capture_owners = install_owner(
            tmp_path,
            monkeypatch,
            purpose="capture",
            pixels=True,
            fault="cleanup-missing-resource",
        )
    else:
        original = c.service.run_original_configuration_capture

        def changed(*a, **kw):
            if fault == "source":
                c.source_state["hash"] = "b" * 64
            elif fault == "stop":
                kw["cancellation"].set()
            else:
                app._native_camera = app._native_camera.staged_copy()
            return original(*a, **kw)

        monkeypatch.setattr(c.service, "run_original_configuration_capture", changed)
    result = act(app, CAPTURE, VALUES)
    assert result["status"] != "SUCCEEDED", json.dumps(result, indent=2)
    saved = exported(app, result["operation_id"])
    assert saved["completion"]["status"] != "SUCCEEDED"
    assert saved["queue"]["claimed"] is True
    assert len(c.capture_owners) == (1 if fault == "cleanup" else 0)
    if fault == "cleanup":
        assert saved["dispatch"]["transaction"]["attempt_state"] == "SEALED_UNCERTAIN"
    assert app.view()["camera"]["image_id"] is None and not c.runner.calls


def test_closed_capture_form_default_off_and_uncalibrated(make_service):
    app, runner, _ = make_service(mode="physical")
    action = ACTION_BY_ID[CAPTURE]
    assert action.timeout_s == 300
    assert validate_action_input(action, VALUES) == VALUES
    assert all(f["default"] is False for f in action.fields if f["type"] == "checkbox")
    for change in (
        {"operator_id": "é" * 33},
        {"bounded_configuration_capture_consent": False},
        {"arm_actuator_supply_disconnected": False},
        {"max_frames": 2},
        {"path": "camera0"},
    ):
        with pytest.raises(WizardError):
            validate_action_input(action, {**VALUES, **change})
    actions = {a["action_id"]: a for a in app.view()["actions"]}
    assert not actions[CAPTURE]["enabled"] and not actions[EXPORT]["enabled"]
    assert not actions["physical_camera_capture"]["enabled"]
    assert not runner.calls
