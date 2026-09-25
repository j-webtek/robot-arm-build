"""Strict, zero-authority receipts for manual physical-onboarding stages.

The persistent onboarding journal deliberately accepts only content-addressed
evidence references.  This module gives the *manual* evidence collected at the
highest-risk stages a typed and hash-bound meaning.  It does not open devices,
switch power, send arm commands, mutate an onboarding session, or promote a
physical build.

Four receipt types are intentionally supported:

* :class:`CameraReceiptInspection` records the delivered B0477 and 16 mm lens;
* :class:`PowerSafetyReview` records a power-off mechanical/electrical review;
* :class:`FirstPowerObservation` records one externally controlled power event;
* :class:`ControlledOperatorDecision` records a review of one of the three
  stage-specific diagnostic assessments.

There is no generic ``PASS`` receipt.  Assessment functions can return only
``DIAGNOSTIC_READY``, ``HOLD``, or ``SIDE_EFFECT_UNCERTAIN``.  Even a
``DIAGNOSTIC_READY`` result permanently carries zero power, motion, contact,
release, build-promotion, and session-mutation authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence, TypeAlias

from rocell.application.physical_onboarding import (
    STAGE_PLAN_SHA256,
    EvidenceReference,
    PhysicalOnboardingStage,
)


CAMERA_RECEIPT_INSPECTION_SCHEMA = (
    "rocell.physical_onboarding.camera_receipt_inspection.v1"
)
POWER_SAFETY_REVIEW_SCHEMA = "rocell.physical_onboarding.power_safety_review.v1"
FIRST_POWER_OBSERVATION_SCHEMA = "rocell.physical_onboarding.first_power_observation.v1"
CONTROLLED_OPERATOR_DECISION_SCHEMA = (
    "rocell.physical_onboarding.controlled_operator_decision.v1"
)
DIAGNOSTIC_READINESS_ASSESSMENT_SCHEMA = (
    "rocell.physical_onboarding.diagnostic_readiness_assessment.v1"
)

EXPECTED_CAMERA_MANUFACTURER = "Arducam"
EXPECTED_CAMERA_PRODUCT_ID = "B0477"
EXPECTED_CAMERA_LENS_FOCAL_LENGTH_MM = 16
EXPECTED_POWER_SUPPLY_OUTPUT_MV = 12_000
MINIMUM_POWER_SUPPLY_CURRENT_MA = 5_000

MAX_JSON_BYTES = 256 * 1024
MAX_EVIDENCE_BINDINGS = 32
MAX_REASON_CODES = 32
MAX_TEXT_CHARS = 512

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")
_REASON_CODE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")


class PhysicalOnboardingReceiptError(ValueError):
    """A manual receipt is malformed, ambiguous, or over-authoritative."""


class DiagnosticDisposition(str, Enum):
    """Only diagnostic outcomes; none is a physical-stage PASS or release."""

    DIAGNOSTIC_READY = "DIAGNOSTIC_READY"
    HOLD = "HOLD"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"


class InspectionCondition(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    DAMAGED = "DAMAGED"
    UNCERTAIN = "UNCERTAIN"


class ReviewedPowerState(str, Enum):
    DISCONNECTED_CONFIRMED = "DISCONNECTED_CONFIRMED"
    CONNECTED = "CONNECTED"
    UNKNOWN = "UNKNOWN"


class EstopReviewStatus(str, Enum):
    POWER_OFF_CONTINUITY_VERIFIED = "POWER_OFF_CONTINUITY_VERIFIED"
    BOUND_PRIOR_TEST_EVIDENCE = "BOUND_PRIOR_TEST_EVIDENCE"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNCERTAIN = "UNCERTAIN"


class FirstPowerOutcome(str, Enum):
    COMPLETED_OBSERVATION = "COMPLETED_OBSERVATION"
    CONTROLLED_ABORT = "CONTROLLED_ABORT"
    EFFECT_UNCERTAIN = "EFFECT_UNCERTAIN"


class StartupMotionClassification(str, Enum):
    """Observed motion, including the RoArm's possible startup repositioning."""

    NONE_OBSERVED = "NONE_OBSERVED"
    EXPECTED_AUTOMATIC_REPOSITIONING = "EXPECTED_AUTOMATIC_REPOSITIONING"
    UNEXPECTED_OR_UNBOUNDED = "UNEXPECTED_OR_UNBOUNDED"
    UNKNOWN = "UNKNOWN"


class EffectCertainty(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"


class OperatorDecisionKind(str, Enum):
    """Review actions that cannot upgrade a stage-specific assessment."""

    ACKNOWLEDGE_DIAGNOSTIC_READINESS = "ACKNOWLEDGE_DIAGNOSTIC_READINESS"
    PLACE_HOLD = "PLACE_HOLD"
    ESCALATE_SIDE_EFFECT_UNCERTAINTY = "ESCALATE_SIDE_EFFECT_UNCERTAINTY"


def _validate_json_node(value: object, label: str = "value") -> None:
    """Reject JSON values whose cross-runtime canonical meaning is ambiguous."""

    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if isinstance(value, bool) or not -(2**63) < value < 2**63:
            raise PhysicalOnboardingReceiptError(
                f"{label} integer is outside the signed 64-bit range"
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PhysicalOnboardingReceiptError(f"{label} contains nonfinite data")
        raise PhysicalOnboardingReceiptError(f"{label} must not contain floats")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_node(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PhysicalOnboardingReceiptError(
                    f"{label} contains a non-string object key"
                )
            _validate_json_node(item, f"{label}.{key}")
        return
    raise PhysicalOnboardingReceiptError(
        f"{label} contains unsupported type {type(value).__name__}"
    )


def canonical_json_bytes(value: object) -> bytes:
    """Serialize one record in the sole accepted persisted representation."""

    _validate_json_node(value)
    try:
        payload = (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # guarded above; retain safe boundary
        raise PhysicalOnboardingReceiptError("record is not canonical JSON") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise PhysicalOnboardingReceiptError("record exceeds the JSON resource limit")
    return payload


def canonical_sha256(value: object) -> str:
    """Return the semantic digest used for bindings and receipt identities."""

    _validate_json_node(value)
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingReceiptError("record is not hashable JSON") from exc
    return hashlib.sha256(payload).hexdigest()


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise PhysicalOnboardingReceiptError(f"duplicate JSON key {key!r}")
        document[key] = value
    return document


def _reject_float(value: str) -> None:
    raise PhysicalOnboardingReceiptError(f"receipt JSON float {value!r} is forbidden")


def _reject_constant(value: str) -> None:
    raise PhysicalOnboardingReceiptError(
        f"receipt JSON nonfinite constant {value!r} is forbidden"
    )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PhysicalOnboardingReceiptError(f"{label} must be a JSON object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PhysicalOnboardingReceiptError(f"{label} must be a JSON array")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise PhysicalOnboardingReceiptError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _text(value: object, label: str, *, maximum: int = MAX_TEXT_CHARS) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PhysicalOnboardingReceiptError(
            f"{label} must be non-empty, trimmed, bounded text"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise PhysicalOnboardingReceiptError(f"{label} must be a bounded identifier")
    if value in {".", ".."}:
        raise PhysicalOnboardingReceiptError(f"{label} must not be a path segment")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PhysicalOnboardingReceiptError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = (2**63) - 1,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise PhysicalOnboardingReceiptError(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise PhysicalOnboardingReceiptError(f"{label} must be boolean")
    return value


def _enum(value: object, kind: type[Enum], label: str) -> Any:
    try:
        return kind(value)
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingReceiptError(f"{label} is unsupported") from exc


def _reason_codes(value: Sequence[str], label: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not (1 <= len(value) <= MAX_REASON_CODES):
        raise PhysicalOnboardingReceiptError(
            f"{label} must be a non-empty bounded immutable tuple"
        )
    if any(
        not isinstance(item, str) or _REASON_CODE_RE.fullmatch(item) is None
        for item in value
    ):
        raise PhysicalOnboardingReceiptError(
            f"{label} entries must be bounded uppercase reason codes"
        )
    if tuple(sorted(set(value))) != value:
        raise PhysicalOnboardingReceiptError(f"{label} must be sorted and unique")
    return value


def _parse_reason_codes(value: object, label: str) -> tuple[str, ...]:
    return _reason_codes(tuple(_array(value, label)), label)


@dataclass(frozen=True, slots=True)
class ZeroPhysicalAuthority:
    """Permanent authority ceiling serialized on every record and assessment."""

    scope: str = "DIAGNOSTIC_EVIDENCE_ONLY"
    hardware_commands_generated: int = 0
    power_commands_generated: int = 0
    motion_commands_generated: int = 0
    contact_commands_generated: int = 0
    power_authorized: bool = False
    motion_authorized: bool = False
    contact_authorized: bool = False
    build_promotion_authorized: bool = False
    session_mutation_effect: str = "NONE"
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        if self.to_dict() != _ZERO_AUTHORITY_DOCUMENT:
            raise PhysicalOnboardingReceiptError(
                "manual onboarding receipts cannot exceed zero physical authority"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "hardware_commands_generated": self.hardware_commands_generated,
            "power_commands_generated": self.power_commands_generated,
            "motion_commands_generated": self.motion_commands_generated,
            "contact_commands_generated": self.contact_commands_generated,
            "power_authorized": self.power_authorized,
            "motion_authorized": self.motion_authorized,
            "contact_authorized": self.contact_authorized,
            "build_promotion_authorized": self.build_promotion_authorized,
            "session_mutation_effect": self.session_mutation_effect,
            "physical_release_effect": self.physical_release_effect,
        }


_ZERO_AUTHORITY_DOCUMENT: dict[str, object] = {
    "scope": "DIAGNOSTIC_EVIDENCE_ONLY",
    "hardware_commands_generated": 0,
    "power_commands_generated": 0,
    "motion_commands_generated": 0,
    "contact_commands_generated": 0,
    "power_authorized": False,
    "motion_authorized": False,
    "contact_authorized": False,
    "build_promotion_authorized": False,
    "session_mutation_effect": "NONE",
    "physical_release_effect": "NONE",
}
ZERO_PHYSICAL_AUTHORITY = ZeroPhysicalAuthority()


def _validate_authority(value: object) -> None:
    document = _mapping(value, "authority")
    _exact_fields(document, frozenset(_ZERO_AUTHORITY_DOCUMENT), "authority")
    if dict(document) != _ZERO_AUTHORITY_DOCUMENT:
        raise PhysicalOnboardingReceiptError(
            "serialized receipt authority exceeds zero physical authority"
        )


@dataclass(frozen=True, slots=True)
class BoundEvidence:
    """A complete immutable binding to one onboarding evidence package."""

    evidence_id: str
    stage: PhysicalOnboardingStage
    package_sha256: str
    manifest_sha256: str
    payload_sha256: str
    payload_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "evidence_id")
        )
        if not isinstance(self.stage, PhysicalOnboardingStage):
            raise PhysicalOnboardingReceiptError(
                "bound evidence stage must be PhysicalOnboardingStage"
            )
        for field_name in ("package_sha256", "manifest_sha256", "payload_sha256"):
            object.__setattr__(
                self, field_name, _digest(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self,
            "payload_bytes",
            _integer(
                self.payload_bytes, "payload_bytes", minimum=1, maximum=32 * 1024 * 1024
            ),
        )

    @classmethod
    def from_reference(cls, reference: EvidenceReference) -> "BoundEvidence":
        if not isinstance(reference, EvidenceReference):
            raise PhysicalOnboardingReceiptError(
                "reference must be an onboarding EvidenceReference"
            )
        return cls(
            evidence_id=reference.evidence_id,
            stage=reference.stage,
            package_sha256=reference.package_sha256,
            manifest_sha256=reference.manifest_sha256,
            payload_sha256=reference.payload_sha256,
            payload_bytes=reference.payload_bytes,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "stage": self.stage.value,
            "package_sha256": self.package_sha256,
            "manifest_sha256": self.manifest_sha256,
            "payload_sha256": self.payload_sha256,
            "payload_bytes": self.payload_bytes,
        }

    @classmethod
    def from_dict(cls, value: object) -> "BoundEvidence":
        document = _mapping(value, "bound evidence")
        _exact_fields(
            document,
            frozenset(
                {
                    "evidence_id",
                    "stage",
                    "package_sha256",
                    "manifest_sha256",
                    "payload_sha256",
                    "payload_bytes",
                }
            ),
            "bound evidence",
        )
        return cls(
            evidence_id=_identifier(document["evidence_id"], "evidence_id"),
            stage=_enum(document["stage"], PhysicalOnboardingStage, "evidence stage"),
            package_sha256=_digest(document["package_sha256"], "package_sha256"),
            manifest_sha256=_digest(document["manifest_sha256"], "manifest_sha256"),
            payload_sha256=_digest(document["payload_sha256"], "payload_sha256"),
            payload_bytes=_integer(
                document["payload_bytes"],
                "payload_bytes",
                minimum=1,
                maximum=32 * 1024 * 1024,
            ),
        )


@dataclass(frozen=True, slots=True)
class ReceiptBinding:
    """Explicit source, session, stage-plan, stage, and evidence binding."""

    source_binding_sha256: str
    session_header_sha256: str
    session_id: str
    cell_id: str
    stage: PhysicalOnboardingStage
    evidence: tuple[BoundEvidence, ...]
    stage_plan_sha256: str = STAGE_PLAN_SHA256

    def __post_init__(self) -> None:
        for field_name in (
            "source_binding_sha256",
            "session_header_sha256",
            "stage_plan_sha256",
        ):
            object.__setattr__(
                self, field_name, _digest(getattr(self, field_name), field_name)
            )
        if self.stage_plan_sha256 != STAGE_PLAN_SHA256:
            raise PhysicalOnboardingReceiptError("stage-plan binding has drifted")
        object.__setattr__(
            self, "session_id", _identifier(self.session_id, "session_id")
        )
        object.__setattr__(self, "cell_id", _identifier(self.cell_id, "cell_id"))
        if not isinstance(self.stage, PhysicalOnboardingStage):
            raise PhysicalOnboardingReceiptError(
                "receipt stage must be PhysicalOnboardingStage"
            )
        if not isinstance(self.evidence, tuple) or not (
            1 <= len(self.evidence) <= MAX_EVIDENCE_BINDINGS
        ):
            raise PhysicalOnboardingReceiptError(
                "evidence must be a non-empty bounded immutable tuple"
            )
        if any(not isinstance(item, BoundEvidence) for item in self.evidence):
            raise PhysicalOnboardingReceiptError(
                "evidence contains a non-BoundEvidence item"
            )
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise PhysicalOnboardingReceiptError("evidence bindings contain duplicates")
        if tuple(sorted(evidence_ids)) != evidence_ids:
            raise PhysicalOnboardingReceiptError(
                "evidence bindings must be sorted by evidence_id"
            )
        if any(item.stage is not self.stage for item in self.evidence):
            raise PhysicalOnboardingReceiptError(
                "every evidence binding must belong to the receipt stage"
            )

    @property
    def evidence_ids(self) -> frozenset[str]:
        return frozenset(item.evidence_id for item in self.evidence)

    def core_dict(self) -> dict[str, object]:
        return {
            "source_binding_sha256": self.source_binding_sha256,
            "session_header_sha256": self.session_header_sha256,
            "session_id": self.session_id,
            "cell_id": self.cell_id,
            "stage_plan_sha256": self.stage_plan_sha256,
            "stage": self.stage.value,
            "evidence": [item.to_dict() for item in self.evidence],
        }

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self.core_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "binding_sha256": self.binding_sha256}

    @classmethod
    def from_dict(cls, value: object) -> "ReceiptBinding":
        document = _mapping(value, "receipt binding")
        _exact_fields(
            document,
            frozenset(
                {
                    "source_binding_sha256",
                    "session_header_sha256",
                    "session_id",
                    "cell_id",
                    "stage_plan_sha256",
                    "stage",
                    "evidence",
                    "binding_sha256",
                }
            ),
            "receipt binding",
        )
        binding = cls(
            source_binding_sha256=_digest(
                document["source_binding_sha256"], "source_binding_sha256"
            ),
            session_header_sha256=_digest(
                document["session_header_sha256"], "session_header_sha256"
            ),
            session_id=_identifier(document["session_id"], "session_id"),
            cell_id=_identifier(document["cell_id"], "cell_id"),
            stage_plan_sha256=_digest(
                document["stage_plan_sha256"], "stage_plan_sha256"
            ),
            stage=_enum(document["stage"], PhysicalOnboardingStage, "receipt stage"),
            evidence=tuple(
                BoundEvidence.from_dict(item)
                for item in _array(document["evidence"], "receipt evidence")
            ),
        )
        if (
            _digest(document["binding_sha256"], "binding_sha256")
            != binding.binding_sha256
        ):
            raise PhysicalOnboardingReceiptError("receipt binding hash mismatch")
        return binding


def _bound_evidence_ids(
    value: tuple[str, ...], binding: ReceiptBinding, label: str
) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise PhysicalOnboardingReceiptError(f"{label} must be a non-empty tuple")
    normalized = tuple(_identifier(item, f"{label} item") for item in value)
    if tuple(sorted(set(normalized))) != normalized:
        raise PhysicalOnboardingReceiptError(f"{label} must be sorted and unique")
    if not set(normalized).issubset(binding.evidence_ids):
        raise PhysicalOnboardingReceiptError(
            f"{label} references evidence outside the receipt binding"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CameraReceiptInspection:
    """Manual inspection of the purchased Arducam B0477 delivery."""

    binding: ReceiptBinding
    operator_id: str
    observed_at_ns: int
    observed_manufacturer: str
    observed_product_id: str
    observed_camera_serial: str
    observed_lens_focal_length_mm: int | None
    body_condition: InspectionCondition
    lens_condition: InspectionCondition
    connector_condition: InspectionCondition
    identity_label_legible: bool
    purchase_record_matches: bool
    package_contents_complete: bool
    inspection_uncertain: bool
    purchase_record_evidence_id: str
    inspection_image_evidence_ids: tuple[str, ...]
    schema: str = CAMERA_RECEIPT_INSPECTION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CAMERA_RECEIPT_INSPECTION_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported camera-receipt schema")
        if not isinstance(self.binding, ReceiptBinding) or (
            self.binding.stage is not PhysicalOnboardingStage.CAMERA_RECEIPT
        ):
            raise PhysicalOnboardingReceiptError(
                "camera receipt must bind to the camera_receipt stage"
            )
        object.__setattr__(
            self, "operator_id", _identifier(self.operator_id, "operator_id")
        )
        object.__setattr__(
            self,
            "observed_at_ns",
            _integer(self.observed_at_ns, "observed_at_ns", minimum=1),
        )
        for field_name in (
            "observed_manufacturer",
            "observed_product_id",
            "observed_camera_serial",
        ):
            object.__setattr__(
                self, field_name, _text(getattr(self, field_name), field_name)
            )
        if self.observed_lens_focal_length_mm is not None:
            object.__setattr__(
                self,
                "observed_lens_focal_length_mm",
                _integer(
                    self.observed_lens_focal_length_mm,
                    "observed_lens_focal_length_mm",
                    minimum=1,
                    maximum=500,
                ),
            )
        for field_name in ("body_condition", "lens_condition", "connector_condition"):
            if not isinstance(getattr(self, field_name), InspectionCondition):
                raise PhysicalOnboardingReceiptError(
                    f"{field_name} must be InspectionCondition"
                )
        for field_name in (
            "identity_label_legible",
            "purchase_record_matches",
            "package_contents_complete",
            "inspection_uncertain",
        ):
            _boolean(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "purchase_record_evidence_id",
            _identifier(
                self.purchase_record_evidence_id, "purchase_record_evidence_id"
            ),
        )
        if self.purchase_record_evidence_id not in self.binding.evidence_ids:
            raise PhysicalOnboardingReceiptError(
                "purchase record is outside the camera receipt evidence binding"
            )
        object.__setattr__(
            self,
            "inspection_image_evidence_ids",
            _bound_evidence_ids(
                self.inspection_image_evidence_ids,
                self.binding,
                "inspection_image_evidence_ids",
            ),
        )

    def core_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "binding": self.binding.to_dict(),
            "operator_id": self.operator_id,
            "observed_at_ns": self.observed_at_ns,
            "observed_manufacturer": self.observed_manufacturer,
            "observed_product_id": self.observed_product_id,
            "observed_camera_serial": self.observed_camera_serial,
            "observed_lens_focal_length_mm": self.observed_lens_focal_length_mm,
            "body_condition": self.body_condition.value,
            "lens_condition": self.lens_condition.value,
            "connector_condition": self.connector_condition.value,
            "identity_label_legible": self.identity_label_legible,
            "purchase_record_matches": self.purchase_record_matches,
            "package_contents_complete": self.package_contents_complete,
            "inspection_uncertain": self.inspection_uncertain,
            "purchase_record_evidence_id": self.purchase_record_evidence_id,
            "inspection_image_evidence_ids": list(self.inspection_image_evidence_ids),
            "authority": ZERO_PHYSICAL_AUTHORITY.to_dict(),
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.core_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "receipt_sha256": self.receipt_sha256}

    @classmethod
    def from_dict(cls, value: object) -> "CameraReceiptInspection":
        document = _mapping(value, "camera receipt")
        _exact_fields(document, _CAMERA_RECEIPT_FIELDS, "camera receipt")
        if document["schema"] != CAMERA_RECEIPT_INSPECTION_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported camera-receipt schema")
        _validate_authority(document["authority"])
        receipt = cls(
            binding=ReceiptBinding.from_dict(document["binding"]),
            operator_id=_identifier(document["operator_id"], "operator_id"),
            observed_at_ns=_integer(
                document["observed_at_ns"], "observed_at_ns", minimum=1
            ),
            observed_manufacturer=_text(
                document["observed_manufacturer"], "observed_manufacturer"
            ),
            observed_product_id=_text(
                document["observed_product_id"], "observed_product_id"
            ),
            observed_camera_serial=_text(
                document["observed_camera_serial"], "observed_camera_serial"
            ),
            observed_lens_focal_length_mm=(
                None
                if document["observed_lens_focal_length_mm"] is None
                else _integer(
                    document["observed_lens_focal_length_mm"],
                    "observed_lens_focal_length_mm",
                    minimum=1,
                    maximum=500,
                )
            ),
            body_condition=_enum(
                document["body_condition"], InspectionCondition, "body_condition"
            ),
            lens_condition=_enum(
                document["lens_condition"], InspectionCondition, "lens_condition"
            ),
            connector_condition=_enum(
                document["connector_condition"],
                InspectionCondition,
                "connector_condition",
            ),
            identity_label_legible=_boolean(
                document["identity_label_legible"], "identity_label_legible"
            ),
            purchase_record_matches=_boolean(
                document["purchase_record_matches"], "purchase_record_matches"
            ),
            package_contents_complete=_boolean(
                document["package_contents_complete"], "package_contents_complete"
            ),
            inspection_uncertain=_boolean(
                document["inspection_uncertain"], "inspection_uncertain"
            ),
            purchase_record_evidence_id=_identifier(
                document["purchase_record_evidence_id"],
                "purchase_record_evidence_id",
            ),
            inspection_image_evidence_ids=tuple(
                _identifier(item, "inspection_image_evidence_ids item")
                for item in _array(
                    document["inspection_image_evidence_ids"],
                    "inspection_image_evidence_ids",
                )
            ),
        )
        if (
            _digest(document["receipt_sha256"], "receipt_sha256")
            != receipt.receipt_sha256
        ):
            raise PhysicalOnboardingReceiptError("camera receipt hash mismatch")
        return receipt


_CAMERA_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "binding",
        "operator_id",
        "observed_at_ns",
        "observed_manufacturer",
        "observed_product_id",
        "observed_camera_serial",
        "observed_lens_focal_length_mm",
        "body_condition",
        "lens_condition",
        "connector_condition",
        "identity_label_legible",
        "purchase_record_matches",
        "package_contents_complete",
        "inspection_uncertain",
        "purchase_record_evidence_id",
        "inspection_image_evidence_ids",
        "authority",
        "receipt_sha256",
    }
)


@dataclass(frozen=True, slots=True)
class PowerSafetyReview:
    """Power-off review; it is evidence and never permission to energize."""

    binding: ReceiptBinding
    operator_id: str
    reviewed_at_ns: int
    arm_power_state: ReviewedPowerState
    estop_status: EstopReviewStatus
    power_supply_output_mv: int
    power_supply_current_ma: int
    polarity_verified: bool
    arm_base_secured: bool
    camera_structure_secured: bool
    placemat_secured: bool
    cables_restrained: bool
    keepout_zone_clear: bool
    emergency_disconnect_reachable: bool
    tool_clear_of_keyboard_and_phone: bool
    energization_occurred_during_review: bool
    motion_observed_during_review: bool
    contact_occurred_during_review: bool
    review_uncertain: bool
    estop_test_evidence_id: str
    wiring_image_evidence_ids: tuple[str, ...]
    schema: str = POWER_SAFETY_REVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != POWER_SAFETY_REVIEW_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported power-safety schema")
        if not isinstance(self.binding, ReceiptBinding) or (
            self.binding.stage is not PhysicalOnboardingStage.POWER_SAFETY
        ):
            raise PhysicalOnboardingReceiptError(
                "power safety review must bind to the power_safety stage"
            )
        object.__setattr__(
            self, "operator_id", _identifier(self.operator_id, "operator_id")
        )
        object.__setattr__(
            self,
            "reviewed_at_ns",
            _integer(self.reviewed_at_ns, "reviewed_at_ns", minimum=1),
        )
        if not isinstance(self.arm_power_state, ReviewedPowerState):
            raise PhysicalOnboardingReceiptError(
                "arm_power_state must be ReviewedPowerState"
            )
        if not isinstance(self.estop_status, EstopReviewStatus):
            raise PhysicalOnboardingReceiptError(
                "estop_status must be EstopReviewStatus"
            )
        object.__setattr__(
            self,
            "power_supply_output_mv",
            _integer(
                self.power_supply_output_mv,
                "power_supply_output_mv",
                minimum=0,
                maximum=100_000,
            ),
        )
        object.__setattr__(
            self,
            "power_supply_current_ma",
            _integer(
                self.power_supply_current_ma,
                "power_supply_current_ma",
                minimum=0,
                maximum=100_000,
            ),
        )
        for field_name in _POWER_SAFETY_BOOLEAN_FIELDS:
            _boolean(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "estop_test_evidence_id",
            _identifier(self.estop_test_evidence_id, "estop_test_evidence_id"),
        )
        if self.estop_test_evidence_id not in self.binding.evidence_ids:
            raise PhysicalOnboardingReceiptError(
                "E-stop test evidence is outside the power-safety binding"
            )
        object.__setattr__(
            self,
            "wiring_image_evidence_ids",
            _bound_evidence_ids(
                self.wiring_image_evidence_ids,
                self.binding,
                "wiring_image_evidence_ids",
            ),
        )

    def core_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema": self.schema,
            "binding": self.binding.to_dict(),
            "operator_id": self.operator_id,
            "reviewed_at_ns": self.reviewed_at_ns,
            "arm_power_state": self.arm_power_state.value,
            "estop_status": self.estop_status.value,
            "power_supply_output_mv": self.power_supply_output_mv,
            "power_supply_current_ma": self.power_supply_current_ma,
            "estop_test_evidence_id": self.estop_test_evidence_id,
            "wiring_image_evidence_ids": list(self.wiring_image_evidence_ids),
            "authority": ZERO_PHYSICAL_AUTHORITY.to_dict(),
        }
        document.update(
            {name: getattr(self, name) for name in _POWER_SAFETY_BOOLEAN_FIELDS}
        )
        return document

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.core_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "receipt_sha256": self.receipt_sha256}

    @classmethod
    def from_dict(cls, value: object) -> "PowerSafetyReview":
        document = _mapping(value, "power safety review")
        _exact_fields(document, _POWER_SAFETY_FIELDS, "power safety review")
        if document["schema"] != POWER_SAFETY_REVIEW_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported power-safety schema")
        _validate_authority(document["authority"])
        receipt = cls(
            binding=ReceiptBinding.from_dict(document["binding"]),
            operator_id=_identifier(document["operator_id"], "operator_id"),
            reviewed_at_ns=_integer(
                document["reviewed_at_ns"], "reviewed_at_ns", minimum=1
            ),
            arm_power_state=_enum(
                document["arm_power_state"], ReviewedPowerState, "arm_power_state"
            ),
            estop_status=_enum(
                document["estop_status"], EstopReviewStatus, "estop_status"
            ),
            power_supply_output_mv=_integer(
                document["power_supply_output_mv"],
                "power_supply_output_mv",
                maximum=100_000,
            ),
            power_supply_current_ma=_integer(
                document["power_supply_current_ma"],
                "power_supply_current_ma",
                maximum=100_000,
            ),
            estop_test_evidence_id=_identifier(
                document["estop_test_evidence_id"], "estop_test_evidence_id"
            ),
            wiring_image_evidence_ids=tuple(
                _identifier(item, "wiring_image_evidence_ids item")
                for item in _array(
                    document["wiring_image_evidence_ids"], "wiring_image_evidence_ids"
                )
            ),
            polarity_verified=_boolean(
                document["polarity_verified"], "polarity_verified"
            ),
            arm_base_secured=_boolean(document["arm_base_secured"], "arm_base_secured"),
            camera_structure_secured=_boolean(
                document["camera_structure_secured"], "camera_structure_secured"
            ),
            placemat_secured=_boolean(document["placemat_secured"], "placemat_secured"),
            cables_restrained=_boolean(
                document["cables_restrained"], "cables_restrained"
            ),
            keepout_zone_clear=_boolean(
                document["keepout_zone_clear"], "keepout_zone_clear"
            ),
            emergency_disconnect_reachable=_boolean(
                document["emergency_disconnect_reachable"],
                "emergency_disconnect_reachable",
            ),
            tool_clear_of_keyboard_and_phone=_boolean(
                document["tool_clear_of_keyboard_and_phone"],
                "tool_clear_of_keyboard_and_phone",
            ),
            energization_occurred_during_review=_boolean(
                document["energization_occurred_during_review"],
                "energization_occurred_during_review",
            ),
            motion_observed_during_review=_boolean(
                document["motion_observed_during_review"],
                "motion_observed_during_review",
            ),
            contact_occurred_during_review=_boolean(
                document["contact_occurred_during_review"],
                "contact_occurred_during_review",
            ),
            review_uncertain=_boolean(document["review_uncertain"], "review_uncertain"),
        )
        if (
            _digest(document["receipt_sha256"], "receipt_sha256")
            != receipt.receipt_sha256
        ):
            raise PhysicalOnboardingReceiptError("power safety receipt hash mismatch")
        return receipt


_POWER_SAFETY_BOOLEAN_FIELDS = (
    "polarity_verified",
    "arm_base_secured",
    "camera_structure_secured",
    "placemat_secured",
    "cables_restrained",
    "keepout_zone_clear",
    "emergency_disconnect_reachable",
    "tool_clear_of_keyboard_and_phone",
    "energization_occurred_during_review",
    "motion_observed_during_review",
    "contact_occurred_during_review",
    "review_uncertain",
)
_POWER_SAFETY_FIELDS = frozenset(
    {
        "schema",
        "binding",
        "operator_id",
        "reviewed_at_ns",
        "arm_power_state",
        "estop_status",
        "power_supply_output_mv",
        "power_supply_current_ma",
        "estop_test_evidence_id",
        "wiring_image_evidence_ids",
        "authority",
        "receipt_sha256",
        *_POWER_SAFETY_BOOLEAN_FIELDS,
    }
)


@dataclass(frozen=True, slots=True)
class FirstPowerObservation:
    """Evidence of one externally controlled power event, which may move the arm."""

    binding: ReceiptBinding
    event_id: str
    operator_id: str
    observer_id: str
    observed_at_ns: int
    event_started_monotonic_ns: int
    event_ended_monotonic_ns: int
    pre_event_power_state: ReviewedPowerState
    post_event_power_state: ReviewedPowerState
    outcome: FirstPowerOutcome
    effect_certainty: EffectCertainty
    startup_motion: StartupMotionClassification
    attempt_count: int
    automatic_retry_count: int
    startup_movement_warning_acknowledged: bool
    exclusion_zone_clear_before_event: bool
    estop_operator_ready_before_event: bool
    continuous_line_of_sight: bool
    controller_boot_observed: bool
    clearance_preserved: bool
    estop_activated: bool
    collision_observed: bool
    contact_observed: bool
    abnormal_condition_observed: bool
    observation_media_evidence_ids: tuple[str, ...]
    schema: str = FIRST_POWER_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != FIRST_POWER_OBSERVATION_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported first-power schema")
        if not isinstance(self.binding, ReceiptBinding) or (
            self.binding.stage is not PhysicalOnboardingStage.POWER_ON_OBSERVATION
        ):
            raise PhysicalOnboardingReceiptError(
                "first-power receipt must bind to the power_on_observation stage"
            )
        for field_name in ("event_id", "operator_id", "observer_id"):
            object.__setattr__(
                self, field_name, _identifier(getattr(self, field_name), field_name)
            )
        for field_name in (
            "observed_at_ns",
            "event_started_monotonic_ns",
            "event_ended_monotonic_ns",
        ):
            object.__setattr__(
                self,
                field_name,
                _integer(getattr(self, field_name), field_name, minimum=1),
            )
        if self.event_ended_monotonic_ns <= self.event_started_monotonic_ns:
            raise PhysicalOnboardingReceiptError(
                "first-power event end must be after its start"
            )
        for field_name in ("pre_event_power_state", "post_event_power_state"):
            if not isinstance(getattr(self, field_name), ReviewedPowerState):
                raise PhysicalOnboardingReceiptError(
                    f"{field_name} must be ReviewedPowerState"
                )
        if not isinstance(self.outcome, FirstPowerOutcome):
            raise PhysicalOnboardingReceiptError("outcome must be FirstPowerOutcome")
        if not isinstance(self.effect_certainty, EffectCertainty):
            raise PhysicalOnboardingReceiptError(
                "effect_certainty must be EffectCertainty"
            )
        if not isinstance(self.startup_motion, StartupMotionClassification):
            raise PhysicalOnboardingReceiptError(
                "startup_motion must be StartupMotionClassification"
            )
        object.__setattr__(
            self,
            "attempt_count",
            _integer(self.attempt_count, "attempt_count", maximum=100),
        )
        object.__setattr__(
            self,
            "automatic_retry_count",
            _integer(self.automatic_retry_count, "automatic_retry_count", maximum=100),
        )
        for field_name in _FIRST_POWER_BOOLEAN_FIELDS:
            _boolean(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "observation_media_evidence_ids",
            _bound_evidence_ids(
                self.observation_media_evidence_ids,
                self.binding,
                "observation_media_evidence_ids",
            ),
        )

    def core_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema": self.schema,
            "binding": self.binding.to_dict(),
            "event_id": self.event_id,
            "operator_id": self.operator_id,
            "observer_id": self.observer_id,
            "observed_at_ns": self.observed_at_ns,
            "event_started_monotonic_ns": self.event_started_monotonic_ns,
            "event_ended_monotonic_ns": self.event_ended_monotonic_ns,
            "pre_event_power_state": self.pre_event_power_state.value,
            "post_event_power_state": self.post_event_power_state.value,
            "outcome": self.outcome.value,
            "effect_certainty": self.effect_certainty.value,
            "startup_motion": self.startup_motion.value,
            "attempt_count": self.attempt_count,
            "automatic_retry_count": self.automatic_retry_count,
            "observation_media_evidence_ids": list(self.observation_media_evidence_ids),
            "authority": ZERO_PHYSICAL_AUTHORITY.to_dict(),
        }
        document.update(
            {name: getattr(self, name) for name in _FIRST_POWER_BOOLEAN_FIELDS}
        )
        return document

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.core_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "receipt_sha256": self.receipt_sha256}

    @classmethod
    def from_dict(cls, value: object) -> "FirstPowerObservation":
        document = _mapping(value, "first-power observation")
        _exact_fields(document, _FIRST_POWER_FIELDS, "first-power observation")
        if document["schema"] != FIRST_POWER_OBSERVATION_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported first-power schema")
        _validate_authority(document["authority"])
        receipt = cls(
            binding=ReceiptBinding.from_dict(document["binding"]),
            event_id=_identifier(document["event_id"], "event_id"),
            operator_id=_identifier(document["operator_id"], "operator_id"),
            observer_id=_identifier(document["observer_id"], "observer_id"),
            observed_at_ns=_integer(
                document["observed_at_ns"], "observed_at_ns", minimum=1
            ),
            event_started_monotonic_ns=_integer(
                document["event_started_monotonic_ns"],
                "event_started_monotonic_ns",
                minimum=1,
            ),
            event_ended_monotonic_ns=_integer(
                document["event_ended_monotonic_ns"],
                "event_ended_monotonic_ns",
                minimum=1,
            ),
            pre_event_power_state=_enum(
                document["pre_event_power_state"],
                ReviewedPowerState,
                "pre_event_power_state",
            ),
            post_event_power_state=_enum(
                document["post_event_power_state"],
                ReviewedPowerState,
                "post_event_power_state",
            ),
            outcome=_enum(document["outcome"], FirstPowerOutcome, "outcome"),
            effect_certainty=_enum(
                document["effect_certainty"], EffectCertainty, "effect_certainty"
            ),
            startup_motion=_enum(
                document["startup_motion"],
                StartupMotionClassification,
                "startup_motion",
            ),
            attempt_count=_integer(
                document["attempt_count"], "attempt_count", maximum=100
            ),
            automatic_retry_count=_integer(
                document["automatic_retry_count"], "automatic_retry_count", maximum=100
            ),
            observation_media_evidence_ids=tuple(
                _identifier(item, "observation_media_evidence_ids item")
                for item in _array(
                    document["observation_media_evidence_ids"],
                    "observation_media_evidence_ids",
                )
            ),
            startup_movement_warning_acknowledged=_boolean(
                document["startup_movement_warning_acknowledged"],
                "startup_movement_warning_acknowledged",
            ),
            exclusion_zone_clear_before_event=_boolean(
                document["exclusion_zone_clear_before_event"],
                "exclusion_zone_clear_before_event",
            ),
            estop_operator_ready_before_event=_boolean(
                document["estop_operator_ready_before_event"],
                "estop_operator_ready_before_event",
            ),
            continuous_line_of_sight=_boolean(
                document["continuous_line_of_sight"], "continuous_line_of_sight"
            ),
            controller_boot_observed=_boolean(
                document["controller_boot_observed"], "controller_boot_observed"
            ),
            clearance_preserved=_boolean(
                document["clearance_preserved"], "clearance_preserved"
            ),
            estop_activated=_boolean(document["estop_activated"], "estop_activated"),
            collision_observed=_boolean(
                document["collision_observed"], "collision_observed"
            ),
            contact_observed=_boolean(document["contact_observed"], "contact_observed"),
            abnormal_condition_observed=_boolean(
                document["abnormal_condition_observed"],
                "abnormal_condition_observed",
            ),
        )
        if (
            _digest(document["receipt_sha256"], "receipt_sha256")
            != receipt.receipt_sha256
        ):
            raise PhysicalOnboardingReceiptError("first-power receipt hash mismatch")
        return receipt


_FIRST_POWER_BOOLEAN_FIELDS = (
    "startup_movement_warning_acknowledged",
    "exclusion_zone_clear_before_event",
    "estop_operator_ready_before_event",
    "continuous_line_of_sight",
    "controller_boot_observed",
    "clearance_preserved",
    "estop_activated",
    "collision_observed",
    "contact_observed",
    "abnormal_condition_observed",
)
_FIRST_POWER_FIELDS = frozenset(
    {
        "schema",
        "binding",
        "event_id",
        "operator_id",
        "observer_id",
        "observed_at_ns",
        "event_started_monotonic_ns",
        "event_ended_monotonic_ns",
        "pre_event_power_state",
        "post_event_power_state",
        "outcome",
        "effect_certainty",
        "startup_motion",
        "attempt_count",
        "automatic_retry_count",
        "observation_media_evidence_ids",
        "authority",
        "receipt_sha256",
        *_FIRST_POWER_BOOLEAN_FIELDS,
    }
)


ReceiptSubject: TypeAlias = (
    CameraReceiptInspection | PowerSafetyReview | FirstPowerObservation
)


_ASSESSMENT_FACTORY_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class DiagnosticReadinessAssessment:
    """Stage-specific diagnostic result with no public generic constructor."""

    binding: ReceiptBinding
    subject_schema: str
    subject_receipt_sha256: str
    disposition: DiagnosticDisposition
    reason_codes: tuple[str, ...]

    def __init__(
        self,
        *,
        binding: ReceiptBinding,
        subject_schema: str,
        subject_receipt_sha256: str,
        disposition: DiagnosticDisposition,
        reason_codes: tuple[str, ...],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _ASSESSMENT_FACTORY_TOKEN:
            raise PhysicalOnboardingReceiptError(
                "diagnostic assessments must come from a stage-specific assessor"
            )
        object.__setattr__(self, "binding", binding)
        object.__setattr__(self, "subject_schema", subject_schema)
        object.__setattr__(self, "subject_receipt_sha256", subject_receipt_sha256)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "reason_codes", reason_codes)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ReceiptBinding):
            raise PhysicalOnboardingReceiptError("assessment binding is invalid")
        object.__setattr__(
            self, "subject_schema", _text(self.subject_schema, "subject_schema")
        )
        object.__setattr__(
            self,
            "subject_receipt_sha256",
            _digest(self.subject_receipt_sha256, "subject_receipt_sha256"),
        )
        if not isinstance(self.disposition, DiagnosticDisposition):
            raise PhysicalOnboardingReceiptError(
                "assessment disposition must be DiagnosticDisposition"
            )
        object.__setattr__(
            self, "reason_codes", _reason_codes(self.reason_codes, "reason_codes")
        )

    @property
    def diagnostic_ready(self) -> bool:
        return self.disposition is DiagnosticDisposition.DIAGNOSTIC_READY

    @property
    def hold_required(self) -> bool:
        return self.disposition is not DiagnosticDisposition.DIAGNOSTIC_READY

    @property
    def side_effect_uncertain(self) -> bool:
        return self.disposition is DiagnosticDisposition.SIDE_EFFECT_UNCERTAIN

    def core_dict(self) -> dict[str, object]:
        return {
            "schema": DIAGNOSTIC_READINESS_ASSESSMENT_SCHEMA,
            "binding": self.binding.to_dict(),
            "subject_schema": self.subject_schema,
            "subject_receipt_sha256": self.subject_receipt_sha256,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "diagnostic_ready": self.diagnostic_ready,
            "hold_required": self.hold_required,
            "side_effect_uncertain": self.side_effect_uncertain,
            "authority": ZERO_PHYSICAL_AUTHORITY.to_dict(),
        }

    @property
    def assessment_sha256(self) -> str:
        return canonical_sha256(self.core_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "assessment_sha256": self.assessment_sha256}


def _assessment(
    subject: ReceiptSubject,
    disposition: DiagnosticDisposition,
    reasons: Iterable[str],
) -> DiagnosticReadinessAssessment:
    return DiagnosticReadinessAssessment(
        binding=subject.binding,
        subject_schema=subject.schema,
        subject_receipt_sha256=subject.receipt_sha256,
        disposition=disposition,
        reason_codes=tuple(sorted(set(reasons))),
        _factory_token=_ASSESSMENT_FACTORY_TOKEN,
    )


def assess_camera_receipt(
    receipt: CameraReceiptInspection,
) -> DiagnosticReadinessAssessment:
    """Assess only the fixed B0477/16 mm receipt-inspection contract."""

    if not isinstance(receipt, CameraReceiptInspection):
        raise PhysicalOnboardingReceiptError(
            "camera assessment requires CameraReceiptInspection"
        )
    uncertain = receipt.inspection_uncertain or any(
        condition is InspectionCondition.UNCERTAIN
        for condition in (
            receipt.body_condition,
            receipt.lens_condition,
            receipt.connector_condition,
        )
    )
    if uncertain:
        # A passive visual inspection has no physical side effect to reconcile;
        # uncertainty therefore creates a HOLD, not a side-effect-uncertain state.
        return _assessment(
            receipt,
            DiagnosticDisposition.HOLD,
            ("CAMERA_RECEIPT_INSPECTION_UNCERTAIN",),
        )
    reasons: list[str] = []
    if (
        receipt.observed_manufacturer.casefold()
        != EXPECTED_CAMERA_MANUFACTURER.casefold()
    ):
        reasons.append("CAMERA_MANUFACTURER_MISMATCH")
    if receipt.observed_product_id.upper() != EXPECTED_CAMERA_PRODUCT_ID:
        reasons.append("CAMERA_PRODUCT_ID_MISMATCH")
    if receipt.observed_lens_focal_length_mm != EXPECTED_CAMERA_LENS_FOCAL_LENGTH_MM:
        reasons.append("CAMERA_LENS_FOCAL_LENGTH_MISMATCH")
    if any(
        condition is not InspectionCondition.ACCEPTABLE
        for condition in (
            receipt.body_condition,
            receipt.lens_condition,
            receipt.connector_condition,
        )
    ):
        reasons.append("CAMERA_OR_LENS_DAMAGE_OBSERVED")
    if not receipt.identity_label_legible:
        reasons.append("CAMERA_IDENTITY_LABEL_NOT_LEGIBLE")
    if not receipt.purchase_record_matches:
        reasons.append("CAMERA_PURCHASE_RECORD_MISMATCH")
    if not receipt.package_contents_complete:
        reasons.append("CAMERA_PACKAGE_CONTENTS_INCOMPLETE")
    return _assessment(
        receipt,
        (
            DiagnosticDisposition.HOLD
            if reasons
            else DiagnosticDisposition.DIAGNOSTIC_READY
        ),
        reasons or ("B0477_RECEIPT_INSPECTION_DIAGNOSTICALLY_READY",),
    )


def assess_power_safety(
    receipt: PowerSafetyReview,
) -> DiagnosticReadinessAssessment:
    """Assess the power-off review without authorizing a future power event."""

    if not isinstance(receipt, PowerSafetyReview):
        raise PhysicalOnboardingReceiptError(
            "power-safety assessment requires PowerSafetyReview"
        )
    if (
        receipt.review_uncertain
        or receipt.arm_power_state is ReviewedPowerState.UNKNOWN
    ):
        return _assessment(
            receipt,
            DiagnosticDisposition.HOLD,
            ("POWER_SAFETY_REVIEW_UNCERTAIN",),
        )
    reasons: list[str] = []
    if receipt.arm_power_state is not ReviewedPowerState.DISCONNECTED_CONFIRMED:
        reasons.append("ARM_POWER_NOT_DISCONNECTED_FOR_REVIEW")
    if receipt.estop_status not in {
        EstopReviewStatus.POWER_OFF_CONTINUITY_VERIFIED,
        EstopReviewStatus.BOUND_PRIOR_TEST_EVIDENCE,
    }:
        reasons.append("ESTOP_NOT_VERIFIED")
    if receipt.power_supply_output_mv != EXPECTED_POWER_SUPPLY_OUTPUT_MV:
        reasons.append("POWER_SUPPLY_OUTPUT_NOT_12000_MV")
    if receipt.power_supply_current_ma < MINIMUM_POWER_SUPPLY_CURRENT_MA:
        reasons.append("POWER_SUPPLY_CURRENT_BELOW_5000_MA")
    readiness_checks = {
        "POLARITY_NOT_VERIFIED": receipt.polarity_verified,
        "ARM_BASE_NOT_SECURED": receipt.arm_base_secured,
        "CAMERA_STRUCTURE_NOT_SECURED": receipt.camera_structure_secured,
        "PLACEMAT_NOT_SECURED": receipt.placemat_secured,
        "CABLES_NOT_RESTRAINED": receipt.cables_restrained,
        "KEEPOUT_ZONE_NOT_CLEAR": receipt.keepout_zone_clear,
        "EMERGENCY_DISCONNECT_NOT_REACHABLE": receipt.emergency_disconnect_reachable,
        "TOOL_NOT_CLEAR_OF_DEVICES": receipt.tool_clear_of_keyboard_and_phone,
    }
    reasons.extend(
        code for code, satisfied in readiness_checks.items() if not satisfied
    )
    if receipt.energization_occurred_during_review:
        reasons.append("UNPLANNED_ENERGIZATION_DURING_POWER_OFF_REVIEW")
    if receipt.motion_observed_during_review:
        reasons.append("MOTION_DURING_POWER_OFF_REVIEW")
    if receipt.contact_occurred_during_review:
        reasons.append("CONTACT_DURING_POWER_OFF_REVIEW")
    return _assessment(
        receipt,
        (
            DiagnosticDisposition.HOLD
            if reasons
            else DiagnosticDisposition.DIAGNOSTIC_READY
        ),
        reasons or ("POWER_OFF_SAFETY_REVIEW_DIAGNOSTICALLY_READY",),
    )


def assess_first_power_observation(
    receipt: FirstPowerObservation,
) -> DiagnosticReadinessAssessment:
    """Assess one observed event; expected startup motion is still recorded motion."""

    if not isinstance(receipt, FirstPowerObservation):
        raise PhysicalOnboardingReceiptError(
            "first-power assessment requires FirstPowerObservation"
        )
    uncertain = (
        receipt.effect_certainty is EffectCertainty.UNCERTAIN
        or receipt.outcome is FirstPowerOutcome.EFFECT_UNCERTAIN
        or receipt.startup_motion is StartupMotionClassification.UNKNOWN
        or receipt.post_event_power_state is ReviewedPowerState.UNKNOWN
        or not receipt.continuous_line_of_sight
    )
    if uncertain:
        return _assessment(
            receipt,
            DiagnosticDisposition.SIDE_EFFECT_UNCERTAIN,
            ("FIRST_POWER_SIDE_EFFECT_UNCERTAIN",),
        )
    reasons: list[str] = []
    if receipt.pre_event_power_state is not ReviewedPowerState.DISCONNECTED_CONFIRMED:
        reasons.append("FIRST_POWER_PRESTATE_NOT_DISCONNECTED")
    if receipt.post_event_power_state is not ReviewedPowerState.DISCONNECTED_CONFIRMED:
        reasons.append("FIRST_POWER_POSTSTATE_NOT_DISCONNECTED")
    if receipt.attempt_count != 1:
        reasons.append("FIRST_POWER_ATTEMPT_COUNT_NOT_ONE")
    if receipt.automatic_retry_count != 0:
        reasons.append("FIRST_POWER_AUTOMATIC_RETRY_FORBIDDEN")
    prerequisites = {
        "STARTUP_MOVEMENT_WARNING_NOT_ACKNOWLEDGED": (
            receipt.startup_movement_warning_acknowledged
        ),
        "EXCLUSION_ZONE_NOT_CLEAR_BEFORE_POWER": (
            receipt.exclusion_zone_clear_before_event
        ),
        "ESTOP_OPERATOR_NOT_READY_BEFORE_POWER": (
            receipt.estop_operator_ready_before_event
        ),
        "CONTROLLER_BOOT_NOT_OBSERVED": receipt.controller_boot_observed,
        "CLEARANCE_NOT_PRESERVED": receipt.clearance_preserved,
    }
    reasons.extend(code for code, satisfied in prerequisites.items() if not satisfied)
    if receipt.outcome is not FirstPowerOutcome.COMPLETED_OBSERVATION:
        reasons.append("FIRST_POWER_OBSERVATION_NOT_COMPLETED")
    if receipt.startup_motion is StartupMotionClassification.UNEXPECTED_OR_UNBOUNDED:
        reasons.append("UNEXPECTED_OR_UNBOUNDED_STARTUP_MOTION")
    if receipt.estop_activated:
        reasons.append("ESTOP_ACTIVATED_DURING_FIRST_POWER")
    if receipt.collision_observed:
        reasons.append("COLLISION_DURING_FIRST_POWER")
    if receipt.contact_observed:
        reasons.append("CONTACT_DURING_FIRST_POWER")
    if receipt.abnormal_condition_observed:
        reasons.append("ABNORMAL_CONDITION_DURING_FIRST_POWER")
    ready_reason = (
        "FIRST_POWER_EXPECTED_STARTUP_MOTION_SAFELY_OBSERVED"
        if receipt.startup_motion
        is StartupMotionClassification.EXPECTED_AUTOMATIC_REPOSITIONING
        else "FIRST_POWER_NO_STARTUP_MOTION_SAFELY_OBSERVED"
    )
    return _assessment(
        receipt,
        (
            DiagnosticDisposition.HOLD
            if reasons
            else DiagnosticDisposition.DIAGNOSTIC_READY
        ),
        reasons or (ready_reason,),
    )


_SUBJECT_SCHEMAS_BY_STAGE: dict[PhysicalOnboardingStage, str] = {
    PhysicalOnboardingStage.CAMERA_RECEIPT: CAMERA_RECEIPT_INSPECTION_SCHEMA,
    PhysicalOnboardingStage.POWER_SAFETY: POWER_SAFETY_REVIEW_SCHEMA,
    PhysicalOnboardingStage.POWER_ON_OBSERVATION: FIRST_POWER_OBSERVATION_SCHEMA,
}


@dataclass(frozen=True, slots=True)
class ControlledOperatorDecision:
    """A review bound to an assessment; it can never improve its disposition."""

    binding: ReceiptBinding
    reviewer_id: str
    decided_at_ns: int
    decision: OperatorDecisionKind
    subject_schema: str
    subject_receipt_sha256: str
    subject_assessment_sha256: str
    subject_disposition: DiagnosticDisposition
    reason_codes: tuple[str, ...]
    decision_evidence_id: str
    schema: str = CONTROLLED_OPERATOR_DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CONTROLLED_OPERATOR_DECISION_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported operator-decision schema")
        if not isinstance(self.binding, ReceiptBinding) or (
            self.binding.stage not in _SUBJECT_SCHEMAS_BY_STAGE
        ):
            raise PhysicalOnboardingReceiptError(
                "operator decision supports only camera receipt, power safety, and first power"
            )
        object.__setattr__(
            self, "reviewer_id", _identifier(self.reviewer_id, "reviewer_id")
        )
        object.__setattr__(
            self,
            "decided_at_ns",
            _integer(self.decided_at_ns, "decided_at_ns", minimum=1),
        )
        if not isinstance(self.decision, OperatorDecisionKind):
            raise PhysicalOnboardingReceiptError(
                "decision must be OperatorDecisionKind"
            )
        if (
            self.decision is OperatorDecisionKind.ESCALATE_SIDE_EFFECT_UNCERTAINTY
            and self.binding.stage is not PhysicalOnboardingStage.POWER_ON_OBSERVATION
        ):
            raise PhysicalOnboardingReceiptError(
                "side-effect uncertainty escalation is limited to first power"
            )
        expected_schema = _SUBJECT_SCHEMAS_BY_STAGE[self.binding.stage]
        object.__setattr__(
            self, "subject_schema", _text(self.subject_schema, "subject_schema")
        )
        if self.subject_schema != expected_schema:
            raise PhysicalOnboardingReceiptError(
                "operator-decision subject schema does not match its stage"
            )
        for field_name in ("subject_receipt_sha256", "subject_assessment_sha256"):
            object.__setattr__(
                self, field_name, _digest(getattr(self, field_name), field_name)
            )
        if not isinstance(self.subject_disposition, DiagnosticDisposition):
            raise PhysicalOnboardingReceiptError(
                "subject_disposition must be DiagnosticDisposition"
            )
        object.__setattr__(
            self, "reason_codes", _reason_codes(self.reason_codes, "reason_codes")
        )
        object.__setattr__(
            self,
            "decision_evidence_id",
            _identifier(self.decision_evidence_id, "decision_evidence_id"),
        )
        if self.decision_evidence_id not in self.binding.evidence_ids:
            raise PhysicalOnboardingReceiptError(
                "operator decision evidence is outside the stage binding"
            )

    def core_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "binding": self.binding.to_dict(),
            "reviewer_id": self.reviewer_id,
            "decided_at_ns": self.decided_at_ns,
            "decision": self.decision.value,
            "subject_schema": self.subject_schema,
            "subject_receipt_sha256": self.subject_receipt_sha256,
            "subject_assessment_sha256": self.subject_assessment_sha256,
            "subject_disposition": self.subject_disposition.value,
            "reason_codes": list(self.reason_codes),
            "decision_evidence_id": self.decision_evidence_id,
            "authority": ZERO_PHYSICAL_AUTHORITY.to_dict(),
        }

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self.core_dict())

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "receipt_sha256": self.receipt_sha256}

    @classmethod
    def from_dict(cls, value: object) -> "ControlledOperatorDecision":
        document = _mapping(value, "controlled operator decision")
        _exact_fields(
            document, _OPERATOR_DECISION_FIELDS, "controlled operator decision"
        )
        if document["schema"] != CONTROLLED_OPERATOR_DECISION_SCHEMA:
            raise PhysicalOnboardingReceiptError("unsupported operator-decision schema")
        _validate_authority(document["authority"])
        receipt = cls(
            binding=ReceiptBinding.from_dict(document["binding"]),
            reviewer_id=_identifier(document["reviewer_id"], "reviewer_id"),
            decided_at_ns=_integer(
                document["decided_at_ns"], "decided_at_ns", minimum=1
            ),
            decision=_enum(document["decision"], OperatorDecisionKind, "decision"),
            subject_schema=_text(document["subject_schema"], "subject_schema"),
            subject_receipt_sha256=_digest(
                document["subject_receipt_sha256"], "subject_receipt_sha256"
            ),
            subject_assessment_sha256=_digest(
                document["subject_assessment_sha256"], "subject_assessment_sha256"
            ),
            subject_disposition=_enum(
                document["subject_disposition"],
                DiagnosticDisposition,
                "subject_disposition",
            ),
            reason_codes=_parse_reason_codes(document["reason_codes"], "reason_codes"),
            decision_evidence_id=_identifier(
                document["decision_evidence_id"], "decision_evidence_id"
            ),
        )
        if (
            _digest(document["receipt_sha256"], "receipt_sha256")
            != receipt.receipt_sha256
        ):
            raise PhysicalOnboardingReceiptError("operator decision hash mismatch")
        return receipt


_OPERATOR_DECISION_FIELDS = frozenset(
    {
        "schema",
        "binding",
        "reviewer_id",
        "decided_at_ns",
        "decision",
        "subject_schema",
        "subject_receipt_sha256",
        "subject_assessment_sha256",
        "subject_disposition",
        "reason_codes",
        "decision_evidence_id",
        "authority",
        "receipt_sha256",
    }
)


def assess_operator_decision(
    decision: ControlledOperatorDecision,
    subject: ReceiptSubject,
    assessment: DiagnosticReadinessAssessment,
) -> DiagnosticReadinessAssessment:
    """Validate a reviewer decision without allowing it to upgrade a HOLD."""

    if not isinstance(decision, ControlledOperatorDecision):
        raise PhysicalOnboardingReceiptError(
            "operator-decision assessment requires ControlledOperatorDecision"
        )
    if not isinstance(
        subject, (CameraReceiptInspection, PowerSafetyReview, FirstPowerObservation)
    ):
        raise PhysicalOnboardingReceiptError("unsupported operator-decision subject")
    if not isinstance(assessment, DiagnosticReadinessAssessment):
        raise PhysicalOnboardingReceiptError("subject assessment is invalid")
    if (
        decision.binding != subject.binding
        or assessment.binding != subject.binding
        or decision.subject_schema != subject.schema
        or assessment.subject_schema != subject.schema
        or decision.subject_receipt_sha256 != subject.receipt_sha256
        or assessment.subject_receipt_sha256 != subject.receipt_sha256
        or decision.subject_assessment_sha256 != assessment.assessment_sha256
        or decision.subject_disposition is not assessment.disposition
    ):
        raise PhysicalOnboardingReceiptError(
            "operator decision is not exactly bound to its subject and assessment"
        )

    if decision.decision is OperatorDecisionKind.ESCALATE_SIDE_EFFECT_UNCERTAINTY:
        disposition = DiagnosticDisposition.SIDE_EFFECT_UNCERTAIN
        reasons = set(decision.reason_codes) | {
            "OPERATOR_ESCALATED_SIDE_EFFECT_UNCERTAINTY"
        }
    elif decision.decision is OperatorDecisionKind.PLACE_HOLD:
        disposition = DiagnosticDisposition.HOLD
        reasons = set(decision.reason_codes) | {"OPERATOR_PLACED_HOLD"}
    elif assessment.disposition is DiagnosticDisposition.DIAGNOSTIC_READY:
        disposition = DiagnosticDisposition.DIAGNOSTIC_READY
        reasons = set(decision.reason_codes) | {
            "OPERATOR_ACKNOWLEDGED_DIAGNOSTIC_READINESS"
        }
    else:
        # An acknowledgement cannot transform HOLD or uncertainty into readiness.
        disposition = assessment.disposition
        reasons = set(decision.reason_codes) | {
            "OPERATOR_CANNOT_UPGRADE_SUBJECT_ASSESSMENT"
        }

    return DiagnosticReadinessAssessment(
        binding=decision.binding,
        subject_schema=decision.schema,
        subject_receipt_sha256=decision.receipt_sha256,
        disposition=disposition,
        reason_codes=tuple(sorted(reasons)),
        _factory_token=_ASSESSMENT_FACTORY_TOKEN,
    )


ReceiptRecord: TypeAlias = (
    CameraReceiptInspection
    | PowerSafetyReview
    | FirstPowerObservation
    | ControlledOperatorDecision
)


def receipt_json_bytes(receipt: ReceiptRecord) -> bytes:
    """Serialize a supported receipt; assessments are deliberately separate."""

    if not isinstance(
        receipt,
        (
            CameraReceiptInspection,
            PowerSafetyReview,
            FirstPowerObservation,
            ControlledOperatorDecision,
        ),
    ):
        raise PhysicalOnboardingReceiptError("unsupported receipt type")
    return canonical_json_bytes(receipt.to_dict())


def parse_receipt_json(payload: bytes) -> ReceiptRecord:
    """Strictly parse one canonical receipt with duplicate/float rejection."""

    if not isinstance(payload, bytes):
        raise PhysicalOnboardingReceiptError("receipt payload must be bytes")
    if len(payload) > MAX_JSON_BYTES:
        raise PhysicalOnboardingReceiptError("receipt exceeds the JSON resource limit")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingReceiptError(
            "receipt is not strict UTF-8 JSON"
        ) from exc
    document = _mapping(value, "receipt")
    if canonical_json_bytes(dict(document)) != payload:
        raise PhysicalOnboardingReceiptError("receipt JSON is not canonical")
    schema = document.get("schema")
    if schema == CAMERA_RECEIPT_INSPECTION_SCHEMA:
        return CameraReceiptInspection.from_dict(document)
    if schema == POWER_SAFETY_REVIEW_SCHEMA:
        return PowerSafetyReview.from_dict(document)
    if schema == FIRST_POWER_OBSERVATION_SCHEMA:
        return FirstPowerObservation.from_dict(document)
    if schema == CONTROLLED_OPERATOR_DECISION_SCHEMA:
        return ControlledOperatorDecision.from_dict(document)
    raise PhysicalOnboardingReceiptError("unsupported receipt schema")


__all__ = [
    "CAMERA_RECEIPT_INSPECTION_SCHEMA",
    "CONTROLLED_OPERATOR_DECISION_SCHEMA",
    "DIAGNOSTIC_READINESS_ASSESSMENT_SCHEMA",
    "EXPECTED_CAMERA_LENS_FOCAL_LENGTH_MM",
    "EXPECTED_CAMERA_MANUFACTURER",
    "EXPECTED_CAMERA_PRODUCT_ID",
    "EXPECTED_POWER_SUPPLY_OUTPUT_MV",
    "FIRST_POWER_OBSERVATION_SCHEMA",
    "MINIMUM_POWER_SUPPLY_CURRENT_MA",
    "POWER_SAFETY_REVIEW_SCHEMA",
    "BoundEvidence",
    "CameraReceiptInspection",
    "ControlledOperatorDecision",
    "DiagnosticDisposition",
    "DiagnosticReadinessAssessment",
    "EffectCertainty",
    "EstopReviewStatus",
    "FirstPowerObservation",
    "FirstPowerOutcome",
    "InspectionCondition",
    "OperatorDecisionKind",
    "PhysicalOnboardingReceiptError",
    "PowerSafetyReview",
    "ReceiptBinding",
    "ReceiptRecord",
    "ReceiptSubject",
    "ReviewedPowerState",
    "StartupMotionClassification",
    "ZERO_PHYSICAL_AUTHORITY",
    "ZeroPhysicalAuthority",
    "assess_camera_receipt",
    "assess_first_power_observation",
    "assess_operator_decision",
    "assess_power_safety",
    "canonical_json_bytes",
    "canonical_sha256",
    "parse_receipt_json",
    "receipt_json_bytes",
]
