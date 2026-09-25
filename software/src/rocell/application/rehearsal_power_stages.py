"""Closed synthetic power-ceremony checks, with no energy-control capability.

Evaluation invokes the real typed receipt assessors. Verification checks only
retained bytes, typed inputs and a finite expected-case table; it neither repeats
an observation nor calls an assessor. The caller authenticates the expected M1
binding and evidence digest. Neither operation publishes a receipt or permit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from rocell.application import physical_onboarding_receipts as receipts
from rocell.application.physical_onboarding import (
    STAGE_PLAN_SHA256,
    PhysicalOnboardingStage,
)


SCHEMA = "rocell.rehearsal_power_stage.v1"
EVALUATOR_ID = "SYNTHETIC_TYPED_POWER_CEREMONY_V1"
MAX_EVIDENCE_BYTES = 96 * 1024
MAX_SEQUENCE = 1_000_000
_MAX_SOURCE_BYTES = 2 * 1024 * 1024
_STAGES = ("power_safety", "power_on_observation")
_HEX = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,95}")
_SOURCE_PATHS = (
    "software/src/rocell/application/rehearsal_power_stages.py",
    "software/src/rocell/application/physical_onboarding_receipts.py",
    "software/src/rocell/application/physical_onboarding.py",
)
_EFFECTS = {
    "device_enumerations": 0,
    "device_opens": 0,
    "hardware_commands": 0,
    "power_events": 0,
    "motion_commands": 0,
    "contact_commands": 0,
    "physical_receipts_published": 0,
    "permits_published": 0,
}
_AUTHORITY = {
    "composition": "HARDWARE_INCAPABLE_REHEARSAL",
    "physical_authority": False,
    "stage_advance_authority": False,
    "physical_release_effect": "NONE",
    "actual_physical_effects": _EFFECTS,
}
_MEANING = (
    "Synthetic typed-assessor checks only. No installed safety, actual power "
    "state, startup trajectory, controller connection or physical readiness "
    "is established; no energization, motion, contact or permit is authorized."
)


class RehearsalPowerError(ValueError):
    """Invalid, oversized, inconsistent or incorrectly bound retained evidence."""


def _digest(value: object) -> str:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise RehearsalPowerError("expected a lowercase SHA-256 digest")
    return value


def _integer(value: object, maximum: int = MAX_SEQUENCE) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise RehearsalPowerError("integer is outside its bound")
    return value


def _object(value: object, keys: set[str] | None = None) -> dict[str, Any]:
    if type(value) is not dict or (keys is not None and set(value) != keys):
        raise RehearsalPowerError("object has missing or unknown fields")
    return value


def _tree(value: object, depth: int = 0) -> None:
    if depth > 20:
        raise RehearsalPowerError("report nesting exceeds the bound")
    if type(value) is dict:
        if len(value) > 64 or any(
            type(key) is not str or len(key) > 256 for key in value
        ):
            raise RehearsalPowerError("invalid object keys/count")
        for item in value.values():
            _tree(item, depth + 1)
    elif type(value) is list:
        if len(value) > 64:
            raise RehearsalPowerError("array exceeds the bound")
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is str:
        if len(value) > 2048:
            raise RehearsalPowerError("text exceeds the bound")
    elif type(value) is int:
        if not -(2**63) < value < 2**63:
            raise RehearsalPowerError("integer exceeds the bound")
    elif value is not None and type(value) is not bool:
        raise RehearsalPowerError("unsupported JSON value; floats are forbidden")


def _canonical(value: object) -> bytes:
    _tree(value)
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise RehearsalPowerError("invalid JSON encoding") from error
    if len(encoded) > MAX_EVIDENCE_BYTES:
        raise RehearsalPowerError("power evidence exceeds the 96 KiB bound")
    return encoded


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _same(actual: object, expected: object, label: str) -> None:
    # Unlike dict equality, canonical equality never confuses false/0 or true/1.
    if _canonical(actual) != _canonical(expected):
        raise RehearsalPowerError(f"{label} mismatch")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RehearsalPowerError("duplicate JSON key")
        result[key] = value
    return result


def _reject_numeric(value: str) -> None:
    raise RehearsalPowerError("JSON floats/nonfinite constants are forbidden")


def _decode(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        raise RehearsalPowerError("evidence must be nonempty bounded bytes")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_float=_reject_numeric,
            parse_constant=_reject_numeric,
        )
        _tree(document)
        return _object(document)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise RehearsalPowerError("invalid bounded power evidence JSON") from error


@dataclass(frozen=True, slots=True)
class RehearsalPowerBinding:
    """Server-pinned dependencies, never browser-authored authority fields.

    The predecessor trio hashes complete canonical M1 evidence payloads, not an
    embedded assessment's self-hash. Arm identity names the stage-9 evaluation.
    The caller verifies stage-9 PASS for stage 10, or stage-10 PASS for stage 11.
    """

    workspace_source_sha256: str
    catalog_sha256: str
    cell_id: str
    session_id: str
    operator_id: str
    stage: str
    predecessor_receipt_sha256: str
    predecessor_assessment_sha256: str
    predecessor_review_sha256: str
    arm_identity_evidence_sha256: str

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if key in {"cell_id", "session_id", "operator_id"}:
                if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
                    raise RehearsalPowerError(f"invalid {key}")
            elif key == "stage":
                if type(value) is not str or value not in _STAGES:
                    raise RehearsalPowerError("unsupported power stage")
            else:
                _digest(value)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RehearsalPowerEvidence:
    """Immutable canonical bytes; nested reports returned to callers are copies."""

    _payload: bytes

    @property
    def outcome(self) -> str:
        return str(self.to_dict()["outcome"])

    @property
    def checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.to_dict()["checks"])

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    @property
    def evaluation_sha256(self) -> str:
        """Projection alias; deliberately not a self-referential payload field."""
        return self.evidence_sha256

    def canonical_bytes(self) -> bytes:
        return self._payload

    def to_dict(self) -> dict[str, Any]:
        return _decode(self._payload)


def _provenance(stage: str) -> dict[str, Any]:
    return {
        "kind": "SYNTHETIC_TYPED_ASSESSOR_REHEARSAL",
        "composition": "HARDWARE_INCAPABLE_REHEARSAL",
        "input_origin": "CLOSED_SYNTHETIC_FIXTURE",
        "assessor_module": "rocell.application.physical_onboarding_receipts",
        "assessor_function": (
            "assess_power_safety"
            if stage == "power_safety"
            else "assess_first_power_observation"
        ),
        "physical_observations": False,
        "inner_receipt_role": "ASSESSOR_FIXTURE_NOT_PHYSICAL_M1_EVIDENCE",
        "evidence_media_role": "SYNTHETIC_TEXT_NOT_INSPECTION_IMAGE_OR_VIDEO",
        "startup_motion_role": "PROCEDURAL_TEST_INPUT_NOT_PREDICTED_TRAJECTORY",
        "timestamps_role": "DETERMINISTIC_SYNTHETIC_VALUES_NOT_WALL_CLOCK",
    }


def _fixture_material(
    binding: RehearsalPowerBinding, sequence: int
) -> tuple[receipts.ReceiptBinding, list[dict[str, Any]]]:
    """Bind retained small text artifacts, without impersonating an M1 package.

    Package/manifest values below are explicitly synthetic fixture digests. All
    their constituent documents are retained and checked; no external media is
    read, and none of these legacy receipt shapes is published independently.
    """
    stage = PhysicalOnboardingStage(binding.stage)
    fixture_source = _hash(
        {
            "schema": "rocell.synthetic_power_fixture_source.v1",
            "composition": "HARDWARE_INCAPABLE_REHEARSAL",
            "binding": binding.to_dict(),
            "sequence": sequence,
        }
    )
    fixture_header = _hash(
        {
            "schema": "rocell.synthetic_power_fixture_header.v1",
            "fixture_source_sha256": fixture_source,
            "purpose": "ASSESSOR_INPUT_ONLY_NOT_M1_SESSION",
        }
    )
    materials: list[dict[str, Any]] = []
    evidence: list[receipts.BoundEvidence] = []
    for evidence_id in ("synthetic-procedure", "synthetic-supporting-media"):
        payload = {
            "schema": "rocell.synthetic_power_fixture_material.v1",
            "evidence_id": evidence_id,
            "fixture_source_sha256": fixture_source,
            "stage": stage.value,
            "physical_observation": False,
            "meaning": "Retained synthetic text; no physical inspection or event.",
        }
        payload_bytes = _canonical(payload)
        manifest = {
            "schema": "rocell.synthetic_power_fixture_manifest.v1",
            "evidence_id": evidence_id,
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "payload_bytes": len(payload_bytes),
        }
        package = {
            "schema": "rocell.synthetic_power_fixture_package.v1",
            "manifest_sha256": _hash(manifest),
            "payload_sha256": _hash(payload),
            "purpose": "NOT_AN_M1_EVIDENCE_PACKAGE",
        }
        evidence.append(
            receipts.BoundEvidence(
                evidence_id=evidence_id,
                stage=stage,
                package_sha256=_hash(package),
                manifest_sha256=_hash(manifest),
                payload_sha256=_hash(payload),
                payload_bytes=len(payload_bytes),
            )
        )
        materials.append({"payload": payload, "manifest": manifest, "package": package})
    return (
        receipts.ReceiptBinding(
            source_binding_sha256=fixture_source,
            session_header_sha256=fixture_header,
            session_id="synthetic-" + fixture_header[:32],
            cell_id="synthetic-" + fixture_source[:24],
            stage=stage,
            evidence=tuple(evidence),
        ),
        materials,
    )


@dataclass(frozen=True, slots=True)
class _Case:
    check_id: str
    kind: str
    subject: receipts.PowerSafetyReview | receipts.FirstPowerObservation
    disposition: str
    reasons: tuple[str, ...]
    meaning: str


def _cases(binding: RehearsalPowerBinding, sequence: int) -> tuple[_Case, ...]:
    """Finite typed fixtures and independently stated expected outcomes.

    This is deliberately not a general replacement safety assessor. Every
    retained subject must exactly match one closed fixture. A new production
    assessor policy requires a reviewed fixture/table and source-binding change.
    """
    legacy, _ = _fixture_material(binding, sequence)
    timestamp = 1_000_000 + sequence * 1000
    ready = receipts.DiagnosticDisposition.DIAGNOSTIC_READY.value
    hold = receipts.DiagnosticDisposition.HOLD.value
    uncertain = receipts.DiagnosticDisposition.SIDE_EFFECT_UNCERTAIN.value
    nominal: receipts.PowerSafetyReview | receipts.FirstPowerObservation
    specifications: tuple[
        tuple[str, str, dict[str, Any], str, tuple[str, ...], str], ...
    ]
    if binding.stage == "power_safety":
        nominal = receipts.PowerSafetyReview(
            binding=legacy,
            operator_id="synthetic-operator",
            reviewed_at_ns=timestamp,
            arm_power_state=receipts.ReviewedPowerState.DISCONNECTED_CONFIRMED,
            estop_status=receipts.EstopReviewStatus.POWER_OFF_CONTINUITY_VERIFIED,
            power_supply_output_mv=12000,
            power_supply_current_ma=5000,
            polarity_verified=True,
            arm_base_secured=True,
            camera_structure_secured=True,
            placemat_secured=True,
            cables_restrained=True,
            keepout_zone_clear=True,
            emergency_disconnect_reachable=True,
            tool_clear_of_keyboard_and_phone=True,
            energization_occurred_during_review=False,
            motion_observed_during_review=False,
            contact_occurred_during_review=False,
            review_uncertain=False,
            estop_test_evidence_id="synthetic-procedure",
            wiring_image_evidence_ids=("synthetic-supporting-media",),
        )
        specifications = (
            (
                "nominal_power_off_review",
                "NOMINAL",
                {},
                ready,
                ("POWER_OFF_SAFETY_REVIEW_DIAGNOSTICALLY_READY",),
                "Complete synthetic power-off input is diagnostically ready only.",
            ),
            (
                "unknown_power_state",
                "EXPECTED_FAULT",
                {"arm_power_state": receipts.ReviewedPowerState.UNKNOWN},
                hold,
                ("POWER_SAFETY_REVIEW_UNCERTAIN",),
                "Unknown synthetic power state must hold the power-off review.",
            ),
            (
                "uncertain_review",
                "EXPECTED_FAULT",
                {"review_uncertain": True},
                hold,
                ("POWER_SAFETY_REVIEW_UNCERTAIN",),
                "An uncertain review must hold.",
            ),
            (
                "power_not_disconnected",
                "EXPECTED_FAULT",
                {"arm_power_state": receipts.ReviewedPowerState.CONNECTED},
                hold,
                ("ARM_POWER_NOT_DISCONNECTED_FOR_REVIEW",),
                "A connected-state fixture cannot satisfy a power-off review.",
            ),
            (
                "missing_stop_verification",
                "EXPECTED_FAULT",
                {"estop_status": receipts.EstopReviewStatus.NOT_VERIFIED},
                hold,
                ("ESTOP_NOT_VERIFIED",),
                "An unverified independent stop must hold.",
            ),
            (
                "wrong_supply",
                "EXPECTED_FAULT",
                {"power_supply_output_mv": 9000, "power_supply_current_ma": 4000},
                hold,
                (
                    "POWER_SUPPLY_CURRENT_BELOW_5000_MA",
                    "POWER_SUPPLY_OUTPUT_NOT_12000_MV",
                ),
                "Synthetic supply values outside the existing 12 V / 5 A contract hold.",
            ),
            (
                "polarity_not_verified",
                "EXPECTED_FAULT",
                {"polarity_verified": False},
                hold,
                ("POLARITY_NOT_VERIFIED",),
                "Missing polarity verification holds.",
            ),
            (
                "unsecured_structures",
                "EXPECTED_FAULT",
                {
                    "arm_base_secured": False,
                    "camera_structure_secured": False,
                    "placemat_secured": False,
                },
                hold,
                (
                    "ARM_BASE_NOT_SECURED",
                    "CAMERA_STRUCTURE_NOT_SECURED",
                    "PLACEMAT_NOT_SECURED",
                ),
                "Missing arm, overhead-camera and placemat securing each remains visible.",
            ),
            (
                "clearance_and_disconnect_missing",
                "EXPECTED_FAULT",
                {
                    "cables_restrained": False,
                    "keepout_zone_clear": False,
                    "emergency_disconnect_reachable": False,
                    "tool_clear_of_keyboard_and_phone": False,
                },
                hold,
                (
                    "CABLES_NOT_RESTRAINED",
                    "EMERGENCY_DISCONNECT_NOT_REACHABLE",
                    "KEEPOUT_ZONE_NOT_CLEAR",
                    "TOOL_NOT_CLEAR_OF_DEVICES",
                ),
                "Missing cable, clearance and reachable-disconnect checks cannot be hidden.",
            ),
            (
                "unexpected_review_effects",
                "EXPECTED_FAULT",
                {
                    "energization_occurred_during_review": True,
                    "motion_observed_during_review": True,
                    "contact_occurred_during_review": True,
                },
                hold,
                (
                    "CONTACT_DURING_POWER_OFF_REVIEW",
                    "MOTION_DURING_POWER_OFF_REVIEW",
                    "UNPLANNED_ENERGIZATION_DURING_POWER_OFF_REVIEW",
                ),
                "Synthetic energization, motion or contact during an off-review holds.",
            ),
        )
    else:
        nominal = receipts.FirstPowerObservation(
            binding=legacy,
            event_id="synthetic-event-" + str(sequence),
            operator_id="synthetic-operator",
            observer_id="synthetic-observer",
            observed_at_ns=timestamp,
            event_started_monotonic_ns=timestamp + 10,
            event_ended_monotonic_ns=timestamp + 100,
            pre_event_power_state=receipts.ReviewedPowerState.DISCONNECTED_CONFIRMED,
            post_event_power_state=receipts.ReviewedPowerState.DISCONNECTED_CONFIRMED,
            outcome=receipts.FirstPowerOutcome.COMPLETED_OBSERVATION,
            effect_certainty=receipts.EffectCertainty.CONFIRMED,
            startup_motion=receipts.StartupMotionClassification.NONE_OBSERVED,
            attempt_count=1,
            automatic_retry_count=0,
            startup_movement_warning_acknowledged=True,
            exclusion_zone_clear_before_event=True,
            estop_operator_ready_before_event=True,
            continuous_line_of_sight=True,
            controller_boot_observed=True,
            clearance_preserved=True,
            estop_activated=False,
            collision_observed=False,
            contact_observed=False,
            abnormal_condition_observed=False,
            observation_media_evidence_ids=(
                "synthetic-procedure",
                "synthetic-supporting-media",
            ),
        )
        specifications = (
            (
                "nominal_no_startup_motion",
                "NOMINAL",
                {},
                ready,
                ("FIRST_POWER_NO_STARTUP_MOTION_SAFELY_OBSERVED",),
                "A complete synthetic observation without motion is diagnostic only.",
            ),
            (
                "nominal_expected_startup_motion",
                "NOMINAL",
                {
                    "startup_motion": receipts.StartupMotionClassification.EXPECTED_AUTOMATIC_REPOSITIONING
                },
                ready,
                ("FIRST_POWER_EXPECTED_STARTUP_MOTION_SAFELY_OBSERVED",),
                "Expected startup movement is still recorded movement, never predicted clearance.",
            ),
            (
                "unknown_final_power",
                "EXPECTED_FAULT",
                {"post_event_power_state": receipts.ReviewedPowerState.UNKNOWN},
                uncertain,
                ("FIRST_POWER_SIDE_EFFECT_UNCERTAIN",),
                "Unknown final power must remain uncertain, not a normal hold or ready result.",
            ),
            (
                "lost_observation",
                "EXPECTED_FAULT",
                {"continuous_line_of_sight": False},
                uncertain,
                ("FIRST_POWER_SIDE_EFFECT_UNCERTAIN",),
                "Loss of observation cannot be repaired by software cancellation or cleanup.",
            ),
            (
                "automatic_retry",
                "EXPECTED_FAULT",
                {"automatic_retry_count": 1},
                hold,
                ("FIRST_POWER_AUTOMATIC_RETRY_FORBIDDEN",),
                "Any automatic retry is rejected.",
            ),
            (
                "multiple_attempts",
                "EXPECTED_FAULT",
                {"attempt_count": 2},
                hold,
                ("FIRST_POWER_ATTEMPT_COUNT_NOT_ONE",),
                "The typed ceremony permits one observed attempt.",
            ),
            (
                "unbounded_startup_motion",
                "EXPECTED_FAULT",
                {
                    "startup_motion": receipts.StartupMotionClassification.UNEXPECTED_OR_UNBOUNDED
                },
                hold,
                ("UNEXPECTED_OR_UNBOUNDED_STARTUP_MOTION",),
                "Unexpected or unbounded startup movement must hold.",
            ),
            (
                "unknown_startup_motion",
                "EXPECTED_FAULT",
                {"startup_motion": receipts.StartupMotionClassification.UNKNOWN},
                uncertain,
                ("FIRST_POWER_SIDE_EFFECT_UNCERTAIN",),
                "Unknown startup motion remains uncertain.",
            ),
            (
                "uncertain_effect",
                "EXPECTED_FAULT",
                {"effect_certainty": receipts.EffectCertainty.UNCERTAIN},
                uncertain,
                ("FIRST_POWER_SIDE_EFFECT_UNCERTAIN",),
                "Uncertain effects cannot qualify a ceremony.",
            ),
            (
                "uncertain_outcome",
                "EXPECTED_FAULT",
                {"outcome": receipts.FirstPowerOutcome.EFFECT_UNCERTAIN},
                uncertain,
                ("FIRST_POWER_SIDE_EFFECT_UNCERTAIN",),
                "An uncertain outcome remains uncertain.",
            ),
            (
                "connected_pre_or_post_state",
                "EXPECTED_FAULT",
                {
                    "pre_event_power_state": receipts.ReviewedPowerState.CONNECTED,
                    "post_event_power_state": receipts.ReviewedPowerState.CONNECTED,
                },
                hold,
                (
                    "FIRST_POWER_POSTSTATE_NOT_DISCONNECTED",
                    "FIRST_POWER_PRESTATE_NOT_DISCONNECTED",
                ),
                "Pre-event and final disconnection are independently required.",
            ),
            (
                "missing_startup_readiness",
                "EXPECTED_FAULT",
                {
                    "startup_movement_warning_acknowledged": False,
                    "exclusion_zone_clear_before_event": False,
                    "estop_operator_ready_before_event": False,
                    "controller_boot_observed": False,
                    "clearance_preserved": False,
                },
                hold,
                (
                    "CLEARANCE_NOT_PRESERVED",
                    "CONTROLLER_BOOT_NOT_OBSERVED",
                    "ESTOP_OPERATOR_NOT_READY_BEFORE_POWER",
                    "EXCLUSION_ZONE_NOT_CLEAR_BEFORE_POWER",
                    "STARTUP_MOVEMENT_WARNING_NOT_ACKNOWLEDGED",
                ),
                "Warning, exclusion, stop operator, boot and clearance are separate prerequisites.",
            ),
            (
                "abnormal_observation",
                "EXPECTED_FAULT",
                {
                    "estop_activated": True,
                    "collision_observed": True,
                    "contact_observed": True,
                    "abnormal_condition_observed": True,
                },
                hold,
                (
                    "ABNORMAL_CONDITION_DURING_FIRST_POWER",
                    "COLLISION_DURING_FIRST_POWER",
                    "CONTACT_DURING_FIRST_POWER",
                    "ESTOP_ACTIVATED_DURING_FIRST_POWER",
                ),
                "Stop activation, collision, contact and abnormalities each prevent readiness.",
            ),
            (
                "controlled_abort",
                "EXPECTED_FAULT",
                {"outcome": receipts.FirstPowerOutcome.CONTROLLED_ABORT},
                hold,
                ("FIRST_POWER_OBSERVATION_NOT_COMPLETED",),
                "A controlled abort is not a completed successful observation.",
            ),
        )
    return tuple(
        _Case(
            check_id,
            kind,
            replace(nominal, **changes),
            disposition,
            tuple(sorted(reasons)),
            meaning,
        )
        for check_id, kind, changes, disposition, reasons, meaning in specifications
    )


def _assessment_document(value: object, subject: Any) -> dict[str, Any]:
    """Validate structural consistency without rerunning a production assessor."""
    document = _object(
        value,
        {
            "schema",
            "binding",
            "subject_schema",
            "subject_receipt_sha256",
            "disposition",
            "reason_codes",
            "diagnostic_ready",
            "hold_required",
            "side_effect_uncertain",
            "authority",
            "assessment_sha256",
        },
    )
    _same(
        document["schema"],
        receipts.DIAGNOSTIC_READINESS_ASSESSMENT_SCHEMA,
        "assessment schema",
    )
    _same(document["binding"], subject.binding.to_dict(), "assessment binding")
    _same(document["subject_schema"], subject.schema, "assessment subject schema")
    _same(
        document["subject_receipt_sha256"],
        subject.receipt_sha256,
        "assessment subject hash",
    )
    _same(
        document["authority"],
        receipts.ZERO_PHYSICAL_AUTHORITY.to_dict(),
        "assessment authority",
    )
    disposition = document["disposition"]
    if type(disposition) is not str or disposition not in {
        d.value for d in receipts.DiagnosticDisposition
    }:
        raise RehearsalPowerError("invalid assessment disposition")
    for key, expected in {
        "diagnostic_ready": disposition == "DIAGNOSTIC_READY",
        "hold_required": disposition != "DIAGNOSTIC_READY",
        "side_effect_uncertain": disposition == "SIDE_EFFECT_UNCERTAIN",
    }.items():
        _same(document[key], expected, key)
    reasons = document["reason_codes"]
    if (
        type(reasons) is not list
        or not 1 <= len(reasons) <= 32
        or any(type(r) is not str or _REASON.fullmatch(r) is None for r in reasons)
        or reasons != sorted(set(reasons))
    ):
        raise RehearsalPowerError("invalid assessment reason codes")
    core = {key: value for key, value in document.items() if key != "assessment_sha256"}
    _same(
        document["assessment_sha256"],
        receipts.canonical_sha256(core),
        "assessment hash",
    )
    return document


def _derive(
    document: dict[str, Any],
    binding: RehearsalPowerBinding,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sequence = _integer(document["sequence"])
    cases = _cases(binding, sequence)
    reports = _object(document["reports"], {case.check_id for case in cases})
    legacy_binding, materials = _fixture_material(binding, sequence)
    selected = {
        "fixture_binding": legacy_binding.to_dict(),
        "fixture_materials": materials,
        "subject_sha256_by_check": {},
        "arm_identity_evidence_sha256": binding.arm_identity_evidence_sha256,
        "predecessor_stage": (
            "arm_identity" if binding.stage == "power_safety" else "power_safety"
        ),
        "settings_epoch": "NOT_APPLICABLE_NO_DEVICE_CONFIGURATION",
        "dataset": "NOT_APPLICABLE_SYNTHETIC_TEXT_ONLY",
        "stage_plan_sha256": STAGE_PLAN_SHA256,
    }
    subject_hashes: dict[str, str] = {}
    checks: list[dict[str, Any]] = []
    for case in cases:
        report = _object(
            reports[case.check_id], {"check_kind", "typed_input", "assessment"}
        )
        _same(report["check_kind"], case.kind, "case kind")
        # Exact reconstruction catches legacy authority bool/int ambiguities too.
        model = (
            receipts.PowerSafetyReview
            if binding.stage == "power_safety"
            else receipts.FirstPowerObservation
        ).from_dict(report["typed_input"])
        _same(report["typed_input"], model.to_dict(), "typed input roundtrip")
        _same(model.to_dict(), case.subject.to_dict(), "closed synthetic input")
        assessment = _assessment_document(report["assessment"], model)
        subject_hashes[case.check_id] = model.receipt_sha256
        passed = assessment["disposition"] == case.disposition and assessment[
            "reason_codes"
        ] == list(case.reasons)
        checks.append(
            {
                "check_id": case.check_id,
                "check_kind": case.kind,
                "passed": passed,
                "observed": {
                    key: assessment[key]
                    for key in (
                        "disposition",
                        "reason_codes",
                        "diagnostic_ready",
                        "hold_required",
                        "side_effect_uncertain",
                    )
                },
                "meaning": case.meaning,
            }
        )
    selected["subject_sha256_by_check"] = subject_hashes
    checks.append(
        {
            "check_id": "zero_actual_physical_effects",
            "check_kind": "INVARIANT",
            "passed": True,
            "observed": {
                "actual_physical_effects": dict(_EFFECTS),
                "physical_authority": False,
            },
            "meaning": "Pure synthetic receipt construction and assessment; no device or energy action occurs.",
        }
    )
    return checks, selected


def _outcome(checks: list[dict[str, Any]]) -> str:
    # Nominal readiness is explicitly required, not inferred from fault matches.
    nominal = [check for check in checks if check["check_kind"] == "NOMINAL"]
    return (
        "REHEARSAL_CHECKS_PASSED"
        if nominal and all(check["passed"] is True for check in checks)
        else "BLOCKED"
    )


def verify_rehearsal_power_evidence(
    payload: bytes,
    *,
    expected_binding: RehearsalPowerBinding,
    expected_evidence_sha256: str | None = None,
    expected_evaluator_source_sha256: str | None = None,
) -> RehearsalPowerEvidence:
    """Pure retained verification, not a rerun or authentication of its caller.

    Trust requires the caller's authenticated binding and retained byte digest.
    The optional evaluator digest names this module alone. Dependency hashes are
    retained under that authenticated envelope; no disk/source reads occur here.
    A coherent assessor regression remains inspectable as BLOCKED. Malformed
    data, forged check claims or conflicting hashes raise RehearsalPowerError.
    """
    if type(expected_binding) is not RehearsalPowerBinding:
        raise RehearsalPowerError("expected binding must use the exact typed contract")
    expected_binding.__post_init__()
    try:
        document = _object(
            _decode(payload),
            {
                "schema",
                "stage",
                "binding",
                "evaluator",
                "sequence",
                "provenance",
                "reports",
                "report_hashes",
                "selected_inputs",
                "selected_inputs_sha256",
                "checks",
                "outcome",
                "authority",
                "physical_authority",
                "meaning",
            },
        )
        _same(document["schema"], SCHEMA, "schema")
        _same(document["stage"], expected_binding.stage, "stage")
        _same(document["binding"], expected_binding.to_dict(), "expected binding")
        _same(document["authority"], _AUTHORITY, "zero authority")
        _same(document["physical_authority"], False, "physical authority")
        _same(document["meaning"], _MEANING, "scope meaning")
        _same(document["provenance"], _provenance(expected_binding.stage), "provenance")
        evaluator = _object(
            document["evaluator"],
            {"id", "source_file_sha256", "dependency_source_sha256"},
        )
        _same(evaluator["id"], EVALUATOR_ID, "evaluator identity")
        _digest(evaluator["source_file_sha256"])
        dependencies = _object(
            evaluator["dependency_source_sha256"], set(_SOURCE_PATHS[1:])
        )
        for digest in dependencies.values():
            _digest(digest)
        if expected_evaluator_source_sha256 is not None:
            _same(
                evaluator["source_file_sha256"],
                _digest(expected_evaluator_source_sha256),
                "evaluator source",
            )
        canonical = _canonical(document)
        # Require sole canonical encoding so an authenticated byte hash cannot
        # accidentally be replaced with a semantically similar alternate file.
        if canonical != payload:
            raise RehearsalPowerError("retained evidence is not canonical JSON bytes")
        if expected_evidence_sha256 is not None:
            _same(
                hashlib.sha256(payload).hexdigest(),
                _digest(expected_evidence_sha256),
                "retained evidence hash",
            )
        reports = _object(document["reports"])
        _same(
            document["report_hashes"],
            {key: _hash(value) for key, value in reports.items()},
            "report hashes",
        )
        checks, selected = _derive(document, expected_binding)
        _same(document["checks"], checks, "derived checks")
        _same(document["selected_inputs"], selected, "selected inputs")
        _same(
            document["selected_inputs_sha256"], _hash(selected), "selected input hash"
        )
        _same(document["outcome"], _outcome(checks), "derived outcome")
        return RehearsalPowerEvidence(canonical)
    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ) as error:
        if isinstance(error, RehearsalPowerError):
            raise
        raise RehearsalPowerError("retained power report is invalid") from error


def _read_source(root: Path, relative: str) -> bytes:
    path = root / relative
    for component in (path, *path.parents):
        stat = component.lstat()
        if component.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
            raise RehearsalPowerError("source path contains a link/reparse component")
    with path.open("rb") as stream:
        payload = stream.read(_MAX_SOURCE_BYTES + 1)
    if not 0 < len(payload) <= _MAX_SOURCE_BYTES:
        raise RehearsalPowerError("source file exceeds the fixed read bound")
    return payload


def evaluate_rehearsal_power_stage(
    workspace: Path,
    binding: RehearsalPowerBinding,
    *,
    sequence: int = 0,
) -> RehearsalPowerEvidence:
    """Run fixed typed-assessor cases; no provider or observation input is accepted.

    Only three fixed Python source files are read for provenance. The sequence
    changes deterministic fixture identities/timestamps, never retries an action.
    No OS inventory, serial API, power control, persistence or permits are used.
    """
    if type(binding) is not RehearsalPowerBinding:
        raise RehearsalPowerError("binding must use the exact typed contract")
    binding.__post_init__()
    _integer(sequence)
    root = Path(workspace).absolute()
    sources = {relative: _read_source(root, relative) for relative in _SOURCE_PATHS}
    if (root / _SOURCE_PATHS[0]).resolve(strict=True) != Path(__file__).resolve(
        strict=True
    ):
        raise RehearsalPowerError("workspace does not contain this loaded evaluator")
    reports: dict[str, Any] = {}
    for case in _cases(binding, sequence):
        if isinstance(case.subject, receipts.PowerSafetyReview):
            assessment = receipts.assess_power_safety(case.subject)
        else:
            assessment = receipts.assess_first_power_observation(case.subject)
        reports[case.check_id] = {
            "check_kind": case.kind,
            "typed_input": case.subject.to_dict(),
            "assessment": assessment.to_dict(),
        }
    evaluator_hash = hashlib.sha256(sources[_SOURCE_PATHS[0]]).hexdigest()
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "stage": binding.stage,
        "binding": binding.to_dict(),
        "evaluator": {
            "id": EVALUATOR_ID,
            "source_file_sha256": evaluator_hash,
            "dependency_source_sha256": {
                relative: hashlib.sha256(sources[relative]).hexdigest()
                for relative in _SOURCE_PATHS[1:]
            },
        },
        "sequence": sequence,
        "provenance": _provenance(binding.stage),
        "reports": reports,
        "authority": _AUTHORITY,
        "physical_authority": False,
        "meaning": _MEANING,
    }
    checks, selected = _derive(document, binding)
    document.update(
        {
            "checks": checks,
            "selected_inputs": selected,
            "selected_inputs_sha256": _hash(selected),
            "report_hashes": {key: _hash(value) for key, value in reports.items()},
            "outcome": _outcome(checks),
        }
    )
    if any(
        _read_source(root, relative) != payload for relative, payload in sources.items()
    ):
        raise RehearsalPowerError(
            "evaluator/dependency source changed during evaluation"
        )
    return verify_rehearsal_power_evidence(
        _canonical(document),
        expected_binding=binding,
        expected_evaluator_source_sha256=evaluator_hash,
    )


__all__ = [
    "SCHEMA",
    "EVALUATOR_ID",
    "MAX_EVIDENCE_BYTES",
    "MAX_SEQUENCE",
    "RehearsalPowerError",
    "RehearsalPowerBinding",
    "RehearsalPowerEvidence",
    "evaluate_rehearsal_power_stage",
    "verify_rehearsal_power_evidence",
]
