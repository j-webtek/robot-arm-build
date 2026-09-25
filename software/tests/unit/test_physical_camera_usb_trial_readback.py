"""Real typed originals; modeled unit facts. No phase/device query is performed."""

from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from threading import Event
import os
import time

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_trial_readback as trial
from rocell.application import physical_camera_usb_readback as usb_reader
from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    _parse_evidence_reference,
)
from rocell.application.physical_onboarding_v2 import V2StageState, V2JournalEvent
from rocell.providers.windows.native_camera_protocol import canonical
from test_physical_camera_identity_readback import (
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    initial_epoch,
    identity_subjects,
    identity_inputs,
    refresh_read,
    actual_identity_entry,
    actual_transaction_state,
)
from test_physical_camera_usb_readback import (
    baseline_subjects,
    retain_modeled_known_campaign,
)
from test_physical_camera_session import LAUNCH, SOURCE, session_fixture, perform
from test_physical_camera_intake_session import read

TRIAL = "usbtrial-" + "d" * 32


def change_last_event(fixture_state, **changes):
    old = fixture_state["events"][-1]
    values = {
        key: getattr(old, key)
        for key in (
            "sequence",
            "stage",
            "previous_state",
            "state",
            "occurred_at_ns",
            "previous_event_sha256",
            "evidence",
            "detail_code",
        )
    }
    values.update(changes)
    fixture_state["events"][-1] = V2JournalEvent.build(
        header=fixture_state["header"], **values
    )


@pytest.fixture
def ready(identity_ready, monkeypatch):
    initial_epoch(identity_ready)
    identity_ready[2]["identity_subjects"] = identity_subjects(
        identity_ready, **identity_inputs()
    )
    monkeypatch.setattr(usb_reader, "read_original_usb_campaigns", lambda *a: ())
    return identity_ready


def declare(case, *, phase="declared", before=None, **changes):
    """Use actual immutable plan and journal codecs; scope/file seam is modeled."""
    before = before or refresh_read(case)
    owner, prerequisites, state = case
    refs = trial.usb_qualification_predecessor_references(before)
    state["advance"](
        V2StageState.WAITING_OPERATOR,
        trial.usb_qualification_event("REQUESTED", TRIAL),
        refs,
        stage=STAGE_ORDER[3],
    )
    # Existing source-model fixture uses tiny journal times; new declaration
    # has its own faithful UTC bracket after the prior received review.
    timestamp = time.time_ns()
    change_last_event(state, occurred_at_ns=timestamp)
    if phase == "requested":
        return None, before
    fields = dict(
        trial_id=TRIAL,
        operator_id="trial-operator",
        launch_session_id=LAUNCH,
        cable_label="Operator-declared cable, not verified",
        port_label="Declared port A",
        created_at_utc_ns=timestamp + 1,
    )
    fields.update(changes)
    plan = trial.build_original_usb_qualification_plan(prerequisites, before, **fields)
    ref = state["add"](
        plan.payload, label=trial.TRIAL_LABEL_PREFIX + TRIAL, stage=STAGE_ORDER[3]
    )
    if phase == "declared":
        state["advance"](
            V2StageState.REVIEW_PENDING,
            trial.usb_qualification_event("DECLARED", TRIAL),
            (ref,),
            stage=STAGE_ORDER[3],
        )
        change_last_event(state, occurred_at_ns=timestamp + 2)
    return plan, before


@pytest.mark.parametrize(
    "phase,state",
    [
        ("requested", "INCOMPLETE"),
        ("plan", "PLAN_RETAINED_NOT_COMMITTED"),
        ("declared", "PLAN_DECLARED"),
    ],
)
def test_exact_v7_prefix_and_partial_original_declaration(ready, phase, state):
    plan, before = declare(ready, phase=phase)
    value = refresh_read(ready)
    assert value["schema"] == session.SOURCE_WORKFLOW_USB_TRIAL_SCHEMA
    assert value["camera_identity_cycles"] == before["camera_identity_cycles"]
    assert "usb_baseline" not in value
    row = value["usb_qualification_trial"]
    assert set(row) == {
        "trial_id",
        "state",
        "request_event",
        "declaration_event",
        "plan",
    }
    assert row["state"] == state
    if plan:
        assert canonical(row["plan"]["document"]) == plan.payload
        assert row["plan"]["evidence_sha256"] == plan.sha256
        assert plan.to_dict()["phases"] == [
            "BASELINE",
            "RECONNECT_ABSENCE",
            "AFTER_RECONNECT",
            "AFTER_REBOOT",
        ]
    assert all(
        stage.state is V2StageState.PENDING
        for stage in ready[2]["snapshot"]().stages[4:]
    )
    raw = canonical(value)
    assert session._decode_cached_source_workflow(raw) == value
    value["usb_qualification_trial"]["state"] = "FORGED"
    assert (
        ready[0].retained_source_workflow()["usb_qualification_trial"]["state"] == state
    )


def test_known_clean_v8_remains_original_diagnostic_not_series_baseline(
    ready, monkeypatch
):
    # Use the already modeled metadata chain, not a second metadata cycle.
    metadata = ready[2]["identity_subjects"]
    made = retain_modeled_known_campaign(baseline_subjects(ready, metadata=metadata))
    monkeypatch.setattr(
        usb_reader, "read_original_usb_campaigns", lambda *a: made.original_campaigns
    )
    plan, before = declare(ready)
    restored = refresh_read(ready)
    assert restored["usb_baseline"] == before["usb_baseline"]
    assert restored["usb_baseline"]["outcome"]["document"]["outcome"] == "HELD"
    assert "phases" not in restored["usb_qualification_trial"]
    assert (
        plan.to_dict()["created_at_utc_ns"]
        > made.subjects["execution"].to_dict()["finished_utc_ns"]
    )


@pytest.mark.parametrize(
    "fault", ["missing-epoch", "partial-metadata", "v8-partial", "quarantine"]
)
def test_no_declaration_from_partial_or_uncertain_context(ready, fault):
    value = refresh_read(ready)
    if fault == "missing-epoch":
        value["configuration_epochs"] = None
    elif fault == "partial-metadata":
        value["camera_identity_cycles"][-1]["state"] = "INCOMPLETE"
    else:
        value["schema"] = session.SOURCE_WORKFLOW_USB_SCHEMA
        value["usb_baseline"] = dict(
            state=(
                "ORIGINAL_CAMPAIGN_HELD" if fault == "quarantine" else "READY_TO_QUERY"
            )
        )
    with pytest.raises(ValueError):
        trial.usb_qualification_predecessor_references(value)


@pytest.mark.parametrize(
    "fault",
    [
        "extra-role",
        "wrong-stage",
        "unknown-event",
        "second-trial",
        "early-plan",
        "modeled-mode",
        "received-reference",
        "source",
        "pass",
    ],
)
def test_full_snapshot_rejects_foreign_suffix_or_plan(ready, fault):
    plan, before = declare(ready)
    state = ready[2]
    if fault in {"extra-role", "wrong-stage", "second-trial"}:
        state["add"](
            plan.payload,
            label=(
                "unowned-trial-role"
                if fault == "extra-role"
                else trial.TRIAL_LABEL_PREFIX
                + ("usbtrial-" + "e" * 32 if fault == "second-trial" else TRIAL)
            ),
            stage=STAGE_ORDER[4] if fault == "wrong-stage" else STAGE_ORDER[3],
        )
    elif fault in {"unknown-event", "pass"}:
        change_last_event(
            state,
            detail_code=(
                "UNOWNED_TRIAL_EVENT"
                if fault == "unknown-event"
                else state["events"][-1].detail_code
            ),
            state=V2StageState.PASS if fault == "pass" else V2StageState.REVIEW_PENDING,
        )
    else:
        document = plan.to_dict()
        if fault == "early-plan":
            document["created_at_utc_ns"] = 1
        elif fault == "modeled-mode":
            document["mode"] = "MODELED"
        elif fault == "source":
            document["binding"]["source_sha256"] = "f" * 64
        else:
            document["received"][0]["reference"]["evidence_id"] = "evidence-" + "f" * 64
        # Change fully retained bytes/reference and cited event together. Hash
        # recomputation alone must not authenticate a wrong original subject.
        old = state["events"][-1].evidence[0]
        state["references"].remove(old)
        new = state["add"](
            canonical(document),
            label=trial.TRIAL_LABEL_PREFIX + TRIAL,
            stage=STAGE_ORDER[3],
        )
        change_last_event(state, evidence=(new,))
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)


def test_old_public_reader_rejects_trial_suffix(ready, monkeypatch):
    from rocell.application.physical_camera_identity_readback import (
        verify_camera_identity_workflow,
    )

    declare(ready)
    captures = []
    original = session._verify_original_source_roles

    def capture(*args, **kwargs):
        captures.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(session, "_verify_original_source_roles", capture)
    refresh_read(ready)
    with pytest.raises(session.PhysicalCameraSessionError):
        verify_camera_identity_workflow(*captures[-1][:11])


def test_pure_plan_restoration_never_reads_files_or_creates_process(ready, monkeypatch):
    plan, _ = declare(ready)

    def denied(*a, **k):
        pytest.fail("pure trial restoration read a file")

    monkeypatch.setattr(Path, "open", denied)
    assert trial.UsbQualificationPlan(plan.payload).payload == plan.payload


@pytest.mark.parametrize(
    "fault", ["late-stop", "late-source", "late-deadline", "lease-exit"]
)
def test_late_readback_hold_preserves_complete_plan(ready, monkeypatch, fault):
    plan, _ = declare(ready)
    owner, _, state = ready
    cancellation = Event()
    original = session._verify_original_source_roles

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if fault == "late-stop":
            cancellation.set()
        elif fault == "late-source":
            state["source"] = "f" * 64
        elif fault == "late-deadline":
            state["now"] += session.DIAGNOSTIC_TIMEOUT_NS
        return result

    monkeypatch.setattr(session, "_verify_original_source_roles", late)
    state["exit_failure"] = fault == "lease-exit"
    with pytest.raises((session.PhysicalCameraSessionError, RuntimeError)):
        refresh_read(ready, cancellation=cancellation)
    value = owner.retained_source_workflow()
    assert (
        canonical(value["usb_qualification_trial"]["plan"]["document"]) == plan.payload
    )
    assert owner.view()["status"] == "HELD"


def test_changed_initial_epoch_cannot_be_hidden_by_trial_suffix(ready):
    declare(ready)
    state = ready[2]
    old = next(
        ref
        for ref in state["references"]
        if session.CONFIGURATION_EPOCH_LABEL.encode()
        in state["manifests"][ref.evidence_id]
    )
    import json

    document = json.loads(state["payloads"][old.evidence_id])
    document["binding"]["source_sha256"] = "f" * 64
    state["references"].remove(old)
    state["add"](canonical(document), label=session.CONFIGURATION_EPOCH_LABEL)
    with pytest.raises(session.PhysicalCameraSessionError):
        refresh_read(ready)


@pytest.mark.skipif(os.name != "nt", reason="Actual qualified NTFS original required")
def test_actual_ntfs_declared_and_partial_originals_reopen_without_replay(
    workspace, monkeypatch
):
    case = actual_identity_entry(
        workspace, monkeypatch, include_configuration_epochs=True
    )
    owner, prerequisites, state = case
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        state.update(
            actual_transaction_state(tx), events=tx.snapshot().committed_events
        )
        identity_subjects(case, **identity_inputs())
    perform(owner, "refresh")
    before = read(owner, state["header"].header_sha256)
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        current = actual_transaction_state(tx)
        current["advance"](
            V2StageState.WAITING_OPERATOR,
            trial.usb_qualification_event("REQUESTED", TRIAL),
            trial.usb_qualification_predecessor_references(before),
            stage=STAGE_ORDER[3],
        )
        plan = trial.build_original_usb_qualification_plan(
            prerequisites,
            before,
            trial_id=TRIAL,
            operator_id="modeled-file-declaration",
            launch_session_id=LAUNCH,
            cable_label="MODELED cable",
            port_label="MODELED port",
            created_at_utc_ns=time.time_ns(),
        )
        ref = current["add"](
            plan.payload, label=trial.TRIAL_LABEL_PREFIX + TRIAL, stage=STAGE_ORDER[3]
        )
    fresh = session_fixture(workspace)
    perform(fresh, "refresh")
    partial = read(fresh, state["header"].header_sha256)
    assert partial["usb_qualification_trial"]["state"] == "PLAN_RETAINED_NOT_COMMITTED"
    assert (
        canonical(partial["usb_qualification_trial"]["plan"]["document"])
        == plan.payload
    )
    # Explicit test-owned completion, not service replay/recovery. Production
    # exposes the partial as held and does not complete it automatically.
    with fresh.stage_transaction(
        expected_challenge_sha256=fresh.view()["verification"]["challenge_sha256"]
    ) as tx:
        actual_transaction_state(tx)["advance"](
            V2StageState.REVIEW_PENDING,
            trial.usb_qualification_event("DECLARED", TRIAL),
            (ref,),
            stage=STAGE_ORDER[3],
        )
    reopened = session_fixture(workspace)
    perform(reopened, "refresh")
    full = read(reopened, state["header"].header_sha256)
    assert full["usb_qualification_trial"]["state"] == "PLAN_DECLARED"
    assert (
        canonical(full["usb_qualification_trial"]["plan"]["document"]) == plan.payload
    )
    assert all(row["state"] == "PENDING" for row in reopened.view()["stages"][4:])
    assert full["camera_identity_cycles"] == before["camera_identity_cycles"]
