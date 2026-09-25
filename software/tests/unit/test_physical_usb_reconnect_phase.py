"""Pure reconnect originals. Every OS, process and storage fact is MODELED.

The real closed codecs reconstruct these test subjects; no helper, hardware,
CIM, original M1 admission or physical observation is executed here.
"""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import os
import subprocess

import pytest

from rocell.application import physical_camera_usb_qualification as qualification
from rocell.application import physical_received_camera_submission as received
from rocell.application import physical_usb_identity_campaign as campaign_module
from rocell.application import physical_usb_presence_campaign as presence_campaign
from rocell.application import physical_usb_presence_phase as presence_phase
from rocell.application import physical_usb_reconnect_phase as m
from rocell.application.physical_usb_presence_binding import (
    build_usb_presence_phase_binding,
)
from rocell.application.usb_identity_stage_policy import UsbIdentityAdmissionIdentity
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.providers.windows import usb_identity_protocol as wire
from rocell.providers.windows.usb_identity_registration import (
    review_usb_identity_runtime,
    usb_identity_runtime_candidate,
)
from rocell.providers.windows.usb_presence_review import review_usb_presence_runtime
from test_host_boot_observation import (
    request as boot_request,
    execution,
    response,
    FakeExecutor,
)
from test_physical_camera_usb_qualification import plan_fixture, usb_native_enrollment
from test_physical_camera_usb_readback import modeled_clean_held_evidence
from test_physical_received_camera import prerequisites, workspace
from test_physical_received_camera_submission import submission_fixture, rebuild
from test_physical_usb_identity_phase_operation import phase_permit
from test_physical_usb_presence_binding import observed_native, reference
from test_physical_usb_presence_dispatch import modeled_owned_presence
from test_physical_usb_presence_phase import (
    phase_fixture as absence_fixture,
    build as build_absence,
)
from test_usb_identity_protocol import reaccount


@pytest.fixture(autouse=True)
def no_process_or_device(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Pure reconnect fixture attempted process or device I/O")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)


def _absence_with_matching_received_label(prerequisites):
    """Rebuild received/plan/baseline/absence from actual producers, not flags."""
    seed = absence_fixture(prerequisites)
    original = dict(seed.case.original_baseline)
    received_case = submission_fixture(prerequisites)
    inspection = replace(
        received_case["kwargs"]["inspection"], observed_camera_serial="MODELED-ONLY"
    )
    submission = rebuild(received_case, inspection=inspection)
    assessment = received.assess_received_camera_submission(submission)
    review = received.review_received_camera_submission(
        submission,
        assessment,
        reviewer_id="MODELED-label-reviewer",
        review_launch_id=received_case["review"].to_dict()["review_launch_id"],
        reviewed_at_ns=1002,
        decision="ACKNOWLEDGE_EXACT",
    )
    _, _, plan_args = plan_fixture(prerequisites, mode="PHYSICAL")
    plan_args.update(
        received_submission=submission,
        received_assessment=assessment,
        received_review=review,
        received_references=[
            reference(
                item.payload,
                "MODELED-received-" + role,
                qualification.PhysicalOnboardingStage.CAMERA_RECEIPT,
            )
            for role, item in (
                ("submission", submission),
                ("assessment", assessment),
                ("review", review),
            )
        ],
    )
    plan = qualification.build_usb_qualification_plan(**plan_args)
    baseline = qualification.build_usb_qualification_phase(
        plan,
        phase="BASELINE",
        predecessor=None,
        context=original["baseline"].to_dict()["context"],
        sources=original["baseline_sources"],
        references={
            row["role"]: row["reference"]
            for row in original["baseline"].to_dict()["records"]
        },
    )
    plan_ref = reference(plan.payload, "MODELED-reconnect-plan")
    event = replace(original["declaration_event"], evidence=(plan_ref,))
    from rocell.application.physical_onboarding_v2 import _stable_hash

    event = replace(event, event_sha256=_stable_hash(event.core_dict()))
    original.update(
        plan=plan,
        baseline=baseline,
        plan_reference=plan_ref,
        baseline_reference=reference(baseline.payload, "MODELED-reconnect-baseline"),
        declaration_event=event,
    )
    binding = build_usb_presence_phase_binding(**original)
    op = seed.case.operation.to_dict()
    operation = presence_campaign.usb_presence_operation(
        phase_binding=binding,
        runtime=seed.case.runtime,
        policy=seed.case.policy,
        operation_id=op["operation_id"],
        launch_session_id=op["launch_session_id"],
        request_nonce=op["request_nonce"],
    )
    old_review = seed.case.review.to_dict()
    runtime_review = review_usb_presence_runtime(
        seed.case.runtime,
        phase_binding=binding,
        policy=seed.case.policy,
        operation_sha256=operation.sha256,
        **{
            key: old_review[key]
            for key in (
                "operator_id",
                "reviewer_id",
                "launch_session_id",
                "reviewed_at_ns",
            )
        },
    )
    campaign = presence_campaign.PhysicalUsbPresenceCampaign(
        operation, review=runtime_review
    )
    admission = replace(
        seed.case.permit.admission,
        selected_identity_sha256=binding.sha256,
        phase_binding_sha256=binding.sha256,
        runtime_review_sha256=runtime_review.sha256,
    )
    permit = replace(
        seed.case.permit,
        admission=admission,
        registration=campaign.registration(),
        request=replace(
            seed.case.permit.request,
            expected_challenge_sha256=admission.challenge_sha256,
        ),
    )
    prepared = campaign.preparation_for_permit(permit)
    rd = seed.case.owned_run.to_dict()
    run = modeled_owned_presence(
        prepared,
        deadline_ns=rd["original_deadline_ns"],
        checks=rd["scope_checks"],
        started_ns=rd["started_monotonic_ns"],
        started_utc_ns=rd["started_utc_ns"],
        finished_ns=rd["finished_monotonic_ns"],
        finished_utc_ns=rd["finished_utc_ns"],
    )
    ev = presence_phase.build_usb_presence_operator_event(
        phase_binding=binding,
        phase_id=op["operation_id"],
        launch_session_id=seed.context["launch_session_id"],
        operator_id=seed.context["operator_id"],
        phase_started_at_utc_ns=seed.context["started_at_utc_ns"],
        reported_at_utc_ns=seed.context["started_at_utc_ns"] + 2000,
    )
    sources = dict(
        seed.sources,
        operation=operation.payload,
        operator_event=ev.payload,
        owned_presence_run=run.payload,
    )
    made = presence_phase.build_usb_presence_qualification_phase(
        original_baseline=original,
        context=seed.context,
        sources=sources,
        references={
            key: reference(raw, "MODELED-absence-" + key)
            for key, raw in sources.items()
        },
    )
    assert made.to_dict()["status"] == "ABSENCE_OBSERVATIONS_RETAINED"
    return original, made, sources


def modeled_reconnect_boot(
    plan,
    context,
    *,
    wall,
    origin="WINDOWS_LOCAL_CIM",
    host_change=False,
    boot_change=False,
):
    p = plan.to_dict()["binding"]
    req = boot_request(
        source_sha256=p["source_sha256"],
        session_id=p["session_id"],
        trial_id=p["trial_id"],
        phase=m.PHASE,
        operation_id=context["operation_id"],
        launch_session_id=context["launch_session_id"],
    )
    changes = {}
    if host_change:
        changes["machine_uuid"] = "aaaaaaaa-1234-5678-9abc-0123456789ab"
    if boot_change:
        changes.update(
            last_boot_up_time_utc="2026-01-01T02:00:00.010000Z",
            confirmation_boot_up_time_utc="2026-01-01T02:00:00.010000Z",
        )
    ex = execution(req, wall=wall, raw=response(req, **changes))
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
    raw["origin"] = origin  # Explicit physical-shaped model, not executed CIM.
    return host.HostBootObservation(wire.canonical(raw))


def modeled_reconnect_run(
    prepared,
    *,
    utc,
    serial="MODELED-ONLY",
    physical_instance=None,
    outcome="OBSERVED",
    ex_speed=3,
    operating_usb3=True,
):
    """Complete strict wire and owner facts, all modeled without a child."""
    raw = modeled_clean_held_evidence(prepared).to_dict()
    raw.update(started_utc_ns=utc, finished_utc_ns=utc + 1000)
    if outcome == "HELD":
        return owned.OwnedUsbIdentityRunEvidence(wire.canonical(raw))
    observation = observed_native(
        prepared.request, physical_instance=physical_instance
    ).to_dict()
    if serial != "MODELED-ONLY":
        serial_raw = bytes((2 + 2 * len(serial), 3)) + serial.encode("utf-16-le")
        observation["serial_descriptors"][0].update(
            raw_hex=serial_raw.hex(), value=serial
        )
        for row in observation["calls"]:
            if row["operation"] == "SERIAL_DESCRIPTOR":
                row.update(
                    returned_raw_hex=serial_raw.hex(),
                    returned_bytes=len(serial_raw) + 12,
                    requested_bytes=max(128, len(serial_raw) + 12),
                )
    ex = bytearray.fromhex(observation["link"]["ex_raw_hex"])
    ex[23] = ex_speed
    observation["link"].update(ex_speed=ex_speed, ex_raw_hex=ex.hex())
    for row in observation["calls"]:
        if row["operation"] == "CONNECTION_EX":
            row["returned_raw_hex"] = ex.hex()
    if not operating_usb3:
        v2 = bytearray.fromhex(observation["link"]["ex_v2_raw_hex"])
        v2[12:16] = (2).to_bytes(4, "little")
        observation["link"].update(
            ex_v2_raw_hex=v2.hex(), operating_superspeed_or_higher=False
        )
        for row in observation["calls"]:
            if row["operation"] == "CONNECTION_EX_V2":
                row["returned_raw_hex"] = v2.hex()
    reaccount(observation)
    native = wire.parse_usb_identity_observation(
        wire.canonical(observation), request=prepared.request
    )
    ready_wire = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)[
        : raw["ready_length"]
    ]
    ready = wire.UsbIdentityReady(ready_wire.rstrip(b"\n"))
    result = dict(
        schema=wire.RESULT_SCHEMA,
        request_sha256=prepared.request.request_sha256,
        child_pid=31415,
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=prepared.request.to_dict()["permit_sha256"],
        native_receipt=native.to_dict(),
    )
    raw["process"]["returncode"] = 0
    raw.update(
        status="OBSERVED",
        stdout=owned.stream_record(ready_wire + wire.canonical(result), complete=True),
    )
    return owned.OwnedUsbIdentityRunEvidence(wire.canonical(raw))


def reconnect_fixture(
    prerequisites,
    *,
    serial="MODELED-ONLY",
    driver_version="1.2.3.4",
    outcome="OBSERVED",
    physical_instance=None,
    host_change=False,
    boot_change=False,
    boot_origin="WINDOWS_LOCAL_CIM",
    ex_speed=3,
    operating_usb3=True,
):
    """Full actual-codec chain; variants affect reconnect observations only."""
    original, absence, absence_sources = _absence_with_matching_received_label(
        prerequisites
    )
    plan, p = original["plan"], original["plan"].to_dict()["binding"]
    start = absence.to_dict()["context"]["finished_at_utc_ns"] + 1_000_000
    context = dict(
        launch_session_id="wizard-MODELED-reconnect",
        operation_id="usbphase-" + "e" * 32,
        operator_id="MODELED-reconnect-inspector",
        started_at_utc_ns=start,
        finished_at_utc_ns=start + 10000,
    )
    native = usb_native_enrollment(
        p["source_sha256"],
        context["launch_session_id"],
        serial=serial,
        driver_version=driver_version,
        suffix="MODELED-reconnect",
    )
    # All three acquisition identifiers are new. Rebuild the actual generic
    # and enrollment owners; changing cached hashes would not prove this join.
    from rocell.application.wizard_device_selection import WizardDeviceSelection
    from rocell.application.wizard_native_camera_enrollment import (
        WizardNativeCameraEnrollment,
    )

    generic_owner = WizardDeviceSelection(
        "physical", context["launch_session_id"], p["source_sha256"]
    )
    generic_owner.ingest(
        native["generic_review"]["inventory_report"],
        operation_id="generic-MODELED-reconnect",
    )
    generic_owner.review(
        generic_owner.choices("CAMERA")[0]["value"],
        "CAMERA",
        "MODELED-generic-reviewer",
    )
    generic = generic_owner.reviewed_candidate("CAMERA")
    native_owner = WizardNativeCameraEnrollment(
        "physical",
        context["launch_session_id"],
        p["source_sha256"],
        {
            key: native["identity_packet"][key]
            for key in ("provenance", "helper_sha256")
        },
    )
    native_owner.ingest_inventory(
        native["inventory_packet"],
        operation_id="native-inventory-MODELED-reconnect",
        generic_review=generic,
    )
    choice = native_owner.choices()[0]["value"]
    native_owner.retain_identity(
        choice,
        native["identity_packet"],
        operation_id="native-identity-MODELED-reconnect",
    )
    native_owner.review(choice, "MODELED-native-reviewer")
    native = native_owner.export_snapshot()
    _, selection, _ = qualification._native(plan, context, wire.canonical(native))
    runtime = usb_identity_runtime_candidate(
        Path.cwd(), source_sha256=p["source_sha256"]
    )
    operation = campaign_module.usb_identity_phase_operation(
        plan=plan,
        phase=m.PHASE,
        operation_id=context["operation_id"],
        predecessor_sha256=absence.sha256,
        selection=selection,
        runtime=runtime,
        policy=campaign_module.usb_identity_stage_policy(),
    )
    sd = selection.identity_document
    review = review_usb_identity_runtime(
        runtime,
        selection_sha256=selection.sha256,
        native_identity_sha256=sd["native_identity_sha256"],
        endpoint_sha256=sd["endpoint_sha256"],
        device_instance_id_sha256=wire.digest(
            sd["metadata_review"]["observed_instance_id"].encode()
        ),
        operation_sha256=operation.sha256,
        operator_id=context["operator_id"],
        reviewer_id="MODELED-distinct-reviewer",
        launch_session_id=context["launch_session_id"],
        reviewed_at_ns=start + 2000,
    )
    rd = review.to_dict()
    subjects = [
        dict(
            role=role,
            document_sha256=wire.digest(raw),
            reference=reference(raw, "MODELED-reconnect-" + role).to_dict(),
        )
        for role, raw in (
            ("metadata", wire.canonical(native)),
            ("policy_review", b"MODELED-original-policy-review"),
            ("runtime_review", review.payload),
        )
    ]
    identity = UsbIdentityAdmissionIdentity(
        wire.canonical(
            dict(
                schema="rocell.usb_identity_admission_identity.v1",
                cell_id=p["cell_id"],
                session_id=p["session_id"],
                source_sha256=p["source_sha256"],
                header_sha256=p["header_sha256"],
                stage_policy_sha256=p["stage_policy_sha256"],
                policy_review_sha256=subjects[1]["document_sha256"],
                runtime_review_sha256=review.sha256,
                runtime_registration_sha256=runtime.sha256,
                original_subjects=subjects,
                **{
                    key: rd[key]
                    for key in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                        "device_instance_id_sha256",
                        "operation_sha256",
                    )
                },
            )
        )
    )
    campaign = campaign_module.PhysicalUsbIdentityCampaign(
        operation, identity=identity, review=review
    )
    permit = replace(
        phase_permit(campaign), attempt_id="attempt-" + "e" * 32, nonce="e" * 64
    )
    prepared = campaign.preparation_for_permit(permit)
    run = modeled_reconnect_run(
        prepared,
        utc=start + 5000,
        serial=serial,
        physical_instance=physical_instance,
        outcome=outcome,
        ex_speed=ex_speed,
        operating_usb3=operating_usb3,
    )
    boot = modeled_reconnect_boot(
        plan,
        context,
        wall=start + 3000,
        origin=boot_origin,
        host_change=host_change,
        boot_change=boot_change,
    )
    event = m.build_usb_reconnect_operator_event(
        plan=plan,
        absence=absence,
        phase_id=context["operation_id"],
        launch_session_id=context["launch_session_id"],
        operator_id=context["operator_id"],
        phase_started_at_utc_ns=start,
        reported_at_utc_ns=start + 1000,
    )
    sources = dict(
        operation=operation.payload,
        operator_event=event.payload,
        native_enrollment=wire.canonical(native),
        owned_usb_run=run.payload,
        host_boot=boot.payload,
    )
    return SimpleNamespace(
        original_baseline=original,
        absence=absence,
        absence_sources=absence_sources,
        context=context,
        sources=sources,
        operation=operation,
        campaign=campaign,
        permit=permit,
        run=run,
        boot=boot,
        event=event,
    )


def build(subject, *, sources=None, references=None, context=None, permit=None):
    sources = subject.sources if sources is None else sources
    return m.build_usb_reconnect_qualification_phase(
        original_baseline=subject.original_baseline,
        absence=subject.absence,
        absence_sources=subject.absence_sources,
        permit=subject.permit if permit is None else permit,
        context=subject.context if context is None else context,
        sources=sources,
        references=(
            {
                key: reference(raw, "MODELED-reconnect-" + key)
                for key, raw in sources.items()
            }
            if references is None
            else references
        ),
    )


@pytest.fixture
def subject(prerequisites):
    return reconnect_fixture(prerequisites)


def test_full_physical_shaped_reconnect_rebuilds_without_v1_absence(
    subject, monkeypatch
):
    def denied(*args, **kwargs):
        pytest.fail("pure builder accessed original files")

    monkeypatch.setattr(Path, "open", denied)
    phase = build(subject)
    d = phase.to_dict()
    assert d["status"] == "RECONNECT_OBSERVATIONS_RETAINED", d["missing_requirements"]
    assert d["predecessor_sha256"] == subject.absence.sha256
    assert d["baseline_sha256"] == subject.original_baseline["baseline"].sha256
    assert d["boot_relation"] == "SAME_HOST_SAME_BOOT"
    assert all(d[key] is False for key in m.FLAGS)
    assert all(row["status"] == "MATCHED" for row in d["comparisons"])
    assert len(phase.payload) <= m.PHASE_LIMIT
    assert (
        m.verify_usb_reconnect_qualification_phase(
            phase.payload,
            expected_sha256=phase.sha256,
            original_baseline=subject.original_baseline,
            absence=subject.absence,
            absence_sources=subject.absence_sources,
            permit=subject.permit,
            sources=subject.sources,
        ).payload
        == phase.payload
    )
    with pytest.raises(FrozenInstanceError):
        phase.payload = b"{}"
    d["context"]["operator_id"] = "changed"
    assert phase.to_dict()["context"] == subject.context


@pytest.mark.parametrize(
    "changes,missing",
    [
        ({"serial": "MODELED-OTHER"}, "RECEIVED_SERIAL_MATCH"),
        ({"driver_version": "9.9.9.9"}, "BASELINE_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY"),
        (
            {"physical_instance": r"USB\VID_1234&PID_5678\MODELED-OTHER"},
            "EXACT_ABSENCE_PHYSICAL_NODE_RETURNED",
        ),
        ({"host_change": True}, "SAME_HOST_SAME_BOOT_AS_ABSENCE"),
        ({"boot_change": True}, "SAME_HOST_SAME_BOOT_AS_ABSENCE"),
        ({"boot_origin": "INJECTED_CIM_EXECUTOR"}, "HOST_BOOT_PHYSICAL_OWNED_CLEAN"),
        ({"outcome": "HELD"}, "USB_OBSERVATION_COMPLETE"),
        ({"operating_usb3": False}, "V2_OPERATING_USB3_OBSERVED"),
    ],
)
def test_actual_changed_or_missing_observations_are_retained_held(
    prerequisites, changes, missing
):
    d = build(reconnect_fixture(prerequisites, **changes)).to_dict()
    assert d["status"] == "HELD" and missing in d["missing_requirements"]
    assert all(d[key] is False for key in m.FLAGS)


def test_highspeed_ex_with_observed_superspeed_v2_is_not_rewritten(prerequisites):
    d = build(reconnect_fixture(prerequisites, ex_speed=2)).to_dict()
    assert d["status"] == "RECONNECT_OBSERVATIONS_RETAINED"
    assert d["execution"]["ex_speed"] == 2 and d["execution"]["usb3_operating"] is True


def test_report_after_review_holds_literal_original_without_inference(subject):
    event = subject.event.to_dict()
    event["reported_at_utc_ns"] = subject.context["started_at_utc_ns"] + 2001
    d = build(
        subject, sources=dict(subject.sources, operator_event=wire.canonical(event))
    ).to_dict()
    assert d["status"] == "HELD"
    assert "OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER" in d["missing_requirements"]


def test_no_event_or_phase_can_claim_authority(subject):
    phase = build(subject)
    for cls, original in (
        (m.UsbReconnectOperatorEvent, subject.event),
        (m.UsbReconnectQualificationPhase, phase),
    ):
        for key in m.FLAGS:
            d = original.to_dict()
            d[key] = True
            with pytest.raises(m.UsbReconnectPhaseError, match="AUTHORITY"):
                cls(wire.canonical(d))


def test_each_wrong_original_reference_is_rejected(subject):
    refs = {
        key: reference(raw, "MODELED-reconnect-" + key)
        for key, raw in subject.sources.items()
    }
    for role in m.ROLES:
        changed = dict(refs)
        changed[role] = reference(
            b"MODELED-unrelated-original", "MODELED-unrelated-role"
        )
        with pytest.raises(m.UsbReconnectPhaseError):
            build(subject, references=changed)


def test_exact_permit_is_independently_required_not_synthesized(subject):
    for permit in (
        replace(subject.permit, nonce="f" * 64),
        replace(subject.permit, expires_at_ns=1000),
    ):
        with pytest.raises(m.UsbReconnectPhaseError):
            build(subject, permit=permit)
    # A fully re-bound current operation/request cannot reuse the preceding
    # presence attempt even when the new permit and wire are self-consistent.
    previous = m.OwnedUsbPresenceRunEvidence(
        subject.absence_sources["owned_presence_run"]
    )
    permit = replace(subject.permit, attempt_id=previous.preparation.permit.attempt_id)
    prepared = subject.campaign.preparation_for_permit(permit)
    run = modeled_reconnect_run(prepared, utc=subject.run.to_dict()["started_utc_ns"])
    with pytest.raises(m.UsbReconnectPhaseError, match="NO_REPLAY"):
        build(
            subject,
            permit=permit,
            sources=dict(subject.sources, owned_usb_run=run.payload),
        )


def test_old_phase_type_and_physical_held_predecessor_cannot_be_relabelled(
    subject, prerequisites
):
    with pytest.raises(m.UsbReconnectPhaseError, match="PHYSICAL_ABSENCE"):
        m.verify_usb_reconnect_predecessor(
            original_baseline=subject.original_baseline,
            absence=subject.original_baseline["baseline"],
            absence_sources=subject.absence_sources,
        )
    old = absence_fixture(prerequisites, outcome="PRESENT")
    with pytest.raises(m.UsbReconnectPhaseError, match="COMPLETE_PHYSICAL_ABSENCE"):
        m.verify_usb_reconnect_predecessor(
            original_baseline=old.case.original_baseline,
            absence=build_absence(old),
            absence_sources=old.sources,
        )


def test_uncertain_cleanup_and_post_query_stop_preserve_raw_observation(subject):
    for changes in (
        {"cleanup_errors": ["MODELED_CLEANUP_FAILED"]},
        {"primary_error": "CANCELLED"},
    ):
        raw = subject.run.to_dict()
        raw.update(changes)
        run = owned.retain_owned_usb_identity_run(raw)
        assert run.observation.to_dict() == subject.run.observation.to_dict()
        d = build(
            subject, sources=dict(subject.sources, owned_usb_run=run.payload)
        ).to_dict()
        assert (
            d["status"] == "HELD"
            and "OWNED_RESULT_CURRENT_COMPLETE" in d["missing_requirements"]
        )
        assert d["values"]["descriptor_serial"]["value"] == "MODELED-ONLY"


def test_original_hash_only_value_is_not_unknown_and_manifest_capacity_is_bounded(
    subject,
):
    d = build(subject).to_dict()
    assert d["values"]["port_topology"]["status"] == "VALUE_IN_ORIGINAL"
    row = next(row for row in d["comparisons"] if row["field"] == "port_topology")
    assert row["status"] == "MATCHED" and row["reconnect_sha256"] is not None
    # Closed display-capacity model only, not a new original observation.
    # Full maximum-sized original documents stay external to this manifest.
    for row in d["records"]:
        row["payload_bytes"] = m.ROLE_LIMITS[row["role"]]
        row["reference"]["payload_bytes"] = row["payload_bytes"]
    for key in d["values"]:
        d["values"][key] = qualification._display("M" * 126)
    for row in d["comparisons"]:
        row.update(
            baseline_sha256=d["values"][row["field"]]["sha256"],
            reconnect_sha256=d["values"][row["field"]]["sha256"],
            status="MATCHED",
        )
    d["context"].update(operator_id="M" * 64, launch_session_id="M" * 128)
    for row in d["checks"]:
        row["passed"] = False
    d.update(status="HELD", missing_requirements=list(m.CHECKS))
    capacity = m.UsbReconnectQualificationPhase(wire.canonical(d))
    assert len(capacity.payload) < 24 * 1024 < m.PHASE_LIMIT
    assert m.ROLE_LIMITS["operation"] == 80 * 1024


def test_released_without_native_result_remains_unknown_not_zero(subject):
    raw = subject.run.to_dict()
    stdout = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)
    raw.update(
        stdout=owned.stream_record(stdout[: raw["ready_length"]], complete=True),
        primary_error="USB_RESULT_UNAVAILABLE",
        result_validated=False,
    )
    run = owned.retain_owned_usb_identity_run(raw)
    assert run.released and run.actual_counts is None and run.observation is None
    d = build(
        subject, sources=dict(subject.sources, owned_usb_run=run.payload)
    ).to_dict()
    assert d["status"] == "HELD" and d["execution"]["native_clean"] is False
    assert d["values"]["descriptor_serial"]["status"] == "NOT_OBSERVED"
    assert "USB_OBSERVATION_COMPLETE" in d["missing_requirements"]
