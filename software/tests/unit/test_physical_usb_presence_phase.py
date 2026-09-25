"""Pure retained absence records; all physical-shaped facts are MODELED.

No original NTFS admission, process, CIM, USB, camera or arm action is performed.
Independent original-byte reconstruction is exercised with actual closed codecs.
"""

from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import os
import subprocess

import pytest

from rocell.application import physical_usb_presence_phase as m
from rocell.application import physical_camera_usb_qualification as legacy
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows import owned_usb_presence_evidence as owned
from rocell.providers.windows.usb_presence_protocol import canonical, digest
from test_host_boot_observation import request, execution, response, FakeExecutor
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_presence_binding import reference
from test_physical_usb_presence_campaign import modeled_presence_campaign


@pytest.fixture(autouse=True)
def no_hardware(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure phase record must not execute a process or device query")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(host, "_system_powershell", forbidden)
    monkeypatch.setattr(host, "_native_owner", forbidden)


def modeled_boot(
    case, *, origin="WINDOWS_LOCAL_CIM", host_change=False, boot_change=False
):
    op = case.operation.to_dict()
    req = request(
        source_sha256=op["source_sha256"],
        session_id=op["session_id"],
        trial_id=op["trial_id"],
        phase=m.PHASE,
        launch_session_id=op["launch_session_id"],
        operation_id=op["operation_id"],
    )
    changes = {}
    if host_change:
        changes["machine_uuid"] = "aaaaaaaa-1234-5678-9abc-0123456789ab"
    if boot_change:
        changes.update(
            last_boot_up_time_utc="2026-01-01T02:00:00.010000Z",
            confirmation_boot_up_time_utc="2026-01-01T02:00:00.010000Z",
        )
    ex = execution(req, wall=case.phase_start + 3_000, raw=response(req, **changes))
    ex = replace(
        ex,
        command={**ex.command, "process_model": host.PROCESS_MODEL},
        ownership=dict(
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
        ),
    )
    raw = (
        host.WindowsHostBootObserver(FakeExecutor(ex))
        .observe(
            req,
            cancellation=Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: None,
        )
        .to_dict()
    )
    # Closed physical-shaped model only; no report is promoted by production code.
    raw["origin"] = origin
    return host.HostBootObservation(canonical(raw))


def phase_fixture(prerequisites, *, outcome="ABSENT", **boot_options):
    seed = modeled_presence_campaign(prerequisites)
    phase_start = seed.phase_binding.to_dict()["not_before_utc_ns"] + 1_000_000_000
    case = modeled_presence_campaign(
        prerequisites, outcome=outcome, reviewed_at_ns=phase_start + 1_000_000
    )
    case.phase_start = phase_start
    boot = modeled_boot(case, **boot_options)
    op = case.operation.to_dict()
    event = m.build_usb_presence_operator_event(
        phase_binding=case.phase_binding,
        phase_id=op["operation_id"],
        launch_session_id=op["launch_session_id"],
        operator_id="MODELED-inspector",
        phase_started_at_utc_ns=phase_start,
        reported_at_utc_ns=phase_start + 2_000,
    )
    sources = dict(
        operation=case.operation.payload,
        operator_event=event.payload,
        owned_presence_run=case.owned_run.payload,
        host_boot=boot.payload,
    )
    context = dict(
        launch_session_id=op["launch_session_id"],
        operation_id=op["operation_id"],
        operator_id="MODELED-inspector",
        started_at_utc_ns=phase_start,
        finished_at_utc_ns=case.owned_run.to_dict()["finished_utc_ns"] + 1_000,
    )
    return SimpleNamespace(case=case, context=context, sources=sources)


def build(subject, *, sources=None, context=None, references=None):
    sources = subject.sources if sources is None else sources
    return m.build_usb_presence_qualification_phase(
        original_baseline=subject.case.original_baseline,
        context=subject.context if context is None else context,
        sources=sources,
        references=(
            {
                key: reference(raw, "MODELED-absence-" + key)
                for key, raw in sources.items()
            }
            if references is None
            else references
        ),
    )


@pytest.fixture
def subject(prerequisites):
    return phase_fixture(prerequisites)


@pytest.mark.parametrize("outcome", ["ABSENT", "PRESENT", "HELD"])
def test_physical_samples_are_distinct_from_operator_report(prerequisites, outcome):
    subject = phase_fixture(prerequisites, outcome=outcome)
    phase = build(subject)
    d = phase.to_dict()
    assert d["presence_outcome"] == outcome
    assert d["status"] == (
        "ABSENCE_OBSERVATIONS_RETAINED" if outcome == "ABSENT" else "HELD"
    )
    assert d["physical_node_absence_observed"] is (outcome == "ABSENT")
    assert all(d[key] is False for key in m.FLAGS)
    assert d["boot_relation"] == "SAME_HOST_SAME_BOOT"
    assert len(phase.payload) <= m.PHASE_LIMIT
    assert (
        m.verify_usb_presence_qualification_phase(
            phase.payload,
            expected_sha256=phase.sha256,
            original_baseline=subject.case.original_baseline,
            sources=subject.sources,
        ).payload
        == phase.payload
    )


@pytest.mark.parametrize(
    "changes,missing",
    [
        ({"origin": "INJECTED_CIM_EXECUTOR"}, "HOST_BOOT_PHYSICAL_OWNED_CLEAN"),
        ({"host_change": True}, "SAME_HOST_SAME_BOOT_AS_BASELINE"),
        ({"boot_change": True}, "SAME_HOST_SAME_BOOT_AS_BASELINE"),
    ],
)
def test_injected_host_or_boot_changes_hold_without_fabricating_absence(
    prerequisites, changes, missing
):
    d = build(phase_fixture(prerequisites, **changes)).to_dict()
    assert d["status"] == "HELD" and missing in d["missing_requirements"]
    assert d["presence_outcome"] == "ABSENT" and not d["physical_node_absence_observed"]


def test_operator_report_after_boot_is_retained_but_cannot_qualify(subject):
    event = m.UsbPresenceOperatorEvent(subject.sources["operator_event"]).to_dict()
    event["reported_at_utc_ns"] = subject.case.phase_start + 4_001
    sources = dict(subject.sources, operator_event=canonical(event))
    d = build(subject, sources=sources).to_dict()
    assert d["status"] == "HELD"
    assert "OPERATOR_REPORT_BOOT_REVIEW_QUERY_ORDER" in d["missing_requirements"]


def test_phase_ending_before_owned_run_cannot_pass(subject):
    d = build(
        subject,
        context=dict(
            subject.context,
            finished_at_utc_ns=subject.case.owned_run.to_dict()["started_utc_ns"],
        ),
    ).to_dict()
    assert d["status"] == "HELD"
    assert "OPERATOR_REPORT_BOOT_REVIEW_QUERY_ORDER" in d["missing_requirements"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase_id", "usbphase-" + "e" * 32),
        ("launch_session_id", "wizard-other"),
        ("operator_id", "MODELED-other"),
        ("phase_started_at_utc_ns", 1),
        ("phase_binding_sha256", "e" * 64),
    ],
)
def test_rehashed_operator_event_cannot_move_between_originals(subject, field, value):
    event = m.UsbPresenceOperatorEvent(subject.sources["operator_event"]).to_dict()
    event[field] = value
    with pytest.raises(m.UsbPresencePhaseError):
        build(subject, sources=dict(subject.sources, operator_event=canonical(event)))


@pytest.mark.parametrize("role", m.ROLES)
def test_wrong_original_reference_rejected(subject, role):
    refs = {
        key: reference(raw, "MODELED-absence-" + key)
        for key, raw in subject.sources.items()
    }
    refs[role] = reference(b"unrelated retained bytes", "MODELED-wrong-role")
    with pytest.raises(m.UsbPresencePhaseError):
        build(subject, references=refs)


@pytest.mark.parametrize("field", tuple(m.FLAGS))
def test_operator_event_cannot_claim_any_physical_authority(subject, field):
    event = m.UsbPresenceOperatorEvent(subject.sources["operator_event"]).to_dict()
    event[field] = True
    with pytest.raises(m.UsbPresencePhaseError, match="AUTHORITY"):
        m.UsbPresenceOperatorEvent(canonical(event))


def test_rehashed_display_cannot_replace_independent_original_observation(
    prerequisites,
):
    subject = phase_fixture(prerequisites, outcome="PRESENT")
    d = build(subject).to_dict()
    d.update(
        presence_outcome="ABSENT",
        status="ABSENCE_OBSERVATIONS_RETAINED",
        physical_node_absence_observed=True,
        missing_requirements=[],
    )
    for row in d["checks"]:
        row["passed"] = True
    forged = canonical(d)
    # Syntax-valid caches are not original trust; verification must rebuild.
    m.UsbPresenceQualificationPhase(forged)
    with pytest.raises(m.UsbPresencePhaseError, match="RECONSTRUCTION"):
        m.verify_usb_presence_qualification_phase(
            forged,
            expected_sha256=digest(forged),
            original_baseline=subject.case.original_baseline,
            sources=subject.sources,
        )


def test_changed_operation_nonce_cannot_reuse_owned_presence_evidence(subject):
    operation = subject.case.operation.to_dict()
    operation["request_nonce"] = "b" * 64
    with pytest.raises(m.UsbPresencePhaseError):
        build(subject, sources=dict(subject.sources, operation=canonical(operation)))


def test_incomplete_and_wrong_baseline_originals_cannot_qualify(subject):
    original = dict(subject.case.original_baseline)
    original["baseline_sources"] = dict(
        original["baseline_sources"], host_boot=subject.sources["host_boot"]
    )
    sources = subject.sources
    with pytest.raises(m.UsbPresencePhaseError):
        m.build_usb_presence_qualification_phase(
            original_baseline=original,
            context=subject.context,
            sources=sources,
            references={
                key: reference(raw, "MODELED-absence-" + key)
                for key, raw in sources.items()
            },
        )


def test_uncertain_cleanup_keeps_observation_but_withholds_phase(subject):
    raw = subject.case.owned_run.to_dict()
    raw.update(
        cleanup_finished_ns=raw["cleanup_deadline_ns"] + 1,
        finished_monotonic_ns=raw["cleanup_deadline_ns"] + 2,
    )
    changed = owned.retain_owned_usb_presence_run(raw)
    d = build(
        subject, sources=dict(subject.sources, owned_presence_run=changed.payload)
    ).to_dict()
    assert d["status"] == "HELD" and d["presence_outcome"] == "ABSENT"
    assert "PRESENCE_PROCESS_CLEANUP_CONFIRMED" in d["missing_requirements"]
    assert not d["physical_node_absence_observed"]


def test_new_record_is_not_old_endpoint_absence(subject, monkeypatch):
    phase = build(subject)
    with pytest.raises(ValueError):
        legacy.UsbQualificationPhase(phase.payload)
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure reconstruction opens a file")
    )
    assert build(subject).payload == phase.payload


def test_missing_native_receipt_keeps_unknown_observation_and_holds(subject):
    raw = subject.case.owned_run.to_dict()
    raw.update(
        stdout=raw["ready_wire"],
        primary_error="RESULT_NOT_OBSERVED",
        process=dict(raw["process"], returncode=1),
    )
    missing = owned.retain_owned_usb_presence_run(raw)
    assert missing.actual_counts is None
    d = build(
        subject, sources=dict(subject.sources, owned_presence_run=missing.payload)
    ).to_dict()
    assert d["status"] == "HELD" and d["presence_outcome"] is None
    assert d["provenance"]["native"] is None
    assert not d["physical_node_absence_observed"]


def test_report_cannot_reuse_the_baseline_phase_id(subject):
    # Independently modeled binding syntax; full reconstruction is tested above.
    binding = subject.case.phase_binding.to_dict()
    phase_id = subject.case.operation.to_dict()["operation_id"]
    binding["baseline"]["context"]["operation_id"] = phase_id
    changed = m.UsbPresencePhaseBinding(canonical(binding))
    with pytest.raises(m.UsbPresencePhaseError, match="DISTINCT_ABSENCE_PHASE"):
        m.build_usb_presence_operator_event(
            phase_binding=changed,
            phase_id=phase_id,
            launch_session_id=subject.context["launch_session_id"],
            operator_id=subject.context["operator_id"],
            phase_started_at_utc_ns=subject.context["started_at_utc_ns"],
            reported_at_utc_ns=subject.context["started_at_utc_ns"],
        )


@pytest.mark.parametrize("expected", [None, {}, [], 1, True, "bad", "A" * 64])
def test_verifier_requires_an_exact_expected_hash(subject, expected):
    phase = build(subject)
    with pytest.raises(m.UsbPresencePhaseError, match="EXPECTED_PHASE_HASH"):
        m.verify_usb_presence_qualification_phase(
            phase.payload,
            expected_sha256=expected,
            original_baseline=subject.case.original_baseline,
            sources=subject.sources,
        )


@pytest.mark.parametrize(
    "payload", [b"[]", b"{}", b"null", b"not-json", b"x" * (m.PHASE_LIMIT + 1)]
)
def test_malformed_or_oversized_wire_is_closed(payload):
    with pytest.raises(m.UsbPresencePhaseError):
        m.UsbPresenceQualificationPhase(payload)
