"""Pure boot-intent and collector tests; M1 method effects are explicitly modeled.

Actual immutable plan/event/host codecs run. The collector sees the exact M1
transaction type with a closed in-memory storage seam, not real leases or an
authenticated original store. The observer uses an injected incapable executor;
its provider-shaped values are never presented as a physical host observation.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event
import subprocess
import time
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_trial_boot as m
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2JournalEvent, V2StageState
from rocell.providers.windows import host_boot_observation as host
from test_host_boot_observation import WALL, execution
from test_physical_camera_usb_qualification import plan_fixture, reference
from test_physical_received_camera import prerequisites, workspace

PHASE = "usbphase-" + "5" * 32
LAUNCH = "wizard-" + "6" * 32
STAGE = STAGE_ORDER[3]


@pytest.fixture(autouse=True)
def no_process_or_cim(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Boot contract tests must not start a process or query CIM")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(host, "_system_powershell", forbidden)
    monkeypatch.setattr(host, "_native_owner", forbidden)


def event(case, name, previous, state, refs, sequence, previous_hash="a" * 64):
    provisional = V2JournalEvent(
        session_id=case.binding["session_id"],
        session_header_sha256=case.binding["header_sha256"],
        sequence=sequence,
        stage=STAGE,
        previous_state=previous,
        state=state,
        occurred_at_ns=WALL + sequence,
        previous_event_sha256=previous_hash,
        evidence=tuple(refs),
        detail_code=m.usb_phase_event(name, PHASE),
        event_sha256="0" * 64,
    )
    result = replace(
        provisional, event_sha256=m.digest(m.canonical(provisional.core_dict()))
    )
    return m._parse_event(result.to_dict())


@pytest.fixture
def boot_case(prerequisites, monkeypatch):
    # PHYSICAL is required by the intent. All underlying facts/refs here are
    # nevertheless explicitly MODELED fixtures, not received-unit authority.
    plan, _, _ = plan_fixture(prerequisites, mode="PHYSICAL")
    case = SimpleNamespace(
        plan=plan, binding=plan.to_dict()["binding"], calls=[], stored=[]
    )
    case.plan_reference = reference(plan.payload, "modeled-original-plan")
    case.start = event(
        case,
        "PREPARATION_REQUESTED",
        V2StageState.BLOCKED,
        V2StageState.WAITING_OPERATOR,
        (case.plan_reference,),
        2,
    )
    case.args = dict(
        plan=plan,
        plan_reference=case.plan_reference,
        phase_start_event=case.start,
        phase_id=PHASE,
        launch_session_id=LAUNCH,
    )
    case.intent = m.build_usb_trial_boot_intent(**case.args)
    case.intent_reference = reference(
        case.intent.payload, "modeled-original-boot-intent"
    )
    reviewed = event(
        case,
        "REVIEWED",
        V2StageState.REVIEW_PENDING,
        V2StageState.BLOCKED,
        (case.intent_reference,),
        4,
        case.start.event_sha256,
    )
    case.events = [case.start, reviewed]
    case.payloads = {
        case.plan_reference: plan.payload,
        case.intent_reference: case.intent.payload,
    }
    case.states = {
        stage: V2StageState.PASS if i < 3 else V2StageState.PENDING
        for i, stage in enumerate(STAGE_ORDER)
    }
    case.states[STAGE] = V2StageState.BLOCKED
    case.header = SimpleNamespace(
        **{
            key: case.binding[key] for key in ("session_id", "cell_id", "header_sha256")
        },
        source_binding_sha256=m.physical_camera_source_binding(
            case.binding["source_sha256"]
        ),
    )
    case.leases = (
        m.LeaseSpec(m.LeaseLevel.CELL, case.binding["cell_id"]),
        m.LeaseSpec(m.LeaseLevel.SESSION, case.binding["session_id"]),
    )
    case.reconciliation = False
    case.cancel = Event()
    case.deadline = time.monotonic_ns() + 60_000_000_000
    case.source = case.binding["source_sha256"]

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

    def commit(
        stage, state, *, occurred_at_ns, detail_code, expected_head_sha256, evidence
    ):
        assert expected_head_sha256 == snapshot().head.head_sha256
        last = case.events[-1]
        row = V2JournalEvent(
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
        row = replace(row, event_sha256=m.digest(m.canonical(row.core_dict())))
        m._parse_event(row.to_dict())
        case.events.append(row)
        case.states[stage] = state
        case.calls.append(("commit", detail_code))
        return snapshot()

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

    # This exact-type seam tests the production collector, not M1 qualification.
    case.tx = object.__new__(m.M1PhysicalCameraTransaction)
    monkeypatch.setattr(
        m.M1PhysicalCameraTransaction, "held_leases", property(lambda self: case.leases)
    )
    monkeypatch.setattr(case.tx, "snapshot", snapshot)
    monkeypatch.setattr(case.tx, "read_stage_evidence", read)
    monkeypatch.setattr(case.tx, "commit_stage_state", commit)
    monkeypatch.setattr(case.tx, "store_evidence", store)
    monkeypatch.setattr(m, "source_fingerprint", lambda path: case.source)
    monkeypatch.setattr(m, "time_ns", lambda: WALL + 100)
    case.collector = m.OriginalUsbTrialBootCollector(Path.cwd(), case.intent)
    return case


def owned_report(
    request, *, admission_check=lambda: None, cancellation=None, fault=None
):
    """Actual host observer codec with only an injected in-memory executor."""

    class Executor:
        def execute(self, req, **kwargs):
            kwargs["admission_check"]()
            result = execution(req, wall=WALL + 200)
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
                cleanup_deadline_ns=result.finished_monotonic_ns + 1_000_000_000,
            )
            result = replace(
                result,
                command={**result.command, "process_model": host.PROCESS_MODEL},
                ownership=ownership,
            )
            if fault:
                result = replace(result, status="CANCELLED", primary_error="CANCELLED")
                if fault in (
                    "handles_remaining",
                    "pins_remaining",
                    "unclosed_handles_remaining",
                ):
                    ownership[fault] = 1
                elif fault == "stdin_pending":
                    ownership[fault] = True
                elif fault == "late_cleanup":
                    ownership["cleanup_deadline_ns"] = result.finished_monotonic_ns - 1
                elif fault == "unknown":
                    ownership["accounting_complete"] = False
                    ownership["handles_remaining"] = None
                elif fault == "cleanup_error":
                    result = replace(
                        result, cleanup_errors=("OWNED_RESOURCE_CLEANUP_UNCONFIRMED",)
                    )
                elif fault == "legacy":
                    result = replace(
                        result,
                        ownership=None,
                        command={
                            k: v
                            for k, v in result.command.items()
                            if k != "process_model"
                        },
                    )
                elif fault != "cancelled":
                    raise AssertionError(fault)
            return result

    return host.WindowsHostBootObserver(Executor()).observe(
        request,
        cancellation=cancellation or Event(),
        deadline_ns=request.expires_at_ns,
        admission_check=admission_check,
    )


def install_observer(case, monkeypatch, *, fault=None, during=None):
    class Observer:
        def observe(self, request, **kwargs):
            case.calls.append(("observe", request))
            assert case.events[-1].detail_code == m.usb_phase_event(
                "BOOT_REQUESTED", PHASE
            )
            if during:
                during()
            report = owned_report(
                request,
                admission_check=kwargs["admission_check"],
                cancellation=kwargs["cancellation"],
                fault=fault,
            )
            case.report = report
            return report

    monkeypatch.setattr(m, "WindowsHostBootObserver", Observer)


def collect(case, **kwargs):
    return case.collector.collect(
        case.tx,
        intent_reference=case.intent_reference,
        cancellation=case.cancel,
        deadline_ns=case.deadline,
        revalidate_context=kwargs.pop("revalidate_context", lambda: None),
        **kwargs,
    )


def test_intent_constructor_and_reconstruction_are_inert(boot_case, monkeypatch):
    case = boot_case
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure intent read file")
    )
    original = m.verify_usb_trial_boot_intent(
        case.intent, expected_sha256=case.intent.sha256, **case.args
    )
    assert original.payload == case.intent.payload
    assert original.to_dict()["budget"] == {
        "admission_window_ms": 30000,
        "process_run_ms": 10000,
        "cleanup_ms": 2000,
    }
    with pytest.raises(FrozenInstanceError):
        original.payload = b"{}"
    result = m.OriginalUsbTrialBootCollector(
        Path.cwd(), original
    ).retained_diagnostics()
    result["state"] = "invented"
    assert case.collector.retained_diagnostics()["state"] == "NOT_STARTED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "AFTER_RECONNECT"),
        ("phase_id", "old-operation"),
        ("launch_session_id", "wizard-generic"),
        ("script_sha256", "f" * 64),
        (
            "budget",
            {"admission_window_ms": 30001, "process_run_ms": 10000, "cleanup_ms": 2000},
        ),
        ("physical_authority", 0),
        ("plan_sha256", "f" * 64),
        ("extra", None),
    ],
)
def test_intent_closed_binding_and_budget(boot_case, field, value):
    d = boot_case.intent.to_dict()
    d[field] = value
    with pytest.raises(ValueError):
        m.UsbTrialBootIntent(m.canonical(d))


def test_intent_verifier_requires_exact_original_plan_and_event(boot_case):
    case = boot_case
    changed = case.plan.to_dict()
    changed["port_label"] = "Another declared port"
    plan = m.UsbQualificationPlan(m.canonical(changed))
    ref = reference(plan.payload, "changed-plan")
    start = event(
        case,
        "PREPARATION_REQUESTED",
        V2StageState.BLOCKED,
        V2StageState.WAITING_OPERATOR,
        (ref,),
        2,
    )
    with pytest.raises(ValueError, match="RECONSTRUCTION"):
        m.verify_usb_trial_boot_intent(
            case.intent,
            expected_sha256=case.intent.sha256,
            **dict(case.args, plan=plan, plan_reference=ref, phase_start_event=start),
        )


def test_collector_records_request_before_observer_and_exact_full_held_bytes(
    boot_case, monkeypatch
):
    case = boot_case
    install_observer(case, monkeypatch)
    result = collect(case)
    d = case.collector.retained_diagnostics()
    assert d["state"] == "BOOT_HELD"  # Injected values cannot be physical boot proof.
    assert case.report.to_dict()["origin"] == "INJECTED_CIM_EXECUTOR"
    assert case.report.to_dict()["status"] == "OBSERVED_HOST_BOOT"
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert m.canonical(result["document"]) == case.stored[0][1] == case.report.payload
    assert [x[0] for x in case.calls].index("commit") < [
        x[0] for x in case.calls
    ].index("observe")
    assert case.states[STAGE] is V2StageState.BLOCKED
    assert all(case.states[s] is V2StageState.PENDING for s in STAGE_ORDER[4:])
    assert len(case.stored) == 1
    result["document"]["origin"] = "changed"
    assert (
        case.collector.retained_diagnostics()["host_boot"]["document"]["origin"]
        == "INJECTED_CIM_EXECUTOR"
    )
    with pytest.raises(ValueError, match="ALREADY_USED"):
        collect(case)
    assert len([x for x in case.calls if x[0] == "observe"]) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "handles_remaining",
        "pins_remaining",
        "unclosed_handles_remaining",
        "stdin_pending",
        "late_cleanup",
        "unknown",
        "cleanup_error",
        "legacy",
    ],
)
def test_uncertain_owned_cleanup_is_retained_not_clean_terminal(
    boot_case, monkeypatch, fault
):
    case = boot_case
    install_observer(case, monkeypatch, fault=fault)
    result = collect(case)
    assert case.collector.retained_diagnostics()["state"] == "BOOT_UNCERTAIN"
    assert case.states[STAGE] is V2StageState.SIDE_EFFECT_UNCERTAIN
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert m.canonical(result["document"]) == case.report.payload
    if fault == "unknown":
        assert result["document"]["execution"]["ownership"]["handles_remaining"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "cancel",
        "deadline",
        "guard",
        "head",
        "leases",
        "missing-start",
        "intent-bytes",
    ],
)
def test_initial_stale_or_unreviewed_scope_has_no_commit_or_observer(
    boot_case, monkeypatch, fault
):
    case = boot_case
    install_observer(case, monkeypatch)
    guard = lambda: None
    if fault == "source":
        case.source = "f" * 64
    elif fault == "cancel":
        case.cancel.set()
    elif fault == "deadline":
        case.deadline = 1
    elif fault == "guard":
        guard = lambda: True
    elif fault == "head":
        case.events[-1] = case.start
    elif fault == "leases":
        case.leases = (
            *case.leases,
            m.LeaseSpec(m.LeaseLevel.CAMERA, case.binding["cell_id"]),
        )
    elif fault == "missing-start":
        case.events.pop(0)
    else:
        case.payloads[case.intent_reference] = b"{}"
    with pytest.raises(ValueError):
        collect(case, revalidate_context=guard)
    assert not case.stored and not any(
        x[0] in {"commit", "observe"} for x in case.calls
    )


def test_stop_after_request_is_durable_pending_and_reopened_owner_does_not_replay(
    boot_case, monkeypatch
):
    case = boot_case
    install_observer(case, monkeypatch)
    original = case.tx.commit_stage_state

    def stop_after_commit(*a, **k):
        result = original(*a, **k)
        case.cancel.set()
        return result

    monkeypatch.setattr(case.tx, "commit_stage_state", stop_after_commit)
    with pytest.raises(ValueError, match="INTERRUPTED"):
        collect(case)
    assert case.collector.retained_diagnostics()["state"] == "REQUESTED"
    assert not case.stored and not any(x[0] == "observe" for x in case.calls)
    case.cancel.clear()
    case.collector = m.OriginalUsbTrialBootCollector(Path.cwd(), case.intent)
    with pytest.raises(ValueError, match="CURRENT_REVIEWED"):
        collect(case)
    assert len([x for x in case.calls if x[0] == "commit"]) == 1


def test_changed_head_at_observer_admission_is_refused(boot_case, monkeypatch):
    case = boot_case
    install_observer(
        case, monkeypatch, during=lambda: setattr(case, "reconciliation", True)
    )
    with pytest.raises(ValueError, match="ADMISSION_CHANGED"):
        collect(case)
    assert case.states[STAGE] is V2StageState.WAITING_OPERATOR and not case.stored
    assert case.collector.retained_diagnostics()["host_boot"] is None


def test_stop_after_observer_return_does_not_discard_full_report(
    boot_case, monkeypatch
):
    case = boot_case
    install_observer(case, monkeypatch, fault="cancelled")
    observer_type = m.WindowsHostBootObserver

    class StopAfterObserver(observer_type):
        def observe(self, *a, **k):
            report = super().observe(*a, **k)
            case.cancel.set()
            return report

    monkeypatch.setattr(m, "WindowsHostBootObserver", StopAfterObserver)
    result = collect(case)
    assert case.cancel.is_set()
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert case.collector.retained_diagnostics()["state"] == "BOOT_HELD"


def test_failed_original_store_retains_collected_bytes_without_terminal(
    boot_case, monkeypatch
):
    case = boot_case
    install_observer(case, monkeypatch)

    def failed_store(*a, **k):
        raise OSError("MODELED_ORIGINAL_STORAGE_FAILURE")

    monkeypatch.setattr(case.tx, "store_evidence", failed_store)
    with pytest.raises(OSError):
        collect(case)
    d = case.collector.retained_diagnostics()
    assert d["host_boot"]["reference"] is None
    assert d["host_boot"]["retention"] == "COLLECTED_NOT_M1_RETAINED"
    assert m.canonical(d["host_boot"]["document"]) == case.report.payload
    assert (
        d["terminal_event"] is None
        and case.states[STAGE] is V2StageState.WAITING_OPERATOR
    )


def observation_subjects(case, **changes):
    requested = event(
        case,
        "BOOT_REQUESTED",
        V2StageState.BLOCKED,
        V2StageState.WAITING_OPERATOR,
        (case.intent_reference,),
        5,
        case.events[-1].event_sha256,
    )
    fields = dict(
        source_sha256=case.binding["source_sha256"],
        session_id=case.binding["session_id"],
        launch_session_id=LAUNCH,
        operation_id=PHASE,
        trial_id=case.binding["trial_id"],
        phase="BASELINE",
        expires_at_ns=time.monotonic_ns() + 30_000_000_000,
    )
    fields.update(changes)
    return owned_report(host.HostBootRequest(**fields)), requested


def test_observation_verifier_is_pure_and_preserves_injected_origin(
    boot_case, monkeypatch
):
    case = boot_case
    report, requested = observation_subjects(case)
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure verifier read file")
    )
    checked = m.verify_usb_trial_boot_observation(
        report,
        intent=case.intent,
        expected_sha256=report.sha256,
        requested_event=requested,
    )
    assert checked.payload == report.payload
    assert checked.to_dict()["origin"] == "INJECTED_CIM_EXECUTOR"
    assert m._terminal(checked) == "BOOT_HELD"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "f" * 64),
        ("session_id", "physical-camera-" + "f" * 32),
        ("launch_session_id", "wizard-" + "f" * 32),
        ("operation_id", "usbphase-" + "f" * 32),
        ("trial_id", "usbtrial-" + "f" * 32),
        ("phase", "AFTER_REBOOT"),
    ],
)
def test_observation_requires_exact_original_request_context(boot_case, field, value):
    case = boot_case
    report, requested = observation_subjects(case, **{field: value})
    with pytest.raises(ValueError, match="INTENT_MISMATCH"):
        m.verify_usb_trial_boot_observation(
            report,
            intent=case.intent,
            expected_sha256=report.sha256,
            requested_event=requested,
        )


@pytest.mark.parametrize(
    "fault", ["event-hash", "event-sequence", "report-hash", "window"]
)
def test_observation_revalidates_event_bytes_hash_and_separate_30s_window(
    boot_case, fault
):
    case = boot_case
    changes = (
        {"expires_at_ns": time.monotonic_ns() + 31_000_000_000}
        if fault == "window"
        else {}
    )
    report, requested = observation_subjects(case, **changes)
    expected = report.sha256
    if fault == "event-hash":
        requested = replace(requested, event_sha256="f" * 64)
    elif fault == "event-sequence":
        requested = replace(requested, sequence=requested.sequence + 1)
    elif fault == "report-hash":
        expected = "f" * 64
    with pytest.raises(ValueError):
        m.verify_usb_trial_boot_observation(
            report,
            intent=case.intent,
            expected_sha256=expected,
            requested_event=requested,
        )
