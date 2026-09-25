"""Public intent/log -> actual camera service/M1/core -> incapable native owner.

Original predecessor authentication and facts remain explicitly MODELED in this
lane (the complete reader/facts composition is tested separately). No physical
camera, serial port, capable process or hardware qualification is involved.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application.camera_probe_preparation import SOURCE_WORKFLOW_PROBE_SCHEMA
from rocell.application.camera_probe_attempt_export import restore_probe_attempt_export
from rocell.application.arrival_wizard_service import _json_payload
from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _ticket
from test_camera_original_probe_service import prepare_services
from test_camera_activation_dispatch_handoff import install_owner
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner
from test_commissioning_camera_persistence import WINDOWS

PROBE = "physical_camera_probe"
EXPORT = "physical_camera_probe_attempt_export"
VALUES = dict(
    operator_id="MODELED operator",
    arm_actuator_supply_disconnected=True,
    bounded_probe_consent=True,
)


def complete(app, op):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        row = app.operation(op)
        if row["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return row
        Event().wait(0.02)
    pytest.fail("Original action still running; do not create a replacement")


@pytest.fixture
def joined(make_service, tmp_path, monkeypatch):
    app, runner, source = make_service(mode="physical")
    c = prepare_services(tmp_path, monkeypatch, launch=app.session_id)
    app._physical_camera = c.service
    setup = app._physical_camera_setup
    setup._acquisition = c.service
    setup.session = c.session
    setup._publication = dict(status="CURRENT", operation_id="MODELED-original-review")
    setup._source_workflow = dict(
        schema=SOURCE_WORKFLOW_PROBE_SCHEMA,
        prerequisites=None,
        session_header_sha256=c.values["expected_header_sha256"],
        camera_probe_preparation=dict(
            state="REVIEWED_FOR_ADMISSION",
            preparation=dict(
                evidence_sha256="1" * 64,
                document=dict(plan=c.plan, enrollment=c.enrollment.export_snapshot()),
            ),
            review=dict(evidence_sha256="2" * 64),
        ),
    )
    app._native_camera = c.enrollment
    snapshot = c.enrollment.export_snapshot()
    operations = {
        "MODELED-current-" + str(i): action
        for i, action in enumerate(
            (
                "inventory_devices",
                "native_camera_inventory",
                "native_camera_identity",
                "native_camera_review",
            )
        )
    }
    for op, action in operations.items():
        app._operations[op] = dict(
            operation_id=op,
            action_id=action,
            status="SUCCEEDED",
            completion_log_persisted=True,
            message="MODELED current provenance",
            # These predecessor operation records model logged metadata; no
            # real acquisition result exists in this scoped fixture. The
            # general exporter must report that omission, not invent a result.
            result_retention="OMITTED_MODELED_METADATA_RESULT",
            result_sha256=None,
        )
    app._probe_metadata_publication = dict(
        enrollment_sha256=hashlib.sha256(_json_payload(snapshot)).hexdigest(),
        operations=operations,
    )
    c.app, c.runner, c.source_state = app, runner, source
    return c


def exported(app):
    ticket = _ticket(app, EXPORT)
    row = complete(app, app.execute_action(ticket["ticket_id"])["operation_id"])
    assert row["status"] == "SUCCEEDED", row
    receipt = row["result"]["steps"][0]["report"]["receipt"]
    folder = Path(receipt["path"])
    assert folder.parent == app.export_directory
    assert verify_export(folder)["valid"]
    snapshot = json.loads((folder / "report.json").read_bytes())["snapshot"]
    parts = {
        p.name[len("attachment-") :]: p.read_bytes()
        for p in folder.glob("attachment-*.json")
    }
    return restore_probe_attempt_export(snapshot, parts)


@WINDOWS
@pytest.mark.parametrize(
    "fault", [None, "bad-result", "admission-deadline", "completion-log", "late-stop"]
)
def test_public_probe_runs_once_and_exports_complete_original_attempt(
    joined, tmp_path, monkeypatch, fault
):
    c, app = joined, joined.app
    owners = install_owner(
        tmp_path,
        monkeypatch,
        purpose="probe",
        fault=fault if fault in {"bad-result", "admission-deadline"} else None,
    )
    if fault == "completion-log":
        append = app._append_event
        monkeypatch.setattr(
            app,
            "_append_event",
            lambda kind, data: (
                False
                if kind == "ACTION_FINISHED" and data["action_id"] == PROBE
                else append(kind, data)
            ),
        )
    if fault == "late-stop":
        finish = app._finish

        def stop_at_finish(op, status, result):
            if app._operations[op]["action_id"] == PROBE:
                app._cancel.set()
            return finish(op, status, result)

        monkeypatch.setattr(app, "_finish", stop_at_finish)
    ticket = _ticket(app, PROBE, VALUES)
    assert ticket["input"] == VALUES
    assert c.values["expected_plan_sha256"] in " ".join(ticket["effects"])
    assert not owners and not c.original_calls and app._probe_dispatch_queue is None
    receipt = app.execute_action(ticket["ticket_id"])
    result = complete(app, receipt["operation_id"])
    assert result["status"] == (
        "FAILED"
        if fault in {"bad-result", "admission-deadline", "completion-log"}
        else "SUCCEEDED"
    ), result
    assert len(owners) == len(c.original_calls) == 1
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    with pytest.raises(WizardError, match="queued once"):
        _ticket(app, PROBE, VALUES)
    view = c.service.view()
    assert (view["publication"]["status"] == "CURRENT") is (fault is None)
    assert view["connected"] is view["physical_authority"] is False
    assert app.view()["camera"]["image_id"] is None
    saved = exported(app)
    assert saved == app._probe_attempt_packet()
    assert saved["queue"]["claimed"] is True
    assert saved["completion"]["operation_id"] == receipt["operation_id"]
    assert saved["dispatch"]["original_admission"] == saved["admission"]["admission"]
    assert saved["dispatch"]["original_evidence"]["run"]
    if fault in {"bad-result", "admission-deadline"}:
        summary = result["result"]["camera_attempt_failure"]
        supervision = saved["dispatch"]["original_evidence"]["supervision"]
        assert summary["reported_primary_error"] == supervision["primary_error"]
        assert summary["reported_primary_error"] in result["error"]["message"]
        assert summary["release_check_passed"] is supervision["release_check_passed"]
        assert summary["attempt_id"] == saved["dispatch"]["transaction"]["attempt_id"]
        assert summary["native_accounting_available"] is False
        assert summary["quarantine_latched"] is True
        assert summary["physical_authority"] is summary["automatic_replay"] is False
        assert saved["completion"]["result"]["camera_attempt_failure"] == summary
        if fault == "admission-deadline":
            assert summary["reported_primary_error"] == "ADMISSION_DEADLINE_EXPIRED"
            assert summary["release_check_passed"] is False
            assert owners[0].phase == "ready"
        # The ordinary assigned-folder export retains the bounded error/result
        # too; full native pipe originals still use the dedicated export above.
        ordinary_ticket = _ticket(app, "export_logs")
        ordinary = complete(
            app, app.execute_action(ordinary_ticket["ticket_id"])["operation_id"]
        )
        assert ordinary["status"] == "SUCCEEDED", json.dumps(ordinary, indent=2)
        folder = Path(ordinary["result"]["receipt"]["path"])
        assert folder.parent == app.export_directory
        assert verify_export(folder)["valid"]
        attachment = folder / (
            "attachment-result-"
            + receipt["operation_id"].removeprefix("operation-")
            + ".json"
        )
        assert json.loads(attachment.read_bytes())["camera_attempt_failure"] == summary
    assert not c.runner.calls
    assert not c.runtime.verify(
        c.session.descriptor()["session_id"]
    ).active_lease_owners


@WINDOWS
def test_failed_intent_is_exportable_without_service_or_native_dispatch(
    joined, tmp_path, monkeypatch
):
    app, c = joined.app, joined
    owners = install_owner(tmp_path, monkeypatch)
    append = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda kind, data: (
            False
            if kind == "ACTION_EXECUTED" and data["action_id"] == PROBE
            else append(kind, data)
        ),
    )
    result = complete(
        app,
        app.execute_action(_ticket(app, PROBE, VALUES)["ticket_id"])["operation_id"],
    )
    assert result["status"] == "FAILED"
    saved = exported(app)
    assert saved["queue"]["claimed"] is False
    assert saved["admission"] is saved["dispatch"] is None
    assert not owners and not c.original_calls and not c.runner.calls
    # Notes must not evict the one-use queue or its pinned original completion.
    for index in range(36):
        note = _ticket(
            app, "record_note", {"note": f"MODELED investigation note {index}"}
        )
        assert (
            complete(app, app.execute_action(note["ticket_id"])["operation_id"])[
                "status"
            ]
            == "SUCCEEDED"
        )
    assert result["operation_id"] not in app._operations
    assert exported(app) == saved


@WINDOWS
@pytest.mark.parametrize(
    "change", ["metadata-log", "owner-copy", "source", "stop", "context"]
)
def test_changed_owner_or_stop_refuses_before_original_reader(
    joined, monkeypatch, change
):
    app, c = joined.app, joined
    run = c.service.run_original_probe

    def change_before(*args, **kwargs):
        if change == "metadata-log":
            op = next(iter(app._probe_metadata_publication["operations"]))
            app._operations[op]["completion_log_persisted"] = False
        elif change == "owner-copy":
            app._native_camera = app._native_camera.staged_copy()
        elif change == "source":
            c.source_state["hash"] = "b" * 64
        elif change == "stop":
            kwargs["cancellation"].set()
        else:
            app._physical_camera_setup._source_workflow["camera_probe_preparation"][
                "review"
            ]["evidence_sha256"] = ("9" * 64)
        return run(*args, **kwargs)

    monkeypatch.setattr(c.service, "run_original_probe", change_before)
    result = complete(
        app,
        app.execute_action(_ticket(app, PROBE, VALUES)["ticket_id"])["operation_id"],
    )
    assert result["status"] != "SUCCEEDED"
    assert not c.original_calls
    assert c.service.view()["publication"]["status"] != "CURRENT"
    saved = exported(app)
    assert saved["admission"]["status"] == "FAILED_HELD"


def test_probe_fields_are_closed_and_consent_never_defaults_on():
    action = ACTION_BY_ID[PROBE]
    assert action.timeout_s == 300
    for values in (
        {},
        {**VALUES, "bounded_probe_consent": False},
        {**VALUES, "arm_actuator_supply_disconnected": False},
        {**VALUES, "operator_id": "é" * 33},
        {**VALUES, "expected_plan_sha256": "a" * 64},
    ):
        with pytest.raises(WizardError):
            validate_action_input(action, values)
