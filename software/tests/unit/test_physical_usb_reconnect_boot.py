"""Reconnect boot original joins with MODELED storage and host observations.

Actual immutable codecs and collector logic run. No real M1 lease, process,
USB/CIM/camera/serial operation or original-store qualification is claimed.
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

from rocell.application import physical_usb_reconnect_boot as m
from rocell.application import physical_camera_usb_reconnect as preparation_module
from rocell.application.usb_identity_stage_policy import (
    UsbIdentityPolicyReview,
    UsbIdentityAdmissionIdentity,
)
from rocell.providers.windows import host_boot_observation as host
from test_physical_camera_usb_qualification import reference
from test_physical_camera_usb_reconnect_preparation import preparation_inputs
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_absence_boot import modeled_boot
from test_physical_usb_reconnect_phase import reconnect_fixture

STAGE = m.STAGE_ORDER[3]


@pytest.fixture(autouse=True)
def no_process_or_devices(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Reconnect boot tests cannot invoke native processes/devices/CIM")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)


def journal(case, code, previous, state, refs, sequence, timestamp, previous_hash):
    event = m.V2JournalEvent(
        case.binding["session_id"],
        case.binding["header_sha256"],
        sequence,
        STAGE,
        previous,
        state,
        timestamp,
        previous_hash,
        tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
        code,
        "0" * 64,
    )
    return m._parse_event(
        replace(event, event_sha256=m.digest(m.canonical(event.core_dict()))).to_dict()
    )


def reconnect_boot_subjects(prerequisites):
    """Reusable original-shaped sources, built through the actual pure codecs."""
    seed = reconnect_fixture(prerequisites)
    args = preparation_inputs(
        original_baseline=seed.original_baseline,
        absence=seed.absence,
        absence_sources=seed.absence_sources,
        operator_event=seed.event,
        operation=seed.operation,
        enrollment=seed.sources["native_enrollment"],
    )
    preparation = preparation_module.build_usb_reconnect_preparation(**args)
    prep_ref = reference(preparation.payload, "MODELED-reconnect-preparation")
    intent = m.build_usb_reconnect_boot_intent(
        preparation=preparation, preparation_reference=prep_ref
    )
    case = SimpleNamespace(
        seed=seed,
        prep_args=args,
        preparation=preparation,
        prep_ref=prep_ref,
        operation_ref=reference(seed.operation.payload, "MODELED-reconnect-operation"),
        intent=intent,
        intent_ref=reference(intent.payload, "MODELED-reconnect-boot-request"),
        binding=seed.original_baseline["plan"].to_dict()["binding"],
        phase_id=seed.context["operation_id"],
        launch=seed.context["launch_session_id"],
        workspace=Path(seed.operation.to_dict()["workspace"]),
        start=args["phase_start_event"],
        start_ns=seed.context["started_at_utc_ns"],
    )
    runtime_review = seed.run.preparation.review
    rd = runtime_review.to_dict()
    policy = UsbIdentityPolicyReview(
        m.canonical(
            dict(
                schema="rocell.usb_identity_stage_policy_review.v1",
                **{
                    key: case.binding[key]
                    for key in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                    )
                },
                policy=m.qualification.usb_identity_stage_policy().to_dict(),
                policy_sha256=case.binding["stage_policy_sha256"],
                operator_id=rd["operator_id"],
                reviewer_id=rd["reviewer_id"],
                reviewed_at_utc_ns=rd["reviewed_at_ns"],
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
    case.policy_ref = reference(policy.payload, "MODELED-reconnect-policy-review")
    case.runtime_ref = reference(
        runtime_review.payload, "MODELED-reconnect-runtime-review"
    )
    identity = seed.campaign.identity.to_dict()
    identity.update(
        policy_review_sha256=policy.sha256,
        original_subjects=[
            dict(role=role, reference=ref.to_dict(), document_sha256=ref.payload_sha256)
            for role, ref in (
                ("metadata", args["enrollment_reference"]),
                ("policy_review", case.policy_ref),
                ("runtime_review", case.runtime_ref),
            )
        ],
    )
    case.identity = UsbIdentityAdmissionIdentity(m.canonical(identity))
    case.identity_ref = reference(case.identity.payload, "MODELED-reconnect-identity")
    case.current_payloads = {
        prep_ref: preparation.payload,
        case.operation_ref: seed.operation.payload,
        case.intent_ref: intent.payload,
        args["operator_event_reference"]: seed.event.payload,
        args["enrollment_reference"]: seed.sources["native_enrollment"],
        case.policy_ref: policy.payload,
        case.runtime_ref: runtime_review.payload,
        case.identity_ref: case.identity.payload,
    }
    case.prepared = journal(
        case,
        m.usb_reconnect_event("PREPARED", case.phase_id),
        m.V2StageState.WAITING_OPERATOR,
        m.V2StageState.REVIEW_PENDING,
        (
            prep_ref,
            case.operation_ref,
            args["operator_event_reference"],
            args["enrollment_reference"],
        ),
        case.start.sequence + 1,
        preparation.to_dict()["prepared_at_utc_ns"],
        case.start.event_sha256,
    )
    case.reviewed = journal(
        case,
        m.usb_reconnect_event("REVIEWED", case.phase_id),
        m.V2StageState.REVIEW_PENDING,
        m.V2StageState.BLOCKED,
        tuple(case.current_payloads),
        case.prepared.sequence + 1,
        rd["reviewed_at_ns"] + 1,
        case.prepared.event_sha256,
    )
    ad = seed.absence.to_dict()
    absence_refs = [
        m.qualification._reference(row["reference"]) for row in ad["records"]
    ]
    # The collector consumes the four exact phase sources and phase record.
    # Four additional v11 slots model the outer original reader's prior audit;
    # these inert placeholders are not claimed as actual M1 or verified roles.
    absence_refs += [
        reference(
            m.canonical({"MODELED_V11_READER_SLOT": index}),
            "MODELED-v11-slot-" + str(index),
        )
        for index in range(4)
    ]
    absence_refs.append(args["absence_reference"])
    case.absence_terminal = journal(
        case,
        "CAMERA_USB_TRIAL_ABSENCE_RETAINED_"
        + ad["context"]["operation_id"][9:].upper(),
        m.V2StageState.WAITING_OPERATOR,
        m.V2StageState.BLOCKED,
        absence_refs,
        case.start.sequence - 1,
        ad["context"]["finished_at_utc_ns"] + 1,
        "a" * 64,
    )
    return case


@pytest.fixture
def boot_case(prerequisites, monkeypatch):
    c = reconnect_boot_subjects(prerequisites)
    original = c.seed.original_baseline
    c.events = [
        original["declaration_event"],
        c.absence_terminal,
        c.start,
        c.prepared,
        c.reviewed,
    ]
    c.payloads = dict(c.current_payloads)
    c.payloads.update(
        {
            original["plan_reference"]: original["plan"].payload,
            original["baseline_reference"]: original["baseline"].payload,
            c.prep_args["absence_reference"]: c.seed.absence.payload,
        }
    )
    for row in original["baseline"].to_dict()["records"]:
        c.payloads[m.qualification._reference(row["reference"])] = original[
            "baseline_sources"
        ][row["role"]]
    for row in c.seed.absence.to_dict()["records"]:
        c.payloads[m.qualification._reference(row["reference"])] = (
            c.seed.absence_sources[row["role"]]
        )
    c.calls, c.stored = [], []
    c.states = {
        stage: m.V2StageState.PASS if index < 3 else m.V2StageState.PENDING
        for index, stage in enumerate(m.STAGE_ORDER)
    }
    c.states[STAGE] = m.V2StageState.BLOCKED
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
    c.source, c.reconciliation = c.binding["source_sha256"], False
    c.cancel, c.deadline = Event(), time.monotonic_ns() + 60_000_000_000
    c.wall = c.reviewed.occurred_at_ns + 1

    def snapshot():
        return SimpleNamespace(
            header=c.header,
            committed_events=tuple(c.events),
            head=SimpleNamespace(head_sha256=c.events[-1].event_sha256),
            reconciliation_required=c.reconciliation,
            state_for=lambda stage: c.states[stage],
        )

    def read(ref):
        c.calls.append(("read", ref))
        return c.payloads[ref]

    def store(
        stage, payload, *, label, media_type, captured_at_ns, expected_head_sha256
    ):
        assert stage is STAGE and media_type == "application/json"
        assert expected_head_sha256 == snapshot().head.head_sha256
        ref = reference(payload, label)
        c.payloads[ref] = payload
        c.stored.append((ref, payload, label))
        c.calls.append(("store", label))
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

    c.tx = object.__new__(m.M1PhysicalCameraTransaction)
    monkeypatch.setattr(
        m.M1PhysicalCameraTransaction, "held_leases", property(lambda self: c.leases)
    )
    monkeypatch.setattr(c.tx, "snapshot", snapshot)
    monkeypatch.setattr(c.tx, "read_stage_evidence", read)
    monkeypatch.setattr(c.tx, "store_evidence", store)
    monkeypatch.setattr(c.tx, "commit_stage_state", commit)
    monkeypatch.setattr(m, "source_fingerprint", lambda path: c.source)
    monkeypatch.setattr(m, "time_ns", lambda: c.wall)
    c.collector = m.OriginalUsbReconnectBootCollector(c.workspace, c.intent)
    return c


def install_observer(c, monkeypatch, *, fault=None, physical=True, after=None):
    class Observer:
        def observe(self, request, **kwargs):
            c.calls.append(("observe", request))
            assert c.events[-1].detail_code == m.usb_reconnect_event(
                "BOOT_REQUESTED", c.phase_id
            )
            assert request.expires_at_ns == kwargs["deadline_ns"] <= c.deadline
            c.report = modeled_boot(
                c,
                request,
                fault=fault,
                origin="WINDOWS_LOCAL_CIM" if physical else "INJECTED_CIM_EXECUTOR",
                admission_check=kwargs["admission_check"],
            )
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


def test_intent_inert_exact_detached_and_bounded(boot_case, monkeypatch):
    c = boot_case
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("intent performed file I/O")
    )
    intent = m.verify_usb_reconnect_boot_intent(
        c.intent,
        expected_sha256=c.intent.sha256,
        preparation=c.preparation,
        preparation_reference=c.prep_ref,
    )
    m.OriginalUsbReconnectBootCollector(c.workspace, intent)
    assert len(intent.payload) < m.MAX_INTENT_BYTES
    assert intent.to_dict()["budget"] == dict(
        admission_window_ms=30000, process_run_ms=10000, cleanup_ms=2000
    )
    assert all(intent.to_dict()[key] is False for key in m._FLAGS)
    with pytest.raises(FrozenInstanceError):
        intent.payload = b"{}"
    changed = c.collector.retained_diagnostics()
    changed["state"] = "invented"
    assert c.collector.retained_diagnostics()["state"] == "NOT_STARTED"


def test_exact_original_read_review_request_observe_and_retention(
    boot_case, monkeypatch
):
    c = boot_case
    install_observer(c, monkeypatch)
    record = collect(c)
    assert record["retention"] == "M1_FULL_BYTES_READ_BACK"
    diag = c.collector.retained_diagnostics()
    assert len(c.prepared.evidence) == 4 and len(c.reviewed.evidence) == 8
    assert diag["state"] == "BOOT_RETAINED" and diag["context_current"] is True
    assert diag["boot_comparison"]["status"] == "SAME_HOST_SAME_BOOT"
    request_index = next(
        i
        for i, row in enumerate(c.calls)
        if row == ("commit", m.usb_reconnect_event("BOOT_REQUESTED", c.phase_id))
    )
    observe_index = next(i for i, row in enumerate(c.calls) if row[0] == "observe")
    assert request_index < observe_index
    assert set(c.current_payloads) <= {
        row[1] for row in c.calls[:request_index] if row[0] == "read"
    }
    assert all(c.states[stage] is m.V2StageState.PENDING for stage in m.STAGE_ORDER[4:])
    assert c.events[-1].evidence == tuple(
        sorted(
            (c.intent_ref, m.qualification._reference(record["reference"])),
            key=lambda ref: ref.evidence_id,
        )
    )
    assert (
        m.verify_usb_reconnect_boot_observation(
            c.report,
            intent=c.intent,
            expected_sha256=c.report.sha256,
            requested_event=c.events[-2],
        ).payload
        == c.report.payload
    )


@pytest.mark.parametrize(
    "fault,physical,terminal",
    [
        (None, False, "BOOT_HELD"),
        ("different_host", True, "BOOT_HELD"),
        ("different_boot", True, "BOOT_HELD"),
        ("unknown", True, "BOOT_UNCERTAIN"),
        ("late_cleanup", True, "BOOT_UNCERTAIN"),
        ("cancelled", True, "BOOT_HELD"),
    ],
)
def test_actual_typed_host_and_cleanup_mismatches_retain_without_false_success(
    boot_case, monkeypatch, fault, physical, terminal
):
    c = boot_case
    install_observer(c, monkeypatch, fault=fault, physical=physical)
    record = collect(c)
    assert record["document"] == c.report.to_dict()
    assert c.collector.retained_diagnostics()["state"] == terminal
    assert c.states[STAGE] is (
        m.V2StageState.SIDE_EFFECT_UNCERTAIN
        if terminal == "BOOT_UNCERTAIN"
        else m.V2StageState.BLOCKED
    )


def test_intent_policy_original_hash_and_report_binding_fail_closed(boot_case):
    c = boot_case
    for field, value in (
        ("schema", "other"),
        ("phase", "BASELINE"),
        ("operation_sha256", "f" * 64),
        ("launch_session_id", "different-launch"),
        ("script_sha256", "f" * 64),
        ("automatic_replay", True),
        ("physical_authority", 0),
        ("unknown", None),
    ):
        d = c.intent.to_dict()
        d[field] = value
        with pytest.raises(ValueError):
            m.verify_usb_reconnect_boot_intent(
                m.canonical(d),
                expected_sha256=m.digest(m.canonical(d)),
                preparation=c.preparation,
                preparation_reference=c.prep_ref,
            )


@pytest.mark.parametrize(
    "omitted", ["declaration", "absence_terminal", "start", "prepared"]
)
def test_missing_original_event_never_requests_or_constructs_observer(
    boot_case, monkeypatch, omitted
):
    c = boot_case
    target = (
        c.seed.original_baseline["declaration_event"]
        if omitted == "declaration"
        else getattr(c, omitted)
    )
    c.events.remove(target)
    monkeypatch.setattr(
        m,
        "WindowsHostBootObserver",
        lambda: pytest.fail("unexpected observer construction"),
    )
    with pytest.raises(ValueError):
        collect(c)
    assert not c.stored and not any(row[0] == "commit" for row in c.calls)


def test_changed_original_bytes_current_header_or_review_ref_never_requests(
    boot_case, monkeypatch
):
    c = boot_case
    monkeypatch.setattr(
        m,
        "WindowsHostBootObserver",
        lambda: pytest.fail("unexpected observer construction"),
    )
    saved_payloads, saved_header, saved_events = (
        dict(c.payloads),
        deepcopy(c.header),
        list(c.events),
    )
    for fault in ("preparation", "report", "absence", "header", "review_ref"):
        c.payloads, c.header, c.events = (
            dict(saved_payloads),
            deepcopy(saved_header),
            list(saved_events),
        )
        c.collector = m.OriginalUsbReconnectBootCollector(c.workspace, c.intent)
        if fault in ("preparation", "report", "absence"):
            ref = {
                "preparation": c.prep_ref,
                "report": c.prep_args["operator_event_reference"],
                "absence": c.prep_args["absence_reference"],
            }[fault]
            c.payloads[ref] += b" "
        elif fault == "header":
            c.header.header_sha256 = "f" * 64
        else:
            event = replace(
                c.reviewed,
                evidence=tuple(
                    ref for ref in c.reviewed.evidence if ref != c.intent_ref
                ),
            )
            c.events[-1] = replace(
                event, event_sha256=m.digest(m.canonical(event.core_dict()))
            )
        with pytest.raises(ValueError):
            collect(c)
    assert not c.stored and not any(row[0] == "commit" for row in c.calls)


@pytest.mark.parametrize("fault", ["stop", "source", "source_returns", "unknown_stop"])
def test_post_report_context_loss_retains_and_never_downgrades_uncertainty(
    boot_case, monkeypatch, fault
):
    c = boot_case

    def after():
        if fault in ("source", "source_returns"):
            c.source = "f" * 64
        else:
            c.cancel.set()

    install_observer(
        c,
        monkeypatch,
        fault="unknown" if fault == "unknown_stop" else None,
        after=after,
    )
    if fault == "source_returns":
        original_store = c.tx.store_evidence

        def store(*args, **kwargs):
            result = original_store(*args, **kwargs)
            c.source = c.binding["source_sha256"]
            return result

        monkeypatch.setattr(c.tx, "store_evidence", store)
    result = collect(c)
    assert result["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert c.collector.retained_diagnostics()["state"] == (
        "BOOT_UNCERTAIN" if fault == "unknown_stop" else "BOOT_HELD"
    )
    assert c.collector.retained_diagnostics()["context_current"] is False


def test_stop_during_store_is_rechecked_after_readback(boot_case, monkeypatch):
    c = boot_case
    install_observer(c, monkeypatch)
    original_store = c.tx.store_evidence

    def store(*args, **kwargs):
        result = original_store(*args, **kwargs)
        c.cancel.set()
        return result

    monkeypatch.setattr(c.tx, "store_evidence", store)
    collect(c)
    assert c.collector.retained_diagnostics()["state"] == "BOOT_HELD"
    assert (
        c.collector.retained_diagnostics()["host_boot"]["retention"]
        == "M1_FULL_BYTES_READ_BACK"
    )


def test_pending_request_no_replay_and_constructor_failure_preserved(
    boot_case, monkeypatch
):
    c = boot_case

    def failed():
        raise RuntimeError("MODELED_CONSTRUCTOR_FAILED")

    monkeypatch.setattr(m, "WindowsHostBootObserver", failed)
    with pytest.raises(RuntimeError, match="CONSTRUCTOR_FAILED"):
        collect(c)
    assert c.events[-1].detail_code == m.usb_reconnect_event(
        "BOOT_REQUESTED", c.phase_id
    )
    assert (
        c.collector.retained_diagnostics()["requested_event"] == c.events[-1].to_dict()
    )
    with pytest.raises(ValueError, match="ALREADY_USED"):
        collect(c)
    c.collector = m.OriginalUsbReconnectBootCollector(c.workspace, c.intent)
    with pytest.raises(ValueError, match="REVIEWED"):
        collect(c)
    assert len([row for row in c.calls if row[0] == "commit"]) == 1 and not c.stored


def test_failed_readback_keeps_full_collected_and_published_reference(
    boot_case, monkeypatch
):
    c = boot_case
    install_observer(c, monkeypatch)
    original = c.tx.read_stage_evidence

    def read(ref):
        if c.stored and ref == c.stored[-1][0]:
            return original(ref) + b" "
        return original(ref)

    monkeypatch.setattr(c.tx, "read_stage_evidence", read)
    with pytest.raises(ValueError):
        collect(c)
    d = c.collector.retained_diagnostics()
    assert d["host_boot"]["document"] == c.report.to_dict()
    assert d["host_boot"]["reference"] == c.stored[-1][0].to_dict()
    assert d["host_boot"]["retention"] == "M1_PUBLISHED_READBACK_PENDING"
    assert d["terminal_event"] is None


def test_pre_request_stop_source_deadline_guard_or_lease_refuses_without_effect(
    boot_case, monkeypatch
):
    c = boot_case
    monkeypatch.setattr(
        m, "WindowsHostBootObserver", lambda: pytest.fail("unexpected observer")
    )
    original_leases, original_deadline = c.leases, c.deadline
    for fault in ("stop", "source", "deadline", "guard", "leases"):
        c.cancel = Event()
        c.source, c.leases, c.deadline = (
            c.binding["source_sha256"],
            original_leases,
            original_deadline,
        )
        c.collector = m.OriginalUsbReconnectBootCollector(c.workspace, c.intent)
        args = {}
        if fault == "stop":
            c.cancel.set()
        elif fault == "source":
            c.source = "f" * 64
        elif fault == "deadline":
            c.deadline = 1
        elif fault == "guard":
            args["revalidate_context"] = lambda: True
        else:
            c.leases = ()
        with pytest.raises(ValueError):
            collect(c, **args)
    assert not c.stored and not any(row[0] == "commit" for row in c.calls)


def test_observation_needs_exact_reconstructed_request_event_and_current_intent(
    boot_case, monkeypatch
):
    c = boot_case
    install_observer(c, monkeypatch)
    collect(c)
    event = c.events[-2]
    for fields in (
        {"session_header_sha256": "f" * 64},
        {"detail_code": m.usb_reconnect_event("QUERY_REQUESTED", c.phase_id)},
        {"evidence": (c.prep_ref,)},
    ):
        changed = replace(event, **fields)
        changed = replace(
            changed, event_sha256=m.digest(m.canonical(changed.core_dict()))
        )
        with pytest.raises(ValueError):
            m.verify_usb_reconnect_boot_observation(
                c.report,
                intent=c.intent,
                expected_sha256=c.report.sha256,
                requested_event=changed,
            )
    with pytest.raises(ValueError):
        m.verify_usb_reconnect_boot_observation(
            c.report, intent=c.intent, expected_sha256="f" * 64, requested_event=event
        )


def test_store_failure_keeps_collected_bytes_and_durable_pending_request(
    boot_case, monkeypatch
):
    c = boot_case
    install_observer(c, monkeypatch)

    def failed(*args, **kwargs):
        raise OSError("MODELED_STORE_FAILURE")

    monkeypatch.setattr(c.tx, "store_evidence", failed)
    with pytest.raises(OSError, match="STORE_FAILURE"):
        collect(c)
    d = c.collector.retained_diagnostics()
    assert d["host_boot"]["document"] == c.report.to_dict()
    assert d["host_boot"]["retention"] == "COLLECTED_NOT_M1_RETAINED"
    assert d["host_boot"]["reference"] is None and d["terminal_event"] is None
    assert d["requested_event"] == c.events[-1].to_dict()


def test_separate_operation_original_required_in_prepared_and_reviewed(
    boot_case, monkeypatch
):
    c = boot_case
    monkeypatch.setattr(
        m, "WindowsHostBootObserver", lambda: pytest.fail("unexpected observer")
    )
    saved_events, saved_payloads = list(c.events), dict(c.payloads)
    for fault in ("missing_prepared", "missing_reviewed", "reviewed_alias"):
        c.events, c.payloads = list(saved_events), dict(saved_payloads)
        c.collector = m.OriginalUsbReconnectBootCollector(c.workspace, c.intent)
        event_index = -2 if fault == "missing_prepared" else -1
        event = c.events[event_index]
        refs = [ref for ref in event.evidence if ref != c.operation_ref]
        if fault == "reviewed_alias":
            alias = reference(c.seed.operation.payload, "MODELED-operation-alias")
            assert alias != c.operation_ref
            refs.append(alias)
            c.payloads[alias] = c.seed.operation.payload
        c.events[event_index] = journal(
            c,
            event.detail_code,
            event.previous_state,
            event.state,
            refs,
            event.sequence,
            event.occurred_at_ns,
            event.previous_event_sha256,
        )
        if event_index == -2:
            old = c.events[-1]
            c.events[-1] = journal(
                c,
                old.detail_code,
                old.previous_state,
                old.state,
                old.evidence,
                old.sequence,
                old.occurred_at_ns,
                c.events[-2].event_sha256,
            )
        with pytest.raises(ValueError):
            collect(c)
    assert not c.stored and not any(row[0] == "commit" for row in c.calls)


def test_actual_operation_bytes_must_match_preparation_not_just_typed_shape(
    boot_case, monkeypatch
):
    c = boot_case
    monkeypatch.setattr(
        m, "WindowsHostBootObserver", lambda: pytest.fail("unexpected observer")
    )
    # This is a valid, separately retained V2 operation, but for another phase.
    changed = c.seed.operation.to_dict()
    changed["phase_binding"]["operation_id"] = "usbphase-" + "f" * 32
    different = m.UsbIdentityOperation(m.canonical(changed))
    assert different.sha256 != c.seed.operation.sha256
    different_ref = reference(different.payload, "MODELED-different-operation")
    c.payloads[different_ref] = different.payload
    for index in (-2, -1):
        event = c.events[index]
        refs = [
            different_ref if ref == c.operation_ref else ref for ref in event.evidence
        ]
        previous = (
            c.events[-2].event_sha256 if index == -1 else event.previous_event_sha256
        )
        c.events[index] = journal(
            c,
            event.detail_code,
            event.previous_state,
            event.state,
            refs,
            event.sequence,
            event.occurred_at_ns,
            previous,
        )
    with pytest.raises(ValueError, match="BOOT_ORIGINAL_OPERATION_MISMATCH"):
        collect(c)
    assert ("read", different_ref) in c.calls
    assert not c.stored and not any(row[0] == "commit" for row in c.calls)
