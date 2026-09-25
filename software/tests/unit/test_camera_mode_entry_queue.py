"""One-use public queue and pre-dispatch faults with MODELED availability only.

No original acceptance is claimed: the fake cached predecessor cannot pass the
real original reader. These tests stop before dispatch or model that one seam.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application import physical_camera_mode_entry_service as m
from rocell.application.wizard_actions import (
    WizardError,
    validate_action_input,
    ACTION_BY_ID,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from test_arrival_wizard_service import make_service, _ticket, _run


def ready(app):
    setup = app._physical_camera_setup
    setup.session._cached.update(
        status="REFRESHED_STORAGE_ONLY",
        initialize_attempted=True,
        verification=dict(
            effects_allowed_by_m1_storage=True, challenge_sha256="c" * 64
        ),
        stages=[
            dict(
                stage=stage.value,
                state="PASS" if i < 4 else "PENDING",
                last_event_sequence=None,
                evidence_ids=[],
            )
            for i, stage in enumerate(STAGE_ORDER)
        ],
    )
    setup._source_workflow = dict(
        schema=m.SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
        state="PASS",
        binding=setup.session.descriptor(),
        session_header_sha256="b" * 64,
        configuration_epochs={},
        prerequisites=None,
        receipt=None,
        assessment=None,
        review=None,
        usb_qualification_complete=dict(
            state="REVIEWED_PASS",
            series={},
            assessment={},
            review={},
            events=[{}, {}, {}],
        ),
    )
    setup._publication = dict(status="CURRENT", operation_id="MODELED-read")
    return setup


VALUES = dict(operator_id="MODELED-setup", file_only=True)


@pytest.mark.parametrize(
    "label", ["Camera setup operator", "Étienne", "É" * 32, "A" * 64]
)
def test_entry_label_reaches_writer_with_exact_public_value(
    make_service, monkeypatch, label
):
    app, runner, _ = make_service(mode="physical")
    setup = ready(app)
    seen = []

    def writer(*args, **kwargs):
        seen.append(kwargs["operator_id"])
        # This cheap routing test stops before original I/O. The full composed
        # test separately exercises successful retention/publication with spaces.
        raise WizardError("MODELED_ENTRY_REACHED", "Incapable routing boundary.")

    monkeypatch.setattr(m, "enter_camera_mode", writer)
    result = _run(app, m.ACTION, dict(operator_id=label, file_only=True))
    assert result["error"]["code"] == "MODELED_ENTRY_REACHED"
    assert seen == [label] and setup._mode_entry_queue["claimed"] is True
    assert not runner.calls and setup._mode_entry_attempt is None


@pytest.mark.parametrize(
    "label",
    [
        "",
        " ",
        " operator",
        "operator ",
        "A" * 65,
        "É" * 33,
        "line\nlabel",
        "tab\tlabel",
        "bad\x7f",
        "\ud800",
        1,
        None,
    ],
)
def test_invalid_entry_labels_fail_before_consuming_queue(
    make_service, monkeypatch, label
):
    app, runner, _ = make_service(mode="physical")
    setup = ready(app)
    with pytest.raises(WizardError):
        _ticket(app, m.ACTION, dict(operator_id=label, file_only=True))
    assert not setup._mode_entry_attempted and setup._mode_entry_queue is None
    assert not app.view()["operations"] and not runner.calls


def test_other_setup_actions_keep_their_existing_portable_label_rule(
    make_service, monkeypatch
):
    from threading import Event

    app, runner, _ = make_service(mode="physical")
    setup = ready(app)
    monkeypatch.setattr(setup, "blocked_reason", lambda _: None)
    with pytest.raises(WizardError, match="portable operator"):
        setup.perform(
            "physical_camera_refresh",
            expected_context_sha256="a" * 64,
            operator_id="Not a portable ID",
            enrollment=None,
            source_report=None,
            cancellation=Event(),
            progress=lambda _: pytest.fail("unexpected progress"),
        )
    assert not runner.calls and setup._mode_entry_queue is None


def test_navigation_is_inert_and_consent_is_explicit(make_service):
    app, runner, source = make_service(mode="physical")
    setup = ready(app)
    before = deepcopy(setup._source_workflow)
    reads = source["calls"]
    for _ in range(3):
        assert app.view()["camera_mode_entry"]["status"] == "READY_TO_ENTER"
    assert source["calls"] == reads
    action = ACTION_BY_ID[m.ACTION]
    assert action.worker == "physical_camera_setup" and action.timeout_s == 180
    for values in (
        {},
        {"operator_id": "MODEL"},
        {**VALUES, "file_only": False},
        {**VALUES, "allow_hardware": True},
    ):
        with pytest.raises(WizardError):
            validate_action_input(action, values)
    ticket = _ticket(app, m.ACTION, VALUES)
    assert "No camera is opened" in " ".join(ticket["effects"])
    assert not setup._mode_entry_attempted and setup._mode_entry_queue is None
    assert setup._source_workflow == before and not runner.calls


def test_intent_log_failure_consumes_queue_without_original_dispatch(
    make_service, monkeypatch
):
    app, runner, _ = make_service(mode="physical")
    setup = ready(app)
    original = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda name, data: False if name == "ACTION_EXECUTED" else original(name, data),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("failed intent logging reached the entry writer")

    monkeypatch.setattr(m, "enter_camera_mode", forbidden)
    result = _run(app, m.ACTION, VALUES)
    assert result["status"] == "FAILED"
    assert setup._mode_entry_attempted and setup._mode_entry_queue["claimed"] is False
    assert setup._mode_entry_attempt is None and not runner.calls
    assert setup.mode_entry_view()["status"] == "HISTORICAL_HELD"
    with pytest.raises(WizardError):
        _ticket(app, m.ACTION, VALUES)
    diagnostics = setup.mode_entry_diagnostics()
    assert (
        diagnostics["attempted"]
        and diagnostics["queued_operation_id"] == result["operation_id"]
    )
    assert diagnostics["original"] is diagnostics["attempt"] is None
    # A failed intent log must still be useful in the ordinary assigned-folder
    # export; exporting must not dispatch/replay the consumed entry attempt.
    monkeypatch.setattr(app, "_append_event", original)
    exported = _run(app, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    saved = json.loads((folder / "attachment-camera-mode-entry.json").read_bytes())
    assert saved["original_bytes_preserved"] is True
    assert saved["queued_operation_id"] == result["operation_id"]
    assert saved["attempt"] is saved["original"] is None and not runner.calls


def test_changed_context_after_preview_is_not_written(make_service, monkeypatch):
    app, runner, _ = make_service(mode="physical")
    setup = ready(app)
    ticket = _ticket(app, m.ACTION, VALUES)
    setup._source_workflow["configuration_epochs"]["MODELED-change"] = True

    def forbidden(*args, **kwargs):
        pytest.fail("stale context reached original writer")

    monkeypatch.setattr(m, "enter_camera_mode", forbidden)
    from test_arrival_wizard_service import _complete

    receipt = app.execute_action(ticket["ticket_id"])
    result = _complete(app, receipt["operation_id"])
    assert result["status"] == "FAILED"
    assert setup._mode_entry_queue["claimed"] is True and not runner.calls
    assert setup.mode_entry_view()["status"] == "HISTORICAL_HELD"
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "unpublished",
        "partial",
        "rejected",
        "already_entered",
        "stage",
        "mode",
        "already_attempted",
    ],
)
def test_only_the_unused_published_review_can_queue(make_service, fault):
    app, _, _ = make_service(mode="physical")
    setup = ready(app)
    if fault == "unpublished":
        setup._publication["status"] = "HISTORICAL_HELD"
    elif fault in {"partial", "rejected"}:
        setup._source_workflow["usb_qualification_complete"]["state"] = (
            "INCOMPLETE" if fault == "partial" else "REVIEWED_BLOCKED"
        )
    elif fault == "already_entered":
        setup._source_workflow["schema"] = (
            "rocell.physical_camera_source_workflow_readback.v15"
        )
    elif fault == "stage":
        setup.session._cached["stages"][4]["state"] = "WAITING_OPERATOR"
    elif fault == "mode":
        setup.mode = "rehearsal"
    else:
        setup._mode_entry_attempted = True
    with pytest.raises(WizardError):
        setup.begin_mode_entry("a" * 64, "MODELED-operation")
    assert setup._mode_entry_queue is None
