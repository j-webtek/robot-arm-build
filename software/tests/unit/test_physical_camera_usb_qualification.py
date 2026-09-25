"""Role-split series with actual codecs, explicitly modeled physical facts.

No CIM, device, physical native child, campaign, M1 replay or original-store
mutation. One fixture uses the separately linked incapable child and real Job.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from rocell.application import physical_camera_usb_qualification as m
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
)
from test_physical_received_camera_submission import submission_fixture
from test_physical_received_camera import prerequisites, workspace


def reference(payload, name, stage=PhysicalOnboardingStage.CAMERA_IDENTITY):
    package = m.digest(name.encode("ascii"))
    return EvidenceReference(
        "evidence-" + package, stage, package, "b" * 64, m.digest(payload), len(payload)
    )


def subjects(prerequisites):
    case = submission_fixture(prerequisites)
    return {key: case[key] for key in ("submission", "assessment", "review")}


def plan_fixture(prerequisites, **changes):
    received = submission_fixture(prerequisites)
    b = received["submission"].to_dict()["binding"]
    policy = m.usb_identity_stage_policy()
    binding = {
        k: b[k]
        for k in (
            "source_sha256",
            "cell_id",
            "session_id",
            "header_sha256",
            "origin_launch_id",
            "prerequisites_sha256",
        )
    }
    binding.update(
        trial_id="usbtrial-" + "1" * 32,
        identity_entry_sha256="9" * 64,
        stage_policy_sha256=policy.sha256,
        stage_catalog_sha256=policy.to_dict()["base_catalog_sha256"],
        stage_order_sha256=policy.to_dict()["canonical_stage_order_sha256"],
    )
    args = dict(
        binding=binding,
        mode="MODELED",
        operator_id="series-operator",
        launch_session_id="wizard-series",
        created_at_utc_ns=2000,
        cable_label="modeled-cable_A",
        port_label="modeled-port_A",
        received_submission=received["submission"],
        received_assessment=received["assessment"],
        received_review=received["review"],
        received_references=[
            reference(received[k].payload, k, PhysicalOnboardingStage.CAMERA_RECEIPT)
            for k in ("submission", "assessment", "review")
        ],
    )
    args.update(changes)
    return m.build_usb_qualification_plan(**args), received, args


def test_actual_received_trio_plan_is_detached_and_bound(prerequisites):
    plan, original, _ = plan_fixture(prerequisites)
    restored = m.verify_usb_qualification_plan(
        plan,
        expected_sha256=plan.sha256,
        received_submission=original["submission"],
        received_assessment=original["assessment"],
        received_review=original["review"],
    )
    assert restored.payload == plan.payload
    assert (
        plan.to_dict()["received_label"]["serial"]
        == original["submission"].to_dict()["inspection"]["observed_camera_serial"]
    )
    assert plan.to_dict()["cable_label"] == "modeled-cable_A"
    detached = plan.to_dict()
    detached["received_label"]["serial"] = "not-the-original"
    assert (
        plan.to_dict()["received_label"]["serial"]
        != detached["received_label"]["serial"]
    )
    with pytest.raises(FrozenInstanceError):
        plan.payload = b"{}"


def test_empty_series_is_explicitly_blocked_not_pass_by_vacuous_checks(prerequisites):
    plan, _, _ = plan_fixture(prerequisites)
    series = m.build_usb_qualification_series(plan, phases=[], references=[])
    assessment = m.assess_usb_qualification_series(
        plan, series, phases=[], phase_sources=[], received=subjects(prerequisites)
    )
    summary = assessment.safe_summary()
    assert summary["verdict"] == "BLOCKED"
    assert summary["missing_requirements"] == [
        "PHYSICAL_PROVENANCE_REQUIRED",
        "ALL_FOUR_PHASES_REQUIRED",
        "PHYSICAL_USB_ABSENCE_REQUIRED",
    ]
    assert all(summary[key] is False for key in m.FLAGS)
    assert "device_io_performed" not in summary  # real USB reads are effects
    assert len(m.canonical(summary)) < 24 * 1024
    review = m.review_usb_qualification_series(
        plan,
        series,
        assessment,
        phases=[],
        phase_sources=[],
        received=subjects(prerequisites),
        reviewer_id="independent-label",
        review_launch_id="wizard-review",
        reviewed_at_utc_ns=2001,
        decision="ACKNOWLEDGE_EXACT",
    )
    assert review.to_dict()["verdict"] == "BLOCKED"
    assert not review.to_dict()["authenticated_independent_people"]
    assert (
        m.verify_usb_qualification_review(
            review,
            expected_sha256=review.sha256,
            plan=plan,
            series=series,
            assessment=assessment,
            phases=[],
            phase_sources=[],
            received=subjects(prerequisites),
        ).payload
        == review.payload
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(extra=True),
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(created_at_utc_ns=True),
        lambda d: d["binding"].update(stage_policy_sha256="f" * 64),
        lambda d: d["received"][0].update(payload_bytes=1),
        lambda d: d["received"].reverse(),
        lambda d: d.update(mode="physical"),
    ],
)
def test_plan_closed_wire_and_role_binding(prerequisites, change):
    plan, _, _ = plan_fixture(prerequisites)
    changed = plan.to_dict()
    change(changed)
    with pytest.raises(ValueError):
        m.UsbQualificationPlan(m.canonical(changed))


def test_rehashed_label_substitution_fails_original_reconstruction(prerequisites):
    plan, original, _ = plan_fixture(prerequisites)
    changed = plan.to_dict()
    changed["received_label"]["serial"] = "substituted"
    fake = m.UsbQualificationPlan(m.canonical(changed))
    with pytest.raises(ValueError, match="RECONSTRUCTION"):
        m.verify_usb_qualification_plan(
            fake,
            expected_sha256=fake.sha256,
            received_submission=original["submission"],
            received_assessment=original["assessment"],
            received_review=original["review"],
        )


@pytest.mark.parametrize("label", ["series-operator", "SERIES-OPERATOR"])
def test_review_is_separate_exact_subject_not_new_authority(prerequisites, label):
    plan, _, _ = plan_fixture(prerequisites)
    series = m.build_usb_qualification_series(plan, phases=[], references=[])
    assessment = m.assess_usb_qualification_series(
        plan, series, phases=[], phase_sources=[], received=subjects(prerequisites)
    )
    with pytest.raises(ValueError, match="DISTINCT_REVIEW_LABEL"):
        m.review_usb_qualification_series(
            plan,
            series,
            assessment,
            phases=[],
            phase_sources=[],
            received=subjects(prerequisites),
            reviewer_id=label,
            review_launch_id="wizard-review",
            reviewed_at_utc_ns=2001,
            decision="ACKNOWLEDGE_EXACT",
        )


def test_long_values_are_explicit_original_references_not_silent_truncation():
    raw = "USB\\" + "x" * 4096
    view = m._display(raw)
    assert view == dict(
        status="VALUE_IN_ORIGINAL", value=None, sha256=m.digest(m.canonical(raw))
    )
    m._display_check(view)
    assert m._display(None) == dict(status="NOT_OBSERVED", value=None, sha256=None)


def test_import_and_empty_assessment_do_not_acquire(monkeypatch, prerequisites):
    def forbidden(*args, **kwargs):
        raise AssertionError("renderer/codec acquired")

    import subprocess
    from rocell.providers.windows.host_boot_observation import WindowsHostBootObserver

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(WindowsHostBootObserver, "observe", forbidden)
    plan, _, _ = plan_fixture(prerequisites)
    series = m.build_usb_qualification_series(plan, phases=[], references=[])
    m.assess_usb_qualification_series(
        plan, series, phases=[], phase_sources=[], received=subjects(prerequisites)
    ).safe_summary()


def test_actual_reviewed_native_snapshot_value_extraction(prerequisites):
    from test_physical_camera_identity_readback import identity_inputs

    plan, _, _ = plan_fixture(prerequisites)
    context = dict(
        launch_session_id="wizard-series",
        operation_id="baseline-operation",
        operator_id="series-operator",
        started_at_utc_ns=2000,
        finished_at_utc_ns=3000,
    )
    native = identity_inputs(
        source=plan.to_dict()["binding"]["source_sha256"],
        launch=context["launch_session_id"],
    )["enrollment"]
    data, selection, values = m._native(plan, context, m.canonical(native))
    assert selection is not None
    assert (
        values["driver_provider"] is None
    )  # original v1 never invents v2 driver facts
    assert values["generic_serial"] == "SYNTHETIC-CAMERA-A"


def failed_phase_fixture(
    prerequisites, *, phase="BASELINE", predecessor=None, index=0, plan=None
):
    """Actual prepared/evidence codecs, explicitly modeled no-process failure."""
    from pathlib import Path
    from rocell.providers.windows import usb_identity_registration as registration
    from rocell.providers.windows import owned_usb_identity_evidence as evidence
    from rocell.providers.windows.usb_identity_protocol import (
        UsbIdentityAdmissionRequest,
        REQUEST_SCHEMA,
    )
    from rocell.application.usb_identity_stage_policy import (
        UsbIdentityAdmissionIdentity,
        IDENTITY_SCHEMA,
    )
    from test_physical_camera_identity_readback import identity_inputs
    from test_host_boot_observation import (
        request as boot_request,
        modeled_observation,
        WALL,
    )

    plan = plan or plan_fixture(prerequisites)[0]
    p = plan.to_dict()["binding"]
    start = WALL + index * 100000
    context = dict(
        launch_session_id="wizard-series" + str(index),
        operation_id="phase-operation-" + str(index),
        operator_id="phase-operator",
        started_at_utc_ns=start,
        finished_at_utc_ns=start + 90000,
    )
    enrollment = identity_inputs(
        source=p["source_sha256"], launch=context["launch_session_id"]
    )["enrollment"]
    _, selection, _ = m._native(plan, context, m.canonical(enrollment))
    runtime = registration.incapable_usb_identity_runtime_candidate(
        Path.cwd(), source_sha256=p["source_sha256"]
    )
    sd = selection.identity_document
    target = dict(
        selection_sha256=selection.sha256,
        native_identity_sha256=sd["native_identity_sha256"],
        endpoint_sha256=sd["endpoint_sha256"],
        device_instance_id_sha256=m.digest(
            sd["metadata_review"]["observed_instance_id"].encode()
        ),
        operation_sha256=m.digest(context["operation_id"].encode()),
    )
    review = registration.review_usb_identity_runtime(
        runtime,
        **target,
        operator_id="runtime-operator",
        reviewer_id="runtime-reviewer",
        launch_session_id=context["launch_session_id"],
        reviewed_at_ns=start - 1,
    )
    subjects = []
    for role, payload in (
        ("metadata", m.canonical(enrollment)),
        ("policy_review", b"modeled-policy-review"),
        ("runtime_review", review.payload),
    ):
        ref = reference(payload, role + str(index))
        subjects.append(
            dict(role=role, document_sha256=m.digest(payload), reference=ref.to_dict())
        )
    identity = UsbIdentityAdmissionIdentity(
        m.canonical(
            dict(
                schema=IDENTITY_SCHEMA,
                **{
                    k: p[k]
                    for k in (
                        "cell_id",
                        "session_id",
                        "source_sha256",
                        "header_sha256",
                        "stage_policy_sha256",
                    )
                },
                policy_review_sha256=subjects[1]["document_sha256"],
                runtime_review_sha256=review.sha256,
                runtime_registration_sha256=runtime.sha256,
                original_subjects=subjects,
                **target,
            )
        )
    )
    request = UsbIdentityAdmissionRequest(
        m.canonical(
            dict(
                schema=REQUEST_SCHEMA,
                attempt_id="attempt-phase-" + str(index),
                session_id=p["session_id"],
                source_sha256=p["source_sha256"],
                operation_sha256=target["operation_sha256"],
                selected_identity_sha256=identity.sha256,
                native_identity_sha256=target["native_identity_sha256"],
                endpoint=sd["symbolic_link"],
                endpoint_sha256=sd["endpoint_sha256"],
                expected_device_instance_id=sd["metadata_review"][
                    "observed_instance_id"
                ],
                expected_device_instance_id_sha256=target["device_instance_id_sha256"],
                helper_sha256=runtime.to_dict()["helper"]["sha256"],
                runtime_registration_sha256=runtime.sha256,
                permit_sha256=m.digest(("permit" + str(index)).encode()),
                native_duration_ms=10000,
                admission_timeout_ms=5000,
            )
        )
    )
    prepared = registration.prepare_incapable_usb_identity(
        runtime,
        review=review,
        expected_review_sha256=review.sha256,
        identity=identity,
        request=request,
    )
    run = evidence.retain_owned_usb_identity_run(
        dict(
            schema=evidence.SCHEMA,
            preparation=prepared.to_dict(),
            preparation_sha256=prepared.sha256,
            provenance="INCAPABLE_USB_QUERY",
            original_deadline_ns=30_000_000_001,
            started_monotonic_ns=1,
            finished_monotonic_ns=2,
            started_utc_ns=start + 2000,
            finished_utc_ns=start + 3000,
            scope_checks=[],
            owner_constructed=False,
            process=dict(evidence.PROCESS_DEFAULTS),
            stdout=evidence.stream_record(b"", complete=True),
            stderr=evidence.stream_record(b"", complete=True),
            ready_length=0,
            release_wire=evidence.stream_record(b"", complete=True),
            release_write_attempted=False,
            release_check_passed=False,
            release_delivery_confirmed=False,
            result_validated=False,
            primary_error="CANCELLED",
            cleanup_errors=[],
            status="CANCELLED",
            physical_authority=False,
            hardware_qualified=False,
            retries=0,
        )
    )
    req = boot_request(
        source_sha256=p["source_sha256"],
        session_id=p["session_id"],
        trial_id=p["trial_id"],
        phase=phase,
        launch_session_id=context["launch_session_id"],
        operation_id=context["operation_id"],
    )
    boot = modeled_observation(req=req, wall=start)
    sources = dict(
        native_enrollment=m.canonical(enrollment),
        owned_usb_run=run.payload,
        host_boot=boot.payload,
    )
    refs = {
        role: reference(payload, role + str(index)) for role, payload in sources.items()
    }
    made = m.build_usb_qualification_phase(
        plan,
        phase=phase,
        predecessor=predecessor,
        context=context,
        sources=sources,
        references=refs,
    )
    return plan, made, sources, refs, run


def test_actual_prepared_owned_failure_and_boot_phase_join(prerequisites):
    plan, phase, sources, refs, run = failed_phase_fixture(prerequisites)
    assert run.no_attempt and run.observation is None
    assert phase.to_dict()["status"] == "HELD"
    assert phase.to_dict()["values"]["descriptor_serial"]["status"] == "NOT_OBSERVED"
    assert phase.to_dict()["values"]["endpoint"]["status"] == "VALUE_RETAINED"
    assert not phase.to_dict()["execution"]["process_clean"]
    restored = m.verify_usb_qualification_phase(
        phase,
        plan=plan,
        predecessor=None,
        sources=sources,
        expected_sha256=phase.sha256,
    )
    assert restored.payload == phase.payload
    series = m.build_usb_qualification_series(
        plan, phases=[phase], references=[reference(phase.payload, "baseline")]
    )
    summary = m.assess_usb_qualification_series(
        plan,
        series,
        phases=[phase],
        phase_sources=[sources],
        received=subjects(prerequisites),
    ).safe_summary()
    assert "BASELINE_COMPLETE" in summary["missing_requirements"]
    assert "PHYSICAL_USB_ABSENCE_REQUIRED" in summary["missing_requirements"]


def test_rehashed_phase_value_cannot_replace_original_owned_result(prerequisites):
    plan, phase, sources, _, _ = failed_phase_fixture(prerequisites)
    data = phase.to_dict()
    data["values"]["descriptor_serial"] = m._display(
        plan.to_dict()["received_label"]["serial"]
    )
    changed = m.UsbQualificationPhase(m.canonical(data))
    with pytest.raises(ValueError, match="RECONSTRUCTION"):
        m.verify_usb_qualification_phase(
            changed,
            plan=plan,
            predecessor=None,
            sources=sources,
            expected_sha256=changed.sha256,
        )


def test_endpoint_empty_inventory_is_not_fresh_physical_absence(prerequisites):
    from test_host_boot_observation import request as boot_request, modeled_observation

    plan, baseline, originals, _, _ = failed_phase_fixture(prerequisites)
    packet = deepcopy(
        m._load(originals["native_enrollment"], m.ROLE_LIMITS["native_enrollment"])[
            "inventory_packet"
        ]
    )
    packet["receipt"]["devices"] = []
    context = dict(baseline.to_dict()["context"])
    context.update(
        operation_id="explicit-absence",
        started_at_utc_ns=context["finished_at_utc_ns"] + 1,
        finished_at_utc_ns=context["finished_at_utc_ns"] + 50000,
    )
    p = plan.to_dict()["binding"]
    req = boot_request(
        source_sha256=p["source_sha256"],
        session_id=p["session_id"],
        trial_id=p["trial_id"],
        phase="RECONNECT_ABSENCE",
        launch_session_id=context["launch_session_id"],
        operation_id=context["operation_id"],
    )
    boot = modeled_observation(req=req, wall=context["started_at_utc_ns"])
    sources = dict(endpoint_inventory=m.canonical(packet), host_boot=boot.payload)
    refs = {r: reference(b, "absence-" + r) for r, b in sources.items()}
    absence = m.build_usb_qualification_phase(
        plan,
        phase="RECONNECT_ABSENCE",
        predecessor=baseline,
        context=context,
        sources=sources,
        references=refs,
    )
    checks = {row["check_id"]: row["passed"] for row in absence.to_dict()["checks"]}
    assert checks["ENDPOINT_INVENTORY_COMPLETE"] and checks["REVIEWED_ENDPOINT_ABSENT"]
    assert not checks["ENDPOINT_INVENTORY_FRESHNESS_REQUIRED"]
    assert absence.to_dict()["status"] == "HELD"
    assert absence.to_dict()["absence_scope"] == "CAMERA_ENDPOINTS_ONLY"
    assert absence.to_dict()["execution"]["process_clean"] is None


@pytest.mark.parametrize(
    "ex,available,operating,capable,expected",
    [
        (2, True, True, True, True),
        (3, True, True, True, True),
        (2, True, False, True, False),
        (3, False, None, None, False),
        (2, False, None, None, False),
        (2, True, False, False, False),
    ],
)
def test_operating_v2_not_ex_speed_or_capability(
    ex, available, operating, capable, expected
):
    link = dict(
        ex_speed=ex,
        ex_v2_available=available,
        operating_superspeed_or_higher=operating,
        capable_superspeed_or_higher=capable,
    )
    before = deepcopy(link)
    assert m._operating_usb3(link) is expected
    assert link == before


def usb_native_enrollment(
    source,
    launch,
    *,
    serial="MODELED-ONLY",
    driver_version="1.2.3.4",
    suffix="baseline",
):
    """Explicitly modeled USB target through actual generic/native registries."""
    from test_owned_usb_identity_runner import ENDPOINT, INSTANCE
    from test_wizard_native_camera_enrollment import generic_review
    from test_windows_camera_driver_metadata import driver_fixture
    from rocell.application.wizard_native_camera_metadata import (
        RehearsalNativeCameraMetadataProvider,
    )
    from rocell.application.wizard_native_camera_enrollment import (
        WizardNativeCameraEnrollment,
    )
    from rocell.application.wizard_device_selection import _batch
    from rocell.application.physical_device_inventory import (
        compose_physical_device_inventory_report,
    )
    from rocell.providers.windows.camera_worker_client import CameraCandidate

    provider = RehearsalNativeCameraMetadataProvider("nominal")
    inventory = provider.inventory()
    identity = provider.identity(CameraCandidate(**inventory["receipt"]["devices"][0]))
    descriptor = dict(provenance="WINDOWS_NATIVE_METADATA", helper_sha256="b" * 64)
    for packet in (inventory, identity):
        packet.update(descriptor)
    inventory["receipt"]["devices"][0]["symbolic_link"] = ENDPOINT
    wire = identity["receipt"]
    wire["requested_endpoint"] = ENDPOINT
    wire["mapping"]["interface_path"]["value"] = ENDPOINT
    wire["device"]["instance_id"]["value"] = INSTANCE
    wire.update(
        schema="rocell.windows_camera_identity.v2", driver=driver_fixture()["driver"]
    )
    wire["driver"]["version"]["value"] = driver_version
    wire["driver"]["service"]["value"] = "usbvideo"
    wire["api_calls"] += 4
    wire["observed_property_bytes"] += 512

    def mutate(report):
        row = report["camera_inventory"]["candidates"][0]
        old_instance = row["os_instance_id"]
        row["os_instance_id"] = INSTANCE
        row["usb_identity"].update(vid="1234", pid="5678", unit_serial=serial)
        row["driver_service"] = "usbvideo"
        row["persistent_ids"] = sorted(
            {x.replace(old_instance, INSTANCE) for x in row["persistent_ids"]}
        )
        rebuilt = compose_physical_device_inventory_report(
            platform_system=report["platform_system"],
            captured_at_unix_ns=report["captured_at_unix_ns"],
            camera_inventory=_batch(report["camera_inventory"]),
            serial_inventory=_batch(report["serial_inventory"]),
        ).to_dict()
        report.clear()
        report.update(rebuilt)

    generic = generic_review(
        mode="physical", source=source, session=launch, mutate=mutate
    )
    owner = WizardNativeCameraEnrollment("physical", launch, source, descriptor)
    owner.ingest_inventory(
        inventory, operation_id="native-inventory-" + suffix, generic_review=generic
    )
    choice = owner.choices()[0]["value"]
    owner.retain_identity(choice, identity, operation_id="native-identity-" + suffix)
    owner.review(choice, "modeled-endpoint-reviewer")
    return owner.export_snapshot()


def test_actual_v2_driver_values_not_hash_only(prerequisites):
    plan, _, _ = plan_fixture(prerequisites)
    data = usb_native_enrollment(
        plan.to_dict()["binding"]["source_sha256"], "wizard-series"
    )
    _, selection, values = m._native(
        plan, dict(launch_session_id="wizard-series"), m.canonical(data)
    )
    assert selection is not None
    assert values["driver_version"] == "1.2.3.4"
    assert values["driver_service"] == "usbvideo"
    assert values["generic_vid"] == "1234" and values["generic_pid"] == "5678"


def actual_owned_phase(
    prerequisites,
    monkeypatch,
    *,
    index=0,
    phase="BASELINE",
    predecessor=None,
    plan=None,
):
    from test_owned_usb_identity_runner import usb_fixture, run_case, ENDPOINT, INSTANCE
    from rocell.providers.windows import owned_usb_identity_runner as runner_module
    from test_host_boot_observation import (
        request as boot_request,
        modeled_observation,
        response,
    )
    from datetime import datetime, timezone

    plan = plan or plan_fixture(prerequisites)[0]
    p = plan.to_dict()["binding"]
    launch = "wizard-owned-series-" + str(index)
    native = usb_native_enrollment(p["source_sha256"], launch, suffix=str(index))
    _, selection, _ = m._native(
        plan, dict(launch_session_id=launch), m.canonical(native)
    )
    case = usb_fixture(
        source_sha256=p["source_sha256"],
        selection_sha256=selection.sha256,
        native_identity_sha256=native["view"]["identity"]["identity_sha256"],
        endpoint=ENDPOINT,
        instance=INSTANCE,
        cell_id=p["cell_id"],
        session_id=p["session_id"],
        header_sha256=p["header_sha256"],
        launch_session_id=launch,
        operation_sha256=m.digest(("owned-operation-" + str(index)).encode()),
        attempt_id="attempt-owned-series-" + str(index),
    )
    monkeypatch.setattr(
        runner_module, "source_fingerprint", lambda _: p["source_sha256"]
    )
    _, run = run_case(case)
    assert run.status == "OBSERVED", run.safe_summary()
    d = run.to_dict()
    context = dict(
        launch_session_id=launch,
        operation_id="owned-operation-" + str(index),
        operator_id="series-operator",
        started_at_utc_ns=d["started_utc_ns"] - 1000,
        finished_at_utc_ns=d["finished_utc_ns"] + 10000,
    )
    req = boot_request(
        source_sha256=p["source_sha256"],
        session_id=p["session_id"],
        trial_id=p["trial_id"],
        phase=phase,
        launch_session_id=launch,
        operation_id=context["operation_id"],
    )
    # A real owned incapable process and explicitly injected CIM report are
    # separate origins. No test calls WindowsHostBootObserver's CIM executor.
    boot = modeled_observation(req=req, wall=d["finished_utc_ns"] + 1000)
    sources = dict(
        native_enrollment=m.canonical(native),
        owned_usb_run=run.payload,
        host_boot=boot.payload,
    )
    refs = {
        k: reference(v, "owned-" + str(index) + "-" + k) for k, v in sources.items()
    }
    made = m.build_usb_qualification_phase(
        plan,
        phase=phase,
        predecessor=predecessor,
        context=context,
        sources=sources,
        references=refs,
    )
    return plan, made, sources, run


def test_actual_incapable_owned_run_to_value_phase_and_original_reconstruction(
    prerequisites, monkeypatch
):
    plan, phase, sources, run = actual_owned_phase(prerequisites, monkeypatch)
    data = phase.to_dict()
    assert data["status"] == "OBSERVATIONS_RETAINED"
    assert data["values"]["descriptor_serial"]["value"] == "MODELED-ONLY"
    assert data["values"]["vid"]["value"] == "1234"
    assert data["values"]["pid"]["value"] == "5678"
    assert data["execution"]["usb3_operating"] is True
    assert data["execution"]["process_clean"] is True
    assert data["execution"]["native_clean"] is True
    assert data["provenance"]["usb"] == "INCAPABLE_USB_QUERY"
    assert data["provenance"]["boot"] == "INJECTED_CIM_EXECUTOR"
    assert (
        m.verify_usb_qualification_phase(
            phase,
            plan=plan,
            predecessor=None,
            sources=sources,
            expected_sha256=phase.sha256,
        ).payload
        == phase.payload
    )
    series = m.build_usb_qualification_series(
        plan, phases=[phase], references=[reference(phase.payload, "owned-baseline")]
    )
    summary = m.assess_usb_qualification_series(
        plan,
        series,
        phases=[phase],
        phase_sources=[sources],
        received=subjects(prerequisites),
    ).safe_summary()
    assert summary["verdict"] == "BLOCKED"
    assert (
        "BASELINE_RECEIVED_SERIAL_MATCH" in summary["missing_requirements"]
    )  # separately recorded different label
    assert "BASELINE_PHYSICAL_ORIGINS" in summary["missing_requirements"]
    assert "PHYSICAL_USB_ABSENCE_REQUIRED" in summary["missing_requirements"]


def endpoint_absence_phase(plan, baseline, originals):
    from test_host_boot_observation import request as boot_request, modeled_observation

    packet = deepcopy(
        m._load(originals["native_enrollment"], m.ROLE_LIMITS["native_enrollment"])[
            "inventory_packet"
        ]
    )
    packet["receipt"]["devices"] = []
    context = dict(baseline.to_dict()["context"])
    context.update(
        operation_id="four-phase-absence",
        started_at_utc_ns=context["finished_at_utc_ns"] + 1,
        finished_at_utc_ns=context["finished_at_utc_ns"] + 50000,
    )
    p = plan.to_dict()["binding"]
    req = boot_request(
        source_sha256=p["source_sha256"],
        session_id=p["session_id"],
        trial_id=p["trial_id"],
        phase="RECONNECT_ABSENCE",
        launch_session_id=context["launch_session_id"],
        operation_id=context["operation_id"],
    )
    boot = modeled_observation(req=req, wall=context["started_at_utc_ns"])
    sources = dict(endpoint_inventory=m.canonical(packet), host_boot=boot.payload)
    refs = {k: reference(v, "four-absence-" + k) for k, v in sources.items()}
    made = m.build_usb_qualification_phase(
        plan,
        phase="RECONNECT_ABSENCE",
        predecessor=baseline,
        context=context,
        sources=sources,
        references=refs,
    )
    return made, sources


def test_three_owned_runs_four_original_phases_new_launch_is_not_reboot(
    prerequisites, monkeypatch
):
    plan, baseline, sources0, _ = actual_owned_phase(prerequisites, monkeypatch)
    absence, sources1 = endpoint_absence_phase(plan, baseline, sources0)
    _, reconnect, sources2, _ = actual_owned_phase(
        prerequisites,
        monkeypatch,
        plan=plan,
        predecessor=absence,
        phase="AFTER_RECONNECT",
        index=2,
    )
    _, reboot, sources3, _ = actual_owned_phase(
        prerequisites,
        monkeypatch,
        plan=plan,
        predecessor=reconnect,
        phase="AFTER_REBOOT",
        index=3,
    )
    phases = [baseline, absence, reconnect, reboot]
    sources = [sources0, sources1, sources2, sources3]
    series = m.build_usb_qualification_series(
        plan,
        phases=phases,
        references=[
            reference(x.payload, "phase-" + str(i)) for i, x in enumerate(phases)
        ],
    )
    assessment = m.assess_usb_qualification_series(
        plan,
        series,
        phases=phases,
        phase_sources=sources,
        received=subjects(prerequisites),
    )
    summary = assessment.safe_summary()
    checks = {x["check_id"]: x["passed"] for x in assessment.to_dict()["checks"]}
    assert checks["ALL_FOUR_PHASES_REQUIRED"]
    assert checks["AFTER_RECONNECT_BOOT_RELATION"]
    assert not checks["AFTER_REBOOT_BOOT_RELATION"]
    assert not checks["PHYSICAL_USB_ABSENCE_REQUIRED"]
    assert all(x["status"] == "MATCHED" for x in summary["comparisons"])
    assert len(m.canonical(summary)) <= 24 * 1024
    assert len(assessment.payload) <= 32 * 1024
    assert len(summary["phases"]) == 4
    assert all(x["before_phase"] == "BASELINE" for x in summary["comparisons"])

    # Reconstruct ONLY an explicitly modeled CIM subject that reports a later
    # boot epoch. Actual owned USB originals stay byte-identical. This is not a
    # claim that this machine rebooted or that an app launch constitutes one.
    from test_host_boot_observation import modeled_observation, response
    from rocell.providers.windows.host_boot_observation import (
        HostBootRequest,
        HostBootObservation,
    )
    from datetime import datetime, timezone

    old = HostBootObservation(sources3["host_boot"]).to_dict()
    before = reconnect.to_dict()["context"]["finished_at_utc_ns"]
    after = reboot.to_dict()["context"]["started_at_utc_ns"]
    midpoint = (before + after) // 2
    boot_time = (
        datetime.fromtimestamp(midpoint // 1_000_000_000, timezone.utc)
        .replace(microsecond=(midpoint % 1_000_000_000) // 1000)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )
    request = HostBootRequest(
        **{k: v for k, v in old["request"].items() if k != "schema"}
    )
    changed_boot = modeled_observation(
        req=request,
        wall=old["execution"]["started_utc_ns"],
        raw=response(
            request,
            last_boot_up_time_utc=boot_time,
            confirmation_boot_up_time_utc=boot_time,
        ),
    )
    changed_sources = dict(sources3, host_boot=changed_boot.payload)
    changed_refs = {r["role"]: r["reference"] for r in reboot.to_dict()["records"]}
    changed_refs["host_boot"] = reference(
        changed_boot.payload, "explicit-modeled-new-boot"
    )
    changed_phase = m.build_usb_qualification_phase(
        plan,
        phase="AFTER_REBOOT",
        predecessor=reconnect,
        context=reboot.to_dict()["context"],
        sources=changed_sources,
        references=changed_refs,
    )
    phases[-1], sources[-1] = changed_phase, changed_sources
    changed_series = m.build_usb_qualification_series(
        plan,
        phases=phases,
        references=[
            reference(x.payload, "newphase-" + str(i)) for i, x in enumerate(phases)
        ],
    )
    changed = m.assess_usb_qualification_series(
        plan,
        changed_series,
        phases=phases,
        phase_sources=sources,
        received=subjects(prerequisites),
    ).safe_summary()
    assert "AFTER_REBOOT_BOOT_RELATION" not in changed["missing_requirements"]
    assert (
        changed["verdict"] == "BLOCKED"
        and "PHYSICAL_USB_ABSENCE_REQUIRED" in changed["missing_requirements"]
    )
    assert changed_sources["owned_usb_run"] == sources3["owned_usb_run"]


def failed_series_fixture(prerequisites):
    plan, baseline, original0, _, _ = failed_phase_fixture(prerequisites)
    absence, original1 = endpoint_absence_phase(plan, baseline, original0)
    _, reconnect, original2, _, _ = failed_phase_fixture(
        prerequisites, plan=plan, phase="AFTER_RECONNECT", predecessor=absence, index=2
    )
    _, reboot, original3, _, _ = failed_phase_fixture(
        prerequisites, plan=plan, phase="AFTER_REBOOT", predecessor=reconnect, index=3
    )
    phases = [baseline, absence, reconnect, reboot]
    originals = [original0, original1, original2, original3]
    series = m.build_usb_qualification_series(
        plan,
        phases=phases,
        references=[
            reference(x.payload, "failed-" + str(i)) for i, x in enumerate(phases)
        ],
    )
    assessment = m.assess_usb_qualification_series(
        plan,
        series,
        phases=phases,
        phase_sources=originals,
        received=subjects(prerequisites),
    )
    return plan, series, assessment, phases, originals


def test_max_bounded_value_view_uses_shared_phase_values(prerequisites):
    _, _, assessment, _, _ = failed_series_fixture(prerequisites)
    data = assessment.to_dict()
    # Over-approximation of legal raw metadata: even fixed VID/PID fields are
    # inflated to the display bound. This tests presentation size, not facts.
    for row in data["phases"]:
        row["values"] = {key: m._display("x" * 126) for key in m._VALUE_FIELDS}
    for row in data["comparisons"]:
        row["status"] = "MATCHED"
    for key in ("manufacturer", "product_id", "serial"):
        data["received_label"][key] = "é" * 128
    summary = m.UsbQualificationAssessment(
        m.canonical(m._bounded_assessment_values(data))
    ).safe_summary()
    assert len(m.canonical(summary)) <= 24 * 1024
    assert all(
        "before" not in row and "after" not in row for row in summary["comparisons"]
    )


@pytest.mark.parametrize(
    "kind",
    [
        "extra",
        "phase_extra",
        "wrong_integer",
        "changed_value",
        "changed_reference",
        "wrong_phase_order",
    ],
)
def test_closed_assessment_and_exact_original_reconstruction(prerequisites, kind):
    plan, series, assessment, phases, sources = failed_series_fixture(prerequisites)
    data = assessment.to_dict()
    if kind == "extra":
        data["connected"] = True
    elif kind == "phase_extra":
        data["phases"][0]["raw_endpoint"] = "unexpected"
    elif kind == "wrong_integer":
        data["phases"][0]["execution"]["process_clean"] = 1
    elif kind == "changed_value":
        data["phases"][0]["values"]["driver_provider"] = m._display("substitute")
    elif kind == "changed_reference":
        data["phases"][0]["phase_sha256"] = "f" * 64
    else:
        data["phases"].reverse()
    with pytest.raises(ValueError):
        current = m.UsbQualificationAssessment(m.canonical(data))
        m.verify_usb_qualification_assessment(
            current,
            expected_sha256=current.sha256,
            plan=plan,
            series=series,
            phases=phases,
            phase_sources=sources,
            received=subjects(prerequisites),
        )


def test_rehashed_plan_label_cannot_reach_assessment(prerequisites):
    plan, _, _ = plan_fixture(prerequisites)
    data = plan.to_dict()
    data["received_label"]["serial"] = "substituted"
    forged = m.UsbQualificationPlan(m.canonical(data))
    series = m.build_usb_qualification_series(forged, phases=[], references=[])
    with pytest.raises(ValueError, match="RECONSTRUCTION"):
        m.assess_usb_qualification_series(
            forged,
            series,
            phases=[],
            phase_sources=[],
            received=subjects(prerequisites),
        )
