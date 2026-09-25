"""Queue/export/history tests with an explicitly MODELED context comparator.

There is no original admission, store, camera owner or capture in this lane.
Only actual wizard logs, operation retention and guarded export are exercised.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application.camera_configuration_wizard_contract import (
    CAPTURE_ACTION_ID as CAPTURE,
    EXPORT_ACTION_ID as EXPORT,
)
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical
from test_arrival_wizard_service import make_service, _ticket, _run
from test_camera_configuration_wizard_arrival import VALUES, exported
from test_commissioning_camera_persistence import forbid_device_and_process_calls


@pytest.fixture
def queued_model(make_service, monkeypatch):
    app, runner, source = make_service(mode="physical")
    controller = app._configuration_wizard
    context = dict(
        original_setup={"MODELED": "no actual original admission"},
        intent={
            "capture_budget": dict(
                duration_ms=5000, max_frames=1, max_frame_bytes=16, max_total_bytes=16
            )
        },
        settings_publication_sha256="1" * 64,
        expected_capture_plan_sha256="2" * 64,
    )
    controller._settings = canonical({"MODELED": "not a logged settings reference"})
    monkeypatch.setattr(controller, "_current_context", lambda **k: deepcopy(context))
    retired = []
    monkeypatch.setattr(
        app._physical_camera,
        "withdraw_capture_preview",
        lambda x: retired.append(deepcopy(x)),
    )
    return app, runner, source, controller, context, retired


def enqueue(state, suffix):
    app, _, _, controller, context, _ = state
    key = "operation-" + f"{suffix:032x}"
    controller.queue(key, context, VALUES)
    return key


def test_bounded_attempt_history_is_never_evicted_or_replayed(queued_model):
    app, runner, _, controller, context, retired = queued_model
    first = enqueue(queued_model, 1)
    packet = controller.packet(first)
    with pytest.raises(WizardError):
        controller.queue(first, context, VALUES)
    for index in range(2, 9):
        enqueue(queued_model, index)
    with pytest.raises(WizardError, match="bounded capture history"):
        enqueue(queued_model, 9)
    assert len(retired) == 8 and len(controller.view()["attempts"]) == 8
    assert controller.packet(first) == packet and not runner.calls
    assert exported(app, first) == packet


@pytest.mark.parametrize("hold", ["source", "log", "operation-budget"])
def test_selected_attempt_exports_under_holds_and_outlives_rotating_notes(
    queued_model, hold
):
    app, runner, _, controller, _, _ = queued_model
    first = enqueue(queued_model, 1)
    controller.record_completion(
        dict(
            operation_id=first,
            action_id=CAPTURE,
            status="FAILED",
            completion_log_persisted=False,
            physical_authority=False,
        )
    )
    original = controller.packet(first)
    for index in range(36):
        result = _run(app, "record_note", {"note": f"MODELED investigation {index}"})
        assert result["status"] == "SUCCEEDED"
    if hold == "source":
        app._source_changed = True
    elif hold == "log":
        app._log_error = {
            "code": "MODELED_LOG_HOLD",
            "message": "Inspect the log folder",
        }
    else:
        app._primary_operations = 32
    assert exported(app, first) == original
    assert not runner.calls


def test_export_ticket_change_refuses_without_folder_or_worker(queued_model):
    app, runner, _, controller, _, _ = queued_model
    first = enqueue(queued_model, 1)
    ticket = _ticket(app, EXPORT, {"attempt_choice_id": first})
    controller._attempts[first]["queue"]["claimed"] = True
    receipt = app.execute_action(ticket["ticket_id"])
    from test_camera_original_probe_arrival import complete

    result = complete(app, receipt["operation_id"])
    assert result["status"] == "FAILED"
    assert result["result"]["code"] == "CAMERA_CONFIGURATION_ATTEMPT_EXPORT_CHANGED"
    assert not runner.calls and not app.export_directory.exists()


def test_general_export_keeps_small_settings_pointer_and_no_full_attempt_buffers(
    queued_model, monkeypatch
):
    app, _, _, controller, _, _ = queued_model
    enqueue(queued_model, 1)
    app._physical_camera._original_probe_attempted = True
    app._physical_camera._original_probe_diagnostics = dict(status="FAILED_HELD")
    monkeypatch.setattr(
        app._physical_camera,
        "retained_capture_diagnostics",
        lambda: dict(original_probe={}, dispatch={"raw": "NEVER_IN_GENERAL" * 4000}),
    )
    result = _run(app, "export_logs")
    assert result["status"] == "SUCCEEDED", result
    root = Path(result["result"]["receipt"]["path"])
    payload = json.loads((root / "attachment-native-camera-data.json").read_bytes())
    assert payload["configuration_attempt"] == controller.view()
    assert payload["configuration_export_action"] == EXPORT
    assert "NEVER_IN_GENERAL" not in json.dumps(payload)


def test_restart_has_no_settings_receipt_or_attempts(make_service, queued_model):
    original, _, _, controller, _, _ = queued_model
    enqueue(queued_model, 1)
    fresh, runner, _ = make_service(mode="physical")
    assert original.session_id != fresh.session_id
    card = fresh._configuration_wizard.view()
    assert card["settings_reference_retained"] is card["export_available"] is False
    assert card["attempts"] == [] and not runner.calls


def test_queue_preview_retirement_failure_finishes_and_retains_request(
    queued_model, monkeypatch
):
    app, runner, _, controller, _, _ = queued_model

    def refuse(*a):
        raise WizardError(
            "MODELED_QUEUE_RETIREMENT_FAILED",
            "Preview retirement failed before dispatch",
        )

    monkeypatch.setattr(app._physical_camera, "withdraw_capture_preview", refuse)
    ticket = _ticket(app, CAPTURE, VALUES)
    receipt = app.execute_action(ticket["ticket_id"])
    assert receipt["status"] == "FAILED"
    assert app.execute_action(ticket["ticket_id"]) == receipt
    saved = exported(app, receipt["operation_id"])
    assert (
        saved["queue"]["claimed"] is False and saved["completion"]["status"] == "FAILED"
    )
    assert not runner.calls and app._running is None


def test_rotation_retires_required_owner_without_orphaned_queue(
    queued_model, monkeypatch
):
    app, runner, _, controller, context, _ = queued_model
    for index in range(32):
        op = "operation-" + f"{index:032x}"
        app._operations[op] = dict(
            operation_id=op, action_id="record_note", status="SUCCEEDED", result=None
        )
    owner = next(iter(app._operations))

    def current(**kw):
        if owner not in app._operations:
            raise WizardError(
                "MODELED_RETIRED_METADATA_OWNER",
                "Required metadata owner left bounded history",
            )
        return deepcopy(context)

    monkeypatch.setattr(controller, "_current_context", current)
    ticket = _ticket(app, CAPTURE, VALUES)
    receipt = app.execute_action(ticket["ticket_id"])
    from test_camera_original_probe_arrival import complete

    result = complete(app, receipt["operation_id"])
    assert result["status"] == "FAILED" and owner not in app._operations
    assert len(app._operations) == 32 and app._running is None
    saved = exported(app, receipt["operation_id"])
    assert (
        saved["queue"]["claimed"] is True and saved["completion"]["status"] == "FAILED"
    )
    assert not runner.calls
