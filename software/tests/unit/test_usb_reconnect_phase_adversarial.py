"""Independent reconnect reconstruction attacks; every physical fact is MODELED.

Only closed codecs run. References are explicitly modeled, not authenticated M1
packages. No process, CIM, USB, camera, original store or permit issuer is used.
These tests do not prove the later original-reader or metadata-freshness joins.
"""

from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import json
import os
import subprocess

import pytest

from rocell.application import physical_camera_usb_qualification as legacy
from rocell.application import physical_camera_usb_reconnect as preparation
from rocell.application import physical_usb_presence_phase as presence
from rocell.application import physical_usb_reconnect_phase as m
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_presence_binding import reference
from test_physical_usb_presence_dispatch import modeled_owned_presence
from test_physical_usb_reconnect_phase import reconnect_fixture


@pytest.fixture(autouse=True)
def no_process_or_device(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure reconnect adversarial test attempted process/device access")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(host, "_system_powershell", forbidden)
    monkeypatch.setattr(host, "_native_owner", forbidden)


@pytest.fixture
def subject(prerequisites):
    return reconnect_fixture(prerequisites)


def references(sources):
    return {
        role: reference(raw, "MODELED-adversarial-reconnect-" + role)
        for role, raw in sources.items()
    }


def build(subject, **changes):
    args = dict(
        original_baseline=subject.original_baseline,
        absence=subject.absence,
        absence_sources=subject.absence_sources,
        permit=subject.permit,
        context=subject.context,
        sources=subject.sources,
    )
    args.update(changes)
    args.setdefault("references", references(args["sources"]))
    return m.build_usb_reconnect_qualification_phase(**args)


def verify(subject, phase, **changes):
    args = dict(
        expected_sha256=phase.sha256,
        original_baseline=subject.original_baseline,
        absence=subject.absence,
        absence_sources=subject.absence_sources,
        permit=subject.permit,
        sources=subject.sources,
    )
    args.update(changes)
    return m.verify_usb_reconnect_qualification_phase(phase.payload, **args)


def test_nominal_is_inert_detached_and_never_physical_authority(subject, monkeypatch):
    phase = build(subject)
    assert phase.to_dict()["status"] == "RECONNECT_OBSERVATIONS_RETAINED"
    assert verify(subject, phase).payload == phase.payload
    assert phase.sha256 == digest(phase.payload)
    assert all(phase.to_dict()[key] is False for key in m.FLAGS)
    assert phase.to_dict()["mechanical_reconnection_verified"] is False
    assert phase.to_dict()["metadata_acquisition_freshness_verified"] is False
    detached = phase.to_dict()
    detached["context"]["operator_id"] = "not the retained operator"
    assert phase.to_dict()["context"] == subject.context
    with pytest.raises(FrozenInstanceError):
        phase.payload = b"{}"
    with pytest.raises(ValueError):
        legacy.UsbQualificationPhase(phase.payload)
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure reconstruction opened a file")
    )
    assert build(subject).payload == phase.payload
    assert verify(subject, phase).payload == phase.payload


def test_each_changed_source_is_rejected_even_with_unchanged_cached_phase(subject):
    phase = build(subject)
    for role in m.ROLES:
        changed = dict(subject.sources, **{role: subject.sources[role] + b" "})
        with pytest.raises(m.UsbReconnectPhaseError):
            verify(subject, phase, sources=changed)


def test_every_absence_original_is_independently_reconstructed(subject):
    for role, raw in subject.absence_sources.items():
        changed = dict(subject.absence_sources, **{role: raw + b" "})
        with pytest.raises(m.UsbReconnectPhaseError, match="PREDECESSOR"):
            build(subject, absence_sources=changed)


def test_every_baseline_original_is_independently_reconstructed(subject):
    original = subject.original_baseline
    for role, raw in original["baseline_sources"].items():
        changed = dict(
            original,
            baseline_sources=dict(original["baseline_sources"], **{role: raw + b" "}),
        )
        with pytest.raises(m.UsbReconnectPhaseError, match="PREDECESSOR"):
            build(subject, original_baseline=changed)


def test_rehashed_absence_cache_cannot_replace_independent_sources(subject):
    doc = subject.absence.to_dict()
    doc["target"][
        "physical_usb_instance_id"
    ] = r"USB\VID_1234&PID_5678\OTHER-MODELED-UNIT"
    forged = presence.UsbPresenceQualificationPhase(canonical(doc))
    assert forged.sha256 != subject.absence.sha256
    with pytest.raises(m.UsbReconnectPhaseError, match="PREDECESSOR"):
        build(subject, absence=forged)


def test_rehashed_baseline_cache_and_reference_cannot_replace_sources(subject):
    original = dict(subject.original_baseline)
    doc = original["baseline"].to_dict()
    doc["context"]["finished_at_utc_ns"] += 1
    changed = legacy.UsbQualificationPhase(canonical(doc))
    original.update(
        baseline=changed,
        baseline_reference=reference(changed.payload, "MODELED-rehashed-baseline"),
    )
    with pytest.raises(m.UsbReconnectPhaseError, match="PREDECESSOR"):
        build(subject, original_baseline=original)


def test_old_endpoint_phase_cannot_be_a_physical_absence(subject):
    with pytest.raises(m.UsbReconnectPhaseError, match="PHYSICAL_ABSENCE"):
        build(subject, absence=subject.original_baseline["baseline"])


def test_rehashed_operator_bindings_cannot_move_between_originals(subject):
    substitutions = dict(
        plan_sha256="a" * 64,
        baseline_sha256="b" * 64,
        predecessor_sha256="c" * 64,
        phase_id="usbphase-" + "f" * 32,
        launch_session_id="wizard-other",
        operator_id="MODELED-other",
        phase_started_at_utc_ns=subject.context["started_at_utc_ns"] - 1,
    )
    for key, value in substitutions.items():
        doc = m.UsbReconnectOperatorEvent(subject.sources["operator_event"]).to_dict()
        doc[key] = value
        changed = m.UsbReconnectOperatorEvent(canonical(doc))
        with pytest.raises(m.UsbReconnectPhaseError, match="EVENT_BINDING"):
            build(
                subject, sources=dict(subject.sources, operator_event=changed.payload)
            )


def test_role_swaps_aliases_and_foreign_stage_references_are_rejected(subject):
    refs = references(subject.sources)
    swapped = dict(refs, operation=refs["host_boot"], host_boot=refs["operation"])
    with pytest.raises(m.UsbReconnectPhaseError):
        build(subject, references=swapped)
    # Keep exact per-role payload digests, but alias two modeled package IDs.
    aliased = dict(refs)
    aliased["host_boot"] = replace(
        refs["host_boot"],
        evidence_id=refs["operation"].evidence_id,
        package_sha256=refs["operation"].package_sha256,
    )
    with pytest.raises(m.UsbReconnectPhaseError):
        build(subject, references=aliased)
    wrong_stage = dict(refs)
    wrong_stage["operation"] = replace(
        refs["operation"], stage=PhysicalOnboardingStage.CAMERA_RECEIPT
    )
    with pytest.raises(m.UsbReconnectPhaseError):
        build(subject, references=wrong_stage)
    # Updating both references cannot turn a boot subject into an operation.
    swapped_sources = dict(
        subject.sources,
        operation=subject.sources["host_boot"],
        host_boot=subject.sources["operation"],
    )
    with pytest.raises(m.UsbReconnectPhaseError):
        build(subject, sources=swapped_sources)


def test_closed_role_roster_cannot_drop_or_add_originals(subject):
    for role in m.ROLES:
        sources = dict(subject.sources)
        sources.pop(role)
        with pytest.raises(m.UsbReconnectPhaseError, match="ORIGINAL_ROLES"):
            build(subject, sources=sources)
    with pytest.raises(m.UsbReconnectPhaseError, match="ORIGINAL_ROLES"):
        build(subject, sources=dict(subject.sources, synthetic_measurement=b"{}"))


def test_unknown_nested_fields_and_reordered_records_are_closed(subject):
    phase = build(subject)
    for path in (
        (),
        ("context",),
        ("records", 0),
        ("comparisons", 0),
        ("values", "descriptor_serial"),
        ("execution",),
        ("provenance",),
    ):
        doc = phase.to_dict()
        target = doc
        for key in path:
            target = target[key]
        target["unreviewed_extra"] = "cannot be silently ignored"
        with pytest.raises(m.UsbReconnectPhaseError):
            m.UsbReconnectQualificationPhase(canonical(doc))
    doc = phase.to_dict()
    doc["records"][0], doc["records"][1] = doc["records"][1], doc["records"][0]
    with pytest.raises(m.UsbReconnectPhaseError):
        m.UsbReconnectQualificationPhase(canonical(doc))


def test_flags_reject_true_and_integer_false_aliases(subject):
    phase = build(subject)
    event = m.UsbReconnectOperatorEvent(subject.sources["operator_event"])
    for artifact in (phase, event):
        for field in m.FLAGS:
            for value in (True, 0):
                doc = artifact.to_dict()
                doc[field] = value
                with pytest.raises(m.UsbReconnectPhaseError, match="AUTHORITY"):
                    type(artifact)(canonical(doc))


def test_rehashed_hash_only_display_cannot_substitute_original_serial(subject):
    phase = build(subject)
    doc = phase.to_dict()
    field = "descriptor_serial"
    changed_hash = digest(canonical("MODELED-FORGED-SERIAL"))
    doc["values"][field] = dict(
        status="VALUE_IN_ORIGINAL", value=None, sha256=changed_hash
    )
    row = next(row for row in doc["comparisons"] if row["field"] == field)
    row.update(reconnect_sha256=changed_hash, status="CHANGED")
    forged = m.UsbReconnectQualificationPhase(canonical(doc))
    with pytest.raises(m.UsbReconnectPhaseError, match="RECONSTRUCTION"):
        verify(subject, forged)


def test_rehashed_claimed_provenance_cannot_replace_observation_origin(subject):
    doc = build(subject).to_dict()
    doc["provenance"]["boot"] = "INJECTED_CIM_EXECUTOR"
    forged = m.UsbReconnectQualificationPhase(canonical(doc))
    with pytest.raises(m.UsbReconnectPhaseError, match="RECONSTRUCTION"):
        verify(subject, forged)


def test_late_mechanical_report_is_retained_but_not_observation_proof(subject):
    doc = m.UsbReconnectOperatorEvent(subject.sources["operator_event"]).to_dict()
    doc["reported_at_utc_ns"] = subject.context["finished_at_utc_ns"]
    sources = dict(subject.sources, operator_event=canonical(doc))
    phase = build(subject, sources=sources)
    assert phase.to_dict()["status"] == "HELD"
    assert (
        "OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER"
        in phase.to_dict()["missing_requirements"]
    )
    assert phase.to_dict()["mechanical_reconnection_verified"] is False
    assert verify(subject, phase, sources=sources).payload == phase.payload
    # A syntax-valid status rewrite still cannot overrule the original report.
    forged = phase.to_dict()
    for row in forged["checks"]:
        row["passed"] = True
    forged.update(status="RECONNECT_OBSERVATIONS_RETAINED", missing_requirements=[])
    altered = m.UsbReconnectQualificationPhase(canonical(forged))
    with pytest.raises(m.UsbReconnectPhaseError, match="RECONSTRUCTION"):
        verify(subject, altered, sources=sources)


def test_new_phase_cannot_reuse_old_ids_or_omit_independent_permit(subject):
    for old_id in (
        subject.original_baseline["baseline"].to_dict()["context"]["operation_id"],
        subject.absence.to_dict()["context"]["operation_id"],
    ):
        with pytest.raises(m.UsbReconnectPhaseError):
            build(subject, context=dict(subject.context, operation_id=old_id))
    with pytest.raises(m.UsbReconnectPhaseError, match="ORIGINAL_USB_PERMIT"):
        build(subject, permit=None)
    with pytest.raises(m.UsbReconnectPhaseError):
        build(subject, permit=replace(subject.permit, attempt_id="attempt-" + "f" * 32))


def test_expected_hash_requires_exact_lowercase_text(subject):
    phase = build(subject)
    for expected in (None, {}, [], True, 1, "a", "A" * 64):
        with pytest.raises(m.UsbReconnectPhaseError, match="EXPECTED_RECONNECT_HASH"):
            verify(subject, phase, expected_sha256=expected)


def test_wire_bytes_are_canonical_closed_and_bounded(subject):
    phase = build(subject)
    for raw in (
        b"[]",
        b"null",
        b"{}",
        b"not-json",
        phase.payload + b"\n",
        b"x" * (m.PHASE_LIMIT + 1),
    ):
        with pytest.raises(m.UsbReconnectPhaseError):
            m.UsbReconnectQualificationPhase(raw)
    for raw in (
        b"[]",
        b"{}",
        subject.sources["operator_event"] + b" ",
        b"x" * (m.EVENT_LIMIT + 1),
    ):
        with pytest.raises(m.UsbReconnectPhaseError):
            m.UsbReconnectOperatorEvent(raw)


def modeled_owner_projection(subject):
    """Adapter-only input; deliberately NOT an authenticated v11 M1 readback.

    All consumed original payload/reference subjects use the strict fixture's
    manifests. Journal/epoch/terminal membership is separately the real reader's
    job, so this small owner-shaped projection must never enter an admission.
    """
    original = subject.original_baseline

    def record(payload, ref):
        return dict(
            document=json.loads(payload),
            evidence_sha256=digest(payload),
            reference=ref.to_dict() if hasattr(ref, "to_dict") else ref,
            retention="M1_FULL_BYTES_READ_BACK",
        )

    def phase_row(phase, sources, role_map, phase_reference):
        refs = {row["role"]: row["reference"] for row in phase.to_dict()["records"]}
        result = dict(
            phase=phase.to_dict()["phase"],
            state="RETAINED_BLOCKED",
            phase_record=record(phase.payload, phase_reference),
        )
        result.update(
            {
                target: record(sources[source], refs[source])
                for source, target in role_map
            }
        )
        result["original_campaign"] = dict(
            result=dict(state="SEALED_KNOWN", quarantine_latched=False),
            evidence=deepcopy(result["execution"]["document"]),
            evidence_sha256=result["execution"]["evidence_sha256"],
        )
        return result

    binding = original["plan"].to_dict()["binding"]
    return dict(
        schema="rocell.physical_camera_source_workflow_readback.v11",
        configuration_epochs={"model_only": True},
        binding={
            key: binding[key] for key in ("source_sha256", "cell_id", "session_id")
        },
        session_header_sha256=binding["header_sha256"],
        usb_qualification_trial=dict(
            state="PLAN_DECLARED",
            plan=record(original["plan"].payload, original["plan_reference"]),
            declaration_event=original["declaration_event"].to_dict(),
        ),
        usb_qualification_baseline=phase_row(
            original["baseline"],
            original["baseline_sources"],
            (
                ("native_enrollment", "enrollment"),
                ("owned_usb_run", "execution"),
                ("host_boot", "host_boot"),
            ),
            original["baseline_reference"],
        ),
        usb_qualification_absence=phase_row(
            subject.absence,
            subject.absence_sources,
            (
                ("operation", "operation"),
                ("operator_event", "operator_event"),
                ("owned_presence_run", "execution"),
                ("host_boot", "host_boot"),
            ),
            reference(subject.absence.payload, "MODELED-adapter-absence"),
        ),
    )


def test_adapter_rebuilds_exact_subjects_without_claiming_store_authentication(subject):
    original = preparation.original_usb_reconnect_predecessor(
        modeled_owner_projection(subject)
    )
    assert original["absence"].payload == subject.absence.payload
    assert original["absence_sources"] == subject.absence_sources
    assert (
        original["original_baseline"]["baseline_sources"]
        == subject.original_baseline["baseline_sources"]
    )


def test_adapter_rejects_unknown_terminal_quarantine_and_transfer_changes(subject):
    nominal = modeled_owner_projection(subject)
    for phase in ("usb_qualification_baseline", "usb_qualification_absence"):
        for change in ("missing", "uncertain", "quarantined", "evidence", "hash"):
            workflow = deepcopy(nominal)
            original = workflow[phase]["original_campaign"]
            if change == "missing":
                original["result"] = None
            elif change == "uncertain":
                original["result"]["state"] = "SEALED_UNCERTAIN"
            elif change == "quarantined":
                original["result"]["quarantine_latched"] = True
            elif change == "evidence":
                original["evidence"] = {}
            else:
                original["evidence_sha256"] = "a" * 64
            with pytest.raises(ValueError):
                preparation.original_usb_reconnect_predecessor(workflow)


def test_adapter_refuses_predecessor_schema_pending_and_partial_states(subject):
    nominal = modeled_owner_projection(subject)
    for schema in (None, "rocell.physical_camera_source_workflow_readback.v10", "v12"):
        with pytest.raises(ValueError):
            preparation.original_usb_reconnect_predecessor(dict(nominal, schema=schema))
    for state in ("QUERY_REQUESTED", "BOOT_HELD", "INCOMPLETE"):
        workflow = deepcopy(nominal)
        workflow["usb_qualification_absence"]["state"] = state
        with pytest.raises(ValueError):
            preparation.original_usb_reconnect_predecessor(workflow)


@pytest.mark.parametrize(
    "changes,missing",
    [
        ({"serial": "MODELED-OTHER"}, "RECEIVED_SERIAL_MATCH"),
        ({"driver_version": "9.8.7.6"}, "BASELINE_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY"),
        (
            {"physical_instance": r"USB\VID_1234&PID_5678\OTHER-MODELED-UNIT"},
            "EXACT_ABSENCE_PHYSICAL_NODE_RETURNED",
        ),
    ],
)
def test_actual_codec_changed_observations_hold_not_just_cached_mutations(
    prerequisites, changes, missing
):
    case = reconnect_fixture(prerequisites, **changes)
    phase = build(case)
    doc = phase.to_dict()
    assert case.run.status == "OBSERVED"
    assert doc["status"] == "HELD"
    assert missing in doc["missing_requirements"]
    assert any(row["status"] == "CHANGED" for row in doc["comparisons"])
    assert verify(case, phase).payload == phase.payload
    assert all(doc[field] is False for field in m.FLAGS)


def test_operator_report_does_not_supply_missing_descriptor_observations(prerequisites):
    case = reconnect_fixture(prerequisites, outcome="HELD")
    phase = build(case)
    doc = phase.to_dict()
    assert doc["status"] == "HELD"
    assert "USB_OBSERVATION_COMPLETE" in doc["missing_requirements"]
    assert doc["values"]["descriptor_serial"]["status"] == "NOT_OBSERVED"
    assert doc["mechanical_reconnection_verified"] is False
    assert verify(case, phase).payload == phase.payload


@pytest.mark.parametrize("outcome", ["PRESENT", "HELD"])
def test_adapter_rejects_genuine_nonabsent_predecessor_sources(subject, outcome):
    old = OwnedUsbPresenceRunEvidence(subject.absence_sources["owned_presence_run"])
    rd = old.to_dict()
    run = modeled_owned_presence(
        old.preparation,
        deadline_ns=rd["original_deadline_ns"],
        checks=rd["scope_checks"],
        started_ns=rd["started_monotonic_ns"],
        started_utc_ns=rd["started_utc_ns"],
        finished_ns=rd["finished_monotonic_ns"],
        finished_utc_ns=rd["finished_utc_ns"],
        outcome=outcome,
    )
    sources = dict(subject.absence_sources, owned_presence_run=run.payload)
    phase = presence.build_usb_presence_qualification_phase(
        original_baseline=subject.original_baseline,
        context=subject.absence.to_dict()["context"],
        sources=sources,
        references=references(sources),
    )
    assert phase.to_dict()["presence_outcome"] == outcome
    assert phase.to_dict()["status"] == "HELD"
    changed_subject = copy(subject)
    changed_subject.absence = phase
    changed_subject.absence_sources = sources
    with pytest.raises(ValueError):
        preparation.original_usb_reconnect_predecessor(
            modeled_owner_projection(changed_subject)
        )
