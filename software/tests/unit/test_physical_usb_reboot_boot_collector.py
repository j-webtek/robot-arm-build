"""One-shot collector over MODELED original transactions and in-memory boot facts.

The fixed whole-original reader is modeled at its explicit same-transaction
boundary. Actual immutable preparation, permit, review, intent and report codecs
remain active. These tests do NOT claim an M1 audit, process, CIM or USB run.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import os
import subprocess

import pytest

from rocell.application import physical_usb_reboot_boot as m
from rocell.application import physical_camera_session as session
from rocell.application.usb_identity_stage_policy import (
    UsbIdentityPolicyReview,
    UsbIdentityAdmissionIdentity,
)
from rocell.providers.windows import host_boot_observation as host
from test_physical_camera_usb_reboot_preparation import prepared_case
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_reboot_phase import predecessor, _modeled_boot
from test_physical_usb_presence_binding import reference


@pytest.fixture(autouse=True)
def no_process_or_devices(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Collector model attempted process, CIM or device access")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)
    monkeypatch.setattr(host.LocalCimHostBootExecutor, "execute", denied)


def journal(c, kind, previous, state, refs, sequence, timestamp, previous_hash):
    event = m.V2JournalEvent(
        c.binding["session_id"],
        c.binding["header_sha256"],
        sequence,
        m._STAGE,
        previous,
        state,
        timestamp,
        previous_hash,
        m._refs(*refs),
        kind,
        "0" * 64,
    )
    return m._parse_event(
        replace(event, event_sha256=m.digest(m.canonical(event.core_dict()))).to_dict()
    )


@pytest.fixture
def case(prepared_case, monkeypatch):
    p = prepared_case
    c = SimpleNamespace(
        pure=p,
        subject=p.subject,
        binding=p.args["original_baseline"]["plan"].to_dict()["binding"],
    )
    c.phase_id, c.start = p.args["phase_id"], p.args["phase_start_event"]
    c.workspace = Path(p.args["operation"].to_dict()["workspace"])
    c.predecessor = {
        key: p.args[key]
        for key in (
            "original_baseline",
            "received",
            "absence",
            "absence_reference",
            "absence_sources",
            "reconnect",
            "reconnect_reference",
            "reconnect_sources",
            "reconnect_permit",
        )
    }
    prep_ref = reference(p.prepared.payload, "MODELED-reboot-collector-preparation")
    c.intent = m.build_usb_reboot_boot_intent(
        preparation=p.prepared,
        preparation_reference=prep_ref,
        reconnect=p.args["reconnect"],
        reconnect_reference=p.args["reconnect_reference"],
    )
    c.intent_ref = reference(c.intent.payload, "MODELED-reboot-collector-intent")
    runtime_review = p.subject.run.preparation.review
    r = runtime_review.to_dict()
    policy = UsbIdentityPolicyReview(
        m.canonical(
            dict(
                schema="rocell.usb_identity_stage_policy_review.v1",
                **{
                    key: c.binding[key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                },
                policy=m.qualification.usb_identity_stage_policy().to_dict(),
                policy_sha256=c.binding["stage_policy_sha256"],
                operator_id=r["operator_id"],
                reviewer_id=r["reviewer_id"],
                reviewed_at_utc_ns=r["reviewed_at_ns"],
                purpose="REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
                physical_authority=False,
                hardware_qualified=False,
                camera_capture_authorized=False,
                arm_access_authorized=False,
                motion_authorized=False,
                contact_authorized=False,
            )
        )
    )
    policy_ref = reference(policy.payload, "MODELED-reboot-collector-policy-review")
    runtime_ref = reference(
        runtime_review.payload, "MODELED-reboot-collector-runtime-review"
    )
    identity_data = p.subject.campaign.identity.to_dict()
    identity_data.update(
        policy_review_sha256=policy.sha256,
        original_subjects=[
            dict(role=role, document_sha256=ref.payload_sha256, reference=ref.to_dict())
            for role, ref in (
                ("metadata", p.args["enrollment_reference"]),
                ("policy_review", policy_ref),
                ("runtime_review", runtime_ref),
            )
        ],
    )
    identity = UsbIdentityAdmissionIdentity(m.canonical(identity_data))
    c.refs = dict(
        operator_event=p.args["operator_event_reference"],
        enrollment=p.args["enrollment_reference"],
        preparation=prep_ref,
        operation=reference(
            p.subject.operation.payload, "MODELED-reboot-collector-operation"
        ),
        policy_review=policy_ref,
        runtime_review=runtime_ref,
        identity=reference(identity.payload, "MODELED-reboot-collector-identity"),
        boot_request=c.intent_ref,
    )
    c.raw = dict(
        operator_event=p.subject.event.payload,
        enrollment=p.args["enrollment"],
        preparation=p.prepared.payload,
        operation=p.subject.operation.payload,
        policy_review=policy.payload,
        runtime_review=runtime_review.payload,
        identity=identity.payload,
        boot_request=c.intent.payload,
    )
    c.payloads = {c.refs[role]: raw for role, raw in c.raw.items()}
    old = p.args["reconnect"].to_dict()
    old_refs = [m.qualification._reference(row["reference"]) for row in old["records"]]
    for row in old["records"]:
        c.payloads[m.qualification._reference(row["reference"])] = p.args[
            "reconnect_sources"
        ][row["role"]]
    c.payloads[p.args["reconnect_reference"]] = p.args["reconnect"].payload
    # Five unused old role slots model the fixed reader's prior full audit.
    # They are not offered as authentic old role codecs or original M1 proof.
    for index in range(5):
        raw = m.canonical({"MODELED_PREVIOUS_READER_ROLE": index})
        ref = reference(raw, "MODELED-reboot-old-slot-" + str(index))
        old_refs.append(ref)
        c.payloads[ref] = raw
    old_refs.append(p.args["reconnect_reference"])
    c.old_terminal = journal(
        c,
        "CAMERA_USB_TRIAL_RECONNECT_RETAINED_"
        + old["context"]["operation_id"][9:].upper(),
        m.V2StageState.WAITING_OPERATOR,
        m.V2StageState.BLOCKED,
        old_refs,
        c.start.sequence - 1,
        old["context"]["finished_at_utc_ns"] + 1,
        "a" * 64,
    )
    c.prepared = journal(
        c,
        m.usb_reboot_event("PREPARED", c.phase_id),
        m.V2StageState.WAITING_OPERATOR,
        m.V2StageState.REVIEW_PENDING,
        tuple(c.refs.values())[:4],
        c.start.sequence + 1,
        p.args["prepared_at_utc_ns"],
        c.start.event_sha256,
    )
    c.reviewed = journal(
        c,
        m.usb_reboot_event("REVIEWED", c.phase_id),
        m.V2StageState.REVIEW_PENDING,
        m.V2StageState.BLOCKED,
        tuple(c.refs.values()),
        c.prepared.sequence + 1,
        r["reviewed_at_ns"] + 1,
        c.prepared.event_sha256,
    )
    c.events = [
        p.args["original_baseline"]["declaration_event"],
        c.old_terminal,
        c.start,
        c.prepared,
        c.reviewed,
    ]
    phase = dict(
        phase="AFTER_REBOOT",
        phase_id=c.phase_id,
        state="REVIEWED",
        events=[event.to_dict() for event in (c.start, c.prepared, c.reviewed)],
        original_campaign=None,
        original_campaign_event=None,
        **{role: None for role in m.USB_REBOOT_ROLE_BYTES},
    )
    for role in c.refs:
        phase[role] = dict(
            document=m.qualification._load(c.raw[role], m.USB_REBOOT_ROLE_BYTES[role]),
            reference=c.refs[role].to_dict(),
            evidence_sha256=m.digest(c.raw[role]),
            retention="M1_FULL_BYTES_READ_BACK",
        )
    c.workflow = dict(
        schema=m.SOURCE_WORKFLOW_USB_REBOOT_SCHEMA, usb_qualification_reboot=phase
    )
    c.states = {
        stage: m.V2StageState.PASS if n < 3 else m.V2StageState.PENDING
        for n, stage in enumerate(m.STAGE_ORDER)
    }
    c.states[m._STAGE] = m.V2StageState.BLOCKED
    c.header = SimpleNamespace(
        **{key: c.binding[key] for key in ("cell_id", "session_id", "header_sha256")},
        source_binding_sha256=m.physical_camera_source_binding(
            c.binding["source_sha256"]
        ),
    )
    c.leases = (
        m.LeaseSpec(m.LeaseLevel.CELL, c.binding["cell_id"]),
        m.LeaseSpec(m.LeaseLevel.SESSION, c.binding["session_id"]),
    )
    c.cancel, c.deadline, c.clock = Event(), 60_000_000_001, 1
    c.source, c.reconciliation, c.wall = (
        c.binding["source_sha256"],
        False,
        c.reviewed.occurred_at_ns + 1,
    )
    c.calls, c.stored = [], []

    def snapshot():
        return SimpleNamespace(
            header=c.header,
            committed_events=tuple(c.events),
            head=SimpleNamespace(head_sha256=c.events[-1].event_sha256),
            evidence=tuple(c.payloads),
            reconciliation_required=c.reconciliation,
            state_for=lambda stage: c.states[stage],
        )

    c.snapshot = snapshot

    def read(ref):
        c.calls.append(("read", ref))
        return c.payloads[ref]

    def store(
        stage, payload, *, label, media_type, captured_at_ns, expected_head_sha256
    ):
        assert stage is m._STAGE and media_type == "application/json"
        assert expected_head_sha256 == snapshot().head.head_sha256
        ref = reference(payload, label)
        c.payloads[ref] = payload
        c.calls.append(("store", ref))
        c.stored.append((ref, payload))
        return ref

    def commit(
        stage, state, *, occurred_at_ns, detail_code, expected_head_sha256, evidence
    ):
        assert expected_head_sha256 == snapshot().head.head_sha256
        event = journal(
            c,
            detail_code,
            c.states[stage],
            state,
            evidence,
            c.events[-1].sequence + 1,
            occurred_at_ns,
            c.events[-1].event_sha256,
        )
        c.events.append(event)
        c.states[stage] = state
        c.calls.append(("commit", detail_code))
        return snapshot()

    def originals(tx, **kwargs):
        c.calls.append(("authenticate", kwargs))
        assert tx is c.tx
        assert kwargs == dict(
            workspace=c.workspace,
            source_sha256=c.binding["source_sha256"],
            launch_session_id=c.intent.to_dict()["launch_session_id"],
            expected_header_sha256=c.binding["header_sha256"],
            cancellation=c.cancel,
            deadline_ns=c.deadline,
        )
        return snapshot(), deepcopy(c.workflow), c.predecessor

    c.tx = object.__new__(m.M1PhysicalCameraTransaction)
    monkeypatch.setattr(
        m.M1PhysicalCameraTransaction, "held_leases", property(lambda self: c.leases)
    )
    monkeypatch.setattr(c.tx, "snapshot", snapshot)
    monkeypatch.setattr(c.tx, "read_stage_evidence", read)
    monkeypatch.setattr(c.tx, "store_evidence", store)
    monkeypatch.setattr(c.tx, "commit_stage_state", commit)
    monkeypatch.setattr(m, "read_usb_reboot_boot_originals", originals)
    monkeypatch.setattr(m, "source_fingerprint", lambda path: c.source)
    monkeypatch.setattr(m, "monotonic_ns", lambda: c.clock)
    monkeypatch.setattr(m, "time_ns", lambda: c.wall)
    monkeypatch.setattr(
        m,
        "WindowsHostBootObserver",
        lambda: pytest.fail("Observer constructed before installed test model"),
    )
    c.collector = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)
    return c


def install_observer(
    c, monkeypatch, *, epoch=None, host_change=False, uncertain=False, after=None
):
    class Observer:
        def observe(self, request, **kwargs):
            c.calls.append(("observe", request))
            assert c.events[-1].detail_code == m.usb_reboot_event(
                "BOOT_REQUESTED", c.phase_id
            )
            assert kwargs["cancellation"] is c.cancel
            assert (
                request.expires_at_ns
                == kwargs["deadline_ns"]
                == 30_000_000_001
                <= c.deadline
            )
            kwargs["admission_check"]()
            c.report = _modeled_boot(
                c.pure.args["original_baseline"]["plan"],
                c.subject.context,
                boot_epoch=(
                    c.intent.to_dict()["phase_started_at_utc_ns"]
                    if epoch is None
                    else epoch
                ),
                origin="WINDOWS_LOCAL_CIM",
                host_change=host_change,
                cleanup_uncertain=uncertain,
            )
            assert c.report.to_dict()["request"] == request.to_dict()
            c.wall = c.report.to_dict()["execution"]["finished_utc_ns"] + 1
            if after:
                after()
            return c.report

    monkeypatch.setattr(m, "WindowsHostBootObserver", Observer)


def collect(c, **changes):
    args = dict(
        intent_reference=c.intent_ref,
        cancellation=c.cancel,
        deadline_ns=c.deadline,
        revalidate_context=lambda: None,
    )
    args.update(changes)
    return c.collector.collect(c.tx, **args)


def test_constructor_inert_exact_type_and_detached(case, monkeypatch):
    c = case
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("Constructor opened file")
    )
    fresh = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)
    d = fresh.retained_diagnostics()
    assert d["state"] == "NOT_STARTED" and not c.calls
    assert all(d[key] is False for key in m._FLAGS)
    d["state"] = "invented"
    assert fresh.retained_diagnostics()["state"] == "NOT_STARTED"
    for path, intent in (
        (Path("relative"), c.intent),
        (str(c.workspace), c.intent),
        (c.workspace, c.intent.payload),
    ):
        with pytest.raises(
            m.UsbRebootBootError, match="EXACT_REBOOT_BOOT_COLLECTOR_REQUIRED"
        ):
            m.OriginalUsbRebootBootCollector(path, intent)


def test_exact_reviewed_request_observe_retention_and_no_replay(case, monkeypatch):
    c = case
    previous = tuple((ref, raw) for ref, raw in c.payloads.items())
    install_observer(c, monkeypatch)
    record = collect(c)
    d = c.collector.retained_diagnostics()
    assert d["state"] == "BOOT_RETAINED" and d["context_current"] is True
    assert d["boot_comparison"]["status"] == "SAME_HOST_DIFFERENT_BOOT"
    assert record == d["host_boot"] and record["document"] == c.report.to_dict()
    assert record["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert len(c.stored) == 1 and c.stored[0][1] == c.report.payload
    request_index = c.calls.index(
        ("commit", m.usb_reboot_event("BOOT_REQUESTED", c.phase_id))
    )
    assert request_index < next(
        n for n, row in enumerate(c.calls) if row[0] == "observe"
    )
    assert set(c.refs.values()) <= {
        row[1] for row in c.calls[:request_index] if row[0] == "read"
    }
    assert all(c.payloads[ref] == raw for ref, raw in previous)
    assert all(c.states[stage] is m.V2StageState.PENDING for stage in m.STAGE_ORDER[4:])
    assert c.events[-1].evidence == m._refs(c.intent_ref, c.stored[0][0])
    assert c.intent.to_dict()["budget"] == dict(
        admission_window_ms=30000, process_run_ms=10000, cleanup_ms=2000
    )
    with pytest.raises(m.UsbRebootBootError, match="ALREADY_USED"):
        collect(c)
    c.collector = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)
    # The fixed reader would reject a terminal source; modeled current records
    # also fail their exact event membership before another request is written.
    with pytest.raises(m.UsbRebootBootError):
        collect(c)
    assert sum(row[0] == "observe" for row in c.calls) == 1


def test_same_boot_wrong_host_and_epoch_bounds_hold(case, monkeypatch):
    c = case
    original_events, original_payloads = list(c.events), dict(c.payloads)
    lower = c.intent.to_dict()["reconnect_finished_at_utc_ns"]
    upper = c.intent.to_dict()["phase_started_at_utc_ns"]
    old_boot = host.HostBootObservation(c.predecessor["reconnect_sources"]["host_boot"])
    same_epoch = host._utc_ns(old_boot.to_dict()["response"]["last_boot_up_time_utc"])
    for changes in (
        dict(epoch=same_epoch),
        dict(epoch=lower),
        dict(epoch=upper + 1000),
        dict(host_change=True),
    ):
        c.events[:], c.payloads = original_events, dict(original_payloads)
        c.states[m._STAGE], c.wall = (
            m.V2StageState.BLOCKED,
            c.reviewed.occurred_at_ns + 1,
        )
        c.collector = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)
        install_observer(c, monkeypatch, **changes)
        record = collect(c)
        assert record["document"] == c.report.to_dict()
        assert c.collector.retained_diagnostics()["state"] == "BOOT_HELD", changes


@pytest.mark.parametrize("timing", ["after_report", "during_store", "during_readback"])
def test_stop_or_source_loss_retains_and_uncertainty_is_monotone(
    case, monkeypatch, timing
):
    c = case
    old_store, old_read = c.tx.store_evidence, c.tx.read_stage_evidence

    def lose():
        if timing == "during_readback":
            c.source = "b" * 64
        else:
            c.cancel.set()

    def store(*args, **kwargs):
        ref = old_store(*args, **kwargs)
        if timing == "during_store":
            lose()
        return ref

    def read(ref):
        raw = old_read(ref)
        if c.stored and ref == c.stored[-1][0] and timing == "during_readback":
            lose()
        return raw

    monkeypatch.setattr(c.tx, "store_evidence", store)
    monkeypatch.setattr(c.tx, "read_stage_evidence", read)
    install_observer(
        c, monkeypatch, uncertain=True, after=lose if timing == "after_report" else None
    )
    record = collect(c)
    d = c.collector.retained_diagnostics()
    assert d["context_current"] is False and d["state"] == "BOOT_UNCERTAIN"
    assert record["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert record["document"]["execution"]["cleanup_errors"]
    assert c.events[-1].state is m.V2StageState.SIDE_EFFECT_UNCERTAIN


def test_clean_report_stop_during_store_is_held(case, monkeypatch):
    c = case
    old = c.tx.store_evidence

    def store(*args, **kwargs):
        ref = old(*args, **kwargs)
        c.cancel.set()
        return ref

    monkeypatch.setattr(c.tx, "store_evidence", store)
    install_observer(c, monkeypatch)
    assert collect(c)["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert c.collector.retained_diagnostics()["state"] == "BOOT_HELD"


def test_pending_request_constructor_failure_has_no_replay(case, monkeypatch):
    c = case
    with pytest.raises(pytest.fail.Exception, match="Observer constructed"):
        collect(c)
    d = c.collector.retained_diagnostics()
    assert d["requested_event"] == c.events[-1].to_dict() and d["host_boot"] is None
    assert c.events[-1].detail_code == m.usb_reboot_event("BOOT_REQUESTED", c.phase_id)
    c.collector = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)
    with pytest.raises(m.UsbRebootBootError, match="CURRENT_REVIEWED"):
        collect(c)
    assert not c.stored


def test_original_events_roles_permit_and_independent_read_failure_refuse(
    case, monkeypatch
):
    c = case
    events, payloads, workflow, predecessor_inputs = (
        list(c.events),
        dict(c.payloads),
        deepcopy(c.workflow),
        dict(c.predecessor),
    )

    def reset():
        c.events[:], c.payloads, c.workflow, c.predecessor = (
            list(events),
            dict(payloads),
            deepcopy(workflow),
            dict(predecessor_inputs),
        )
        c.calls.clear()
        c.collector = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)

    for omitted in (events[0], c.old_terminal, c.start, c.prepared, c.reviewed):
        reset()
        c.events.remove(omitted)
        with pytest.raises(m.UsbRebootBootError):
            collect(c)
        assert not any(row[0] == "commit" for row in c.calls)
    for role in c.refs:
        reset()
        c.payloads[c.refs[role]] += b" "
        with pytest.raises(ValueError):
            collect(c)
        assert not any(row[0] == "commit" for row in c.calls)
    reset()
    c.predecessor["reconnect_permit"] = c.subject.permit
    with pytest.raises(ValueError):
        collect(c)
    assert not any(row[0] == "commit" for row in c.calls)
    reset()

    def fail(*args, **kwargs):
        raise ValueError("MODELED_AUTHENTICATION_FAILED")

    monkeypatch.setattr(m, "read_usb_reboot_boot_originals", fail)
    with pytest.raises(ValueError, match="MODELED_AUTHENTICATION_FAILED"):
        collect(c)
    assert not c.stored


def test_pre_request_stop_scope_guard_header_and_inventory_refuse(case, monkeypatch):
    c = case
    header, leases = c.header, c.leases

    def reset():
        c.header, c.leases, c.source, c.clock = (
            header,
            leases,
            c.binding["source_sha256"],
            1,
        )
        c.cancel.clear()
        c.collector = m.OriginalUsbRebootBootCollector(c.workspace, c.intent)

    for fault in ("stop", "source", "deadline", "leases", "header", "guard"):
        reset()
        changes = {}
        if fault == "stop":
            c.cancel.set()
        if fault == "source":
            c.source = "b" * 64
        if fault == "deadline":
            c.clock = c.deadline
        if fault == "leases":
            c.leases = leases[:1]
        if fault == "header":
            c.header = SimpleNamespace(**{**vars(header), "header_sha256": "b" * 64})
        if fault == "guard":
            changes["revalidate_context"] = lambda: False
        with pytest.raises(m.UsbRebootBootError):
            collect(c, **changes)
    reset()
    original = m.read_usb_reboot_boot_originals

    def extra(tx, **kwargs):
        snap, workflow, previous = original(tx, **kwargs)
        raw = b'{"MODELED_UNEXPECTED_INVENTORY":true}'
        c.payloads[reference(raw, "MODELED-extra")] = raw
        return c.snapshot(), workflow, previous

    monkeypatch.setattr(m, "read_usb_reboot_boot_originals", extra)
    with pytest.raises(m.UsbRebootBootError, match="BOOT_ORIGINAL_HEAD_CHANGED"):
        collect(c)
    assert not any(row[0] == "commit" for row in c.calls)


@pytest.mark.parametrize("failure", ["store", "readback", "terminal"])
def test_failed_retention_keeps_returned_bytes_and_any_original_reference(
    case, monkeypatch, failure
):
    c = case
    install_observer(c, monkeypatch)
    if failure == "store":

        def fail(*args, **kwargs):
            raise ValueError("MODELED_STORE_FAILED")

        monkeypatch.setattr(c.tx, "store_evidence", fail)
    elif failure == "readback":
        old = c.tx.read_stage_evidence

        def read(ref):
            if c.stored and ref == c.stored[-1][0]:
                raise ValueError("MODELED_READBACK_FAILED")
            return old(ref)

        monkeypatch.setattr(c.tx, "read_stage_evidence", read)
    else:
        old = c.tx.commit_stage_state

        def commit(*args, **kwargs):
            if "BOOT_RETAINED" in kwargs["detail_code"]:
                raise ValueError("MODELED_TERMINAL_FAILED")
            return old(*args, **kwargs)

        monkeypatch.setattr(c.tx, "commit_stage_state", commit)
    with pytest.raises(ValueError, match="MODELED_"):
        collect(c)
    d = c.collector.retained_diagnostics()
    assert (
        d["host_boot"]["document"] == c.report.to_dict() and d["terminal_event"] is None
    )
    assert (
        d["host_boot"]["retention"]
        == {
            "store": "COLLECTED_NOT_M1_RETAINED",
            "readback": "M1_PUBLISHED_READBACK_PENDING",
            "terminal": "M1_FULL_BYTES_READ_BACK",
        }[failure]
    )
    assert (d["host_boot"]["reference"] is None) is (failure == "store")


def test_fixed_reader_import_forwards_same_transaction_only(monkeypatch):
    calls = []
    expected = (
        object(),
        {"MODELED_WORKFLOW": True},
        {"MODELED_TYPED_PREDECESSOR": True},
    )

    def reader(tx, **kwargs):
        calls.append((tx, kwargs))
        return expected

    monkeypatch.setattr(
        session, "read_usb_reboot_boot_originals", reader, raising=False
    )
    tx = object()
    args = dict(
        workspace=Path.cwd(),
        source_sha256="a" * 64,
        launch_session_id="MODELED-new-launch",
        expected_header_sha256="b" * 64,
        cancellation=Event(),
        deadline_ns=123,
    )
    assert m.read_usb_reboot_boot_originals(tx, **args) is expected
    assert calls == [(tx, args)]
