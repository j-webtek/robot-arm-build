from dataclasses import replace
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.controller_configuration_epoch_intake_v1 import (
    EXPECTED_COMPONENT_IDS,
    R97_APP_SHA256,
    R97_JOINT_MAPPING_SOURCE_SHA256,
    R97_PROTOCOL_SOURCE_SHA256,
    R97_REVIEW_PACKET_SHA256,
    ConfigurationEpochComponent,
    ControllerConfigurationEpochIntakeError,
    ControllerConfigurationEpochIntakeV1,
    MeasuredConfigurationComponentV1,
    assess_controller_configuration_epoch_intake_v1,
    build_synthetic_controller_configuration_epoch_rehearsal_v1,
    parse_controller_configuration_epoch_intake_v1,
)
from rocell.application.installed_controller_qualification_v1 import (
    EvidenceOrigin,
    ReviewDisposition,
)
from rocell.application.r97_independent_review_decision_v1 import (
    R97_REVIEW_MANIFEST_SHA256,
    R97IndependentReviewDecisionV1,
    R97ReviewCheck,
    R97ReviewCheckResultV1,
    R97ReviewEvidenceOrigin,
)


ROOT = Path(__file__).resolve().parents[2]


def _decision(**changes):
    # Synthetic fixture only; never external review evidence.
    values = {
        "decision_id": "synthetic-test-decision",
        "reviewer_id": "synthetic-reviewer",
        "reviewer_affiliation": "test-fixture-only",
        "reviewer_attestation_sha256": "a" * 64,
        "review_started_utc": "2026-09-26T12:00:00Z",
        "review_completed_utc": "2026-09-26T12:30:00Z",
        "reviewed_packet_sha256": R97_REVIEW_PACKET_SHA256,
        "reviewed_manifest_sha256": R97_REVIEW_MANIFEST_SHA256,
        "reviewed_app_sha256": R97_APP_SHA256,
        "evidence_origin": R97ReviewEvidenceOrigin.EXTERNAL_INDEPENDENT,
        "reviewer_independence_asserted": True,
        "reviewer_was_implementation_author": False,
        "checks": tuple(
            R97ReviewCheckResultV1(check=item, passed=True)
            for item in R97ReviewCheck
        ),
        "findings": (),
        "disposition": ReviewDisposition.INDEPENDENTLY_APPROVED,
    }
    values.update(changes)
    return R97IndependentReviewDecisionV1(**values)


def _components(
    *,
    origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
    disposition=ReviewDisposition.INDEPENDENTLY_APPROVED,
    measured=100,
    valid_until=300,
):
    return tuple(
        MeasuredConfigurationComponentV1(
            component=ConfigurationEpochComponent(component),
            evidence_sha256=f"{index + 1:x}" * 64,
            independent_review_sha256=f"{index + 8:x}" * 64,
            measured_monotonic_ns=measured + index,
            valid_until_monotonic_ns=valid_until + index,
            evidence_origin=origin,
            review_disposition=disposition,
        )
        for index, component in enumerate(EXPECTED_COMPONENT_IDS)
    )


def _intake(**changes):
    values = {
        "epoch_id": "cell-a.epoch-1",
        "predecessor_configuration_epoch_sha256": None,
        "r97_review_packet_sha256": R97_REVIEW_PACKET_SHA256,
        "firmware_independent_review_sha256": _decision().decision_sha256,
        "firmware_review_disposition": ReviewDisposition.INDEPENDENTLY_APPROVED,
        "candidate_app_sha256": R97_APP_SHA256,
        "protocol_source_sha256": R97_PROTOCOL_SOURCE_SHA256,
        "joint_mapping_source_sha256": R97_JOINT_MAPPING_SOURCE_SHA256,
        "components": _components(),
    }
    values.update(changes)
    return ControllerConfigurationEpochIntakeV1(**values)


def _assess(intake, **changes):
    values = {
        "evaluated_monotonic_ns": 200,
        "firmware_review_decision": _decision(),
    }
    values.update(changes)
    return assess_controller_configuration_epoch_intake_v1(intake, **values)


def _schema(name):
    return json.loads((ROOT / "ai/schemas" / name).read_text(encoding="utf-8"))


def test_complete_intake_is_ready_only_for_epoch_bound_build_proposal():
    intake = _intake()
    report = _assess(intake)
    assert report.status == "READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL"
    assert report.blockers == ()
    assert report.configuration_epoch_sha256 == intake.configuration_epoch_sha256
    document = report.to_dict()
    assert document["epoch_bound_build_proposal_ready"] is True
    assert document["installation_authorized"] is False
    assert document["controller_start_authorized"] is False
    assert document["execution_authorized"] is False
    assert document["physical_authority"] is False
    jsonschema.Draft202012Validator(_schema(
        "controller_configuration_epoch_intake_v1.schema.json"
    )).validate(intake.to_dict())
    jsonschema.Draft202012Validator(_schema(
        "controller_configuration_epoch_intake_report_v1.schema.json"
    )).validate(document)


def test_epoch_digest_is_deterministic_and_changes_with_evidence():
    first = _intake()
    assert first.configuration_epoch_sha256 == _intake().configuration_epoch_sha256
    components = list(first.components)
    components[0] = replace(components[0], evidence_sha256="e" * 64)
    assert replace(first, components=tuple(components)).configuration_epoch_sha256 != (
        first.configuration_epoch_sha256)
    assert replace(
        first, predecessor_configuration_epoch_sha256="f" * 64
    ).configuration_epoch_sha256 != first.configuration_epoch_sha256


@pytest.mark.parametrize(
    "field, value, blocker",
    [
        ("firmware_review_disposition", ReviewDisposition.UNREVIEWED,
         "FIRMWARE_INDEPENDENT_REVIEW_INCOMPLETE"),
        ("r97_review_packet_sha256", "1" * 64, "REVIEW_PACKET_MISMATCH"),
        ("candidate_app_sha256", "2" * 64, "CANDIDATE_APP_MISMATCH"),
        ("protocol_source_sha256", "3" * 64, "PROTOCOL_SOURCE_MISMATCH"),
        ("joint_mapping_source_sha256", "4" * 64,
         "JOINT_MAPPING_SOURCE_MISMATCH"),
    ],
)
def test_release_identity_or_review_drift_blocks(field, value, blocker):
    report = _assess(_intake(**{field: value}))
    assert report.status == "BLOCKED"
    assert blocker in report.blockers


def test_synthetic_or_unreviewed_component_blocks():
    synthetic = _assess(
        _intake(components=_components(origin=EvidenceOrigin.SYNTHETIC_TEST_ONLY)),
    )
    unreviewed = _assess(
        _intake(components=_components(disposition=ReviewDisposition.UNREVIEWED)),
    )
    assert synthetic.blockers == ("COMPONENT_NOT_PHYSICAL_ORIGINAL",)
    assert unreviewed.blockers == (
        "COMPONENT_INDEPENDENT_REVIEW_INCOMPLETE",)


def test_future_or_stale_measurements_block():
    future = _assess(
        _intake(components=_components(measured=300, valid_until=500)),
    )
    stale = _assess(
        _intake(components=_components(measured=100, valid_until=150)),
    )
    assert future.blockers == ("EVALUATION_PREDATES_MEASUREMENT",)
    assert stale.blockers == ("MEASUREMENT_STALE",)


@pytest.mark.parametrize("components", [(), _components()[::-1], _components()[:-1]])
def test_component_membership_and_order_are_closed(components):
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="eight closed"):
        _intake(components=components)


def test_component_requires_expiry_after_measurement():
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="expiry"):
        replace(_components()[0], valid_until_monotonic_ns=100)


def test_schema_rejects_claimed_physical_authority():
    document = _intake().to_dict()
    document["installation_authorized"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(
            "controller_configuration_epoch_intake_v1.schema.json"
        )).validate(document)


def test_epoch_assessment_requires_full_review_decision():
    report = assess_controller_configuration_epoch_intake_v1(
        _intake(), evaluated_monotonic_ns=200)
    assert report.blockers == ("FIRMWARE_REVIEW_DECISION_MISSING",)


def test_epoch_assessment_rejects_decision_hash_or_disposition_mismatch():
    decision = _decision()
    hash_mismatch = _assess(
        _intake(firmware_independent_review_sha256="d" * 64),
        firmware_review_decision=decision,
    )
    disposition_mismatch = _assess(
        _intake(firmware_review_disposition=ReviewDisposition.REJECTED),
        firmware_review_decision=decision,
    )
    assert "FIRMWARE_REVIEW_DECISION_MISMATCH" in hash_mismatch.blockers
    assert "FIRMWARE_REVIEW_DECISION_MISMATCH" in disposition_mismatch.blockers


def test_epoch_assessment_rejects_blocked_decision():
    decision = _decision(reviewer_independence_asserted=False)
    intake = _intake(
        firmware_independent_review_sha256=decision.decision_sha256)
    report = _assess(intake, firmware_review_decision=decision)
    assert report.blockers == ("FIRMWARE_REVIEW_DECISION_BLOCKED",)


def test_epoch_assessment_never_promotes_synthetic_review():
    decision = _decision(
        evidence_origin=R97ReviewEvidenceOrigin.SYNTHETIC_TEST_ONLY)
    intake = _intake(
        firmware_independent_review_sha256=decision.decision_sha256)
    report = _assess(intake, firmware_review_decision=decision)
    assert report.status == "BLOCKED"
    assert report.blockers == ("FIRMWARE_REVIEW_DECISION_BLOCKED",)
    assert report.to_dict()["epoch_bound_build_proposal_ready"] is False


def test_epoch_assessment_requires_typed_review_decision():
    with pytest.raises(TypeError, match="R97IndependentReviewDecisionV1"):
        _assess(_intake(), firmware_review_decision={})


def test_epoch_json_round_trip_is_strict_and_hash_bound():
    original = _intake()
    parsed = parse_controller_configuration_epoch_intake_v1(original.to_dict())
    assert parsed == original
    tampered = original.to_dict()
    tampered["epoch_id"] = "changed-after-hashing"
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="hash"):
        parse_controller_configuration_epoch_intake_v1(tampered)
    extra = original.to_dict()
    extra["unexpected"] = True
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="closed fields"):
        parse_controller_configuration_epoch_intake_v1(extra)


def test_synthetic_epoch_rehearsal_is_deterministic_and_production_blocked():
    decision = _decision(
        evidence_origin=R97ReviewEvidenceOrigin.SYNTHETIC_TEST_ONLY)
    first, first_report = build_synthetic_controller_configuration_epoch_rehearsal_v1(
        rehearsal_id="arm-037",
        firmware_review_decision=decision,
        measured_monotonic_ns=100,
        valid_until_monotonic_ns=300,
        evaluated_monotonic_ns=200,
    )
    second, second_report = build_synthetic_controller_configuration_epoch_rehearsal_v1(
        rehearsal_id="arm-037",
        firmware_review_decision=decision,
        measured_monotonic_ns=100,
        valid_until_monotonic_ns=300,
        evaluated_monotonic_ns=200,
    )
    assert first.configuration_epoch_sha256 == second.configuration_epoch_sha256
    assert first_report.report_sha256 == second_report.report_sha256
    assert all(
        item.evidence_origin is EvidenceOrigin.SYNTHETIC_TEST_ONLY
        for item in first.components
    )
    assert first_report.status == "BLOCKED"
    assert first_report.blockers == (
        "FIRMWARE_REVIEW_DECISION_BLOCKED",
        "COMPONENT_NOT_PHYSICAL_ORIGINAL",
    )
    assert first_report.to_dict()["epoch_bound_build_proposal_ready"] is False
    assert parse_controller_configuration_epoch_intake_v1(
        first.to_dict()).configuration_epoch_sha256 == first.configuration_epoch_sha256
    jsonschema.Draft202012Validator(_schema(
        "controller_configuration_epoch_intake_v1.schema.json"
    )).validate(first.to_dict())
    jsonschema.Draft202012Validator(_schema(
        "controller_configuration_epoch_intake_report_v1.schema.json"
    )).validate(first_report.to_dict())


def test_synthetic_epoch_rehearsal_rejects_external_review_or_bad_window():
    with pytest.raises(
        ControllerConfigurationEpochIntakeError,
        match="requires synthetic review",
    ):
        build_synthetic_controller_configuration_epoch_rehearsal_v1(
            rehearsal_id="arm-037",
            firmware_review_decision=_decision(),
            measured_monotonic_ns=100,
            valid_until_monotonic_ns=300,
            evaluated_monotonic_ns=200,
        )
    decision = _decision(
        evidence_origin=R97ReviewEvidenceOrigin.SYNTHETIC_TEST_ONLY)
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="window"):
        build_synthetic_controller_configuration_epoch_rehearsal_v1(
            rehearsal_id="arm-037",
            firmware_review_decision=decision,
            measured_monotonic_ns=100,
            valid_until_monotonic_ns=150,
            evaluated_monotonic_ns=200,
        )
