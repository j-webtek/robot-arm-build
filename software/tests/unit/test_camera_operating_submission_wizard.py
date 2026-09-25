"""Public tickets/logs/export with MODELED submission backend and setup adoption.

This verifies UI composition, not original provenance. Real stage storage,
native inputs and full-prefix readers have their own separately labeled tests.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application import camera_operating_submission_wizard as module
from rocell.application.camera_operating_submission import (
    SOURCE_WORKFLOW_OPERATING_SCHEMA,
)
from rocell.application.camera_probe_preparation import SOURCE_WORKFLOW_PROBE_SCHEMA
from rocell.application.camera_operating_proposal_wizard import ACTION as PROPOSAL
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_camera_operating_proposal_wizard import configured_draft, VALUES
from test_commissioning_camera_persistence import forbid_device_and_process_calls
from test_native_camera_activation_supervisor import no_physical_owner

SUBMIT = dict(
    operator_id="MODELED submitter",
    capture_1="capture-one",
    capture_2="capture-two",
    save_for_review=True,
)


@pytest.fixture
def submission_ready(configured_draft, monkeypatch):
    app, runner, source, context, inputs = configured_draft
    assert _run(app, PROPOSAL, VALUES)["status"] == "SUCCEEDED"
    setup = app._physical_camera_setup
    setup._source_workflow.update(
        schema=SOURCE_WORKFLOW_PROBE_SCHEMA,
        camera_probe_preparation=dict(
            state="REVIEWED_FOR_ADMISSION", preparation={}, review={}, events=[{}, {}]
        ),
    )
    captures = {key: {"MODELED": key} for key in ("capture-one", "capture-two")}
    monkeypatch.setattr(
        app._configuration_wizard,
        "export_fields",
        lambda: (
            dict(
                name="attempt_choice_id",
                label="MODELED capture",
                type="select",
                required=True,
                options=[dict(value=k, label=k) for k in captures],
                default="capture-one",
            ),
        ),
    )
    monkeypatch.setattr(
        app._configuration_wizard, "packet", lambda key: deepcopy(captures[key])
    )
    monkeypatch.setattr(
        app._configuration_wizard, "_probe_receipt", lambda: {"MODELED_probe": "one"}
    )
    monkeypatch.setattr(
        app._physical_camera,
        "configuration_capture_context",
        lambda: deepcopy(context["intent"]),
    )
    calls, reopened = [], [None]

    def modeled(*owners, **kwargs):
        kwargs["validate_current_context"]()
        calls.append(kwargs)
        record = dict(
            document=dict(
                submission_id="cameraoperating-" + "a" * 32,
                proposal_sha256=kwargs["expected_proposal_sha256"],
                assessment_sha256="b" * 64,
                assessment=dict(
                    captures=[
                        dict(request_key=k) for k in kwargs["capture_request_keys"]
                    ]
                ),
            ),
            evidence_sha256="c" * 64,
            reference=dict(evidence_id="MODELED original reference"),
            retention="M1_FULL_BYTES_READ_BACK",
        )
        row = dict(
            state="SUBMITTED_REVIEW_REQUIRED",
            submission=record,
            events=[],
            original_stage_authenticated=True,
            currentness_requires_revalidation=True,
            stage_passed=False,
            approved_operating_policy=False,
            connected=False,
            physical_authority=False,
            hardware_qualified=False,
            device_io_performed=False,
            native_inputs={"MODELED": "separate backend tests"},
        )
        kwargs["attempt"].update(
            submission_id=record["document"]["submission_id"],
            record=deepcopy(record),
            events=[],
            commit="COMMITTED_AND_REOPENED_ORIGINAL",
        )
        value = {
            **setup.original_source_workflow(),
            "schema": SOURCE_WORKFLOW_OPERATING_SCHEMA,
            "camera_operating_submission": row,
        }
        reopened[0] = deepcopy(value)
        kwargs["validate_current_context"]()
        return value

    monkeypatch.setattr(module, "run_original_operating_submission", modeled)
    monkeypatch.setattr(
        setup.session, "retained_source_workflow", lambda: deepcopy(reopened[0])
    )
    # The real adoption verifier requires the complete original source prefix;
    # this fixture intentionally models it and never claims hardware provenance.
    monkeypatch.setattr(
        setup,
        "_adopt_source_workflow",
        lambda value: setattr(setup, "_source_workflow", deepcopy(value)),
    )
    return app, runner, source, context, captures, calls, reopened


def test_unprepared_and_rehearsal_submission_is_unavailable(make_service):
    for mode in ("physical", "rehearsal"):
        app, runner, source = make_service(mode=mode)
        before = source["calls"]
        for _ in range(3):
            view = app.view()
            action = next(a for a in view["actions"] if a["action_id"] == module.ACTION)
            assert not action["enabled"]
            assert view["camera_operating_submission"]["state"] == "NOT_STARTED"
            assert not view["camera_operating_submission"]["connected"]
        assert source["calls"] == before and not runner.calls
        with pytest.raises(WizardError):
            _ticket(app, module.ACTION, SUBMIT)


def test_save_uses_one_ticket_durable_log_and_separate_unreviewed_publication(
    submission_ready,
):
    app, runner, _, _, _, calls, _ = submission_ready
    ticket = _ticket(app, module.ACTION, SUBMIT)
    assert "no device is opened" in " ".join(ticket["effects"])
    assert "REVIEW_PENDING" in " ".join(ticket["effects"])
    assert app._operating_submission.packet()["attempts"] == []
    assert [
        f["default"]
        for f in app._operating_submission.fields()
        if f["type"] == "select"
    ] == ["", ""]
    receipt = app.execute_action(ticket["ticket_id"])
    done = _complete(app, receipt["operation_id"])
    assert done["status"] == "SUCCEEDED", done
    assert done["completion_log_persisted"] is True
    assert len(calls) == 1 and calls[0]["capture_request_keys"] == (
        "capture-one",
        "capture-two",
    )
    view = app.view()["camera_operating_submission"]
    assert view["state"] == "SUBMITTED_REVIEW_REQUIRED"
    assert view["review_required"] and not view["stage_passed"]
    assert not view["approved_operating_policy"] and not view["connected"]
    assert (
        app._operating_submission.packet()["attempts"][0]["state"]
        == "RETAINED_UNREVIEWED"
    )
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"] == done["operation_id"]
    )
    assert len(calls) == 1 and not runner.calls
    with pytest.raises(WizardError):
        _ticket(app, module.ACTION, SUBMIT)


@pytest.mark.parametrize(
    "values",
    [
        {"capture_1": "capture-two"},
        {"capture_1": ""},
        {"capture_2": "not-owned"},
        {"save_for_review": False},
        {"operator_id": "é" * 33},
        {"uploaded_report": {}},
    ],
)
def test_explicit_owned_selection_and_consent_are_required(submission_ready, values):
    app = submission_ready[0]
    with pytest.raises(WizardError):
        _ticket(app, module.ACTION, {**SUBMIT, **values})
    assert (
        not submission_ready[5] and not app._operating_submission.packet()["attempts"]
    )


@pytest.mark.parametrize(
    "fault", ["source", "settings", "capture", "owner", "stop", "backend"]
)
def test_changed_context_does_not_publish_and_preserves_partial_outcome(
    submission_ready, monkeypatch, fault
):
    app, _, source, context, captures, _, _ = submission_ready
    original = module.run_original_operating_submission

    def changed(*owners, **kwargs):
        value = original(*owners, **kwargs)
        if fault == "source":
            source["hash"] = "f" * 64
        elif fault == "settings":
            context["intent"]["settings_epoch"] = "f" * 64
        elif fault == "capture":
            captures["capture-one"]["changed"] = True
        elif fault == "owner":
            app._native_camera = object()
        elif fault == "stop":
            kwargs["cancellation"].set()
        else:
            raise OSError("MODELED failure after publication")
        return value

    monkeypatch.setattr(module, "run_original_operating_submission", changed)
    done = _run(app, module.ACTION, SUBMIT)
    assert done["status"] != "SUCCEEDED", done
    row = app._operating_submission.packet()["attempts"][0]
    assert (
        row["state"] == "HISTORICAL_HELD"
        and row["attempt"]["record"]["reference"] is not None
    )
    assert app._physical_camera_setup._publication["status"] == "HISTORICAL_HELD"
    assert not app._operating_submission.view()["approved_operating_policy"]


def test_export_retains_exact_attempt_and_fresh_launch_restores_only_read_originals(
    submission_ready, make_service
):
    app = submission_ready[0]
    done = _run(app, module.ACTION, SUBMIT)
    assert done["status"] == "SUCCEEDED", done
    packet = app._operating_submission.packet()
    assert "current" not in packet["attempts"][0]
    app._full_results.clear()
    exported = _run(app, "export_logs", {})
    assert exported["status"] == "SUCCEEDED", json.dumps(exported, indent=2)
    directories = [p for p in app.export_directory.iterdir() if p.is_dir()]
    assert len(directories) == 1 and verify_export(directories[0])["valid"]
    record = json.loads(
        (directories[0] / "attachment-camera-operating-submissions.json").read_bytes()
    )
    assert record["diagnostics"] == packet and record["original_bytes_preserved"]
    restarted, _, _ = make_service(mode="physical")
    assert restarted._operating_submission.packet()["attempts"] == []
    assert restarted._operating_submission.view()["state"] == "NOT_STARTED"
    # MODEL the established original-reader adoption, never import an export.
    restarted._physical_camera_setup._source_workflow = deepcopy(submission_ready[6][0])
    view = restarted._operating_submission.view()
    assert view["state"] == "SUBMITTED_REVIEW_REQUIRED"
    assert view["original_stage_authenticated"] and not view["connected"]
    assert restarted._operating_submission.packet()["attempts"] == []
    with pytest.raises(WizardError):
        _ticket(restarted, module.ACTION, SUBMIT)


def test_polling_does_not_copy_the_full_original_history(submission_ready, monkeypatch):
    app = submission_ready[0]

    def denied():
        pytest.fail("status polling copied the complete source workflow")

    monkeypatch.setattr(app._physical_camera_setup, "original_source_workflow", denied)
    for _ in range(3):
        assert app._operating_submission.preview_context()["available"]
        assert app._operating_submission.view()["state"] == "NOT_STARTED"


@pytest.mark.parametrize(
    "fault", ["completion_log", "stop", "source", "deadline", "reopened", "settings"]
)
def test_late_failure_after_completion_log_does_not_publish(
    submission_ready, monkeypatch, fault
):
    app, _, source, context, _, _, reopened = submission_ready
    if fault == "completion_log":
        append = app._append_event

        def failed_log(event, data):
            if event == "ACTION_FINISHED" and data["action_id"] == module.ACTION:
                app._log_error = "MODELED late log failure"
                return False
            return append(event, data)

        monkeypatch.setattr(app, "_append_event", failed_log)
    else:
        finish = app._finish

        def changed(operation_id, *args):
            cancellation = app._cancel
            finish(operation_id, *args)
            if app._operations[operation_id]["action_id"] != module.ACTION:
                return
            if fault == "stop":
                if cancellation is not None:
                    cancellation.set()
            elif fault == "source":
                source["hash"] = "f" * 64
            elif fault == "deadline":
                app._operating_submission._attempts[operation_id]["deadline_ns"] = 1
            elif fault == "reopened":
                reopened[0]["unexpected"] = True
            else:
                context["intent"]["settings_epoch"] = "f" * 64

        monkeypatch.setattr(app, "_finish", changed)
    done = _run(app, module.ACTION, SUBMIT)
    assert done["status"] != "SUCCEEDED", done
    assert (
        app._operating_submission.packet()["attempts"][0]["state"] == "HISTORICAL_HELD"
    )
    assert app._physical_camera_setup._publication["status"] == "HISTORICAL_HELD"
