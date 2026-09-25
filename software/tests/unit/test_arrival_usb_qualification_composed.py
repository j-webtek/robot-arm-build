"""Actual declaration/Arrival/codecs and modeled original M1; no device APIs.

All received-unit and host facts in the inherited prefix are explicitly modeled.
Node is used only for the finite cached fake-DOM renderer, never a real browser.
"""

from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import traceback
import time
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_identity_service as module
from rocell.application import physical_camera_usb_readback as usb_readback
from rocell.application.physical_usb_identity_export import (
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay
from test_arrival_camera_identity_composed import (
    identity_composed,
    identity_wait,
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    complete_modeled_storage_projection,
    make_service,
    perform,
    SUBMIT_VALUES,
    REVIEW_VALUES,
    module as identity_module,
)
from test_physical_usb_identity_service import original_epochs
from test_physical_camera_usb_trial_readback import change_last_event
from test_arrival_wizard_service import _ticket
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render


VALUES = dict(
    operator_id="Trial Operator",
    cable_label="original_cable_α",
    port_label="rear_port_1",
    confirm_file_only=True,
)


def _complete(arrival, operation_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        operation = arrival.operation(operation_id)
        if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return operation
        Event().wait(0.01)
    pytest.fail(
        "same original declaration operation exceeded 30-second modeled test bound"
    )


def _run(arrival, action, values):
    ticket = _ticket(arrival, action, values)
    queued = arrival.execute_action(ticket["ticket_id"])
    return _complete(arrival, queued["operation_id"])


@pytest.fixture
def declared_prefix(identity_composed, monkeypatch):
    arrival, _, state, source, runner = identity_composed
    perform(arrival, identity_module.SUBMIT, SUBMIT_VALUES)
    perform(arrival, identity_module.REVIEW, REVIEW_VALUES)
    owner = module.PhysicalUsbIdentityService(arrival._physical_camera_setup)
    arrival._usb_identity = owner
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    # This original prefix has no campaign and uses modeled ownership, not a
    # real M1 ledger. The complete stage reader and trial codecs remain real.
    monkeypatch.setattr(usb_readback, "read_original_usb_campaigns", lambda *a: ())
    owner.observe_setup()
    original_scope = state["store"].stage_transaction

    @contextmanager
    def exact_commit_result(*args, **kwargs):
        with original_scope(*args, **kwargs) as tx:
            original_commit = tx.commit_stage_state

            def commit(stage, next_state, **values):
                original_commit(stage, next_state, **values)
                # Match the actual V2 API: retain its supplied UTC and return
                # the exact committed snapshot. The legacy model omitted both.
                change_last_event(state, occurred_at_ns=values["occurred_at_ns"])
                return tx.snapshot()

            tx.commit_stage_state = commit
            yield tx

    monkeypatch.setattr(state["store"], "stage_transaction", exact_commit_result)
    previous = owner.perform

    def outside_lock(*args, **kwargs):
        assert not arrival._lock._is_owned()
        assert not any(k.startswith("_") for k in args[1])
        try:
            return previous(*args, **kwargs)
        except Exception:
            traceback.print_exc()
            raise

    monkeypatch.setattr(owner, "perform", outside_lock)
    return arrival, owner, state, source, runner


def rendered(arrival):
    snapshot = arrival.view()
    card = snapshot["usb_qualification"]
    _UsbQualificationDisplay._validate(card, snapshot)
    assert _UsbQualificationDisplay.validate(card, snapshot) == card
    for text in render_snapshot(snapshot):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert "USB_IDENTITY_NOT_VERIFIED" not in text
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in text
        assert "CAMERA_IDENTITY_NOT_VERIFIED" not in text
        assert "new app launch is not a reboot" in text
    return snapshot


def test_public_file_only_declaration_pending_original_export_and_cached_adoption(
    declared_prefix, monkeypatch
):
    arrival, owner, state, source, runner = declared_prefix
    initial = rendered(arrival)
    assert initial["usb_qualification"]["next_action"] == module.DECLARE
    page = render(initial, module.DECLARE)
    assert page["navigations"] == ["camera-action-" + module.DECLARE]
    original_payloads = deepcopy(state["payloads"])
    original_metadata = deepcopy(
        owner.setup.original_source_workflow()["camera_identity_cycles"]
    )
    before = state["reads"], state["enters"]
    ticket = _ticket(arrival, module.DECLARE, VALUES)
    assert before == (state["reads"], state["enters"])
    assert "no usb" in " ".join(ticket["effects"]).lower()
    previous = owner.perform

    def observe_pending(*args, **kwargs):
        result = previous(*args, **kwargs)
        assert owner.qualification_view()["publication"]["status"] == "PENDING"
        assert owner.qualification_view()["plan"] is None
        assert arrival.view()["usb_qualification"]["plan"] is None
        assert (
            result["device_open_count"] == 0
            and result["counter_coverage"] == "NO_DEVICE_IO"
        )
        return result

    monkeypatch.setattr(owner, "perform", observe_pending)
    with monkeypatch.context() as guard:
        guard.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: pytest.fail("declaration launched a process"),
        )
        queued = arrival.execute_action(ticket["ticket_id"])
        operation = _complete(arrival, queued["operation_id"])
        assert operation["status"] == "SUCCEEDED", json.dumps(operation, indent=2)
        assert (
            arrival.execute_action(ticket["ticket_id"])["operation_id"]
            == operation["operation_id"]
        )
    monkeypatch.setattr(owner, "perform", previous)
    view = rendered(arrival)
    card = view["usb_qualification"]
    assert card["status"] == "DECLARED" and card["next_action"] == module.BEGIN
    assert card["plan"]["operator_id"] == VALUES["operator_id"]
    assert card["plan"]["cable_label"] == VALUES["cable_label"]
    assert view["usb_identity"]["status"] == "HISTORICAL_HELD"
    workflow = owner.setup.original_source_workflow()
    assert workflow["schema"].endswith(".v9")
    trial = workflow["usb_qualification_trial"]
    assert trial["state"] == "PLAN_DECLARED"
    assert trial["plan"]["evidence_sha256"] == card["plan"]["plan_sha256"]
    assert (
        trial["request_event"]["occurred_at_ns"]
        <= trial["plan"]["document"]["created_at_utc_ns"]
        <= trial["declaration_event"]["occurred_at_ns"]
    )
    assert workflow["camera_identity_cycles"] == original_metadata
    assert all(
        state["payloads"][key] == value for key, value in original_payloads.items()
    )
    assert all(
        row["state"] == "PENDING" for row in owner.setup.session.view()["stages"][4:]
    )
    with pytest.raises(WizardError):
        _ticket(arrival, module.DECLARE, VALUES)
    exported = perform(arrival, module.EXPORT, {"confirm_metadata_export": True})
    directory = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    verify_export(directory)
    saved = json.loads((directory / "report.json").read_text(encoding="utf-8"))[
        "snapshot"
    ]
    restored = restore_usb_identity_diagnostics(
        saved,
        {
            path.name: path.read_bytes()
            for path in directory.glob("attachment-usb-identity-part-*.json")
        },
    )
    assert restored["qualification_trial"] == trial
    assert restored["schema"].endswith(".v2")
    assert rendered(arrival)["usb_qualification"]["publication"]["status"] == "CURRENT"
    generic = perform(arrival, "export_logs", {})
    general = Path(generic["result"]["receipt"]["path"])
    verify_export(general)
    report = json.loads((general / "report.json").read_text(encoding="utf-8"))
    assert (
        report["snapshot"]["usb_qualification"]["plan"]["plan_sha256"]
        == trial["plan"]["evidence_sha256"]
    )
    assert len(list(general.glob("attachment-*"))) <= 8
    # A new service instance adopts the actual retained cache only; no replay.
    before = state["reads"], state["enters"], len(state["events"])
    reopened = module.PhysicalUsbIdentityService(owner.setup)
    reopened.observe_setup()
    assert reopened.qualification_view()["plan"] == card["plan"]
    assert reopened.blocked_reason(module.DECLARE)
    assert before == (state["reads"], state["enters"], len(state["events"]))
    assert not runner.calls


@pytest.mark.parametrize("late", ["source", "stop", "log", "redaction"])
def test_late_declaration_publication_failure_keeps_exact_plan(
    declared_prefix, monkeypatch, late
):
    arrival, owner, state, source, runner = declared_prefix
    previous, log = owner.perform, arrival._log.append

    def after(*args, **kwargs):
        result = previous(*args, **kwargs)
        assert owner.qualification_view()["plan"] is None
        if late == "source":
            source["hash"] = "b" * 64
        elif late == "stop":
            kwargs["cancellation"].set()
        elif late == "log":
            monkeypatch.setattr(
                arrival._log,
                "append",
                lambda *a, **kw: (_ for _ in ()).throw(
                    OSError("modeled completion failure")
                ),
            )
        else:
            result["steps"][0]["report"]["meaning"] = "password=secret-fixture"
        return result

    monkeypatch.setattr(owner, "perform", after)
    operation = _run(arrival, module.DECLARE, VALUES)
    assert operation["status"] == (
        "SUCCEEDED" if late == "stop" else "FAILED"
    ), operation
    card = arrival.view()["usb_qualification"]
    assert card["publication"]["status"] == "HISTORICAL_HELD"
    assert card["next_action"] is None
    full = owner.retained_diagnostics()
    trial = full["qualification_trial"]
    assert trial["state"] == "PLAN_DECLARED"
    assert (
        digest(canonical(trial["plan"]["document"])) == trial["plan"]["evidence_sha256"]
    )
    assert owner.blocked_reason(module.DECLARE) is not None
    monkeypatch.setattr(owner, "perform", previous)
    monkeypatch.setattr(arrival._log, "append", log)
    if late != "log":
        perform(arrival, module.EXPORT, {"confirm_metadata_export": True})
    assert not runner.calls


def test_explicit_bounded_fields_and_cached_preflight_do_not_write(declared_prefix):
    arrival, owner, state, source, runner = declared_prefix
    before = (
        state["reads"],
        state["enters"],
        len(state["events"]),
        len(state["references"]),
    )
    assert {f["name"] for f in owner.fields(module.DECLARE)} == set(VALUES)
    assert all(f["default"] in {"", False} for f in owner.fields(module.DECLARE))
    for changes in (
        {"confirm_file_only": False},
        {"confirm_file_only": 1},
        {"operator_id": "é"},
        {"cable_label": ""},
        {"cable_label": "é" * 65},
        {"port_label": "port\nline"},
        {"port_label": " port"},
        {"path": "unaccepted"},
    ):
        with pytest.raises(WizardError):
            _ticket(arrival, module.DECLARE, {**VALUES, **changes})
        with pytest.raises(ValueError):
            owner.perform(
                module.DECLARE,
                {**VALUES, **changes},
                expected_context_sha256=owner.context_sha256(),
                cancellation=Event(),
                progress=lambda _: None,
            )
    owner.qualification_view()
    arrival.view()
    assert before == (
        state["reads"],
        state["enters"],
        len(state["events"]),
        len(state["references"]),
    )
    assert owner.blocked_reason(module.DECLARE) is None
    assert not runner.calls


@pytest.mark.parametrize("phase", ["requested", "plan"])
def test_partial_original_plan_is_exportable_without_replay(
    declared_prefix, monkeypatch, phase
):
    arrival, owner, state, source, runner = declared_prefix
    original_retain, perform_owner = owner._retain, owner.perform
    active = {}

    def perform_guard(*args, **kwargs):
        active["cancellation"] = kwargs["cancellation"]
        return perform_owner(*args, **kwargs)

    def retain(tx, artifact, role, trial_id):
        assert role == "qualification_plan"
        if phase == "requested":
            raise OSError("modeled failure before plan publication")
        ref = original_retain(tx, artifact, role, trial_id)
        active["cancellation"].set()
        return ref

    monkeypatch.setattr(owner, "perform", perform_guard)
    monkeypatch.setattr(owner, "_retain", retain)
    result = _run(arrival, module.DECLARE, VALUES)
    assert result["status"] in {"FAILED", "CANCELLED"}, result
    full = owner.retained_diagnostics()
    trial = full["qualification_trial"]
    assert trial["state"] == (
        "INCOMPLETE" if phase == "requested" else "PLAN_RETAINED_NOT_COMMITTED"
    )
    assert trial["declaration_event"] is None
    assert (trial["plan"] is None) == (phase == "requested")
    assert (
        arrival.view()["usb_qualification"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert owner.blocked_reason(module.DECLARE)
    before = len(state["events"]), len(state["references"])
    monkeypatch.setattr(owner, "perform", perform_owner)
    exported = perform(arrival, module.EXPORT, {"confirm_metadata_export": True})
    directory = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    verify_export(directory)
    saved = json.loads((directory / "report.json").read_text(encoding="utf-8"))[
        "snapshot"
    ]
    restored = restore_usb_identity_diagnostics(
        saved,
        {
            p.name: p.read_bytes()
            for p in directory.glob("attachment-usb-identity-part-*.json")
        },
    )
    assert restored["qualification_trial"] == trial
    assert before == (len(state["events"]), len(state["references"]))
    assert not runner.calls


def test_known_clean_original_v8_baseline_is_preserved_not_relabelled(
    declared_prefix, monkeypatch
):
    from rocell.application.physical_onboarding import _parse_evidence_reference
    from test_physical_camera_usb_readback import (
        baseline_subjects,
        retain_modeled_known_campaign,
    )

    arrival, owner, state, source, runner = declared_prefix
    workflow = owner.setup.original_source_workflow()
    metadata = workflow["camera_identity_cycles"][-1]
    # These are adapters around already verified immutable original bytes,
    # not new nominal metadata or a replacement baseline acquisition.
    originals = SimpleNamespace(
        refs={
            role: _parse_evidence_reference(metadata[role]["reference"])
            for role in module.METADATA_ROLES
        },
        subjects={
            role: SimpleNamespace(
                payload=canonical(metadata[role]["document"]),
                sha256=metadata[role]["evidence_sha256"],
                to_dict=lambda document=metadata[role]["document"]: deepcopy(document),
            )
            for role in module.METADATA_ROLES
        },
    )
    case = (owner.setup.session, owner.setup.current_prerequisite_artifact(), state)
    made = retain_modeled_known_campaign(baseline_subjects(case, metadata=originals))
    monkeypatch.setattr(
        usb_readback, "read_original_usb_campaigns", lambda *a: made.original_campaigns
    )
    operation = _run(arrival, "physical_camera_refresh", {})
    assert operation["status"] == "SUCCEEDED", operation
    before = deepcopy(owner.setup.original_source_workflow()["usb_baseline"])
    assert before["state"] == "RETAINED_BLOCKED"
    assert owner.blocked_reason(module.DECLARE) is None
    result = _run(arrival, module.DECLARE, VALUES)
    assert result["status"] == "SUCCEEDED", result
    workflow = owner.setup.original_source_workflow()
    assert workflow["usb_baseline"] == before
    plan = workflow["usb_qualification_trial"]["plan"]["document"]
    assert (
        plan["created_at_utc_ns"] > before["execution"]["document"]["finished_utc_ns"]
    )
    assert "phases" not in workflow["usb_qualification_trial"]
    view = rendered(arrival)
    assert view["usb_identity"]["status"] == "HISTORICAL_HELD"
    assert view["usb_qualification"]["status"] == "DECLARED"
    assert not runner.calls
