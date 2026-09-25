from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from typing import Mapping, cast

import pytest

from rocell.application.physical_onboarding import (
    STAGE_PLAN_SHA256,
    PhysicalOnboardingStage,
)
from rocell.application.physical_onboarding_receipts import (
    CAMERA_RECEIPT_INSPECTION_SCHEMA,
    FIRST_POWER_OBSERVATION_SCHEMA,
    POWER_SAFETY_REVIEW_SCHEMA,
    BoundEvidence,
    CameraReceiptInspection,
    ControlledOperatorDecision,
    DiagnosticDisposition,
    DiagnosticReadinessAssessment,
    EffectCertainty,
    EstopReviewStatus,
    FirstPowerObservation,
    FirstPowerOutcome,
    InspectionCondition,
    OperatorDecisionKind,
    PhysicalOnboardingReceiptError,
    PowerSafetyReview,
    ReceiptBinding,
    ReviewedPowerState,
    StartupMotionClassification,
    ZERO_PHYSICAL_AUTHORITY,
    assess_camera_receipt,
    assess_first_power_observation,
    assess_operator_decision,
    assess_power_safety,
    canonical_sha256,
    parse_receipt_json,
    receipt_json_bytes,
)


SOURCE = "1" * 64
HEADER = "2" * 64
START = 10_000_000


def _binding(stage: PhysicalOnboardingStage, count: int = 2) -> ReceiptBinding:
    evidence = tuple(
        BoundEvidence(
            evidence_id=f"evidence-{index}",
            stage=stage,
            package_sha256=f"{index + 1:x}" * 64,
            manifest_sha256=f"{index + 3:x}" * 64,
            payload_sha256=f"{index + 5:x}" * 64,
            payload_bytes=100 + index,
        )
        for index in range(count)
    )
    return ReceiptBinding(
        source_binding_sha256=SOURCE,
        session_header_sha256=HEADER,
        session_id="arrival-001",
        cell_id="cell-a",
        stage=stage,
        evidence=evidence,
    )


def _camera(**changes: object) -> CameraReceiptInspection:
    values: dict[str, object] = {
        "binding": _binding(PhysicalOnboardingStage.CAMERA_RECEIPT),
        "operator_id": "operator-a",
        "observed_at_ns": START,
        "observed_manufacturer": "Arducam",
        "observed_product_id": "B0477",
        "observed_camera_serial": "camera-serial-a",
        "observed_lens_focal_length_mm": 16,
        "body_condition": InspectionCondition.ACCEPTABLE,
        "lens_condition": InspectionCondition.ACCEPTABLE,
        "connector_condition": InspectionCondition.ACCEPTABLE,
        "identity_label_legible": True,
        "purchase_record_matches": True,
        "package_contents_complete": True,
        "inspection_uncertain": False,
        "purchase_record_evidence_id": "evidence-0",
        "inspection_image_evidence_ids": ("evidence-1",),
    }
    values.update(changes)
    return CameraReceiptInspection(**values)  # type: ignore[arg-type]


def _power_safety(**changes: object) -> PowerSafetyReview:
    values: dict[str, object] = {
        "binding": _binding(PhysicalOnboardingStage.POWER_SAFETY),
        "operator_id": "operator-a",
        "reviewed_at_ns": START,
        "arm_power_state": ReviewedPowerState.DISCONNECTED_CONFIRMED,
        "estop_status": EstopReviewStatus.POWER_OFF_CONTINUITY_VERIFIED,
        "power_supply_output_mv": 12_000,
        "power_supply_current_ma": 5_000,
        "polarity_verified": True,
        "arm_base_secured": True,
        "camera_structure_secured": True,
        "placemat_secured": True,
        "cables_restrained": True,
        "keepout_zone_clear": True,
        "emergency_disconnect_reachable": True,
        "tool_clear_of_keyboard_and_phone": True,
        "energization_occurred_during_review": False,
        "motion_observed_during_review": False,
        "contact_occurred_during_review": False,
        "review_uncertain": False,
        "estop_test_evidence_id": "evidence-0",
        "wiring_image_evidence_ids": ("evidence-1",),
    }
    values.update(changes)
    return PowerSafetyReview(**values)  # type: ignore[arg-type]


def _first_power(**changes: object) -> FirstPowerObservation:
    values: dict[str, object] = {
        "binding": _binding(PhysicalOnboardingStage.POWER_ON_OBSERVATION),
        "event_id": "first-power-001",
        "operator_id": "operator-a",
        "observer_id": "observer-a",
        "observed_at_ns": START,
        "event_started_monotonic_ns": START + 10,
        "event_ended_monotonic_ns": START + 100,
        "pre_event_power_state": ReviewedPowerState.DISCONNECTED_CONFIRMED,
        "post_event_power_state": ReviewedPowerState.DISCONNECTED_CONFIRMED,
        "outcome": FirstPowerOutcome.COMPLETED_OBSERVATION,
        "effect_certainty": EffectCertainty.CONFIRMED,
        "startup_motion": StartupMotionClassification.EXPECTED_AUTOMATIC_REPOSITIONING,
        "attempt_count": 1,
        "automatic_retry_count": 0,
        "startup_movement_warning_acknowledged": True,
        "exclusion_zone_clear_before_event": True,
        "estop_operator_ready_before_event": True,
        "continuous_line_of_sight": True,
        "controller_boot_observed": True,
        "clearance_preserved": True,
        "estop_activated": False,
        "collision_observed": False,
        "contact_observed": False,
        "abnormal_condition_observed": False,
        "observation_media_evidence_ids": ("evidence-0", "evidence-1"),
    }
    values.update(changes)
    return FirstPowerObservation(**values)  # type: ignore[arg-type]


def _decision(
    subject: CameraReceiptInspection | PowerSafetyReview | FirstPowerObservation,
    *,
    decision: OperatorDecisionKind = OperatorDecisionKind.ACKNOWLEDGE_DIAGNOSTIC_READINESS,
    subject_disposition: DiagnosticDisposition | None = None,
) -> ControlledOperatorDecision:
    if isinstance(subject, CameraReceiptInspection):
        assessment = assess_camera_receipt(subject)
    elif isinstance(subject, PowerSafetyReview):
        assessment = assess_power_safety(subject)
    else:
        assessment = assess_first_power_observation(subject)
    return ControlledOperatorDecision(
        binding=subject.binding,
        reviewer_id="reviewer-a",
        decided_at_ns=START + 1_000,
        decision=decision,
        subject_schema=subject.schema,
        subject_receipt_sha256=subject.receipt_sha256,
        subject_assessment_sha256=assessment.assessment_sha256,
        subject_disposition=subject_disposition or assessment.disposition,
        reason_codes=("REVIEW_COMPLETED",),
        decision_evidence_id="evidence-0",
    )


def _assert_zero_authority(document: dict[str, object]) -> None:
    authority = document["authority"]
    assert authority == ZERO_PHYSICAL_AUTHORITY.to_dict()
    assert isinstance(authority, dict)
    assert authority["power_authorized"] is False
    assert authority["motion_authorized"] is False
    assert authority["contact_authorized"] is False
    assert authority["physical_release_effect"] == "NONE"
    assert authority["session_mutation_effect"] == "NONE"


def test_camera_receipt_is_exactly_bound_and_only_diagnostically_ready() -> None:
    receipt = _camera()
    assessment = assess_camera_receipt(receipt)

    binding = receipt.to_dict()["binding"]
    assert isinstance(binding, dict)
    assert binding["source_binding_sha256"] == SOURCE
    assert binding["session_header_sha256"] == HEADER
    assert binding["stage_plan_sha256"] == STAGE_PLAN_SHA256
    assert binding["stage"] == "camera_receipt"
    assert len(binding["evidence"]) == 2
    assert assessment.disposition is DiagnosticDisposition.DIAGNOSTIC_READY
    assert assessment.diagnostic_ready is True
    assert assessment.hold_required is False
    _assert_zero_authority(receipt.to_dict())
    _assert_zero_authority(assessment.to_dict())


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"observed_product_id": "not-b0477"}, "CAMERA_PRODUCT_ID_MISMATCH"),
        ({"observed_lens_focal_length_mm": 6}, "CAMERA_LENS_FOCAL_LENGTH_MISMATCH"),
        (
            {"body_condition": InspectionCondition.DAMAGED},
            "CAMERA_OR_LENS_DAMAGE_OBSERVED",
        ),
        ({"purchase_record_matches": False}, "CAMERA_PURCHASE_RECORD_MISMATCH"),
    ],
)
def test_camera_mismatch_or_damage_is_hold(
    changes: dict[str, object], reason: str
) -> None:
    assessment = assess_camera_receipt(_camera(**changes))
    assert assessment.disposition is DiagnosticDisposition.HOLD
    assert assessment.diagnostic_ready is False
    assert reason in assessment.reason_codes


def test_passive_camera_uncertainty_is_hold_not_side_effect_uncertainty() -> None:
    assessment = assess_camera_receipt(_camera(inspection_uncertain=True))
    assert assessment.disposition is DiagnosticDisposition.HOLD
    assert assessment.side_effect_uncertain is False


def test_power_safety_ready_still_does_not_authorize_energization() -> None:
    receipt = _power_safety()
    assessment = assess_power_safety(receipt)
    assert assessment.disposition is DiagnosticDisposition.DIAGNOSTIC_READY
    assert assessment.to_dict()["subject_schema"] == POWER_SAFETY_REVIEW_SCHEMA
    _assert_zero_authority(receipt.to_dict())
    _assert_zero_authority(assessment.to_dict())


def test_power_safety_review_holds_on_wrong_supply_or_any_unplanned_effect() -> None:
    receipt = _power_safety(
        power_supply_output_mv=24_000,
        energization_occurred_during_review=True,
        motion_observed_during_review=True,
    )
    assessment = assess_power_safety(receipt)
    assert assessment.disposition is DiagnosticDisposition.HOLD
    assert {
        "POWER_SUPPLY_OUTPUT_NOT_12000_MV",
        "UNPLANNED_ENERGIZATION_DURING_POWER_OFF_REVIEW",
        "MOTION_DURING_POWER_OFF_REVIEW",
    }.issubset(assessment.reason_codes)


def test_first_power_explicitly_records_possible_startup_motion_without_authority() -> (
    None
):
    receipt = _first_power()
    assessment = assess_first_power_observation(receipt)
    assert (
        receipt.startup_motion
        is StartupMotionClassification.EXPECTED_AUTOMATIC_REPOSITIONING
    )
    assert assessment.disposition is DiagnosticDisposition.DIAGNOSTIC_READY
    assert (
        "FIRST_POWER_EXPECTED_STARTUP_MOTION_SAFELY_OBSERVED" in assessment.reason_codes
    )
    _assert_zero_authority(receipt.to_dict())
    _assert_zero_authority(assessment.to_dict())


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"automatic_retry_count": 1}, "FIRST_POWER_AUTOMATIC_RETRY_FORBIDDEN"),
        (
            {"startup_motion": StartupMotionClassification.UNEXPECTED_OR_UNBOUNDED},
            "UNEXPECTED_OR_UNBOUNDED_STARTUP_MOTION",
        ),
        ({"contact_observed": True}, "CONTACT_DURING_FIRST_POWER"),
        (
            {"post_event_power_state": ReviewedPowerState.CONNECTED},
            "FIRST_POWER_POSTSTATE_NOT_DISCONNECTED",
        ),
    ],
)
def test_first_power_known_deviation_is_hold(
    changes: dict[str, object], reason: str
) -> None:
    assessment = assess_first_power_observation(_first_power(**changes))
    assert assessment.disposition is DiagnosticDisposition.HOLD
    assert reason in assessment.reason_codes


def test_first_power_unknown_effect_is_distinct_terminal_uncertainty() -> None:
    receipt = _first_power(
        effect_certainty=EffectCertainty.UNCERTAIN,
        outcome=FirstPowerOutcome.EFFECT_UNCERTAIN,
        startup_motion=StartupMotionClassification.UNKNOWN,
        post_event_power_state=ReviewedPowerState.UNKNOWN,
    )
    assessment = assess_first_power_observation(receipt)
    assert assessment.disposition is DiagnosticDisposition.SIDE_EFFECT_UNCERTAIN
    assert assessment.side_effect_uncertain is True
    assert assessment.hold_required is True
    _assert_zero_authority(assessment.to_dict())


def test_first_power_rejects_ambiguous_event_timing() -> None:
    with pytest.raises(PhysicalOnboardingReceiptError, match="end must be after"):
        _first_power(
            event_started_monotonic_ns=START + 100,
            event_ended_monotonic_ns=START + 100,
        )


def test_operator_acknowledgement_cannot_upgrade_subject_hold() -> None:
    subject = _camera(observed_product_id="wrong-camera")
    assessment = assess_camera_receipt(subject)
    decision = _decision(subject)
    result = assess_operator_decision(decision, subject, assessment)

    assert assessment.disposition is DiagnosticDisposition.HOLD
    assert result.disposition is DiagnosticDisposition.HOLD
    assert "OPERATOR_CANNOT_UPGRADE_SUBJECT_ASSESSMENT" in result.reason_codes
    _assert_zero_authority(decision.to_dict())
    _assert_zero_authority(result.to_dict())


def test_generic_diagnostic_ready_assessment_cannot_be_constructed() -> None:
    subject = _camera()
    with pytest.raises(PhysicalOnboardingReceiptError, match="stage-specific assessor"):
        DiagnosticReadinessAssessment(
            binding=subject.binding,
            subject_schema=subject.schema,
            subject_receipt_sha256=subject.receipt_sha256,
            disposition=DiagnosticDisposition.DIAGNOSTIC_READY,
            reason_codes=("FABRICATED_READY",),
            _factory_token=object(),
        )


def test_operator_can_add_hold_to_ready_assessment_but_not_release() -> None:
    subject = _power_safety()
    assessment = assess_power_safety(subject)
    decision = _decision(subject, decision=OperatorDecisionKind.PLACE_HOLD)
    result = assess_operator_decision(decision, subject, assessment)
    assert assessment.disposition is DiagnosticDisposition.DIAGNOSTIC_READY
    assert result.disposition is DiagnosticDisposition.HOLD
    assert "OPERATOR_PLACED_HOLD" in result.reason_codes


def test_controlled_operator_decision_has_strict_canonical_round_trip() -> None:
    subject = _first_power()
    decision = _decision(subject)
    parsed = parse_receipt_json(receipt_json_bytes(decision))
    assert parsed == decision
    assert parsed.receipt_sha256 == decision.receipt_sha256


def test_side_effect_escalation_is_limited_to_first_power() -> None:
    with pytest.raises(PhysicalOnboardingReceiptError, match="limited to first power"):
        _decision(
            _camera(),
            decision=OperatorDecisionKind.ESCALATE_SIDE_EFFECT_UNCERTAINTY,
        )

    subject = _first_power()
    assessment = assess_first_power_observation(subject)
    decision = _decision(
        subject,
        decision=OperatorDecisionKind.ESCALATE_SIDE_EFFECT_UNCERTAINTY,
    )
    result = assess_operator_decision(decision, subject, assessment)
    assert result.disposition is DiagnosticDisposition.SIDE_EFFECT_UNCERTAIN


def test_operator_decision_rejects_subject_or_assessment_binding_drift() -> None:
    subject = _camera()
    assessment = assess_camera_receipt(subject)
    decision = _decision(subject)
    drifted = replace(decision, subject_assessment_sha256="f" * 64)
    with pytest.raises(PhysicalOnboardingReceiptError, match="not exactly bound"):
        assess_operator_decision(drifted, subject, assessment)


@pytest.mark.parametrize("receipt", [_camera(), _power_safety(), _first_power()])
def test_canonical_receipt_round_trip_and_hash_stability(
    receipt: CameraReceiptInspection | PowerSafetyReview | FirstPowerObservation,
) -> None:
    payload = receipt_json_bytes(receipt)
    parsed = parse_receipt_json(payload)
    assert parsed == receipt
    assert parsed.receipt_sha256 == receipt.receipt_sha256
    assert canonical_sha256(receipt.core_dict()) == receipt.receipt_sha256


def test_parser_rejects_extra_duplicate_float_nonfinite_noncanonical_and_tamper() -> (
    None
):
    receipt = _camera()
    document = receipt.to_dict()

    extra = dict(document)
    extra["unexpected"] = False
    with pytest.raises(PhysicalOnboardingReceiptError, match="fields differ"):
        parse_receipt_json(
            (json.dumps(extra, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )

    duplicate = receipt_json_bytes(receipt).replace(
        b'  "schema":', b'  "schema": "duplicate",\n  "schema":', 1
    )
    with pytest.raises(PhysicalOnboardingReceiptError, match="duplicate JSON key"):
        parse_receipt_json(duplicate)

    floating = receipt_json_bytes(receipt).replace(
        b'  "observed_at_ns": 10000000,', b'  "observed_at_ns": 1.5,', 1
    )
    with pytest.raises(PhysicalOnboardingReceiptError, match="float"):
        parse_receipt_json(floating)

    nonfinite = receipt_json_bytes(receipt).replace(
        b'  "observed_at_ns": 10000000,', b'  "observed_at_ns": NaN,', 1
    )
    with pytest.raises(PhysicalOnboardingReceiptError, match="nonfinite"):
        parse_receipt_json(nonfinite)

    compact = json.dumps(document, sort_keys=True).encode("utf-8")
    with pytest.raises(PhysicalOnboardingReceiptError, match="not canonical"):
        parse_receipt_json(compact)

    tampered = dict(document)
    tampered["observed_product_id"] = "B0000"
    with pytest.raises(PhysicalOnboardingReceiptError, match="hash mismatch"):
        parse_receipt_json(
            (json.dumps(tampered, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )


def test_binding_rejects_wrong_stage_evidence_unbound_evidence_and_plan_drift() -> None:
    camera_binding = _binding(PhysicalOnboardingStage.CAMERA_RECEIPT)
    wrong = BoundEvidence(
        evidence_id="evidence-x",
        stage=PhysicalOnboardingStage.POWER_SAFETY,
        package_sha256="a" * 64,
        manifest_sha256="b" * 64,
        payload_sha256="c" * 64,
        payload_bytes=1,
    )
    with pytest.raises(PhysicalOnboardingReceiptError, match="receipt stage"):
        ReceiptBinding(
            source_binding_sha256=SOURCE,
            session_header_sha256=HEADER,
            session_id="arrival-001",
            cell_id="cell-a",
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
            evidence=(wrong,),
        )
    with pytest.raises(PhysicalOnboardingReceiptError, match="outside"):
        _camera(
            binding=camera_binding,
            purchase_record_evidence_id="not-bound",
        )
    with pytest.raises(PhysicalOnboardingReceiptError, match="stage-plan"):
        replace(camera_binding, stage_plan_sha256="0" * 64)

    duplicate = replace(
        camera_binding.evidence[0],
        payload_sha256="d" * 64,
    )
    with pytest.raises(PhysicalOnboardingReceiptError, match="duplicates"):
        replace(camera_binding, evidence=(camera_binding.evidence[0], duplicate))


def test_authority_tamper_and_dataclass_mutation_are_rejected() -> None:
    receipt = _first_power()
    document = receipt.to_dict()
    authority = dict(cast(Mapping[str, object], document["authority"]))
    authority["power_authorized"] = True
    document["authority"] = authority
    with pytest.raises(PhysicalOnboardingReceiptError, match="authority"):
        parse_receipt_json(
            (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    with pytest.raises(FrozenInstanceError):
        receipt.attempt_count = 2  # type: ignore[misc]


def test_schema_is_stage_specific_not_interchangeable() -> None:
    camera = _camera()
    document = camera.to_dict()
    document["schema"] = FIRST_POWER_OBSERVATION_SCHEMA
    with pytest.raises(PhysicalOnboardingReceiptError, match="fields differ"):
        parse_receipt_json(
            (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    assert camera.schema == CAMERA_RECEIPT_INSPECTION_SCHEMA
