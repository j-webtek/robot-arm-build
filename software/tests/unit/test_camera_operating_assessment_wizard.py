"""Real wizard/log/export composition; original assessment service is MODELED."""

from copy import deepcopy
import json

import pytest

from rocell.application import camera_operating_assessment_wizard as module
from rocell.application.camera_operating_proposal_wizard import ACTION as PROPOSAL
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_camera_operating_proposal_wizard import configured_draft, VALUES
from test_commissioning_camera_persistence import forbid_device_and_process_calls
from test_native_camera_activation_supervisor import no_physical_owner

VALUES_ASSESS = dict(capture_1="none", capture_2="none")


@pytest.fixture
def draft(configured_draft, monkeypatch):
    app, runner, source, context, inputs = configured_draft
    assert _run(app, PROPOSAL, VALUES)["status"] == "SUCCEEDED"
    calls = []

    def modeled(*owners, **kwargs):
        kwargs["validate_current_context"]()
        calls.append(kwargs)
        return dict(
            schema="MODELED.original_assessment",
            original_inputs_authenticated_at_read=False,
            status="MODELED_APPROVAL_HELD",
            captures=list(kwargs["capture_request_keys"]),
            approved_operating_policy=False,
            original_stage_record_retained=False,
            physical_authority=False,
        )

    monkeypatch.setattr(module, "run_original_operating_assessment", modeled)
    return app, runner, source, context, calls


def test_unprepared_or_rehearsal_assessment_is_unavailable(make_service):
    for mode in ("physical", "rehearsal"):
        app, _, _ = make_service(mode=mode)
        action = next(
            a for a in app.view()["actions"] if a["action_id"] == module.ACTION
        )
        assert not action["enabled"]
        with pytest.raises(WizardError):
            _ticket(app, module.ACTION, VALUES_ASSESS)


def test_public_assessment_runs_once_and_keeps_missing_capture_selection(draft):
    app, runner, _, _, calls = draft
    ticket = _ticket(app, module.ACTION, VALUES_ASSESS)
    assert "no device is opened" in " ".join(ticket["effects"])
    receipt = app.execute_action(ticket["ticket_id"])
    done = _complete(app, receipt["operation_id"])
    assert done["status"] == "SUCCEEDED", done
    assert done["completion_log_persisted"]
    assert len(calls) == 1 and calls[0]["capture_request_keys"] == ()
    assert not runner.calls
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"] == done["operation_id"]
    )
    packet = app._operating_assessment.packet()
    assert packet["attempts"][0]["completion"]["status"] == "SUCCEEDED"
    assert not packet["approved_operating_policy"]


@pytest.mark.parametrize("fault", ["source", "settings", "owner", "stop", "exception"])
def test_changed_context_or_interruption_fails_without_approval(
    draft, monkeypatch, fault
):
    app, _, source, context, _ = draft
    original = module.run_original_operating_assessment

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if fault == "source":
            source["hash"] = "f" * 64
        elif fault == "settings":
            context["intent"]["settings_epoch"] = "f" * 64
        elif fault == "owner":
            app._native_camera = object()
        elif fault == "stop":
            kwargs["cancellation"].set()
        else:
            raise ValueError("MODELED original read failed")
        return result

    monkeypatch.setattr(module, "run_original_operating_assessment", changed)
    done = _run(app, module.ACTION, VALUES_ASSESS)
    assert done["status"] != "SUCCEEDED"
    assert not app._operating_assessment.packet()["approved_operating_policy"]


def test_stale_ticket_does_not_claim_an_attempt(draft):
    app, _, _, context, calls = draft
    ticket = _ticket(app, module.ACTION, VALUES_ASSESS)
    context["intent"]["settings_epoch"] = "f" * 64
    with pytest.raises(WizardError):
        app.execute_action(ticket["ticket_id"])
    assert not calls and not app._operating_assessment.packet()["attempts"]


def test_export_retains_history_and_fresh_instance_restores_no_permission(
    draft, make_service
):
    app, _, _, _, _ = draft
    assert _run(app, module.ACTION, VALUES_ASSESS)["status"] == "SUCCEEDED"
    before = deepcopy(app._operating_assessment.packet())
    app._full_results.clear()
    exported = _run(app, "export_logs", {})
    assert exported["status"] == "SUCCEEDED", exported
    directories = [path for path in app.export_directory.iterdir() if path.is_dir()]
    assert len(directories) == 1
    directory = directories[0]
    assert verify_export(directory)["valid"]
    record = json.loads(
        (directory / "attachment-camera-operating-assessments.json").read_bytes()
    )
    assert record["diagnostics"] == before
    restarted, _, _ = make_service(mode="physical")
    assert restarted._operating_assessment.packet()["attempts"] == []
    with pytest.raises(WizardError):
        restarted._operating_assessment.preview_context()


def test_bounded_history_and_polling_do_not_rerun_original_reads(draft):
    app, _, source, _, calls = draft
    before = source["calls"]
    for _ in range(3):
        app.view()
    assert source["calls"] == before and not calls
    for _ in range(module.MAX_ATTEMPTS):
        assert _run(app, module.ACTION, VALUES_ASSESS)["status"] == "SUCCEEDED"
    with pytest.raises(WizardError):
        _ticket(app, module.ACTION, VALUES_ASSESS)
    assert (
        len(calls)
        == len(app._operating_assessment.packet()["attempts"])
        == module.MAX_ATTEMPTS
    )


@pytest.mark.parametrize("fault", ["completion_log", "redaction", "deadline"])
def test_late_log_redaction_or_deadline_failure_is_not_success(
    draft, monkeypatch, fault
):
    app, _, _, _, _ = draft
    if fault == "completion_log":
        append = app._append_event

        def fail(event, data):
            if event == "ACTION_FINISHED":
                app._log_error = "MODELED_LOG_FAILURE"
                return False
            return append(event, data)

        monkeypatch.setattr(app, "_append_event", fail)
    else:
        run = module.run_original_operating_assessment

        def changed(*args, **kwargs):
            report = run(*args, **kwargs)
            if fault == "redaction":
                report["meaning"] = "password=MODELED_PRIVATE_PASSWORD"
            else:
                monkeypatch.setattr(
                    module, "monotonic_ns", lambda: kwargs["deadline_ns"] + 1
                )
            return report

        monkeypatch.setattr(module, "run_original_operating_assessment", changed)
    done = _run(app, module.ACTION, VALUES_ASSESS)
    assert done["status"] != "SUCCEEDED", done
    packet = app._operating_assessment.packet()
    assert not packet["approved_operating_policy"]
    assert packet["attempts"][0]["completion"]["status"] != "SUCCEEDED"


def test_explicit_capture_choices_reject_duplicates_and_pin_context(draft, monkeypatch):
    app, _, _, _, calls = draft
    keys = ["operation-" + digit * 32 for digit in ("6", "7")]
    hashes = {key: digit * 64 for key, digit in zip(keys, ("6", "7"))}
    monkeypatch.setattr(
        app._configuration_wizard,
        "export_fields",
        lambda: (
            dict(
                name="attempt_choice_id",
                label="MODELED saved capture",
                type="select",
                required=True,
                default=keys[0],
                options=[dict(value=key, label=key) for key in keys],
            ),
        ),
    )
    monkeypatch.setattr(
        app._configuration_wizard, "export_context", lambda key: hashes[key]
    )
    monkeypatch.setattr(
        app._configuration_wizard, "packet", lambda key: {"MODELED_capture": key}
    )
    with pytest.raises(WizardError, match="distinct"):
        _ticket(app, module.ACTION, dict(capture_1=keys[0], capture_2=keys[0]))
    values = dict(capture_1=keys[0], capture_2=keys[1])
    ticket = _ticket(app, module.ACTION, values)
    hashes[keys[0]] = "f" * 64
    with pytest.raises(WizardError):
        app.execute_action(ticket["ticket_id"])
    assert not calls
    assert _run(app, module.ACTION, values)["status"] == "SUCCEEDED"
    assert calls[0]["capture_request_keys"] == tuple(keys)
    assert calls[0]["capture_packets"] == {
        key: {"MODELED_capture": key} for key in keys
    }
