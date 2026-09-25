"""Bounded, zero-authority board-pose correction decisions.

This module is deliberately smaller than a correction *executor*.  It accepts
an immutable arm-camera measurement, derives the candidate ``Wv_T_board``
registration, and classifies the candidate as ``NO_CHANGE``, ``APPLY``, or
``REJECT``.  It never plans a trajectory, sends a command, changes a live
registration, or grants physical authority.

Frame names and transform directions are strict:

* :class:`BoardRegistration` stores exactly ``Wv_T_board``;
* :class:`ArmCameraBoardMeasurement` stores exactly ``Wv_T_C_arm`` and
  ``C_arm_T_board``; and
* the candidate is exactly ``Wv_T_C_arm * C_arm_T_board``.

All distances are millimetres, angles are radians, and timestamps are integer
nanoseconds on the explicitly named measurement clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any

from rocell.geometry.transforms import RigidTransform
from rocell.vision.camera import TimestampQuality


BOARD_REGISTRATION_SCHEMA = "rocell.board_registration.v1"
ARM_CAMERA_BOARD_MEASUREMENT_SCHEMA = "rocell.arm_camera_board_measurement.v1"
BOARD_POSE_CORRECTION_POLICY_SCHEMA = "rocell.board_pose_correction_policy.v1"
BOARD_POSE_CORRECTION_DECISION_SCHEMA = "rocell.board_pose_correction_decision.v1"

VENDOR_WORLD_FRAME = "Wv"
ARM_CAMERA_FRAME = "C_arm"
BOARD_FRAME = "board"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_IDENTIFIER_LENGTH = 256
_MAX_SOURCE_HASHES = 64
_MAX_SEQUENCE = (1 << 63) - 1
_MAX_REGISTRATION_REVISION = 1_000_000_000
_MAX_TRANSLATION_LIMIT_MM = 10_000.0
_MAX_REPROJECTION_RMSE_PX = 1_000_000.0
_MAX_TIMING_LIMIT_NS = 60_000_000_000
_MAX_INLIER_TAGS = 4_096
_MAX_JOINT_MOTION_RAD = 2.0 * math.pi
_YAW_PROJECTION_EPSILON = 1.0e-12

_QUALIFIED_TIMESTAMP_QUALITIES = (
    TimestampQuality.DEVICE_EXPOSURE,
    TimestampQuality.SETTLED_BRACKET,
)


class BoardPoseCorrectionError(ValueError):
    """A correction input violates the bounded pure-decision contract."""


class BoardPoseCorrectionStatus(str, Enum):
    """The only possible outcomes of the pure decision layer."""

    NO_CHANGE = "NO_CHANGE"
    APPLY = "APPLY"
    REJECT = "REJECT"


def _authority() -> dict[str, object]:
    """Return the exact zero-authority declaration for every artifact."""

    return {
        "execution_mode": "VIRTUAL",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _identifier(value: object, label: str, *, maximum: int = _MAX_IDENTIFIER_LENGTH) -> str:
    if not isinstance(value, str) or not value:
        raise BoardPoseCorrectionError(f"{label} must be non-empty text")
    if value != value.strip():
        raise BoardPoseCorrectionError(f"{label} must not have surrounding whitespace")
    if len(value) > maximum:
        raise BoardPoseCorrectionError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise BoardPoseCorrectionError(f"{label} contains a control character")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BoardPoseCorrectionError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = _MAX_SEQUENCE,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BoardPoseCorrectionError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise BoardPoseCorrectionError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return value


def _finite(
    value: object,
    label: str,
    *,
    minimum: float = 0.0,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BoardPoseCorrectionError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BoardPoseCorrectionError(f"{label} must be finite")
    if not minimum <= parsed <= maximum:
        raise BoardPoseCorrectionError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return parsed


def _source_hashes(
    value: object,
    label: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise BoardPoseCorrectionError(f"{label} must be an immutable tuple")
    if not 1 <= len(value) <= _MAX_SOURCE_HASHES:
        raise BoardPoseCorrectionError(
            f"{label} must contain between 1 and {_MAX_SOURCE_HASHES} entries"
        )
    parsed: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, tuple) or len(item) != 2:
            raise BoardPoseCorrectionError(
                f"{label}[{index}] must be an immutable name/digest pair"
            )
        name = _identifier(item[0], f"{label}[{index}] name")
        digest = _digest(item[1], f"{label}[{index}] digest")
        parsed.append((name, digest))
    names = tuple(name for name, _ in parsed)
    if len(names) != len(set(names)):
        raise BoardPoseCorrectionError(f"{label} contains a duplicate source name")
    return tuple(sorted(parsed))


def _transform_dict(value: RigidTransform) -> dict[str, object]:
    return {
        "to_frame": value.parent_frame,
        "from_frame": value.child_frame,
        "rotation_row_major": list(value.rotation.matrix),
        "translation_mm": [
            value.translation_mm.x,
            value.translation_mm.y,
            value.translation_mm.z,
        ],
    }


def _require_transform(
    value: object,
    *,
    parent_frame: str,
    child_frame: str,
    label: str,
) -> RigidTransform:
    if not isinstance(value, RigidTransform):
        raise TypeError(f"{label} must be a RigidTransform")
    if value.parent_frame != parent_frame or value.child_frame != child_frame:
        raise BoardPoseCorrectionError(
            f"{label} must be exactly {parent_frame}_T_{child_frame}; got "
            f"{value.parent_frame}_T_{value.child_frame}"
        )
    return value


@dataclass(frozen=True, slots=True)
class BoardRegistration:
    """One immutable candidate or active ``Wv_T_board`` registration."""

    revision: int
    Wv_T_board: RigidTransform
    source_hashes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "revision",
            _integer(
                self.revision,
                "registration revision",
                maximum=_MAX_REGISTRATION_REVISION,
            ),
        )
        _require_transform(
            self.Wv_T_board,
            parent_frame=VENDOR_WORLD_FRAME,
            child_frame=BOARD_FRAME,
            label="Wv_T_board",
        )
        object.__setattr__(
            self,
            "source_hashes",
            _source_hashes(self.source_hashes, "registration source_hashes"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": BOARD_REGISTRATION_SCHEMA,
            "revision": self.revision,
            "Wv_T_board": _transform_dict(self.Wv_T_board),
            "source_hashes": dict(self.source_hashes),
            "authority": _authority(),
        }

    @property
    def registration_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ArmCameraBoardMeasurement:
    """One exposure-correlated arm-camera board-pose measurement.

    The two transforms are inputs from independent FK/extrinsic and vision
    boundaries.  ``Wv_T_board_candidate`` is derived, never supplied by the
    caller.  Freshness is proven by both an advancing source sequence and a
    changed source token; a repeated value remains constructible so the
    decision can return an auditable ``REJECT`` rather than throwing it away.
    """

    measurement_id: str
    Wv_T_C_arm: RigidTransform
    C_arm_T_board: RigidTransform
    timing_clock: str
    timestamp_quality: TimestampQuality
    feedback_before_timestamp_ns: int
    exposure_timestamp_ns: int
    feedback_after_timestamp_ns: int
    evaluated_at_timestamp_ns: int
    maximum_joint_motion_during_bracket_rad: float
    source_sequence: int
    previous_source_sequence: int
    freshness_token: str
    previous_freshness_token: str
    inlier_tag_count: int
    inlier_reprojection_rmse_px: float
    source_hashes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "measurement_id",
            _identifier(self.measurement_id, "measurement_id"),
        )
        _require_transform(
            self.Wv_T_C_arm,
            parent_frame=VENDOR_WORLD_FRAME,
            child_frame=ARM_CAMERA_FRAME,
            label="Wv_T_C_arm",
        )
        _require_transform(
            self.C_arm_T_board,
            parent_frame=ARM_CAMERA_FRAME,
            child_frame=BOARD_FRAME,
            label="C_arm_T_board",
        )
        object.__setattr__(
            self,
            "timing_clock",
            _identifier(self.timing_clock, "timing_clock"),
        )
        if not isinstance(self.timestamp_quality, TimestampQuality):
            try:
                object.__setattr__(
                    self,
                    "timestamp_quality",
                    TimestampQuality(self.timestamp_quality),
                )
            except (TypeError, ValueError) as exc:
                raise BoardPoseCorrectionError(
                    "timestamp_quality is unsupported"
                ) from exc
        for name in (
            "feedback_before_timestamp_ns",
            "exposure_timestamp_ns",
            "feedback_after_timestamp_ns",
            "evaluated_at_timestamp_ns",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        if not (
            self.feedback_before_timestamp_ns
            <= self.exposure_timestamp_ns
            <= self.feedback_after_timestamp_ns
            <= self.evaluated_at_timestamp_ns
        ):
            raise BoardPoseCorrectionError(
                "timing must satisfy feedback_before <= exposure <= "
                "feedback_after <= evaluated_at on one clock"
            )
        object.__setattr__(
            self,
            "maximum_joint_motion_during_bracket_rad",
            _finite(
                self.maximum_joint_motion_during_bracket_rad,
                "maximum_joint_motion_during_bracket_rad",
                maximum=_MAX_JOINT_MOTION_RAD,
            ),
        )
        object.__setattr__(
            self,
            "source_sequence",
            _integer(self.source_sequence, "source_sequence"),
        )
        object.__setattr__(
            self,
            "previous_source_sequence",
            _integer(self.previous_source_sequence, "previous_source_sequence"),
        )
        object.__setattr__(
            self,
            "freshness_token",
            _identifier(self.freshness_token, "freshness_token", maximum=1_024),
        )
        object.__setattr__(
            self,
            "previous_freshness_token",
            _identifier(
                self.previous_freshness_token,
                "previous_freshness_token",
                maximum=1_024,
            ),
        )
        object.__setattr__(
            self,
            "inlier_tag_count",
            _integer(
                self.inlier_tag_count,
                "inlier_tag_count",
                maximum=_MAX_INLIER_TAGS,
            ),
        )
        object.__setattr__(
            self,
            "inlier_reprojection_rmse_px",
            _finite(
                self.inlier_reprojection_rmse_px,
                "inlier_reprojection_rmse_px",
                maximum=_MAX_REPROJECTION_RMSE_PX,
            ),
        )
        object.__setattr__(
            self,
            "source_hashes",
            _source_hashes(self.source_hashes, "measurement source_hashes"),
        )

    @property
    def Wv_T_board_candidate(self) -> RigidTransform:
        """Derive ``Wv_T_board`` without changing either source direction."""

        return self.Wv_T_C_arm.compose(self.C_arm_T_board)

    @property
    def pose_age_ns(self) -> int:
        return self.evaluated_at_timestamp_ns - self.exposure_timestamp_ns

    @property
    def feedback_bracket_ns(self) -> int:
        return (
            self.feedback_after_timestamp_ns
            - self.feedback_before_timestamp_ns
        )

    @property
    def freshness_advanced(self) -> bool:
        return (
            self.source_sequence > self.previous_source_sequence
            and self.freshness_token != self.previous_freshness_token
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ARM_CAMERA_BOARD_MEASUREMENT_SCHEMA,
            "measurement_id": self.measurement_id,
            "Wv_T_C_arm": _transform_dict(self.Wv_T_C_arm),
            "C_arm_T_board": _transform_dict(self.C_arm_T_board),
            "derived_Wv_T_board_candidate": _transform_dict(
                self.Wv_T_board_candidate
            ),
            "timing": {
                "clock": self.timing_clock,
                "timestamp_quality": self.timestamp_quality.value,
                "feedback_before_ns": self.feedback_before_timestamp_ns,
                "exposure_ns": self.exposure_timestamp_ns,
                "feedback_after_ns": self.feedback_after_timestamp_ns,
                "evaluated_at_ns": self.evaluated_at_timestamp_ns,
                "pose_age_ns": self.pose_age_ns,
                "feedback_bracket_ns": self.feedback_bracket_ns,
                "maximum_joint_motion_during_bracket_rad": (
                    self.maximum_joint_motion_during_bracket_rad
                ),
            },
            "freshness": {
                "source_sequence": self.source_sequence,
                "previous_source_sequence": self.previous_source_sequence,
                "token": self.freshness_token,
                "previous_token": self.previous_freshness_token,
                "advanced": self.freshness_advanced,
            },
            "pose_metrics": {
                "inlier_tag_count": self.inlier_tag_count,
                "inlier_reprojection_rmse_px": self.inlier_reprojection_rmse_px,
            },
            "source_hashes": dict(self.source_hashes),
            "authority": _authority(),
        }

    @property
    def measurement_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class BoardPoseCorrectionPolicy:
    """Finite hard limits and deadbands for one virtual decision."""

    translation_deadband_mm: float = 0.1
    maximum_translation_delta_mm: float = 15.0
    yaw_deadband_rad: float = math.radians(0.1)
    maximum_yaw_delta_rad: float = math.radians(5.0)
    tilt_deadband_rad: float = math.radians(0.1)
    maximum_tilt_delta_rad: float = math.radians(3.0)
    minimum_inlier_tags: int = 4
    maximum_inlier_reprojection_rmse_px: float = 2.0
    maximum_pose_age_ns: int = 250_000_000
    maximum_feedback_bracket_ns: int = 100_000_000
    maximum_joint_motion_during_bracket_rad: float = 0.005

    def __post_init__(self) -> None:
        for name, maximum in (
            ("translation_deadband_mm", _MAX_TRANSLATION_LIMIT_MM),
            ("maximum_translation_delta_mm", _MAX_TRANSLATION_LIMIT_MM),
            ("yaw_deadband_rad", math.pi),
            ("maximum_yaw_delta_rad", math.pi),
            ("tilt_deadband_rad", math.pi / 2.0),
            ("maximum_tilt_delta_rad", math.pi / 2.0),
            (
                "maximum_inlier_reprojection_rmse_px",
                _MAX_REPROJECTION_RMSE_PX,
            ),
            (
                "maximum_joint_motion_during_bracket_rad",
                _MAX_JOINT_MOTION_RAD,
            ),
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name, maximum=maximum),
            )
        if self.translation_deadband_mm > self.maximum_translation_delta_mm:
            raise BoardPoseCorrectionError(
                "translation deadband cannot exceed its rejection limit"
            )
        if self.yaw_deadband_rad > self.maximum_yaw_delta_rad:
            raise BoardPoseCorrectionError(
                "yaw deadband cannot exceed its rejection limit"
            )
        if self.tilt_deadband_rad > self.maximum_tilt_delta_rad:
            raise BoardPoseCorrectionError(
                "tilt deadband cannot exceed its rejection limit"
            )
        if self.maximum_tilt_delta_rad >= math.pi / 2.0:
            raise BoardPoseCorrectionError(
                "maximum_tilt_delta_rad must be less than pi/2 so yaw remains observable"
            )
        object.__setattr__(
            self,
            "minimum_inlier_tags",
            _integer(
                self.minimum_inlier_tags,
                "minimum_inlier_tags",
                minimum=1,
                maximum=_MAX_INLIER_TAGS,
            ),
        )
        for name in ("maximum_pose_age_ns", "maximum_feedback_bracket_ns"):
            object.__setattr__(
                self,
                name,
                _integer(
                    getattr(self, name),
                    name,
                    minimum=1,
                    maximum=_MAX_TIMING_LIMIT_NS,
                ),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": BOARD_POSE_CORRECTION_POLICY_SCHEMA,
            "translation_deadband_mm": self.translation_deadband_mm,
            "maximum_translation_delta_mm": self.maximum_translation_delta_mm,
            "yaw_deadband_rad": self.yaw_deadband_rad,
            "maximum_yaw_delta_rad": self.maximum_yaw_delta_rad,
            "tilt_deadband_rad": self.tilt_deadband_rad,
            "maximum_tilt_delta_rad": self.maximum_tilt_delta_rad,
            "minimum_inlier_tags": self.minimum_inlier_tags,
            "maximum_inlier_reprojection_rmse_px": (
                self.maximum_inlier_reprojection_rmse_px
            ),
            "maximum_pose_age_ns": self.maximum_pose_age_ns,
            "maximum_feedback_bracket_ns": self.maximum_feedback_bracket_ns,
            "maximum_joint_motion_during_bracket_rad": (
                self.maximum_joint_motion_during_bracket_rad
            ),
            "qualified_timestamp_qualities": [
                item.value for item in _QUALIFIED_TIMESTAMP_QUALITIES
            ],
            "decision_semantics": {
                "limits_are_inclusive": True,
                "values_are_never_clamped": True,
                "translation_metric": "NORM_OF_B_ACTIVE_T_B_CANDIDATE_TRANSLATION_MM",
                "yaw_metric": "ABS_ATAN2_R10_R00_ABOUT_ACTIVE_BOARD_Z_RAD",
                "tilt_metric": "ANGLE_BETWEEN_ACTIVE_AND_CANDIDATE_BOARD_Z_RAD",
            },
            "authority": _authority(),
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


def _correction_metrics(
    active: BoardRegistration,
    candidate: BoardRegistration,
) -> tuple[tuple[float, float, float], float, float, float]:
    relative = active.Wv_T_board.inverse().compose(candidate.Wv_T_board)
    translation = relative.translation_mm
    translation_tuple = (translation.x, translation.y, translation.z)
    translation_norm = translation.norm
    rotation = relative.rotation.matrix
    tilt = math.acos(min(1.0, max(-1.0, rotation[8])))
    projected_x_norm = math.hypot(rotation[0], rotation[3])
    # At ninety degrees of tilt yaw about the active board normal is not
    # observable.  Report pi conservatively; policy construction guarantees
    # this cannot be accepted.
    yaw = (
        math.pi
        if projected_x_norm <= _YAW_PROJECTION_EPSILON
        else abs(math.atan2(rotation[3], rotation[0]))
    )
    return translation_tuple, translation_norm, yaw, tilt


def _rejection_reasons(
    measurement: ArmCameraBoardMeasurement,
    policy: BoardPoseCorrectionPolicy,
    *,
    translation_delta_norm_mm: float,
    yaw_delta_rad: float,
    tilt_delta_rad: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if measurement.timestamp_quality not in _QUALIFIED_TIMESTAMP_QUALITIES:
        reasons.append("TIMESTAMP_QUALITY_UNQUALIFIED")
    if not measurement.freshness_advanced:
        reasons.append("FRAME_FRESHNESS_NOT_ADVANCED")
    if measurement.pose_age_ns > policy.maximum_pose_age_ns:
        reasons.append("POSE_AGE_LIMIT_EXCEEDED")
    if measurement.feedback_bracket_ns > policy.maximum_feedback_bracket_ns:
        reasons.append("FEEDBACK_BRACKET_LIMIT_EXCEEDED")
    if (
        measurement.maximum_joint_motion_during_bracket_rad
        > policy.maximum_joint_motion_during_bracket_rad
    ):
        reasons.append("ARM_MOTION_DURING_CAPTURE_LIMIT_EXCEEDED")
    if measurement.inlier_tag_count < policy.minimum_inlier_tags:
        reasons.append("INLIER_TAG_COUNT_BELOW_MINIMUM")
    if (
        measurement.inlier_reprojection_rmse_px
        > policy.maximum_inlier_reprojection_rmse_px
    ):
        reasons.append("REPROJECTION_RMSE_LIMIT_EXCEEDED")
    if translation_delta_norm_mm > policy.maximum_translation_delta_mm:
        reasons.append("TRANSLATION_DELTA_LIMIT_EXCEEDED")
    if yaw_delta_rad > policy.maximum_yaw_delta_rad:
        reasons.append("YAW_DELTA_LIMIT_EXCEEDED")
    if tilt_delta_rad > policy.maximum_tilt_delta_rad:
        reasons.append("TILT_DELTA_LIMIT_EXCEEDED")
    return tuple(reasons)


_DECISION_ISSUER = object()


@dataclass(frozen=True, slots=True)
class BoardPoseCorrectionDecision:
    """An auditable decision with no authority to install its candidate."""

    _issuer: object = field(repr=False, compare=False)
    active_registration: BoardRegistration
    candidate_registration: BoardRegistration
    measurement: ArmCameraBoardMeasurement
    policy: BoardPoseCorrectionPolicy
    status: BoardPoseCorrectionStatus
    translation_delta_board_mm: tuple[float, float, float]
    translation_delta_norm_mm: float
    yaw_delta_rad: float
    tilt_delta_rad: float
    rejection_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self._issuer is not _DECISION_ISSUER:
            raise BoardPoseCorrectionError(
                "correction decisions may only be issued by decide_board_pose_correction"
            )
        if not isinstance(self.active_registration, BoardRegistration):
            raise TypeError("active_registration must be a BoardRegistration")
        if not isinstance(self.candidate_registration, BoardRegistration):
            raise TypeError("candidate_registration must be a BoardRegistration")
        if not isinstance(self.measurement, ArmCameraBoardMeasurement):
            raise TypeError("measurement must be an ArmCameraBoardMeasurement")
        if not isinstance(self.policy, BoardPoseCorrectionPolicy):
            raise TypeError("policy must be a BoardPoseCorrectionPolicy")
        if not isinstance(self.status, BoardPoseCorrectionStatus):
            raise TypeError("status must be a BoardPoseCorrectionStatus")
        if self.candidate_registration.revision != self.active_registration.revision + 1:
            raise BoardPoseCorrectionError(
                "candidate registration must be the next active revision"
            )
        if not self.candidate_registration.Wv_T_board.almost_equal(
            self.measurement.Wv_T_board_candidate,
            absolute_tolerance=0.0,
        ):
            raise BoardPoseCorrectionError(
                "candidate registration does not equal the measured Wv_T_board"
            )

        expected_metrics = _correction_metrics(
            self.active_registration, self.candidate_registration
        )
        if (
            self.translation_delta_board_mm,
            self.translation_delta_norm_mm,
            self.yaw_delta_rad,
            self.tilt_delta_rad,
        ) != expected_metrics:
            raise BoardPoseCorrectionError("serialized correction metrics are inconsistent")
        expected_reasons = _rejection_reasons(
            self.measurement,
            self.policy,
            translation_delta_norm_mm=self.translation_delta_norm_mm,
            yaw_delta_rad=self.yaw_delta_rad,
            tilt_delta_rad=self.tilt_delta_rad,
        )
        if self.rejection_reasons != expected_reasons:
            raise BoardPoseCorrectionError("rejection reasons are inconsistent")
        expected_status = _decision_status(
            expected_reasons,
            policy=self.policy,
            translation_delta_norm_mm=self.translation_delta_norm_mm,
            yaw_delta_rad=self.yaw_delta_rad,
            tilt_delta_rad=self.tilt_delta_rad,
        )
        if self.status is not expected_status:
            raise BoardPoseCorrectionError("decision status is inconsistent")

    @property
    def applies_correction(self) -> bool:
        return self.status is BoardPoseCorrectionStatus.APPLY

    @property
    def selected_registration_hash(self) -> str | None:
        if self.status is BoardPoseCorrectionStatus.REJECT:
            return None
        if self.status is BoardPoseCorrectionStatus.APPLY:
            return self.candidate_registration.registration_hash
        return self.active_registration.registration_hash

    @property
    def gate_results(self) -> dict[str, bool]:
        rejected = set(self.rejection_reasons)
        return {
            "timestamp_quality": "TIMESTAMP_QUALITY_UNQUALIFIED" not in rejected,
            "freshness": "FRAME_FRESHNESS_NOT_ADVANCED" not in rejected,
            "pose_age": "POSE_AGE_LIMIT_EXCEEDED" not in rejected,
            "feedback_bracket": "FEEDBACK_BRACKET_LIMIT_EXCEEDED" not in rejected,
            "arm_motion_during_capture": (
                "ARM_MOTION_DURING_CAPTURE_LIMIT_EXCEEDED" not in rejected
            ),
            "inlier_tag_count": "INLIER_TAG_COUNT_BELOW_MINIMUM" not in rejected,
            "reprojection_rmse": "REPROJECTION_RMSE_LIMIT_EXCEEDED" not in rejected,
            "translation_delta": "TRANSLATION_DELTA_LIMIT_EXCEEDED" not in rejected,
            "yaw_delta": "YAW_DELTA_LIMIT_EXCEEDED" not in rejected,
            "tilt_delta": "TILT_DELTA_LIMIT_EXCEEDED" not in rejected,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": BOARD_POSE_CORRECTION_DECISION_SCHEMA,
            "status": self.status.value,
            "active_registration_sha256": (
                self.active_registration.registration_hash
            ),
            "candidate_registration": self.candidate_registration.to_dict(),
            "candidate_registration_sha256": (
                self.candidate_registration.registration_hash
            ),
            "measurement_sha256": self.measurement.measurement_hash,
            "policy_sha256": self.policy.policy_hash,
            "delta": {
                "frame_semantics": "B_ACTIVE_T_B_CANDIDATE",
                "translation_board_mm": list(self.translation_delta_board_mm),
                "translation_norm_mm": self.translation_delta_norm_mm,
                "absolute_yaw_rad": self.yaw_delta_rad,
                "tilt_rad": self.tilt_delta_rad,
            },
            "gates": self.gate_results,
            "rejection_reasons": list(self.rejection_reasons),
            "selected_registration_sha256": self.selected_registration_hash,
            "candidate_installed": False,
            "authority": _authority(),
        }

    @property
    def decision_hash(self) -> str:
        return _stable_hash(self.to_dict())


def _decision_status(
    rejection_reasons: tuple[str, ...],
    *,
    policy: BoardPoseCorrectionPolicy,
    translation_delta_norm_mm: float,
    yaw_delta_rad: float,
    tilt_delta_rad: float,
) -> BoardPoseCorrectionStatus:
    if rejection_reasons:
        return BoardPoseCorrectionStatus.REJECT
    if (
        translation_delta_norm_mm <= policy.translation_deadband_mm
        and yaw_delta_rad <= policy.yaw_deadband_rad
        and tilt_delta_rad <= policy.tilt_deadband_rad
    ):
        return BoardPoseCorrectionStatus.NO_CHANGE
    return BoardPoseCorrectionStatus.APPLY


def decide_board_pose_correction(
    active_registration: BoardRegistration,
    measurement: ArmCameraBoardMeasurement,
    policy: BoardPoseCorrectionPolicy | None = None,
) -> BoardPoseCorrectionDecision:
    """Classify one measured registration without mutating or clamping it."""

    if not isinstance(active_registration, BoardRegistration):
        raise TypeError("active_registration must be a BoardRegistration")
    if not isinstance(measurement, ArmCameraBoardMeasurement):
        raise TypeError("measurement must be an ArmCameraBoardMeasurement")
    selected_policy = policy or BoardPoseCorrectionPolicy()
    if not isinstance(selected_policy, BoardPoseCorrectionPolicy):
        raise TypeError("policy must be a BoardPoseCorrectionPolicy or None")
    if active_registration.revision >= _MAX_REGISTRATION_REVISION:
        raise BoardPoseCorrectionError("registration revision budget is exhausted")

    candidate = BoardRegistration(
        revision=active_registration.revision + 1,
        Wv_T_board=measurement.Wv_T_board_candidate,
        source_hashes=(
            ("active_registration_sha256", active_registration.registration_hash),
            ("measurement_sha256", measurement.measurement_hash),
        ),
    )
    translation, translation_norm, yaw, tilt = _correction_metrics(
        active_registration, candidate
    )
    reasons = _rejection_reasons(
        measurement,
        selected_policy,
        translation_delta_norm_mm=translation_norm,
        yaw_delta_rad=yaw,
        tilt_delta_rad=tilt,
    )
    status = _decision_status(
        reasons,
        policy=selected_policy,
        translation_delta_norm_mm=translation_norm,
        yaw_delta_rad=yaw,
        tilt_delta_rad=tilt,
    )
    return BoardPoseCorrectionDecision(
        _issuer=_DECISION_ISSUER,
        active_registration=active_registration,
        candidate_registration=candidate,
        measurement=measurement,
        policy=selected_policy,
        status=status,
        translation_delta_board_mm=translation,
        translation_delta_norm_mm=translation_norm,
        yaw_delta_rad=yaw,
        tilt_delta_rad=tilt,
        rejection_reasons=reasons,
    )


__all__ = [
    "ARM_CAMERA_BOARD_MEASUREMENT_SCHEMA",
    "ARM_CAMERA_FRAME",
    "BOARD_FRAME",
    "BOARD_POSE_CORRECTION_DECISION_SCHEMA",
    "BOARD_POSE_CORRECTION_POLICY_SCHEMA",
    "BOARD_REGISTRATION_SCHEMA",
    "VENDOR_WORLD_FRAME",
    "ArmCameraBoardMeasurement",
    "BoardPoseCorrectionDecision",
    "BoardPoseCorrectionError",
    "BoardPoseCorrectionPolicy",
    "BoardPoseCorrectionStatus",
    "BoardRegistration",
    "decide_board_pose_correction",
]
