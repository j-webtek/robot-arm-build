"""Pure AFTER_REBOOT contracts over explicitly MODELED originals.

Every OS, process, USB, lease, permit and package fact in these fixtures is
explicitly modeled. Strict production codecs reconstruct their bytes; no
provider, physical process, CIM, device or original-store admission runs. The
historical baseline/absence/reconnect bytes are never edited to manufacture a
new observation. Only the pure codecs are exercised; no application action is released.
"""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess

import pytest

from rocell.application import physical_camera_usb_qualification as qualification
from rocell.application import physical_received_camera_submission as received_codec
from rocell.application import physical_usb_identity_campaign as campaign_module
from rocell.application import physical_usb_reboot_phase as m
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.usb_identity_stage_policy import UsbIdentityAdmissionIdentity
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.providers.windows import usb_identity_protocol as wire
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    review_usb_identity_runtime,
)
from test_host_boot_observation import execution, request as boot_request, response
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_physical_received_camera import prerequisites, workspace
from test_physical_received_camera_submission import rebuild, submission_fixture
from test_physical_usb_identity_phase_operation import phase_permit
from test_physical_usb_presence_binding import reference
from test_physical_usb_reconnect_phase import (
    build as build_reconnect,
    modeled_reconnect_run,
    reconnect_fixture,
)


@pytest.fixture(autouse=True)
def no_process_or_device(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Pure reboot codec attempted a process, CIM or device operation")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)
    monkeypatch.setattr(host.LocalCimHostBootExecutor, "execute", denied)


def _received_originals(prerequisites, plan):
    """Rebuild the exact received trio used by reconnect_fixture's plan."""
    case = submission_fixture(prerequisites)
    submission = rebuild(
        case,
        inspection=replace(
            case["kwargs"]["inspection"], observed_camera_serial="MODELED-ONLY"
        ),
    )
    assessment = received_codec.assess_received_camera_submission(submission)
    review = received_codec.review_received_camera_submission(
        submission,
        assessment,
        reviewer_id="MODELED-label-reviewer",
        review_launch_id=case["review"].to_dict()["review_launch_id"],
        reviewed_at_ns=1002,
        decision="ACKNOWLEDGE_EXACT",
    )
    assert (
        qualification.verify_usb_qualification_plan(
            plan,
            expected_sha256=plan.sha256,
            received_submission=submission,
            received_assessment=assessment,
            received_review=review,
        ).payload
        == plan.payload
    )
    return dict(submission=submission, assessment=assessment, review=review)


@pytest.fixture
def predecessor(prerequisites):
    seed = reconnect_fixture(prerequisites)
    reconnect = build_reconnect(seed)
    assert reconnect.to_dict()["status"] == "RECONNECT_OBSERVATIONS_RETAINED"
    return SimpleNamespace(
        seed=seed,
        reconnect=reconnect,
        received=_received_originals(prerequisites, seed.original_baseline["plan"]),
    )


def _references(sources):
    return {
        role: reference(payload, "MODELED-reboot-" + role)
        for role, payload in sources.items()
    }


def _utc_text(value):
    # Host codec requires six fractional digits, with no floating-point epoch.
    assert value % 1000 == 0
    value = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        microseconds=value // 1000
    )
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _fresh_enrollment(source, context, *, serial, driver_version, operation_ids=None):
    """Three fresh in-memory metadata-owner operations, never Windows Registry.

    This pure fixture supplies no durable acquisition log or freshness proof;
    the phase must continue to mark acquisition freshness unverified.
    """
    ids = dict(
        generic="generic-MODELED-reboot",
        inventory="native-inventory-MODELED-reboot",
        identity="native-identity-MODELED-reboot",
    )
    if operation_ids is not None:
        ids.update(operation_ids)
    native = usb_native_enrollment(
        source,
        context["launch_session_id"],
        serial=serial,
        driver_version=driver_version,
        suffix="MODELED-reboot",
    )
    generic_owner = WizardDeviceSelection(
        "physical", context["launch_session_id"], source
    )
    generic_owner.ingest(
        native["generic_review"]["inventory_report"],
        operation_id=ids["generic"],
    )
    generic_owner.review(
        generic_owner.choices("CAMERA")[0]["value"],
        "CAMERA",
        "MODELED-reboot-generic-reviewer",
    )
    owner = WizardNativeCameraEnrollment(
        "physical",
        context["launch_session_id"],
        source,
        {
            key: native["identity_packet"][key]
            for key in ("provenance", "helper_sha256")
        },
    )
    owner.ingest_inventory(
        native["inventory_packet"],
        operation_id=ids["inventory"],
        generic_review=generic_owner.reviewed_candidate("CAMERA"),
    )
    choice = owner.choices()[0]["value"]
    owner.retain_identity(
        choice,
        native["identity_packet"],
        operation_id=ids["identity"],
    )
    owner.review(choice, "MODELED-reboot-native-reviewer")
    return owner.export_snapshot()


def _modeled_boot(
    plan, context, *, boot_epoch, origin, host_change, cleanup_uncertain=False
):
    """Build new physical-shaped model facts, never acquire/relabel a predecessor."""
    binding = plan.to_dict()["binding"]
    req = boot_request(
        source_sha256=binding["source_sha256"],
        session_id=binding["session_id"],
        trial_id=binding["trial_id"],
        phase="AFTER_REBOOT",
        operation_id=context["operation_id"],
        launch_session_id=context["launch_session_id"],
        expires_at_ns=30_000_000_001,
    )
    changes = dict(
        last_boot_up_time_utc=_utc_text(boot_epoch),
        confirmation_boot_up_time_utc=_utc_text(boot_epoch),
    )
    if host_change:
        changes["machine_uuid"] = "aaaaaaaa-1234-5678-9abc-0123456789ab"
    ex = execution(
        req,
        wall=context["started_at_utc_ns"] + 3000,
        raw=response(req, **changes),
        started_monotonic_ns=1,
        finished_monotonic_ns=2,
    )
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
            cleanup_deadline_ns=1_000_000_002,
        ),
    )
    if cleanup_uncertain:
        ex = replace(
            ex,
            status="FAILED",
            cleanup_errors=("OWNED_RESOURCE_CLEANUP_UNCONFIRMED",),
        )
    parsed = host._response(ex.stdout, req.sha256)
    blockers, host_key, boot_key = host._derived(req, ex, parsed, req.expires_at_ns)
    return host.HostBootObservation(
        wire.canonical(
            dict(
                schema=host.OWNED_SCHEMA,
                request=req.to_dict(),
                request_sha256=req.sha256,
                deadline_ns=req.expires_at_ns,
                origin=origin,
                command=ex.command,
                command_sha256=wire.digest(wire.canonical(ex.command)),
                execution=host._execution_document(ex),
                response=parsed,
                blockers=blockers,
                status="HELD" if blockers else "OBSERVED_HOST_BOOT",
                host_key_sha256=host_key,
                boot_key_sha256=boot_key,
                limitations=list(host.LIMITATIONS),
                physical_authority=False,
                hardware_qualified=False,
                device_io_performed=False,
            )
        )
    )


def reboot_fixture(
    predecessor,
    *,
    serial="MODELED-ONLY",
    driver_version="1.2.3.4",
    ex_speed=3,
    operating_usb3=True,
    outcome="OBSERVED",
    physical_instance=None,
    epoch="nominal",
    host_change=False,
    boot_origin="WINDOWS_LOCAL_CIM",
    boot_cleanup_uncertain=False,
    metadata_operation_ids=None,
    attempt_id=None,
):
    seed, reconnect = predecessor.seed, predecessor.reconnect
    original = seed.original_baseline
    plan, binding = original["plan"], original["plan"].to_dict()["binding"]
    previous_finish = reconnect.to_dict()["context"]["finished_at_utc_ns"]
    new_boot = (previous_finish // 1000 + 1) * 1000 + 1_000_000
    start = new_boot + 1_000_000
    context = dict(
        launch_session_id="wizard-MODELED-reboot",
        operation_id="usbphase-" + "f" * 32,
        operator_id="MODELED-reboot-inspector",
        started_at_utc_ns=start,
        finished_at_utc_ns=start + 10_000,
    )
    native = _fresh_enrollment(
        binding["source_sha256"],
        context,
        serial=serial,
        driver_version=driver_version,
        operation_ids=metadata_operation_ids,
    )
    _, selection, _ = qualification._native(plan, context, wire.canonical(native))
    runtime = UsbIdentityRuntimeRegistration(
        wire.canonical(seed.operation.to_dict()["runtime"])
    )
    operation = campaign_module.usb_identity_phase_operation(
        plan=plan,
        phase="AFTER_REBOOT",
        operation_id=context["operation_id"],
        predecessor_sha256=reconnect.sha256,
        selection=selection,
        runtime=runtime,
        policy=campaign_module.usb_identity_stage_policy(),
    )
    selected = selection.identity_document
    review = review_usb_identity_runtime(
        runtime,
        selection_sha256=selection.sha256,
        native_identity_sha256=selected["native_identity_sha256"],
        endpoint_sha256=selected["endpoint_sha256"],
        device_instance_id_sha256=wire.digest(
            selected["metadata_review"]["observed_instance_id"].encode()
        ),
        operation_sha256=operation.sha256,
        operator_id=context["operator_id"],
        reviewer_id="MODELED-reboot-distinct-reviewer",
        launch_session_id=context["launch_session_id"],
        reviewed_at_ns=start + 2000,
    )
    subjects = [
        dict(
            role=role,
            document_sha256=wire.digest(raw),
            reference=reference(raw, "MODELED-reboot-admission-" + role).to_dict(),
        )
        for role, raw in (
            ("metadata", wire.canonical(native)),
            ("policy_review", b"MODELED-original-reboot-policy-review"),
            ("runtime_review", review.payload),
        )
    ]
    rd = review.to_dict()
    identity = UsbIdentityAdmissionIdentity(
        wire.canonical(
            dict(
                schema="rocell.usb_identity_admission_identity.v1",
                cell_id=binding["cell_id"],
                session_id=binding["session_id"],
                source_sha256=binding["source_sha256"],
                header_sha256=binding["header_sha256"],
                stage_policy_sha256=binding["stage_policy_sha256"],
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
        phase_permit(campaign),
        attempt_id="attempt-" + "f" * 32 if attempt_id is None else attempt_id,
        nonce="f" * 64,
    )
    run = modeled_reconnect_run(
        campaign.preparation_for_permit(permit),
        utc=start + 5000,
        serial=serial,
        physical_instance=physical_instance,
        outcome=outcome,
        ex_speed=ex_speed,
        operating_usb3=operating_usb3,
    )
    # New-boot monotonic coordinates intentionally precede the old run's 100..200.
    # Only this new modeled run is rebuilt, preserving its admitted request and UTC.
    raw = run.to_dict()
    raw.update(
        started_monotonic_ns=10,
        finished_monotonic_ns=20,
        original_deadline_ns=10 + 25_000_000_000,
    )
    raw["scope_checks"] = [
        dict(boundary=name, started_ns=11 + i, finished_ns=11 + i, passed=True)
        for i, name in enumerate(owned.BOUNDARIES)
    ]
    run = owned.retain_owned_usb_identity_run(raw)
    if epoch == "before_reconnect_finish":
        new_boot = previous_finish // 1000 * 1000 - 1000
    elif epoch == "after_begin":
        new_boot = start + 1000
    elif epoch == "same_boot":
        new_boot = host._utc_ns(
            seed.boot.to_dict()["response"]["last_boot_up_time_utc"]
        )
    else:
        assert epoch == "nominal"
    boot = _modeled_boot(
        plan,
        context,
        boot_epoch=new_boot,
        origin=boot_origin,
        host_change=host_change,
        cleanup_uncertain=boot_cleanup_uncertain,
    )
    event = m.build_usb_reboot_operator_event(
        plan=plan,
        reconnect=reconnect,
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
        seed=seed,
        original_baseline=original,
        received=predecessor.received,
        absence=seed.absence,
        absence_reference=reference(
            seed.absence.payload, "MODELED-reboot-predecessor-absence"
        ),
        absence_sources=seed.absence_sources,
        reconnect=reconnect,
        reconnect_reference=reference(
            reconnect.payload, "MODELED-reboot-predecessor-reconnect"
        ),
        reconnect_sources=seed.sources,
        reconnect_permit=seed.permit,
        permit=permit,
        context=context,
        sources=sources,
        references=_references(sources),
        operation=operation,
        campaign=campaign,
        run=run,
        boot=boot,
        event=event,
    )


_PREDECESSOR_KEYS = (
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


def build(case, **changes):
    args = {key: getattr(case, key) for key in _PREDECESSOR_KEYS}
    args.update(permit=case.permit, context=case.context, sources=case.sources)
    args.update(changes)
    args.setdefault("references", _references(args["sources"]))
    return m.build_usb_reboot_qualification_phase(**args)


def verify(case, phase, **changes):
    args = {key: getattr(case, key) for key in _PREDECESSOR_KEYS}
    args.update(
        expected_sha256=phase.sha256,
        permit=case.permit,
        sources=case.sources,
        references=case.references,
    )
    args.update(changes)
    return m.verify_usb_reboot_qualification_phase(phase.payload, **args)


@pytest.fixture
def subject(predecessor):
    return reboot_fixture(predecessor)


def test_nominal_new_boot_keeps_exact_predecessors_and_never_grants_authority(
    subject, monkeypatch
):
    historical = {
        "baseline": subject.original_baseline["baseline"].payload,
        "absence": subject.absence.payload,
        "reconnect": subject.reconnect.payload,
    }
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure codec opened a file")
    )
    phase = build(subject)
    doc = phase.to_dict()
    assert doc["status"] == "REBOOT_OBSERVATIONS_RETAINED", doc["missing_requirements"]
    assert doc["phase"] == "AFTER_REBOOT" and doc["ordinal"] == 3
    assert doc["predecessor_sha256"] == subject.reconnect.sha256
    assert doc["absence_sha256"] == subject.absence.sha256
    assert doc["boot_relation"] == "SAME_HOST_DIFFERENT_BOOT"
    assert all(row["status"] == "MATCHED" for row in doc["comparisons"])
    assert all(doc[key] is False for key in m.FLAGS)
    assert doc["metadata_acquisition_freshness_verified"] is False
    assert doc["host_restart_verified"] is False
    assert doc["cryptographic_attestation"] is False
    assert phase.sha256 == wire.digest(phase.payload)
    assert verify(subject, phase).payload == phase.payload
    assert len(phase.payload) <= 32 * 1024
    assert len(subject.event.payload) <= 8 * 1024
    assert historical == {
        "baseline": subject.original_baseline["baseline"].payload,
        "absence": subject.absence.payload,
        "reconnect": subject.reconnect.payload,
    }
    with pytest.raises(FrozenInstanceError):
        phase.payload = b"{}"
    detached = phase.to_dict()
    detached["context"]["operator_id"] = "not-original"
    assert phase.to_dict()["context"] == subject.context


def test_reboot_monotonic_coordinates_may_be_lower_without_renewing_permit(subject):
    assert (
        subject.run.to_dict()["started_monotonic_ns"]
        < subject.seed.run.to_dict()["started_monotonic_ns"]
    )
    assert (
        subject.boot.to_dict()["execution"]["started_monotonic_ns"]
        < subject.seed.boot.to_dict()["execution"]["started_monotonic_ns"]
    )
    assert subject.permit.issued_at_ns == subject.seed.permit.issued_at_ns
    assert subject.permit.expires_at_ns == subject.seed.permit.expires_at_ns
    assert subject.permit.permit_sha256 != subject.seed.permit.permit_sha256
    run = subject.run.to_dict()
    assert subject.permit.registration.budget.timeout_ms == 25_000
    assert run["original_deadline_ns"] == run["started_monotonic_ns"] + 25_000_000_000
    assert run["original_deadline_ns"] <= subject.permit.expires_at_ns
    assert subject.seed.run.to_dict()["original_deadline_ns"] == 25_000_000_100
    assert build(subject).to_dict()["status"] == "REBOOT_OBSERVATIONS_RETAINED"


def test_validly_framed_wrong_boot_epoch_or_relation_is_held(predecessor):
    cases = (
        (
            {"epoch": "before_reconnect_finish"},
            "REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN",
        ),
        ({"epoch": "after_begin"}, "REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN"),
        ({"epoch": "same_boot"}, "SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT"),
        ({"host_change": True}, "SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT"),
        ({"boot_origin": "INJECTED_CIM_EXECUTOR"}, "HOST_BOOT_PHYSICAL_OWNED_CLEAN"),
    )
    for changes, missing in cases:
        case = reboot_fixture(predecessor, **changes)
        assert case.boot.to_dict()["status"] == "OBSERVED_HOST_BOOT"
        phase = build(case)
        doc = phase.to_dict()
        assert doc["status"] == "HELD" and missing in doc["missing_requirements"]
        assert all(doc[key] is False for key in m.FLAGS)
        assert verify(case, phase).payload == phase.payload
        if changes.get("epoch") == "before_reconnect_finish":
            # The generic comparison is weaker; the new phase must still hold.
            assert (
                host.compare_boot_observations(case.seed.boot, case.boot)["status"]
                == "SAME_HOST_DIFFERENT_BOOT"
            )


def test_exact_boot_epoch_equality_boundaries_preserve_predecessor_bytes(subject):
    historical = (
        subject.original_baseline["plan"].payload,
        subject.original_baseline["baseline"].payload,
        subject.absence.payload,
        subject.reconnect.payload,
        tuple(sorted(subject.reconnect_sources.items())),
    )
    finish = subject.reconnect.to_dict()["context"]["finished_at_utc_ns"]
    begin = subject.context["started_at_utc_ns"]
    for epoch, expected_status, expected_missing in (
        (finish, "HELD", ["REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN"]),
        (begin, "REBOOT_OBSERVATIONS_RETAINED", []),
    ):
        # Existing immutable history is exactly representable by the host wire.
        # Never round the boundary or rewrite the earlier completion timestamp.
        assert epoch % 1000 == 0
        assert host._utc_ns(_utc_text(epoch)) == epoch
        boot = _modeled_boot(
            subject.original_baseline["plan"],
            subject.context,
            boot_epoch=epoch,
            origin="WINDOWS_LOCAL_CIM",
            host_change=False,
        )
        assert boot.to_dict()["status"] == "OBSERVED_HOST_BOOT"
        assert (
            host._utc_ns(boot.to_dict()["response"]["last_boot_up_time_utc"]) == epoch
        )
        sources = dict(subject.sources, host_boot=boot.payload)
        phase = build(subject, sources=sources)
        doc = phase.to_dict()
        assert doc["boot_relation"] == "SAME_HOST_DIFFERENT_BOOT"
        assert doc["status"] == expected_status
        assert doc["missing_requirements"] == expected_missing
        assert all(doc[key] is False for key in m.FLAGS)
        assert (
            verify(
                subject, phase, sources=sources, references=_references(sources)
            ).payload
            == phase.payload
        )
    assert historical == (
        subject.original_baseline["plan"].payload,
        subject.original_baseline["baseline"].payload,
        subject.absence.payload,
        subject.reconnect.payload,
        tuple(sorted(subject.reconnect_sources.items())),
    )


def test_literal_descriptor_driver_speed_or_missing_observations_are_held(predecessor):
    for changes, missing in (
        ({"serial": "MODELED-OTHER"}, "RECEIVED_SERIAL_MATCH"),
        (
            {"driver_version": "9.8.7.6"},
            "BASELINE_AND_RECONNECT_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY",
        ),
        ({"operating_usb3": False}, "V2_OPERATING_USB3_OBSERVED"),
        ({"outcome": "HELD"}, "USB_OBSERVATION_COMPLETE"),
        (
            {"physical_instance": r"USB\VID_1234&PID_5678\MODELED-OTHER"},
            "EXACT_ABSENCE_PHYSICAL_NODE_RETURNED",
        ),
    ):
        case = reboot_fixture(predecessor, **changes)
        phase = build(case)
        assert phase.to_dict()["status"] == "HELD"
        assert missing in phase.to_dict()["missing_requirements"]
        assert verify(case, phase).payload == phase.payload


def test_ex_highspeed_with_v2_operating_usb3_is_retained_literally(predecessor):
    case = reboot_fixture(predecessor, ex_speed=2)
    doc = build(case).to_dict()
    assert doc["status"] == "REBOOT_OBSERVATIONS_RETAINED"
    assert doc["execution"]["ex_speed"] == 2
    assert doc["execution"]["usb3_operating"] is True


def test_late_report_within_phase_holds_but_outside_frame_is_not_rebased(subject):
    event = subject.event.to_dict()
    event["reported_at_utc_ns"] = subject.context["started_at_utc_ns"] + 2001
    sources = dict(subject.sources, operator_event=wire.canonical(event))
    phase = build(subject, sources=sources)
    assert phase.to_dict()["status"] == "HELD"
    assert (
        "OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER"
        in phase.to_dict()["missing_requirements"]
    )
    assert (
        verify(subject, phase, sources=sources, references=_references(sources)).payload
        == phase.payload
    )
    outside = subject.run.to_dict()
    outside["finished_utc_ns"] = subject.context["finished_at_utc_ns"] + 1
    outside_run = owned.retain_owned_usb_identity_run(outside)
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_ORIGINAL_RECONSTRUCTION_MISMATCH$"
    ):
        build(subject, sources=dict(subject.sources, owned_usb_run=outside_run.payload))


def test_unknown_cleanup_and_missing_native_result_preserve_originals_and_hold(subject):
    for changes in (
        {"cleanup_errors": ["MODELED_CLEANUP_UNCERTAIN"]},
        {"primary_error": "CANCELLED"},
    ):
        raw = subject.run.to_dict()
        raw.update(changes)
        held = owned.retain_owned_usb_identity_run(raw)
        assert held.observation.to_dict() == subject.run.observation.to_dict()
        sources = dict(subject.sources, owned_usb_run=held.payload)
        phase = build(subject, sources=sources)
        assert phase.to_dict()["status"] == "HELD"
        assert (
            "OWNED_RESULT_CURRENT_COMPLETE" in phase.to_dict()["missing_requirements"]
        )
        assert phase.to_dict()["values"]["descriptor_serial"]["value"] == "MODELED-ONLY"
        assert (
            verify(
                subject, phase, sources=sources, references=_references(sources)
            ).payload
            == phase.payload
        )
    raw = subject.run.to_dict()
    stdout = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)
    raw.update(
        stdout=owned.stream_record(stdout[: raw["ready_length"]], complete=True),
        primary_error="USB_RESULT_UNAVAILABLE",
        result_validated=False,
    )
    unknown = owned.retain_owned_usb_identity_run(raw)
    assert (
        unknown.released
        and unknown.observation is None
        and unknown.actual_counts is None
    )
    sources = dict(subject.sources, owned_usb_run=unknown.payload)
    doc = build(subject, sources=sources).to_dict()
    assert doc["status"] == "HELD"
    assert "USB_OBSERVATION_COMPLETE" in doc["missing_requirements"]
    assert doc["values"]["descriptor_serial"]["status"] == "NOT_OBSERVED"


def test_each_current_source_must_reconstruct_from_its_exact_bytes(subject):
    phase = build(subject)
    for role, raw in subject.sources.items():
        changed = dict(subject.sources, **{role: raw + b" "})
        with pytest.raises(
            m.UsbRebootPhaseError, match="^REBOOT_ORIGINAL_RECONSTRUCTION_MISMATCH$"
        ):
            verify(subject, phase, sources=changed)


def test_flags_never_accept_authority_or_integer_false_aliases(subject):
    for artifact in (subject.event, build(subject)):
        for key in m.FLAGS:
            for value in (True, 0):
                changed = artifact.to_dict()
                changed[key] = value
                with pytest.raises(
                    m.UsbRebootPhaseError, match="^NO_REBOOT_AUTHORITY$"
                ):
                    type(artifact)(wire.canonical(changed))


def test_rehashed_display_cannot_replace_original_serial(subject):
    phase = build(subject)
    changed = phase.to_dict()
    fake_hash = wire.digest(wire.canonical("MODELED-NOT-THE-OBSERVED-SERIAL"))
    changed["values"]["descriptor_serial"] = dict(
        status="VALUE_IN_ORIGINAL", value=None, sha256=fake_hash
    )
    row = next(
        row for row in changed["comparisons"] if row["field"] == "descriptor_serial"
    )
    row.update(reboot_sha256=fake_hash, status="CHANGED")
    forged = m.UsbRebootQualificationPhase(wire.canonical(changed))
    assert forged.sha256 != phase.sha256
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PHASE_RECONSTRUCTION_MISMATCH$"
    ):
        verify(subject, forged)


def test_rehashed_success_cannot_override_a_validly_framed_boot_hold(predecessor):
    case = reboot_fixture(predecessor, epoch="before_reconnect_finish")
    phase = build(case)
    changed = phase.to_dict()
    assert changed["status"] == "HELD"
    for row in changed["checks"]:
        row["passed"] = True
    changed.update(status="REBOOT_OBSERVATIONS_RETAINED", missing_requirements=[])
    forged = m.UsbRebootQualificationPhase(wire.canonical(changed))
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PHASE_RECONSTRUCTION_MISMATCH$"
    ):
        verify(case, forged)


def test_both_full_original_permits_are_independent_required_inputs(subject):
    with pytest.raises(
        m.UsbRebootPhaseError, match="^EXACT_ORIGINAL_USB_PERMIT_REQUIRED$"
    ):
        build(subject, permit=None)
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH$"
    ):
        build(subject, reconnect_permit=None)
    for wrong in (
        subject.reconnect_permit,
        replace(subject.permit, attempt_id="attempt-" + "a" * 32),
    ):
        with pytest.raises(
            m.UsbRebootPhaseError, match="^REBOOT_ORIGINAL_RECONSTRUCTION_MISMATCH$"
        ):
            build(subject, permit=wrong)
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH$"
    ):
        build(subject, reconnect_permit=subject.permit)


def test_new_campaign_cannot_reuse_historical_attempt_identity(predecessor):
    case = reboot_fixture(predecessor, attempt_id=predecessor.seed.permit.attempt_id)
    assert (
        case.run.preparation.request.to_dict()["attempt_id"]
        == case.seed.permit.attempt_id
    )
    assert case.permit.permit_sha256 != case.seed.permit.permit_sha256
    with pytest.raises(m.UsbRebootPhaseError, match="^NO_REPLAY_OR_REUSED_ADMISSION$"):
        build(case)


def test_each_metadata_operation_id_must_be_new_even_in_fresh_owner(predecessor):
    historical = json.loads(predecessor.seed.sources["native_enrollment"])
    # These tests use newly constructed in-memory owners, not cache editing.
    previous_ids = {
        "generic": historical["generic_review"]["operation_id"],
        "inventory": historical["view"]["inventory_operation_id"],
        "identity": historical["view"]["identity"]["operation_id"],
    }
    for role, operation_id in previous_ids.items():
        case = reboot_fixture(predecessor, metadata_operation_ids={role: operation_id})
        with pytest.raises(
            m.UsbRebootPhaseError,
            match="^DISTINCT_REBOOT_METADATA_OPERATIONS_REQUIRED$",
        ):
            build(case)


def test_new_phase_and_launch_cannot_rebind_historical_context(subject):
    contexts = (
        subject.original_baseline["baseline"].to_dict()["context"],
        subject.absence.to_dict()["context"],
        subject.reconnect.to_dict()["context"],
    )
    baseline = contexts[0]
    assert baseline["operation_id"] == "operation-presence-baseline"
    with pytest.raises(m.UsbRebootPhaseError, match="^EXACT_REBOOT_PHASE_ID_REQUIRED$"):
        build(
            subject,
            context=dict(subject.context, operation_id=baseline["operation_id"]),
        )
    for old in contexts[1:]:
        assert old["operation_id"].startswith("usbphase-")
        with pytest.raises(
            m.UsbRebootPhaseError, match="^ORDERED_DISTINCT_REBOOT_PHASE_REQUIRED$"
        ):
            build(
                subject, context=dict(subject.context, operation_id=old["operation_id"])
            )
    for old in contexts:
        with pytest.raises(m.UsbRebootPhaseError, match="^NEW_REBOOT_LAUNCH_REQUIRED$"):
            build(
                subject,
                context=dict(
                    subject.context, launch_session_id=old["launch_session_id"]
                ),
            )


def test_unknown_boot_cleanup_preserves_response_but_cannot_qualify(predecessor):
    case = reboot_fixture(predecessor, boot_cleanup_uncertain=True)
    boot = case.boot.to_dict()
    assert boot["status"] == "HELD"
    assert boot["response"]["last_boot_up_time_utc"] is not None
    assert boot["execution"]["cleanup_errors"] == ["OWNED_RESOURCE_CLEANUP_UNCONFIRMED"]
    phase = build(case)
    assert phase.to_dict()["status"] == "HELD"
    assert "HOST_BOOT_PHYSICAL_OWNED_CLEAN" in phase.to_dict()["missing_requirements"]
    assert verify(case, phase).payload == phase.payload


def test_role_references_are_exact_distinct_and_cannot_alias_history(subject):
    for role, ref in subject.references.items():
        for changed_ref in (
            replace(ref, payload_sha256="0" * 64),
            replace(ref, payload_bytes=ref.payload_bytes + 1),
            replace(ref, stage=PhysicalOnboardingStage.CAMERA_RECEIPT),
        ):
            refs = dict(subject.references, **{role: changed_ref})
            with pytest.raises(
                m.UsbRebootPhaseError, match="^REBOOT_ORIGINAL_RECONSTRUCTION_MISMATCH$"
            ):
                build(subject, references=refs)
    ref = subject.references["operation"]
    alias = replace(
        ref,
        evidence_id=subject.reconnect_reference.evidence_id,
        package_sha256=subject.reconnect_reference.package_sha256,
    )
    with pytest.raises(
        m.UsbRebootPhaseError, match="^DISTINCT_REBOOT_ORIGINAL_ROLES_REQUIRED$"
    ):
        build(subject, references=dict(subject.references, operation=alias))
    for key in ("absence_reference", "reconnect_reference"):
        ref = getattr(subject, key)
        with pytest.raises(
            m.UsbRebootPhaseError, match="^REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH$"
        ):
            build(subject, **{key: replace(ref, payload_sha256="0" * 64)})
    historical = subject.original_baseline["baseline_reference"]
    alias = replace(
        subject.absence_reference,
        evidence_id=historical.evidence_id,
        package_sha256=historical.package_sha256,
    )
    with pytest.raises(
        m.UsbRebootPhaseError, match="^DISTINCT_REBOOT_PREDECESSOR_REFERENCES_REQUIRED$"
    ):
        build(subject, absence_reference=alias)


def test_current_role_cannot_alias_received_stage_historical_reference(subject):
    plan_bytes = subject.original_baseline["plan"].payload
    received_ref = subject.original_baseline["plan"].to_dict()["received"][0][
        "reference"
    ]
    assert received_ref["stage"] == PhysicalOnboardingStage.CAMERA_RECEIPT.value
    current_ref = subject.references["operation"]
    assert current_ref.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
    alias = replace(
        current_ref,
        evidence_id=received_ref["evidence_id"],
        package_sha256=received_ref["package_sha256"],
    )
    # Keep the current role's exact bytes/stage: only its package identity now
    # aliases the earlier received-stage original, which must remain excluded.
    assert alias.payload_sha256 == wire.digest(subject.sources["operation"])
    assert alias.payload_bytes == len(subject.sources["operation"])
    assert alias.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
    with pytest.raises(
        m.UsbRebootPhaseError, match="^DISTINCT_REBOOT_ORIGINAL_ROLES_REQUIRED$"
    ):
        build(subject, references=dict(subject.references, operation=alias))
    assert subject.original_baseline["plan"].payload == plan_bytes
    assert subject.references["operation"] == current_ref


def test_independent_manifest_change_cannot_verify_the_old_phase(subject):
    phase = build(subject)
    refs = dict(subject.references)
    refs["host_boot"] = replace(refs["host_boot"], manifest_sha256="0" * 64)
    # A pure codec cannot authenticate a package manifest's origin. It can and
    # must bind the exact independent reference supplied for this verification.
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PHASE_RECONSTRUCTION_MISMATCH$"
    ):
        verify(subject, phase, references=refs)
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PHASE_RECONSTRUCTION_MISMATCH$"
    ):
        verify(
            subject,
            phase,
            reconnect_reference=replace(
                subject.reconnect_reference, manifest_sha256="0" * 64
            ),
        )


def test_source_and_operator_binding_substitutions_fail_after_rehash(subject):
    substitutions = (
        ("plan_sha256", "a" * 64),
        ("absence_sha256", "b" * 64),
        ("predecessor_sha256", "c" * 64),
        ("operator_id", "MODELED-other-operator"),
        ("phase_started_at_utc_ns", subject.context["started_at_utc_ns"] - 1),
    )
    for key, value in substitutions:
        changed = subject.event.to_dict()
        changed[key] = value
        event = m.UsbRebootOperatorEvent(wire.canonical(changed))
        with pytest.raises(
            m.UsbRebootPhaseError, match="^REBOOT_OPERATOR_EVENT_BINDING_MISMATCH$"
        ):
            build(subject, sources=dict(subject.sources, operator_event=event.payload))
    changed = subject.event.to_dict()
    changed["binding"]["source_sha256"] = "0" * 64
    event = m.UsbRebootOperatorEvent(wire.canonical(changed))
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_OPERATOR_EVENT_BINDING_MISMATCH$"
    ):
        build(subject, sources=dict(subject.sources, operator_event=event.payload))


def test_each_predecessor_source_must_independently_reconstruct(subject):
    for key in ("absence_sources", "reconnect_sources"):
        sources = getattr(subject, key)
        for role, payload in sources.items():
            changed = dict(sources, **{role: payload + b" "})
            with pytest.raises(
                m.UsbRebootPhaseError,
                match="^REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH$",
            ):
                build(subject, **{key: changed})
    original = subject.original_baseline
    for role, payload in original["baseline_sources"].items():
        changed = dict(
            original,
            baseline_sources=dict(
                original["baseline_sources"], **{role: payload + b" "}
            ),
        )
        with pytest.raises(
            m.UsbRebootPhaseError, match="^REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH$"
        ):
            build(subject, original_baseline=changed)


def test_role_roster_expected_hash_and_canonical_wire_are_closed(subject):
    for role in m.ROLES:
        missing = dict(subject.sources)
        missing.pop(role)
        with pytest.raises(
            m.UsbRebootPhaseError, match="^EXACT_REBOOT_ORIGINAL_ROLES$"
        ):
            build(subject, sources=missing)
    with pytest.raises(m.UsbRebootPhaseError, match="^EXACT_REBOOT_ORIGINAL_ROLES$"):
        build(subject, sources=dict(subject.sources, fabricated_boot_proof=b"{}"))
    phase = build(subject)
    for expected in (None, True, 0, "A" * 64, "short"):
        with pytest.raises(
            m.UsbRebootPhaseError, match="^EXACT_EXPECTED_REBOOT_HASH_REQUIRED$"
        ):
            verify(subject, phase, expected_sha256=expected)
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PHASE_RECONSTRUCTION_MISMATCH$"
    ):
        verify(subject, phase, expected_sha256="0" * 64)
    for raw in (phase.payload + b"\n", b"[]", b"not-json", b"x" * (m.PHASE_LIMIT + 1)):
        with pytest.raises(m.UsbRebootPhaseError, match="^INVALID_REBOOT_FIELDS$"):
            m.UsbRebootQualificationPhase(raw)
    for artifact in (phase, subject.event):
        changed = artifact.to_dict()
        changed["unreviewed_extra"] = "not ignored"
        with pytest.raises(m.UsbRebootPhaseError, match="^INVALID_REBOOT_FIELDS$"):
            type(artifact)(wire.canonical(changed))


def test_hash_only_values_and_safe_summaries_do_not_erase_original_presence(subject):
    phase = build(subject)
    value = phase.to_dict()["values"]["port_topology"]
    assert value["status"] == "VALUE_IN_ORIGINAL" and value["value"] is None
    assert value["sha256"] is not None
    row = next(
        row for row in phase.to_dict()["comparisons"] if row["field"] == "port_topology"
    )
    assert row["status"] == "MATCHED" and row["reboot_sha256"] == value["sha256"]
    assert len(wire.canonical(phase.safe_summary())) <= m.SUMMARY_LIMIT
    assert len(wire.canonical(subject.event.safe_summary())) <= m.EVENT_LIMIT
    assert [row["role"] for row in phase.to_dict()["predecessor_records"]] == [
        "absence",
        "reconnect",
    ]
    assert [row["role"] for row in phase.to_dict()["records"]] == list(m.ROLES)


def test_valid_but_unreviewed_received_trio_cannot_replace_original_plan(subject):
    old = subject.received["review"].to_dict()
    wrong_review = received_codec.review_received_camera_submission(
        subject.received["submission"],
        subject.received["assessment"],
        reviewer_id="MODELED-other-label-reviewer",
        review_launch_id=old["review_launch_id"],
        reviewed_at_ns=old["reviewed_at_ns"],
        decision="ACKNOWLEDGE_EXACT",
    )
    with pytest.raises(
        m.UsbRebootPhaseError, match="^REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH$"
    ):
        build(subject, received=dict(subject.received, review=wrong_review))


def test_genuinely_held_reconnect_cannot_be_promoted_into_a_reboot_predecessor(
    prerequisites,
):
    seed = reconnect_fixture(prerequisites, outcome="HELD")
    previous = build_reconnect(seed)
    assert previous.to_dict()["status"] == "HELD"
    assert "USB_OBSERVATION_COMPLETE" in previous.to_dict()["missing_requirements"]
    with pytest.raises(
        m.UsbRebootPhaseError, match="^COMPLETE_PHYSICAL_RECONNECT_REQUIRED$"
    ):
        m.verify_usb_reboot_predecessor(
            original_baseline=seed.original_baseline,
            received=_received_originals(prerequisites, seed.original_baseline["plan"]),
            absence=seed.absence,
            absence_reference=reference(
                seed.absence.payload, "MODELED-held-prefix-absence"
            ),
            absence_sources=seed.absence_sources,
            reconnect=previous,
            reconnect_reference=reference(
                previous.payload, "MODELED-held-prefix-reconnect"
            ),
            reconnect_sources=seed.sources,
            reconnect_permit=seed.permit,
        )
