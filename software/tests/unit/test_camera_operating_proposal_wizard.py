"""Real wizard tickets/logs/export with explicitly MODELED predecessor context.

No original M1 authentication is claimed. The production proposal builder reads
the fixed purchase profile; camera data comes from in-memory codec fixtures.
"""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import Event

import pytest

from rocell.application.camera_operating_proposal import (
    CameraOperatingProposal,
    CameraOperatingProposalError,
)
from rocell.application.camera_operating_proposal_wizard import ACTION, MAX_ATTEMPTS
from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _ticket, _run, _complete
from test_camera_operating_evidence_preflight import case
from test_commissioning_camera_persistence import forbid_device_and_process_calls
from test_native_camera_activation_supervisor import no_physical_owner

VALUES = dict(
    operator_id="MODELED proposal operator",
    rationale="Evaluate the currently staged camera mode.",
    variance_rationale="Evaluate 8 fps without rewriting the 9-fps reference.",
)


@pytest.fixture
def configured_draft(make_service, tmp_path, monkeypatch):
    app, runner, source = make_service(mode="physical")
    inputs, _ = case(tmp_path, monkeypatch, version="legacy")
    context = dict(
        intent=dict(settings_epoch=inputs["expected_settings_epoch"]),
        settings_publication_sha256="1" * 64,
        original_setup={
            "MODELED": "cached context, not original storage authentication"
        },
    )
    monkeypatch.setattr(
        app._configuration_wizard,
        "_current_context",
        lambda **kwargs: deepcopy(context),
    )
    app._configuration_wizard._settings = canonical(
        {"MODELED": "not a real publication receipt"}
    )
    entry = json.loads(inputs["entry_payload"])
    app._physical_camera_setup._source_workflow = dict(
        session_header_sha256=entry["binding"]["header_sha256"],
        camera_mode_entry=dict(
            state="ENTERED",
            entry=dict(document=entry, evidence_sha256=digest(inputs["entry_payload"])),
        ),
    )
    app._physical_camera_setup._publication = dict(
        status="CURRENT", operation_id="MODELED-entry"
    )
    monkeypatch.setattr(
        app._physical_camera,
        "operating_proposal_configuration",
        lambda: inputs["configuration_payload"],
    )
    return app, runner, source, context, inputs


def test_unprepared_and_rehearsal_wizards_cannot_record_a_proposal(make_service):
    for mode in ("physical", "rehearsal"):
        app, runner, source = make_service(mode=mode)
        count = source["calls"]
        for _ in range(3):
            view = app.view()
            assert view["camera_operating_proposal"]["state"] == "NOT_STARTED"
            action = next(a for a in view["actions"] if a["action_id"] == ACTION)
            assert not action["enabled"]
        assert source["calls"] == count and not runner.calls
        with pytest.raises(WizardError):
            _ticket(app, ACTION, VALUES)


def test_public_draft_uses_existing_ticket_log_and_exact_proposal_codec(
    configured_draft,
):
    app, runner, source, _, inputs = configured_draft
    before = source["calls"]
    assert app.view()["camera_operating_proposal"]["proposal"] is None
    assert source["calls"] == before
    ticket = _ticket(app, ACTION, VALUES)
    assert inputs["expected_settings_epoch"] in " ".join(ticket["effects"])
    assert ticket["input"] == VALUES
    assert app._operating_proposal.packet()["attempts"] == []
    receipt = app.execute_action(ticket["ticket_id"])
    done = _complete(app, receipt["operation_id"])
    assert done["status"] == "SUCCEEDED", done
    assert done["completion_log_persisted"] is True
    assert not runner.calls
    record = done["result"]["steps"][0]["report"]
    proposal = CameraOperatingProposal(canonical(record["proposal"]))
    assert proposal.sha256 == record["proposal_sha256"]
    assert (
        proposal.to_dict()["subjects"]["settings_epoch"]
        == inputs["expected_settings_epoch"]
    )
    assert record["original_stage_record_retained"] is False
    assert record["assessment_performed"] is False
    view = app.view()["camera_operating_proposal"]
    assert view["state"] == "LOGGED_DRAFT_NOT_APPROVED"
    assert view["current_operation_id"] == done["operation_id"]
    assert view["approved_operating_policy"] is False and view["connected"] is False
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"] == done["operation_id"]
    )
    assert len(app._operating_proposal.packet()["attempts"]) == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("variance_rationale", ""),
        ("rationale", " "),
        ("rationale", "x\x00y"),
        ("operator_id", "x\ny"),
        ("operator_id", "é" * 33),
        ("rationale", "x" * 1025),
        ("variance_rationale", "x" * 1025),
        ("approved", True),
    ],
)
def test_invalid_or_missing_explicit_intent_is_rejected_at_preview(
    configured_draft, key, value
):
    app, runner, _, _, _ = configured_draft
    with pytest.raises(WizardError):
        _ticket(app, ACTION, {**VALUES, key: value})
    assert not runner.calls and not app._operating_proposal.packet()["attempts"]


@pytest.mark.parametrize(
    "fault",
    ["entry_hash", "entry_header", "entry_state", "publication", "settings_epoch"],
)
def test_cached_subject_joins_must_match_before_a_draft_can_be_offered(
    configured_draft, fault
):
    app, _, _, context, _ = configured_draft
    setup = app._physical_camera_setup
    if fault == "entry_hash":
        setup._source_workflow["camera_mode_entry"]["entry"]["evidence_sha256"] = (
            "f" * 64
        )
    elif fault == "entry_header":
        setup._source_workflow["session_header_sha256"] = "f" * 64
    elif fault == "entry_state":
        setup._source_workflow["camera_mode_entry"]["state"] = "PARTIAL"
    elif fault == "publication":
        setup._publication["status"] = "PENDING"
    else:
        context["intent"]["settings_epoch"] = "f" * 64
    with pytest.raises(WizardError):
        _ticket(app, ACTION, VALUES)


def test_changed_preview_context_cannot_be_queued(configured_draft):
    app, _, _, context, _ = configured_draft
    ticket = _ticket(app, ACTION, VALUES)
    context["settings_publication_sha256"] = "2" * 64
    with pytest.raises(WizardError):
        app.execute_action(ticket["ticket_id"])
    assert app._operating_proposal.packet()["attempts"] == []


@pytest.mark.parametrize(
    "fault",
    ["completion_log", "stop", "source", "owner", "settings", "redaction", "deadline"],
)
def test_late_failure_never_publishes_a_current_draft(
    configured_draft, monkeypatch, fault
):
    app, _, source, context, _ = configured_draft
    if fault == "completion_log":
        append = app._append_event

        def fail(event, data):
            if event == "ACTION_FINISHED":
                app._log_error = "MODELED_LOG_FAILURE"
                return False
            return append(event, data)

        monkeypatch.setattr(app, "_append_event", fail)
    elif fault == "redaction":
        # Real sanitizer redacts this input; the original proposal must not be
        # published with a hash naming different bytes.
        pass
    else:
        finish = app._finish

        def changed(*args, **kwargs):
            cancellation = app._cancel
            finish(*args, **kwargs)
            if fault == "source":
                source["hash"] = "f" * 64
            elif fault == "owner":
                app._native_camera = object()
            elif fault == "settings":
                context["settings_publication_sha256"] = "f" * 64
            elif fault == "deadline":
                app._operating_proposal._attempts[args[0]]["deadline_ns"] = 1
            else:
                if cancellation is not None:
                    cancellation.set()

        monkeypatch.setattr(app, "_finish", changed)
    values = (
        {**VALUES, "rationale": "password=MODELED_PRIVATE_PASSWORD"}
        if fault == "redaction"
        else VALUES
    )
    done = _run(app, ACTION, values)
    assert done["status"] != "SUCCEEDED", done
    view = app._operating_proposal.view()
    assert view["current_operation_id"] is None and view["proposal"] is None


@pytest.mark.parametrize("fault", ["settings", "source", "owner"])
def test_existing_draft_becomes_historical_when_cached_context_changes(
    configured_draft, fault
):
    app, _, _, context, _ = configured_draft
    assert _run(app, ACTION, VALUES)["status"] == "SUCCEEDED"
    if fault == "settings":
        context["settings_publication_sha256"] = "f" * 64
    elif fault == "source":
        app._source_changed = True
    else:
        app._native_camera = object()
    view = app._operating_proposal.view()
    assert view["state"] == "HISTORICAL_HELD" and view["proposal"] is None
    assert app._operating_proposal.packet()["attempts"][0]["result"] is not None


def test_dedicated_export_preserves_small_drafts_and_fresh_start_restores_nothing(
    configured_draft, make_service
):
    app, _, _, _, _ = configured_draft
    done = _run(app, ACTION, VALUES)
    assert done["status"] == "SUCCEEDED", done
    app._full_results.clear()  # Model normal bounded full-result cache eviction.
    exported = _run(app, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    # The original export receipt schema belongs to Arrival, not this controller.
    roots = [path for path in app.export_directory.iterdir() if path.is_dir()]
    assert len(roots) == 1
    root = roots[0]
    assert verify_export(root)["valid"]
    saved = json.loads(
        (root / "attachment-camera-operating-proposals.json").read_bytes()
    )
    assert saved["original_bytes_preserved"] is True
    record = saved["diagnostics"]["attempts"][0]
    assert record["operation_id"] == done["operation_id"]
    assert record["completion"]["completion_log_persisted"] is True
    assert (
        record["result"]["steps"][0]["report"]["proposal"]["approved_operating_policy"]
        is False
    )
    fresh, runner, _ = make_service(mode="physical")
    assert fresh._operating_proposal.view()["state"] == "NOT_STARTED"
    assert not fresh._operating_proposal.packet()["attempts"] and not runner.calls


def test_attempt_limit_preserves_history_without_replay(configured_draft):
    app, _, _, _, _ = configured_draft
    for _ in range(MAX_ATTEMPTS):
        assert _run(app, ACTION, VALUES)["status"] == "SUCCEEDED"
    first = deepcopy(app._operating_proposal.packet()["attempts"][0])
    with pytest.raises(WizardError):
        _ticket(app, ACTION, VALUES)
    assert app._operating_proposal.packet()["attempts"][0] == first


def test_polling_does_not_read_profiles_or_full_diagnostics(
    configured_draft, monkeypatch
):
    app, runner, source, _, _ = configured_draft
    assert _run(app, ACTION, VALUES)["status"] == "SUCCEEDED"

    def forbidden(*args, **kwargs):
        pytest.fail("Polling attempted file or full original-history access")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(app._physical_camera_setup, "original_source_workflow", forbidden)
        patch.setattr(app._physical_camera, "retained_capture_diagnostics", forbidden)
        count = source["calls"]
        for _ in range(4):
            assert (
                app._operating_proposal.view()["state"] == "LOGGED_DRAFT_NOT_APPROVED"
            )
            app._operating_proposal.preview_context()
        assert source["calls"] == count and not runner.calls


def test_reference_mode_needs_no_variance_and_does_not_apply_settings(
    configured_draft, tmp_path, monkeypatch
):
    app, runner, _, context, inputs = configured_draft
    reference, _ = case(tmp_path, monkeypatch, version="legacy", fps=9)
    inputs.update(reference)
    context["intent"]["settings_epoch"] = reference["expected_settings_epoch"]
    with pytest.raises(WizardError):
        _ticket(app, ACTION, VALUES)
    done = _run(app, ACTION, {**VALUES, "variance_rationale": ""})
    assert done["status"] == "SUCCEEDED", done
    proposal = done["result"]["steps"][0]["report"]["proposal"]
    assert proposal["policy_kind"] == "REFERENCE_9_FPS_PROPOSAL"
    assert proposal["variance_rationale"] is None
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in app.view()["stages"])
    assert not runner.calls


@pytest.mark.parametrize("bad", [0, -1, True, "1"])
def test_malformed_native_mode_is_a_closed_proposal_error(configured_draft, bad):
    _, _, _, _, inputs = configured_draft
    document = json.loads(inputs["proposal_payload"])
    document["target_mode"]["fps_denominator"] = bad
    with pytest.raises(CameraOperatingProposalError):
        CameraOperatingProposal(canonical(document))


def test_failed_intent_log_never_runs_the_draft(configured_draft, monkeypatch):
    app, runner, _, _, _ = configured_draft
    append = app._append_event

    def fail(event, data):
        if event == "ACTION_EXECUTED":
            app._log_error = "MODELED_INTENT_LOG_FAILURE"
            return False
        return append(event, data)

    monkeypatch.setattr(app, "_append_event", fail)
    try:
        done = _run(app, ACTION, VALUES)
        assert done["status"] != "SUCCEEDED"
    except WizardError:
        pass
    assert app._operating_proposal.packet()["attempts"] == [] and not runner.calls
