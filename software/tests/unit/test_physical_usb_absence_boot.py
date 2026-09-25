"""Actual boot codecs with MODELED original transactions and host observations.

No process, CIM, device API, native helper or real M1 lease is invoked here.
Positive physical-shaped observations are explicit test models, not host proof.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import os
import subprocess
import time

import pytest

from rocell.application import physical_usb_absence_boot as m
from rocell.application.physical_usb_presence_phase import (
    build_usb_presence_operator_event,
)
from rocell.providers.windows import host_boot_observation as host
from test_host_boot_observation import execution, response, FakeExecutor
from test_physical_camera_usb_qualification import reference
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_presence_campaign import modeled_presence_campaign

STAGE = m.STAGE_ORDER[3]


@pytest.fixture(autouse=True)
def no_process_or_devices(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Absence boot tests cannot execute a process or query devices/CIM")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(host, "_system_powershell", forbidden)
    monkeypatch.setattr(host, "_native_owner", forbidden)


def journal(case, kind, previous, state, refs, sequence, timestamp, previous_hash):
    value = m.V2JournalEvent(
        case.binding["session_id"],
        case.binding["header_sha256"],
        sequence,
        STAGE,
        previous,
        state,
        timestamp,
        previous_hash,
        tuple(sorted(refs, key=lambda r: r.evidence_id)),
        m.usb_absence_boot_event(kind, case.phase_id),
        "0" * 64,
    )
    return m._parse_event(
        replace(value, event_sha256=m.digest(m.canonical(value.core_dict()))).to_dict()
    )


def absence_boot_subjects(prerequisites):
    """Reusable strict subjects; all earlier physical originals are MODELED."""
    seed = modeled_presence_campaign(prerequisites)
    op = seed.operation.to_dict()
    case = SimpleNamespace(
        seed=seed,
        operation=seed.operation,
        binding=op["phase_binding"]["binding"],
        phase_id=op["operation_id"],
        launch=op["launch_session_id"],
        workspace=Path(op["workspace"]),
        original_baseline=seed.original_baseline,
        start_ns=seed.phase_binding.to_dict()["not_before_utc_ns"] + 1_000_000_000,
    )
    declaration = seed.original_baseline["declaration_event"]
    case.start = journal(
        case,
        "PREPARATION_REQUESTED",
        m.V2StageState.BLOCKED,
        m.V2StageState.WAITING_OPERATOR,
        (seed.original_baseline["baseline_reference"],),
        declaration.sequence + 10,
        case.start_ns,
        declaration.event_sha256,
    )
    case.operator_event = build_usb_presence_operator_event(
        phase_binding=seed.phase_binding,
        phase_id=case.phase_id,
        launch_session_id=case.launch,
        operator_id="MODELED-inspector",
        phase_started_at_utc_ns=case.start_ns,
        reported_at_utc_ns=case.start_ns + 100,
    )
    case.op_ref = reference(case.operation.payload, "MODELED-absence-operation")
    case.operator_ref = reference(
        case.operator_event.payload, "MODELED-operator-report"
    )
    case.args = dict(
        operation=case.operation,
        operation_reference=case.op_ref,
        operator_event=case.operator_event,
        operator_event_reference=case.operator_ref,
        phase_start_event=case.start,
        original_baseline=case.original_baseline,
    )
    case.intent = m.build_usb_absence_boot_intent(**case.args)
    case.review = m.review_usb_absence_boot_intent(
        case.intent,
        reviewer_id="MODELED-reviewer",
        launch_session_id=case.launch,
        reviewed_at_ns=case.start_ns + 200,
    )
    case.intent_ref = reference(
        case.intent.payload, m.usb_absence_boot_label("boot_intent", case.phase_id)
    )
    case.review_ref = reference(
        case.review.payload, m.usb_absence_boot_label("boot_review", case.phase_id)
    )
    case.reviewed = journal(
        case,
        "BOOT_REVIEWED",
        m.V2StageState.REVIEW_PENDING,
        m.V2StageState.BLOCKED,
        (case.intent_ref, case.review_ref),
        case.start.sequence + 2,
        case.start_ns + 300,
        case.start.event_sha256,
    )
    return case


@pytest.fixture
def boot_case(prerequisites, monkeypatch):
    case = absence_boot_subjects(prerequisites)
    case.events = [
        case.original_baseline["declaration_event"],
        case.start,
        case.reviewed,
    ]
    case.payloads = {
        case.intent_ref: case.intent.payload,
        case.review_ref: case.review.payload,
        case.op_ref: case.operation.payload,
        case.operator_ref: case.operator_event.payload,
        case.original_baseline["plan_reference"]: case.original_baseline[
            "plan"
        ].payload,
        case.original_baseline["baseline_reference"]: case.original_baseline[
            "baseline"
        ].payload,
    }
    for row in case.seed.phase_binding.to_dict()["sources"]:
        case.payloads[m.qualification._reference(row["reference"])] = (
            case.original_baseline["baseline_sources"][row["role"]]
        )
    case.calls, case.stored = [], []
    case.states = {
        stage: m.V2StageState.PASS if n < 3 else m.V2StageState.PENDING
        for n, stage in enumerate(m.STAGE_ORDER)
    }
    case.states[STAGE] = m.V2StageState.BLOCKED
    case.header = SimpleNamespace(
        **{
            key: case.binding[key] for key in ("cell_id", "session_id", "header_sha256")
        },
        source_binding_sha256=m.physical_camera_source_binding(
            case.binding["source_sha256"]
        ),
    )
    case.leases = (
        m.LeaseSpec(m.LeaseLevel.CELL, case.binding["cell_id"]),
        m.LeaseSpec(m.LeaseLevel.SESSION, case.binding["session_id"]),
    )
    case.source, case.reconciliation = case.binding["source_sha256"], False
    case.cancel, case.deadline = Event(), time.monotonic_ns() + 60_000_000_000
    case.wall = case.start_ns + 400

    def snapshot():
        return SimpleNamespace(
            header=case.header,
            committed_events=tuple(case.events),
            head=SimpleNamespace(head_sha256=case.events[-1].event_sha256),
            reconciliation_required=case.reconciliation,
            state_for=lambda stage: case.states[stage],
        )

    def read(ref):
        case.calls.append(("read", ref))
        return case.payloads[ref]

    def store(
        stage, payload, *, label, media_type, captured_at_ns, expected_head_sha256
    ):
        assert stage is STAGE and media_type == "application/json"
        assert expected_head_sha256 == snapshot().head.head_sha256
        ref = reference(payload, label)
        case.payloads[ref] = payload
        case.stored.append((ref, payload, label))
        case.calls.append(("store", label))
        return ref

    def commit(
        stage, state, *, occurred_at_ns, detail_code, expected_head_sha256, evidence
    ):
        assert expected_head_sha256 == snapshot().head.head_sha256
        last = case.events[-1]
        value = m.V2JournalEvent(
            case.binding["session_id"],
            case.binding["header_sha256"],
            last.sequence + 1,
            stage,
            case.states[stage],
            state,
            occurred_at_ns,
            last.event_sha256,
            tuple(evidence),
            detail_code,
            "0" * 64,
        )
        value = m._parse_event(
            replace(
                value, event_sha256=m.digest(m.canonical(value.core_dict()))
            ).to_dict()
        )
        case.events.append(value)
        case.states[stage] = state
        case.calls.append(("commit", detail_code))
        return snapshot()

    # Only storage effects are modeled; no original M1/lease qualification claim.
    case.tx = object.__new__(m.M1PhysicalCameraTransaction)
    monkeypatch.setattr(
        m.M1PhysicalCameraTransaction, "held_leases", property(lambda self: case.leases)
    )
    monkeypatch.setattr(case.tx, "snapshot", snapshot)
    monkeypatch.setattr(case.tx, "read_stage_evidence", read)
    monkeypatch.setattr(case.tx, "store_evidence", store)
    monkeypatch.setattr(case.tx, "commit_stage_state", commit)
    monkeypatch.setattr(m, "source_fingerprint", lambda path: case.source)
    monkeypatch.setattr(m, "time_ns", lambda: case.wall)
    case.collector = m.OriginalUsbAbsenceBootCollector(
        case.workspace, case.intent, case.review
    )
    return case


def modeled_boot(
    case,
    request,
    *,
    fault=None,
    origin="INJECTED_CIM_EXECUTOR",
    admission_check=lambda: None,
):
    """Real immutable producer with an incapable in-memory executor only."""
    changes = {}
    if fault == "different_host":
        changes["machine_uuid"] = "aaaaaaaa-1234-5678-9abc-0123456789ab"
    if fault == "different_boot":
        changes.update(
            last_boot_up_time_utc="2026-01-01T02:00:00.010000Z",
            confirmation_boot_up_time_utc="2026-01-01T02:00:00.010000Z",
        )
    ex = execution(request, wall=case.wall + 1000, raw=response(request, **changes))
    ownership = dict(
        schema=host.OWNERSHIP_SCHEMA,
        accounting_complete=True,
        pid=31415,
        peak_processes=1,
        peak_handles=12,
        handles_remaining=0,
        pins_remaining=0,
        unclosed_handles_remaining=0,
        stdin_pending=False,
        cleanup_deadline_ns=ex.finished_monotonic_ns + 1_000_000_000,
    )
    ex = replace(
        ex,
        command={**ex.command, "process_model": host.PROCESS_MODEL},
        ownership=ownership,
    )
    if fault and fault not in ("different_host", "different_boot"):
        ex = replace(ex, status="CANCELLED", primary_error="CANCELLED")
        if fault in (
            "handles_remaining",
            "pins_remaining",
            "unclosed_handles_remaining",
        ):
            ownership[fault] = 1
        elif fault == "stdin_pending":
            ownership[fault] = True
        elif fault == "unknown":
            ownership.update(
                accounting_complete=False, handles_remaining=None, peak_processes=None
            )
        elif fault == "late_cleanup":
            ownership["cleanup_deadline_ns"] = ex.finished_monotonic_ns - 1
        elif fault == "cleanup_error":
            ex = replace(ex, cleanup_errors=("OWNED_RESOURCE_CLEANUP_UNCONFIRMED",))
        elif fault == "legacy":
            ex = replace(
                ex,
                ownership=None,
                command={k: v for k, v in ex.command.items() if k != "process_model"},
            )
        elif fault != "cancelled":
            raise AssertionError(fault)
    result = host.WindowsHostBootObserver(FakeExecutor(ex)).observe(
        request,
        cancellation=Event(),
        deadline_ns=request.expires_at_ns,
        admission_check=admission_check,
    )
    if origin != "INJECTED_CIM_EXECUTOR":
        # Explicit physical-shaped TEST MODEL, not promotion by production code.
        d = result.to_dict()
        d["origin"] = origin
        result = host.HostBootObservation(m.canonical(d))
    return result


def install_observer(
    case, monkeypatch, *, fault=None, physical=False, before=None, after=None
):
    class Observer:
        def observe(self, request, **kwargs):
            case.calls.append(("observe", request))
            assert case.events[-1].detail_code == m.usb_absence_boot_event(
                "BOOT_REQUESTED", case.phase_id
            )
            if before:
                before()
            case.report = modeled_boot(
                case,
                request,
                fault=fault,
                origin="WINDOWS_LOCAL_CIM" if physical else "INJECTED_CIM_EXECUTOR",
                admission_check=kwargs["admission_check"],
            )
            case.wall = case.report.to_dict()["execution"]["finished_utc_ns"] + 1
            if after:
                after()
            return case.report

    monkeypatch.setattr(m, "WindowsHostBootObserver", Observer)


def collect(case, **changes):
    kwargs = dict(
        intent_reference=case.intent_ref,
        review_reference=case.review_ref,
        cancellation=case.cancel,
        deadline_ns=case.deadline,
        revalidate_context=lambda: None,
    )
    kwargs.update(changes)
    return case.collector.collect(case.tx, **kwargs)


def test_original_intent_review_are_inert_exact_detached_and_bounded(
    boot_case, monkeypatch
):
    c = boot_case
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure reconstruction accessed file")
    )
    checked = m.verify_usb_absence_boot_intent(
        c.intent, expected_sha256=c.intent.sha256, **c.args
    )
    reviewed = m.verify_usb_absence_boot_review(
        c.review, intent=checked, expected_sha256=c.review.sha256
    )
    assert checked.payload == c.intent.payload and reviewed.payload == c.review.payload
    assert (
        len(checked.payload) < m.MAX_INTENT_BYTES
        and len(reviewed.payload) < m.MAX_REVIEW_BYTES
    )
    assert checked.to_dict()["budget"] == {
        "admission_window_ms": 30000,
        "process_run_ms": 10000,
        "cleanup_ms": 2000,
    }
    assert reviewed.to_dict()["authenticated_independent_people"] is False
    assert all(checked.to_dict()[key] is False for key in m._FLAGS)
    with pytest.raises(FrozenInstanceError):
        checked.payload = b"{}"
    value = c.collector.retained_diagnostics()
    value["state"] = "invented"
    assert c.collector.retained_diagnostics()["state"] == "NOT_STARTED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "BASELINE"),
        ("phase_id", "usbphase-old"),
        ("launch_session_id", "not\na-label"),
        ("script_sha256", "f" * 64),
        (
            "budget",
            dict(admission_window_ms=30001, process_run_ms=10000, cleanup_ms=2000),
        ),
        ("physical_authority", 0),
        ("automatic_replay", True),
        ("extra", None),
        ("phase_started_at_utc_ns", True),
        ("reported_at_utc_ns", 0),
    ],
)
def test_intent_rejects_closed_policy_and_boundary_mutations(boot_case, field, value):
    d = boot_case.intent.to_dict()
    d[field] = value
    with pytest.raises(ValueError):
        m.UsbAbsenceBootIntent(m.canonical(d))


@pytest.mark.parametrize(
    "fault",
    ["operator", "casefold", "launch", "time", "intent", "authority", "unknown"],
)
def test_review_requires_distinct_exact_current_intent(boot_case, fault):
    c = boot_case
    if fault in ("operator", "casefold", "launch", "time"):
        kwargs = dict(
            reviewer_id="reviewer",
            launch_session_id=c.launch,
            reviewed_at_ns=c.start_ns + 200,
        )
        if fault in ("operator", "casefold"):
            kwargs["reviewer_id"] = (
                "MODELED-inspector" if fault == "operator" else "modeled-INSPECTOR"
            )
        elif fault == "launch":
            kwargs["launch_session_id"] = "wizard-other"
        else:
            kwargs["reviewed_at_ns"] = c.start_ns
        with pytest.raises(ValueError):
            m.review_usb_absence_boot_intent(c.intent, **kwargs)
    else:
        d = c.review.to_dict()
        d[
            {
                "intent": "intent_sha256",
                "authority": "physical_authority",
                "unknown": "extra",
            }[fault]
        ] = (
            "f" * 64 if fault == "intent" else 0
        )
        with pytest.raises(ValueError):
            m.verify_usb_absence_boot_review(
                m.canonical(d),
                intent=c.intent,
                expected_sha256=m.digest(m.canonical(d)),
            )


@pytest.mark.parametrize(
    "fault",
    [
        "operation",
        "operator",
        "baseline",
        "original-bytes",
        "event-hash",
        "legacy-baseline-id",
    ],
)
def test_intent_reconstruction_rejects_self_consistent_wrong_subjects(boot_case, fault):
    c = boot_case
    args = dict(c.args)
    if fault == "operation":
        d = c.operation.to_dict()
        d["request_nonce"] = "f" * 64
        args["operation"] = m.UsbPresenceOperation(m.canonical(d))
        args["operation_reference"] = reference(
            args["operation"].payload, "changed-operation"
        )
    elif fault == "operator":
        d = c.operator_event.to_dict()
        d["operator_id"] = "other-inspector"
        args["operator_event"] = m.UsbPresenceOperatorEvent(m.canonical(d))
        args["operator_event_reference"] = reference(
            args["operator_event"].payload, "changed-report"
        )
    elif fault == "baseline":
        args["original_baseline"] = dict(
            c.original_baseline,
            baseline_reference=reference(
                c.original_baseline["baseline"].payload, "different-original"
            ),
        )
    elif fault == "original-bytes":
        originals = dict(c.original_baseline)
        originals["baseline_sources"] = dict(
            originals["baseline_sources"], host_boot=b"{}"
        )
        args["original_baseline"] = originals
    elif fault == "event-hash":
        args["phase_start_event"] = replace(c.start, event_sha256="f" * 64)
    else:
        d = c.operation.to_dict()
        d["operation_id"] = d["phase_binding"]["baseline"]["context"]["operation_id"]
        # This modeled predecessor has an old standalone operation identifier;
        # the actual operation constructor rejects reuse at its earlier gate.
        with pytest.raises(
            ValueError, match="EXACT_SERVER_PRESENCE_OPERATION_IDENTITY"
        ):
            m.UsbPresenceOperation(m.canonical(d))
        return
    with pytest.raises(ValueError):
        m.verify_usb_absence_boot_intent(
            c.intent, expected_sha256=c.intent.sha256, **args
        )


@pytest.mark.parametrize(
    "physical,fault,status",
    [
        (False, None, "BOOT_HELD"),
        (True, None, "BOOT_RETAINED"),
        (True, "different_host", "BOOT_HELD"),
        (True, "different_boot", "BOOT_HELD"),
        (True, "cancelled", "BOOT_HELD"),
    ],
)
def test_request_precedes_fixed_observer_complete_original_retention_and_no_replay(
    boot_case, monkeypatch, physical, fault, status
):
    c = boot_case
    install_observer(c, monkeypatch, physical=physical, fault=fault)
    result = collect(c)
    diag = c.collector.retained_diagnostics()
    assert diag["state"] == status
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert m.canonical(result["document"]) == c.report.payload == c.stored[0][1]
    assert c.stored[0][2] == m.usb_absence_boot_label("host_boot", c.phase_id)
    assert c.events[-1].evidence == m._refs(c.intent_ref, c.stored[0][0])
    assert c.events[-2].evidence == (c.intent_ref,)
    assert c.states[STAGE] is m.V2StageState.BLOCKED
    assert all(c.states[s] is m.V2StageState.PENDING for s in m.STAGE_ORDER[4:])
    reads = [r for kind, r in c.calls if kind == "read"]
    assert set(c.payloads) <= set(
        reads
    )  # All nine original subjects plus retained report.
    kinds = [kind for kind, _ in c.calls]
    assert kinds.index("commit") < kinds.index("observe") < kinds.index("store")
    result["document"]["origin"] = "changed"
    assert (
        c.collector.retained_diagnostics()["host_boot"]["document"]["origin"]
        != "changed"
    )
    with pytest.raises(ValueError, match="ALREADY_USED"):
        collect(c)
    c.collector = m.OriginalUsbAbsenceBootCollector(c.workspace, c.intent, c.review)
    with pytest.raises(ValueError):
        collect(c)
    assert len([1 for k, _ in c.calls if k == "observe"]) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "handles_remaining",
        "pins_remaining",
        "unclosed_handles_remaining",
        "stdin_pending",
        "unknown",
        "late_cleanup",
        "cleanup_error",
        "legacy",
    ],
)
def test_unknown_or_incomplete_cleanup_retains_original_as_uncertain(
    boot_case, monkeypatch, fault
):
    c = boot_case
    install_observer(c, monkeypatch, physical=True, fault=fault)
    result = collect(c)
    assert c.collector.retained_diagnostics()["state"] == "BOOT_UNCERTAIN"
    assert c.states[STAGE] is m.V2StageState.SIDE_EFFECT_UNCERTAIN
    assert m.canonical(result["document"]) == c.report.payload
    if fault == "unknown":
        assert result["document"]["execution"]["ownership"]["handles_remaining"] is None
        assert result["document"]["execution"]["ownership"]["peak_processes"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "cancel",
        "deadline",
        "guard",
        "lease",
        "header",
        "cell",
        "session",
        "source-binding",
        "stage",
        "downstream",
        "reconciliation",
        "declaration",
        "start",
        "review",
        "intent-bytes",
        "review-bytes",
        "operation-bytes",
        "operator-bytes",
        "baseline-bytes",
        "baseline-source-bytes",
    ],
)
def test_stale_or_unreviewed_originals_refuse_before_request(
    boot_case, monkeypatch, fault
):
    c = boot_case
    install_observer(c, monkeypatch)
    changes = {}
    if fault == "source":
        c.source = "f" * 64
    elif fault == "cancel":
        c.cancel.set()
    elif fault == "deadline":
        changes["deadline_ns"] = 1
    elif fault == "guard":
        changes["revalidate_context"] = lambda: True
    elif fault == "lease":
        c.leases = (*c.leases, m.LeaseSpec(m.LeaseLevel.CAMERA, c.binding["cell_id"]))
    elif fault in ("header", "cell", "session", "source-binding"):
        setattr(
            c.header,
            {
                "header": "header_sha256",
                "cell": "cell_id",
                "session": "session_id",
                "source-binding": "source_binding_sha256",
            }[fault],
            "f" * 64,
        )
    elif fault == "stage":
        c.states[STAGE] = m.V2StageState.WAITING_OPERATOR
    elif fault == "downstream":
        c.states[m.STAGE_ORDER[4]] = m.V2StageState.WAITING_OPERATOR
    elif fault == "reconciliation":
        c.reconciliation = True
    elif fault in ("declaration", "start", "review"):
        c.events.pop({"declaration": 0, "start": 1, "review": 2}[fault])
    else:
        refs = {
            "intent-bytes": c.intent_ref,
            "review-bytes": c.review_ref,
            "operation-bytes": c.op_ref,
            "operator-bytes": c.operator_ref,
            "baseline-bytes": c.original_baseline["baseline_reference"],
            "baseline-source-bytes": m.qualification._reference(
                c.seed.phase_binding.to_dict()["sources"][2]["reference"]
            ),
        }
        c.payloads[refs[fault]] = b"{}"
    with pytest.raises(ValueError):
        collect(c, **changes)
    assert not c.stored and not any(k in ("commit", "observe") for k, _ in c.calls)


def test_stop_after_request_is_durable_pending_and_cannot_replay(
    boot_case, monkeypatch
):
    c = boot_case
    install_observer(c, monkeypatch)
    original = c.tx.commit_stage_state

    def commit(*a, **kw):
        result = original(*a, **kw)
        c.cancel.set()
        return result

    monkeypatch.setattr(c.tx, "commit_stage_state", commit)
    with pytest.raises(ValueError, match="INTERRUPTED"):
        collect(c)
    assert c.collector.retained_diagnostics()["state"] == "REQUESTED"
    c.cancel.clear()
    c.collector = m.OriginalUsbAbsenceBootCollector(c.workspace, c.intent, c.review)
    with pytest.raises(ValueError, match="CURRENT_REVIEWED"):
        collect(c)
    assert not c.stored and not any(k == "observe" for k, _ in c.calls)
    assert len([1 for k, _ in c.calls if k == "commit"]) == 1


@pytest.mark.parametrize("fault", ["stop", "source", "guard"])
def test_late_stop_source_or_context_loss_retains_complete_report_but_holds(
    boot_case, monkeypatch, fault
):
    c = boot_case
    guard_state = [False]

    def after():
        if fault == "stop":
            c.cancel.set()
        elif fault == "source":
            c.source = "f" * 64
        else:
            guard_state[0] = True

    install_observer(c, monkeypatch, physical=True, after=after)
    result = collect(c, revalidate_context=lambda: True if guard_state[0] else None)
    d = c.collector.retained_diagnostics()
    assert d["state"] == "BOOT_HELD" and d["context_current"] is False
    assert result["document"]["status"] == "OBSERVED_HOST_BOOT"
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert m.canonical(result["document"]) == c.report.payload


@pytest.mark.parametrize("boundary", ["store", "readback"])
@pytest.mark.parametrize("change", ["stop", "source"])
def test_change_during_retention_cannot_become_clean_terminal(
    boot_case, monkeypatch, boundary, change
):
    c = boot_case
    install_observer(c, monkeypatch, physical=True)

    def mutate():
        if change == "stop":
            c.cancel.set()
        else:
            c.source = "f" * 64

    if boundary == "store":
        original = c.tx.store_evidence

        def store(*a, **k):
            result = original(*a, **k)
            mutate()
            return result

        monkeypatch.setattr(c.tx, "store_evidence", store)
    else:
        original = c.tx.read_stage_evidence

        def read(ref):
            result = original(ref)
            if c.stored and ref == c.stored[0][0]:
                mutate()
            return result

        monkeypatch.setattr(c.tx, "read_stage_evidence", read)
    result = collect(c)
    d = c.collector.retained_diagnostics()
    assert d["state"] == "BOOT_HELD" and d["context_current"] is False
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert m.canonical(result["document"]) == c.report.payload


def test_currentness_does_not_recover_after_temporary_loss(boot_case, monkeypatch):
    c = boot_case
    install_observer(
        c, monkeypatch, physical=True, after=lambda: setattr(c, "source", "f" * 64)
    )
    original = c.tx.store_evidence

    def store(*a, **k):
        result = original(*a, **k)
        c.source = c.binding["source_sha256"]
        return result

    monkeypatch.setattr(c.tx, "store_evidence", store)
    collect(c)
    d = c.collector.retained_diagnostics()
    assert d["state"] == "BOOT_HELD" and d["context_current"] is False


@pytest.mark.parametrize("fault", ["store", "readback", "terminal"])
def test_retention_fault_preserves_exact_available_report_without_false_commit(
    boot_case, monkeypatch, fault
):
    c = boot_case
    install_observer(c, monkeypatch)
    if fault == "store":
        monkeypatch.setattr(
            c.tx,
            "store_evidence",
            lambda *a, **k: (_ for _ in ()).throw(ValueError("store-fault")),
        )
    elif fault == "readback":
        original = c.tx.read_stage_evidence
        monkeypatch.setattr(
            c.tx,
            "read_stage_evidence",
            lambda ref: b"{}" if c.stored and ref == c.stored[0][0] else original(ref),
        )
    else:
        original = c.tx.commit_stage_state

        def fail_terminal(*a, **k):
            if c.stored:
                raise ValueError("terminal-fault")
            return original(*a, **k)

        monkeypatch.setattr(c.tx, "commit_stage_state", fail_terminal)
    with pytest.raises(ValueError):
        collect(c)
    d = c.collector.retained_diagnostics()
    assert m.canonical(d["host_boot"]["document"]) == c.report.payload
    assert (
        d["host_boot"]["retention"]
        == {
            "store": "COLLECTED_NOT_M1_RETAINED",
            "readback": "M1_PUBLISHED_READBACK_PENDING",
            "terminal": "M1_FULL_BYTES_READ_BACK",
        }[fault]
    )
    assert (
        d["terminal_event"] is None
        and c.states[STAGE] is m.V2StageState.WAITING_OPERATOR
    )


@pytest.mark.parametrize("fault", ["header", "leases", "head", "source"])
def test_fixed_observer_rechecks_original_scope_before_acquisition(
    boot_case, monkeypatch, fault
):
    c = boot_case

    def before():
        if fault == "header":
            c.header.header_sha256 = "f" * 64
        elif fault == "leases":
            c.leases = ()
        elif fault == "head":
            c.events[-1] = c.reviewed
        else:
            c.source = "f" * 64

    install_observer(c, monkeypatch, before=before)
    with pytest.raises(ValueError):
        collect(c)
    assert not c.stored and c.collector.retained_diagnostics()["host_boot"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "BASELINE"),
        ("operation_id", "usbphase-" + "f" * 32),
        ("launch_session_id", "wizard-other"),
        ("session_id", "other-session"),
        ("trial_id", "usbtrial-other"),
        ("source_sha256", "f" * 64),
    ],
)
def test_pure_observation_verifier_rejects_other_original_request(
    boot_case, field, value
):
    c = boot_case
    requested = journal(
        c,
        "BOOT_REQUESTED",
        m.V2StageState.BLOCKED,
        m.V2StageState.WAITING_OPERATOR,
        (c.intent_ref,),
        c.reviewed.sequence + 1,
        c.wall,
        c.reviewed.event_sha256,
    )
    kwargs = dict(
        source_sha256=c.binding["source_sha256"],
        session_id=c.binding["session_id"],
        trial_id=c.binding["trial_id"],
        phase=m.PHASE,
        operation_id=c.phase_id,
        launch_session_id=c.launch,
        expires_at_ns=time.monotonic_ns() + 30_000_000_000,
    )
    kwargs[field] = value
    report = modeled_boot(c, host.HostBootRequest(**kwargs))
    with pytest.raises(ValueError, match="INTENT_MISMATCH"):
        m.verify_usb_absence_boot_observation(
            report,
            intent=c.intent,
            expected_sha256=report.sha256,
            requested_event=requested,
        )


def test_pure_observation_verifier_rejects_rehashed_event_and_window(boot_case):
    c = boot_case
    requested = journal(
        c,
        "BOOT_REQUESTED",
        m.V2StageState.BLOCKED,
        m.V2StageState.WAITING_OPERATOR,
        (c.intent_ref,),
        c.reviewed.sequence + 1,
        c.wall,
        c.reviewed.event_sha256,
    )
    req = host.HostBootRequest(
        c.binding["source_sha256"],
        c.binding["session_id"],
        c.launch,
        c.phase_id,
        c.binding["trial_id"],
        m.PHASE,
        time.monotonic_ns() + 31_000_000_000,
    )
    report = modeled_boot(c, req)
    with pytest.raises(ValueError, match="INTENT_MISMATCH"):
        m.verify_usb_absence_boot_observation(
            report,
            intent=c.intent,
            expected_sha256=report.sha256,
            requested_event=requested,
        )
    with pytest.raises(ValueError):
        m.verify_usb_absence_boot_observation(
            report,
            intent=c.intent,
            expected_sha256=report.sha256,
            requested_event=replace(requested, event_sha256="f" * 64),
        )
