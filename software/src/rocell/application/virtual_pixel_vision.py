"""Pixel-derived fixed-overview localization for virtual commissioning.

The service in this module is intentionally narrower than a motion observer.
It receives only a capture sequence and a synthetic capture mode.  It never
receives an action index, semantic target, planned waypoint, expected tag
corners, or simulator pose.  The processing boundary is therefore:

``JPEG bytes -> decoded tag pixels -> typed detections -> planar board pose``.

Only after :meth:`VirtualPixelVisionService.process` returns may the caller use
``VirtualPixelVisionAttemptLedger.associate`` to correlate the observation with
an action.  This prevents the detector or estimator from learning the answer
from the plan.  The fixed overview remains a simulation fixture; it is not the
intended arm-mounted camera and cannot provide a robot-frame correction or
release any physical gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from rocell.simulation.synthetic_raster import (
    SyntheticOverviewRasterRenderer,
    SyntheticRasterConfig,
    SyntheticRasterError,
    SyntheticRenderedFrame,
)
from rocell.vision.apriltag_codebook import (
    DEFAULT_APRILTAG_36H11_CODEBOOK,
)
from rocell.vision.detections import (
    AprilTagDetectionBatch,
    TagReference,
    VisionRecordError,
    april_tag_detection_batch_from_dict,
)
from rocell.vision.pixel_detector import (
    AprilTag36h11PixelDetector,
    AprilTagPixelDetectorConfiguration,
    AprilTagPixelDetectorError,
)
from rocell.vision.planar_pose_estimator import (
    PinholeIntrinsics,
    PlanarAprilTagBoardPoseEstimator,
    PlanarBoardTag,
    PlanarBoardTagMap,
    PlanarPoseEstimationError,
    PlanarPoseEstimatorConfig,
)
from rocell.vision.pose_estimation_records import (
    AprilTagPoseObservation,
    april_tag_pose_observation_from_dict,
)

from .context import SimulationContext, revalidate_simulation_context


MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS = 8
WORLD_TAG_IDS = (0, 1, 2, 3)
HELD_OUT_STATION_TAG_IDS = (4, 5)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class VirtualPixelVisionError(ValueError):
    """The virtual pixel pipeline or its evidence is incoherent."""


class VirtualPixelCaptureMode(str, Enum):
    """Explicit simulation-only capture behavior used for fault injection."""

    NORMAL = "NORMAL"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    TAG_LOSS = "TAG_LOSS"


class VirtualPixelVisionStage(str, Enum):
    """Last processing stage reached by one observation attempt."""

    CAPTURE = "CAPTURE"
    DETECTION = "DETECTION"
    POSE = "POSE"
    QUALITY = "QUALITY"
    COMPLETE = "COMPLETE"


def _stable_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VirtualPixelVisionError(
            f"pixel-vision evidence is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise VirtualPixelVisionError(f"{label} must be lowercase SHA-256")
    return value


def _bounded_integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = 1_000_000_000,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise VirtualPixelVisionError(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _bounded_text(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise VirtualPixelVisionError(
            f"{label} must be bounded non-empty text without control characters"
        )
    return value


def _finite_nonnegative(value: object, label: str, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VirtualPixelVisionError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= maximum:
        raise VirtualPixelVisionError(
            f"{label} must be finite and in [0, {maximum}]"
        )
    return result


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
        "live_motion_authorized": False,
        "contact_authorized": False,
        "can_release_physical_gates": False,
    }


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise VirtualPixelVisionError(f"{label} must be a JSON object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise VirtualPixelVisionError(f"{label} must be a JSON array")
    return value


def _exact_keys(
    document: dict[str, Any], expected: set[str], label: str
) -> None:
    actual = set(document)
    if actual != expected:
        raise VirtualPixelVisionError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _canonical_identical(expected: object, observed: object) -> bool:
    """Compare canonical JSON shapes without Python's bool/int coercions."""

    if type(expected) is not type(observed):
        return False
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            return False
        return all(
            _canonical_identical(expected[key], observed[key]) for key in expected
        )
    if isinstance(expected, list):
        return isinstance(observed, list) and len(expected) == len(observed) and all(
            _canonical_identical(left, right)
            for left, right in zip(expected, observed)
        )
    return expected == observed


def _require_literal(value: object, expected: object, label: str) -> None:
    if not _canonical_identical(expected, value):
        raise VirtualPixelVisionError(f"{label} must equal {expected!r}")


def _require_canonical_reconstruction(
    reconstructed: dict[str, object],
    document: dict[str, Any],
    label: str,
) -> None:
    if not _canonical_identical(reconstructed, document):
        raise VirtualPixelVisionError(
            f"{label} is not in canonical normalized form"
        )


def _validate_authority(value: object, label: str) -> None:
    _require_literal(value, _authority(), label)


@dataclass(frozen=True, slots=True)
class VirtualPixelVisionQualityPolicy:
    """Locked acceptance bounds for the deterministic overview fixture."""

    maximum_inlier_rmse_px: float = 1.0
    maximum_translation_error_mm: float = 1.0
    maximum_rotation_error_deg: float = 0.1
    required_world_tag_ids: tuple[int, ...] = WORLD_TAG_IDS
    required_held_out_tag_ids: tuple[int, ...] = HELD_OUT_STATION_TAG_IDS

    def __post_init__(self) -> None:
        for name, maximum in (
            ("maximum_inlier_rmse_px", 10_000.0),
            ("maximum_translation_error_mm", 1_000_000.0),
            ("maximum_rotation_error_deg", 180.0),
        ):
            value = _finite_nonnegative(getattr(self, name), name, maximum=maximum)
            if value <= 0.0:
                raise VirtualPixelVisionError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        for name in ("required_world_tag_ids", "required_held_out_tag_ids"):
            values = tuple(
                _bounded_integer(tag_id, name, maximum=2**31 - 1)
                for tag_id in getattr(self, name)
            )
            if not values or len(values) != len(set(values)):
                raise VirtualPixelVisionError(f"{name} must be non-empty and unique")
            object.__setattr__(self, name, values)
        if set(self.required_world_tag_ids) & set(self.required_held_out_tag_ids):
            raise VirtualPixelVisionError(
                "world and held-out pixel-vision tag sets must be disjoint"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_pixel_vision_quality_policy.v1",
            "maximum_inlier_rmse_px": self.maximum_inlier_rmse_px,
            "maximum_translation_error_mm": self.maximum_translation_error_mm,
            "maximum_rotation_error_deg": self.maximum_rotation_error_deg,
            "required_world_tag_ids": list(self.required_world_tag_ids),
            "required_held_out_tag_ids": list(self.required_held_out_tag_ids),
            "bounds_are_synthetic_not_measured": True,
            "physical_release_effect": "NONE",
        }

    @property
    def content_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class VirtualPixelFrameEvidence:
    """Redacted rendering evidence; encoded image bytes are never retained."""

    capture_id: str
    jpeg_sha256: str
    jpeg_byte_count: int
    width_px: int
    height_px: int
    settings_sha256: str
    freshness_token: str
    renderer_config_sha256: str
    source_bundle_sha256: str
    renderer_definition_sha256: str
    backend_id: str
    backend_version: str
    render_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "capture_id", _bounded_text(self.capture_id, "capture_id"))
        for name in (
            "jpeg_sha256",
            "settings_sha256",
            "renderer_config_sha256",
            "source_bundle_sha256",
            "renderer_definition_sha256",
            "render_hash",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(
            self,
            "jpeg_byte_count",
            _bounded_integer(
                self.jpeg_byte_count,
                "jpeg_byte_count",
                minimum=1,
                maximum=16 * 1024 * 1024,
            ),
        )
        object.__setattr__(
            self,
            "width_px",
            _bounded_integer(self.width_px, "width_px", minimum=1, maximum=4096),
        )
        object.__setattr__(
            self,
            "height_px",
            _bounded_integer(self.height_px, "height_px", minimum=1, maximum=4096),
        )
        for name in ("freshness_token", "backend_id", "backend_version"):
            object.__setattr__(
                self,
                name,
                _bounded_text(getattr(self, name), name, maximum=1024),
            )
        if self.settings_sha256 != self.renderer_definition_sha256:
            raise VirtualPixelVisionError(
                "frame settings hash must bind the renderer definition"
            )

    @classmethod
    def from_rendered(
        cls,
        rendered: SyntheticRenderedFrame,
    ) -> "VirtualPixelFrameEvidence":
        if not isinstance(rendered, SyntheticRenderedFrame):
            raise TypeError("rendered must be SyntheticRenderedFrame")
        frame = rendered.frame_packet
        if frame.freshness_token is None:
            raise VirtualPixelVisionError("synthetic frame lacks a freshness token")
        return cls(
            capture_id=frame.capture_id,
            jpeg_sha256=frame.sha256,
            jpeg_byte_count=len(frame.jpeg_bytes),
            width_px=frame.width_px,
            height_px=frame.height_px,
            settings_sha256=frame.settings_hash,
            freshness_token=frame.freshness_token,
            renderer_config_sha256=rendered.renderer_config_sha256,
            source_bundle_sha256=rendered.source_bundle_sha256,
            renderer_definition_sha256=rendered.renderer_definition_sha256,
            backend_id=rendered.backend_id,
            backend_version=rendered.backend_version,
            render_hash=rendered.render_hash,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_pixel_frame_evidence.v1",
            "capture_id": self.capture_id,
            "jpeg_sha256": self.jpeg_sha256,
            "jpeg_byte_count": self.jpeg_byte_count,
            "resolution_px": [self.width_px, self.height_px],
            "settings_sha256": self.settings_sha256,
            "freshness_token": self.freshness_token,
            "renderer_config_sha256": self.renderer_config_sha256,
            "source_bundle_sha256": self.source_bundle_sha256,
            "renderer_definition_sha256": self.renderer_definition_sha256,
            "backend": {"id": self.backend_id, "version": self.backend_version},
            "render_hash": self.render_hash,
            "jpeg_bytes_serialized": False,
            "embedded_detection_truth": False,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class VirtualPixelVisionQuality:
    """Independent pose quality comparison performed after estimation."""

    detected_tag_ids: tuple[int, ...]
    inlier_tag_ids: tuple[int, ...]
    inlier_rmse_px: float
    translation_error_mm: float
    rotation_error_deg: float
    world_tags_passed: bool
    held_out_tags_passed: bool
    residual_passed: bool
    translation_passed: bool
    rotation_passed: bool
    policy_sha256: str

    def __post_init__(self) -> None:
        for name in ("detected_tag_ids", "inlier_tag_ids"):
            values = tuple(
                _bounded_integer(tag_id, name, maximum=2**31 - 1)
                for tag_id in getattr(self, name)
            )
            if tuple(sorted(values)) != values or len(values) != len(set(values)):
                raise VirtualPixelVisionError(f"{name} must be sorted and unique")
            object.__setattr__(self, name, values)
        for name, maximum in (
            ("inlier_rmse_px", 1_000_000.0),
            ("translation_error_mm", 1_000_000.0),
            ("rotation_error_deg", 180.0),
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name, maximum=maximum),
            )
        for name in (
            "world_tags_passed",
            "held_out_tags_passed",
            "residual_passed",
            "translation_passed",
            "rotation_passed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise VirtualPixelVisionError(f"{name} must be boolean")
        object.__setattr__(
            self, "policy_sha256", _digest(self.policy_sha256, "policy_sha256")
        )

    @property
    def passed(self) -> bool:
        return all(
            (
                self.world_tags_passed,
                self.held_out_tags_passed,
                self.residual_passed,
                self.translation_passed,
                self.rotation_passed,
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_pixel_vision_quality.v1",
            "detected_tag_ids": list(self.detected_tag_ids),
            "inlier_tag_ids": list(self.inlier_tag_ids),
            "inlier_rmse_px": self.inlier_rmse_px,
            "translation_error_mm": self.translation_error_mm,
            "rotation_error_deg": self.rotation_error_deg,
            "checks": {
                "world_tags": self.world_tags_passed,
                "held_out_tags": self.held_out_tags_passed,
                "reprojection_residual": self.residual_passed,
                "translation": self.translation_passed,
                "rotation": self.rotation_passed,
            },
            "passed": self.passed,
            "policy_sha256": self.policy_sha256,
            "comparison_scope": "SYNTHETIC_FIXED_OVERVIEW_EXPECTED_POSE_ONLY",
            "robot_frame_correction_applied": False,
            "physical_release_effect": "NONE",
        }


@dataclass(frozen=True, slots=True)
class VirtualPixelVisionResult:
    """One redacted, unassociated result from the restricted vision service."""

    sequence: int
    capture_mode: VirtualPixelCaptureMode
    status: str
    stage: VirtualPixelVisionStage
    detail_code: str
    service_definition_sha256: str
    frame: VirtualPixelFrameEvidence | None = None
    detection_batch: AprilTagDetectionBatch | None = None
    pose_observation: AprilTagPoseObservation | None = None
    quality: VirtualPixelVisionQuality | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence",
            _bounded_integer(self.sequence, "vision result sequence"),
        )
        if not isinstance(self.capture_mode, VirtualPixelCaptureMode):
            raise TypeError("capture_mode must be VirtualPixelCaptureMode")
        if self.status not in {"PASS", "FAULT"}:
            raise VirtualPixelVisionError("vision result status must be PASS or FAULT")
        if not isinstance(self.stage, VirtualPixelVisionStage):
            raise TypeError("stage must be VirtualPixelVisionStage")
        object.__setattr__(
            self, "detail_code", _bounded_text(self.detail_code, "detail_code")
        )
        object.__setattr__(
            self,
            "service_definition_sha256",
            _digest(self.service_definition_sha256, "service_definition_sha256"),
        )
        if self.frame is not None and not isinstance(self.frame, VirtualPixelFrameEvidence):
            raise TypeError("frame must be VirtualPixelFrameEvidence or None")
        if self.detection_batch is not None and not isinstance(
            self.detection_batch, AprilTagDetectionBatch
        ):
            raise TypeError("detection_batch must be AprilTagDetectionBatch or None")
        if self.pose_observation is not None and not isinstance(
            self.pose_observation, AprilTagPoseObservation
        ):
            raise TypeError("pose_observation must be AprilTagPoseObservation or None")
        if self.quality is not None and not isinstance(
            self.quality, VirtualPixelVisionQuality
        ):
            raise TypeError("quality must be VirtualPixelVisionQuality or None")
        if self.detection_batch is not None:
            if self.frame is None:
                raise VirtualPixelVisionError("detections require frame evidence")
            if self.detection_batch.frame.jpeg_sha256 != self.frame.jpeg_sha256:
                raise VirtualPixelVisionError(
                    "detection batch does not bind the redacted frame"
                )
        if self.pose_observation is not None:
            if self.detection_batch is None:
                raise VirtualPixelVisionError("pose observation requires detections")
            if self.pose_observation.detection_batch != self.detection_batch:
                raise VirtualPixelVisionError(
                    "pose observation does not bind the detection batch"
                )
        if self.quality is not None and self.pose_observation is None:
            raise VirtualPixelVisionError("quality evidence requires a pose")
        if self.status == "PASS":
            if (
                self.capture_mode is not VirtualPixelCaptureMode.NORMAL
                or self.stage is not VirtualPixelVisionStage.COMPLETE
                or self.frame is None
                or self.detection_batch is None
                or self.pose_observation is None
                or self.quality is None
                or not self.quality.passed
            ):
                raise VirtualPixelVisionError(
                    "a passing result requires a complete normal pixel pipeline"
                )

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_pixel_vision_result.v1",
            "sequence": self.sequence,
            "capture_mode": self.capture_mode.value,
            "status": self.status,
            "stage": self.stage.value,
            "detail_code": self.detail_code,
            "service_definition_sha256": self.service_definition_sha256,
            "frame": None if self.frame is None else self.frame.to_dict(),
            "detection_batch": (
                None if self.detection_batch is None else self.detection_batch.to_dict()
            ),
            "detection_batch_sha256": (
                None
                if self.detection_batch is None
                else self.detection_batch.content_hash
            ),
            "pose_observation": (
                None if self.pose_observation is None else self.pose_observation.to_dict()
            ),
            "pose_observation_sha256": (
                None
                if self.pose_observation is None
                else self.pose_observation.content_hash
            ),
            "quality": None if self.quality is None else self.quality.to_dict(),
            "processor_input_contract": "SEQUENCE_AND_CAPTURE_MODE_ONLY",
            "target_or_action_received_by_processor": False,
            "fixed_overview_fixture": True,
            "arm_mounted_camera_simulated": False,
            "robot_frame_correction_applied": False,
            "jpeg_bytes_serialized": False,
            "authority": _authority(),
        }

    @property
    def result_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "result_hash": self.result_hash}


@dataclass(frozen=True, slots=True)
class VirtualPixelVisionAttempt:
    """Post-processing association between a plan occurrence and a result."""

    action_index: int
    target_id: str
    waypoint_sequence: int
    result: VirtualPixelVisionResult

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "action_index",
            _bounded_integer(self.action_index, "vision action_index"),
        )
        object.__setattr__(
            self, "target_id", _bounded_text(self.target_id, "vision target_id")
        )
        object.__setattr__(
            self,
            "waypoint_sequence",
            _bounded_integer(self.waypoint_sequence, "vision waypoint_sequence"),
        )
        if not isinstance(self.result, VirtualPixelVisionResult):
            raise TypeError("result must be VirtualPixelVisionResult")

    def _without_hash(self) -> dict[str, object]:
        return {
            "action_index": self.action_index,
            "target_id": self.target_id,
            "waypoint_sequence": self.waypoint_sequence,
            "association_timing": "AFTER_PIXEL_PROCESSING_COMPLETED",
            "result": self.result.to_dict(),
            "result_hash": self.result.result_hash,
        }

    @property
    def attempt_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "attempt_hash": self.attempt_hash}


@dataclass(frozen=True, slots=True)
class VirtualPixelVisionAttemptLedger:
    """Persistent-value ledger for bounded, ordered post-process associations."""

    service_definition_sha256: str
    attempts: tuple[VirtualPixelVisionAttempt, ...] = ()
    sealed: bool = False
    maximum_attempts: int = MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "service_definition_sha256",
            _digest(self.service_definition_sha256, "service_definition_sha256"),
        )
        object.__setattr__(
            self,
            "maximum_attempts",
            _bounded_integer(
                self.maximum_attempts,
                "maximum_attempts",
                minimum=1,
                maximum=MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS,
            ),
        )
        attempts = tuple(self.attempts)
        if len(attempts) > self.maximum_attempts:
            raise VirtualPixelVisionError("pixel-vision attempt ledger is full")
        if any(not isinstance(item, VirtualPixelVisionAttempt) for item in attempts):
            raise TypeError("attempts must contain VirtualPixelVisionAttempt values")
        for item in attempts:
            if item.result.service_definition_sha256 != self.service_definition_sha256:
                raise VirtualPixelVisionError(
                    "vision result differs from ledger service definition"
                )
        for previous, current in zip(attempts, attempts[1:]):
            if current.action_index <= previous.action_index:
                raise VirtualPixelVisionError(
                    "vision action indices must be strictly increasing"
                )
            if current.waypoint_sequence <= previous.waypoint_sequence:
                raise VirtualPixelVisionError(
                    "vision waypoint sequences must be strictly increasing"
                )
            if current.result.sequence <= previous.result.sequence:
                raise VirtualPixelVisionError(
                    "vision capture sequences must be strictly increasing"
                )
        capture_ids = tuple(
            item.result.frame.capture_id
            for item in attempts
            if item.result.frame is not None
        )
        freshness = tuple(
            item.result.frame.freshness_token
            for item in attempts
            if item.result.frame is not None
        )
        if len(capture_ids) != len(set(capture_ids)) or len(freshness) != len(
            set(freshness)
        ):
            raise VirtualPixelVisionError(
                "captured pixel-vision attempts must have unique freshness evidence"
            )
        object.__setattr__(self, "attempts", attempts)
        if not isinstance(self.sealed, bool):
            raise VirtualPixelVisionError("sealed must be boolean")

    @classmethod
    def create(cls, service_definition_sha256: str) -> "VirtualPixelVisionAttemptLedger":
        return cls(service_definition_sha256=service_definition_sha256)

    def associate(
        self,
        result: VirtualPixelVisionResult,
        *,
        action_index: int,
        target_id: str,
        waypoint_sequence: int,
    ) -> "VirtualPixelVisionAttemptLedger":
        if self.sealed:
            raise VirtualPixelVisionError("cannot append to a sealed vision ledger")
        if len(self.attempts) >= self.maximum_attempts:
            raise VirtualPixelVisionError("pixel-vision attempt ledger is full")
        attempt = VirtualPixelVisionAttempt(
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
            result=result,
        )
        return replace(self, attempts=(*self.attempts, attempt))

    def seal(self) -> "VirtualPixelVisionAttemptLedger":
        if self.sealed:
            return self
        return replace(self, sealed=True)

    @property
    def passed_attempt_count(self) -> int:
        return sum(item.result.passed for item in self.attempts)

    @property
    def all_attempts_passed(self) -> bool:
        return bool(self.attempts) and self.passed_attempt_count == len(self.attempts)

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_pixel_vision_attempt_ledger.v1",
            "service_definition_sha256": self.service_definition_sha256,
            "sealed": self.sealed,
            "maximum_attempts": self.maximum_attempts,
            "attempt_count": len(self.attempts),
            "passed_attempt_count": self.passed_attempt_count,
            "all_attempts_passed": self.all_attempts_passed,
            "attempts": [item.to_dict() for item in self.attempts],
            "input_separation": {
                "pixel_processor_received_target_or_action": False,
                "association_occurs_after_processing": True,
            },
            "fixed_overview_fixture": True,
            "arm_mounted_camera_simulated": False,
            "robot_frame_correction_applied": False,
            "authority": _authority(),
        }

    @property
    def ledger_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "ledger_hash": self.ledger_hash}


def _virtual_pixel_frame_evidence_from_dict(
    value: object,
) -> VirtualPixelFrameEvidence:
    document = _object(value, "virtual pixel frame evidence")
    _exact_keys(
        document,
        {
            "schema",
            "capture_id",
            "jpeg_sha256",
            "jpeg_byte_count",
            "resolution_px",
            "settings_sha256",
            "freshness_token",
            "renderer_config_sha256",
            "source_bundle_sha256",
            "renderer_definition_sha256",
            "backend",
            "render_hash",
            "jpeg_bytes_serialized",
            "embedded_detection_truth",
            "authority",
        },
        "virtual pixel frame evidence",
    )
    _require_literal(
        document["schema"],
        "rocell.virtual_pixel_frame_evidence.v1",
        "frame schema",
    )
    _require_literal(
        document["jpeg_bytes_serialized"], False, "frame jpeg_bytes_serialized"
    )
    _require_literal(
        document["embedded_detection_truth"],
        False,
        "frame embedded_detection_truth",
    )
    _validate_authority(document["authority"], "frame authority")
    resolution = _array(document["resolution_px"], "frame resolution_px")
    if len(resolution) != 2:
        raise VirtualPixelVisionError(
            "frame resolution_px must contain exactly two integers"
        )
    backend = _object(document["backend"], "frame backend")
    _exact_keys(backend, {"id", "version"}, "frame backend")
    frame = VirtualPixelFrameEvidence(
        capture_id=document["capture_id"],
        jpeg_sha256=document["jpeg_sha256"],
        jpeg_byte_count=document["jpeg_byte_count"],
        width_px=resolution[0],
        height_px=resolution[1],
        settings_sha256=document["settings_sha256"],
        freshness_token=document["freshness_token"],
        renderer_config_sha256=document["renderer_config_sha256"],
        source_bundle_sha256=document["source_bundle_sha256"],
        renderer_definition_sha256=document["renderer_definition_sha256"],
        backend_id=backend["id"],
        backend_version=backend["version"],
        render_hash=document["render_hash"],
    )
    _require_canonical_reconstruction(
        frame.to_dict(), document, "virtual pixel frame evidence"
    )
    return frame


def _virtual_pixel_vision_quality_from_dict(
    value: object,
) -> VirtualPixelVisionQuality:
    document = _object(value, "virtual pixel vision quality")
    _exact_keys(
        document,
        {
            "schema",
            "detected_tag_ids",
            "inlier_tag_ids",
            "inlier_rmse_px",
            "translation_error_mm",
            "rotation_error_deg",
            "checks",
            "passed",
            "policy_sha256",
            "comparison_scope",
            "robot_frame_correction_applied",
            "physical_release_effect",
        },
        "virtual pixel vision quality",
    )
    _require_literal(
        document["schema"],
        "rocell.virtual_pixel_vision_quality.v1",
        "quality schema",
    )
    _require_literal(
        document["comparison_scope"],
        "SYNTHETIC_FIXED_OVERVIEW_EXPECTED_POSE_ONLY",
        "quality comparison_scope",
    )
    _require_literal(
        document["robot_frame_correction_applied"],
        False,
        "quality robot_frame_correction_applied",
    )
    _require_literal(
        document["physical_release_effect"],
        "NONE",
        "quality physical_release_effect",
    )
    detected = _array(document["detected_tag_ids"], "quality detected_tag_ids")
    inliers = _array(document["inlier_tag_ids"], "quality inlier_tag_ids")
    checks = _object(document["checks"], "quality checks")
    _exact_keys(
        checks,
        {
            "world_tags",
            "held_out_tags",
            "reprojection_residual",
            "translation",
            "rotation",
        },
        "quality checks",
    )
    quality = VirtualPixelVisionQuality(
        detected_tag_ids=tuple(detected),
        inlier_tag_ids=tuple(inliers),
        inlier_rmse_px=document["inlier_rmse_px"],
        translation_error_mm=document["translation_error_mm"],
        rotation_error_deg=document["rotation_error_deg"],
        world_tags_passed=checks["world_tags"],
        held_out_tags_passed=checks["held_out_tags"],
        residual_passed=checks["reprojection_residual"],
        translation_passed=checks["translation"],
        rotation_passed=checks["rotation"],
        policy_sha256=document["policy_sha256"],
    )
    _require_literal(document["passed"], quality.passed, "quality passed")
    _require_canonical_reconstruction(
        quality.to_dict(), document, "virtual pixel vision quality"
    )
    return quality


def _optional_detection_batch(value: object) -> AprilTagDetectionBatch | None:
    if value is None:
        return None
    try:
        return april_tag_detection_batch_from_dict(value)
    except (TypeError, VisionRecordError) as exc:
        raise VirtualPixelVisionError(
            f"virtual pixel detection batch is invalid: {exc}"
        ) from exc


def _optional_pose_observation(value: object) -> AprilTagPoseObservation | None:
    if value is None:
        return None
    try:
        return april_tag_pose_observation_from_dict(value)
    except (TypeError, VisionRecordError) as exc:
        raise VirtualPixelVisionError(
            f"virtual pixel pose observation is invalid: {exc}"
        ) from exc


def _validate_result_stage_shape(result: VirtualPixelVisionResult) -> None:
    present = (
        result.frame is not None,
        result.detection_batch is not None,
        result.pose_observation is not None,
        result.quality is not None,
    )
    expected_by_stage = {
        VirtualPixelVisionStage.CAPTURE: (False, False, False, False),
        VirtualPixelVisionStage.DETECTION: (True, False, False, False),
        VirtualPixelVisionStage.POSE: (True, True, False, False),
        VirtualPixelVisionStage.QUALITY: (True, True, True, True),
        VirtualPixelVisionStage.COMPLETE: (True, True, True, True),
    }
    if present != expected_by_stage[result.stage]:
        raise VirtualPixelVisionError(
            f"vision result evidence does not match stage {result.stage.value}"
        )
    if (result.status == "PASS") is not (
        result.stage is VirtualPixelVisionStage.COMPLETE
    ):
        raise VirtualPixelVisionError(
            "vision result PASS/FAULT status disagrees with its terminal stage"
        )
    if (
        result.capture_mode is VirtualPixelCaptureMode.CAMERA_UNAVAILABLE
        and result.stage is not VirtualPixelVisionStage.CAPTURE
    ):
        raise VirtualPixelVisionError(
            "CAMERA_UNAVAILABLE can only terminate at the capture stage"
        )
    expected_detail = {
        VirtualPixelVisionStage.CAPTURE: (
            "PIXEL_CAMERA_UNAVAILABLE"
            if result.capture_mode is VirtualPixelCaptureMode.CAMERA_UNAVAILABLE
            else "PIXEL_FRAME_CAPTURE_FAILED"
        ),
        VirtualPixelVisionStage.DETECTION: "PIXEL_TAG_DETECTION_FAILED",
        VirtualPixelVisionStage.POSE: "PIXEL_BOARD_POSE_FAILED",
        VirtualPixelVisionStage.QUALITY: (
            "PIXEL_TAG_LOSS_INJECTION_NOT_REJECTED"
            if result.capture_mode is VirtualPixelCaptureMode.TAG_LOSS
            else "PIXEL_BOARD_POSE_QUALITY_REJECTED"
        ),
        VirtualPixelVisionStage.COMPLETE: "PIXEL_BOARD_POSE_ACCEPTED",
    }[result.stage]
    if result.detail_code != expected_detail:
        raise VirtualPixelVisionError(
            "vision result detail_code disagrees with capture mode and stage"
        )
    if (
        result.stage is VirtualPixelVisionStage.QUALITY
        and result.capture_mode is VirtualPixelCaptureMode.NORMAL
        and result.quality is not None
        and result.quality.passed
    ):
        raise VirtualPixelVisionError(
            "normal quality-stage fault must contain a failed quality assessment"
        )

    if result.frame is not None and result.detection_batch is not None:
        binding = result.detection_batch.frame
        if (
            binding.capture_id != result.frame.capture_id
            or binding.jpeg_sha256 != result.frame.jpeg_sha256
            or binding.width_px != result.frame.width_px
            or binding.height_px != result.frame.height_px
            or binding.settings_sha256 != result.frame.settings_sha256
            or binding.freshness_token != result.frame.freshness_token
            or binding.source_sequence != result.sequence
        ):
            raise VirtualPixelVisionError(
                "detection frame binding disagrees with redacted frame evidence"
            )
    if result.quality is not None and result.pose_observation is not None:
        detected = tuple(
            sorted(
                tag.tag_id
                for tag in result.pose_observation.detection_batch.accepted_tags
            )
        )
        inliers = tuple(
            sorted(tag.tag_id for tag in result.pose_observation.used_tags)
        )
        if result.quality.detected_tag_ids != detected:
            raise VirtualPixelVisionError(
                "quality detected_tag_ids disagree with the detection batch"
            )
        if result.quality.inlier_tag_ids != inliers:
            raise VirtualPixelVisionError(
                "quality inlier_tag_ids disagree with the pose observation"
            )
        if result.quality.inlier_rmse_px != result.pose_observation.inlier_rmse_px:
            raise VirtualPixelVisionError(
                "quality inlier_rmse_px disagrees with the pose observation"
            )


def _virtual_pixel_vision_result_from_dict(
    value: object,
) -> VirtualPixelVisionResult:
    document = _object(value, "virtual pixel vision result")
    _exact_keys(
        document,
        {
            "schema",
            "sequence",
            "capture_mode",
            "status",
            "stage",
            "detail_code",
            "service_definition_sha256",
            "frame",
            "detection_batch",
            "detection_batch_sha256",
            "pose_observation",
            "pose_observation_sha256",
            "quality",
            "processor_input_contract",
            "target_or_action_received_by_processor",
            "fixed_overview_fixture",
            "arm_mounted_camera_simulated",
            "robot_frame_correction_applied",
            "jpeg_bytes_serialized",
            "authority",
            "result_hash",
        },
        "virtual pixel vision result",
    )
    _require_literal(
        document["schema"],
        "rocell.virtual_pixel_vision_result.v1",
        "vision result schema",
    )
    for name, expected in (
        ("processor_input_contract", "SEQUENCE_AND_CAPTURE_MODE_ONLY"),
        ("target_or_action_received_by_processor", False),
        ("fixed_overview_fixture", True),
        ("arm_mounted_camera_simulated", False),
        ("robot_frame_correction_applied", False),
        ("jpeg_bytes_serialized", False),
    ):
        _require_literal(document[name], expected, f"vision result {name}")
    _validate_authority(document["authority"], "vision result authority")
    try:
        capture_mode = VirtualPixelCaptureMode(document["capture_mode"])
    except (TypeError, ValueError) as exc:
        raise VirtualPixelVisionError("vision result capture_mode is invalid") from exc
    try:
        stage = VirtualPixelVisionStage(document["stage"])
    except (TypeError, ValueError) as exc:
        raise VirtualPixelVisionError("vision result stage is invalid") from exc
    frame = (
        None
        if document["frame"] is None
        else _virtual_pixel_frame_evidence_from_dict(document["frame"])
    )
    detection_batch = _optional_detection_batch(document["detection_batch"])
    pose_observation = _optional_pose_observation(document["pose_observation"])
    quality = (
        None
        if document["quality"] is None
        else _virtual_pixel_vision_quality_from_dict(document["quality"])
    )
    if detection_batch is None:
        _require_literal(
            document["detection_batch_sha256"],
            None,
            "vision result detection_batch_sha256",
        )
    else:
        _digest(
            document["detection_batch_sha256"],
            "vision result detection_batch_sha256",
        )
        if document["detection_batch_sha256"] != detection_batch.content_hash:
            raise VirtualPixelVisionError(
                "vision result detection_batch_sha256 does not match its batch"
            )
    if pose_observation is None:
        _require_literal(
            document["pose_observation_sha256"],
            None,
            "vision result pose_observation_sha256",
        )
    else:
        _digest(
            document["pose_observation_sha256"],
            "vision result pose_observation_sha256",
        )
        if document["pose_observation_sha256"] != pose_observation.content_hash:
            raise VirtualPixelVisionError(
                "vision result pose_observation_sha256 does not match its observation"
            )
    result = VirtualPixelVisionResult(
        sequence=document["sequence"],
        capture_mode=capture_mode,
        status=document["status"],
        stage=stage,
        detail_code=document["detail_code"],
        service_definition_sha256=document["service_definition_sha256"],
        frame=frame,
        detection_batch=detection_batch,
        pose_observation=pose_observation,
        quality=quality,
    )
    _validate_result_stage_shape(result)
    _digest(document["result_hash"], "vision result result_hash")
    if document["result_hash"] != result.result_hash:
        raise VirtualPixelVisionError("vision result_hash does not match its result")
    _require_canonical_reconstruction(
        result.to_dict(), document, "virtual pixel vision result"
    )
    return result


def _virtual_pixel_vision_attempt_from_dict(
    value: object,
) -> VirtualPixelVisionAttempt:
    document = _object(value, "virtual pixel vision attempt")
    _exact_keys(
        document,
        {
            "action_index",
            "target_id",
            "waypoint_sequence",
            "association_timing",
            "result",
            "result_hash",
            "attempt_hash",
        },
        "virtual pixel vision attempt",
    )
    _require_literal(
        document["association_timing"],
        "AFTER_PIXEL_PROCESSING_COMPLETED",
        "vision attempt association_timing",
    )
    result = _virtual_pixel_vision_result_from_dict(document["result"])
    _digest(document["result_hash"], "vision attempt result_hash")
    if document["result_hash"] != result.result_hash:
        raise VirtualPixelVisionError(
            "vision attempt result_hash does not match its result"
        )
    attempt = VirtualPixelVisionAttempt(
        action_index=document["action_index"],
        target_id=document["target_id"],
        waypoint_sequence=document["waypoint_sequence"],
        result=result,
    )
    _digest(document["attempt_hash"], "vision attempt attempt_hash")
    if document["attempt_hash"] != attempt.attempt_hash:
        raise VirtualPixelVisionError(
            "vision attempt_hash does not match its attempt"
        )
    _require_canonical_reconstruction(
        attempt.to_dict(), document, "virtual pixel vision attempt"
    )
    return attempt


def virtual_pixel_vision_attempt_ledger_from_dict(
    value: object,
) -> VirtualPixelVisionAttemptLedger:
    """Strictly reconstruct one canonical, zero-authority pixel ledger."""

    document = _object(value, "virtual pixel vision attempt ledger")
    _exact_keys(
        document,
        {
            "schema",
            "service_definition_sha256",
            "sealed",
            "maximum_attempts",
            "attempt_count",
            "passed_attempt_count",
            "all_attempts_passed",
            "attempts",
            "input_separation",
            "fixed_overview_fixture",
            "arm_mounted_camera_simulated",
            "robot_frame_correction_applied",
            "authority",
            "ledger_hash",
        },
        "virtual pixel vision attempt ledger",
    )
    _require_literal(
        document["schema"],
        "rocell.virtual_pixel_vision_attempt_ledger.v1",
        "vision ledger schema",
    )
    input_separation = _object(
        document["input_separation"], "vision ledger input_separation"
    )
    _exact_keys(
        input_separation,
        {
            "pixel_processor_received_target_or_action",
            "association_occurs_after_processing",
        },
        "vision ledger input_separation",
    )
    _require_literal(
        input_separation["pixel_processor_received_target_or_action"],
        False,
        "vision ledger processor target/action flag",
    )
    _require_literal(
        input_separation["association_occurs_after_processing"],
        True,
        "vision ledger association ordering flag",
    )
    for name, expected in (
        ("fixed_overview_fixture", True),
        ("arm_mounted_camera_simulated", False),
        ("robot_frame_correction_applied", False),
    ):
        _require_literal(document[name], expected, f"vision ledger {name}")
    _validate_authority(document["authority"], "vision ledger authority")
    attempt_values = _array(document["attempts"], "vision ledger attempts")
    if len(attempt_values) > MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS:
        raise VirtualPixelVisionError(
            "vision ledger attempts exceed the global resource bound"
        )
    attempts = tuple(
        _virtual_pixel_vision_attempt_from_dict(item) for item in attempt_values
    )
    ledger = VirtualPixelVisionAttemptLedger(
        service_definition_sha256=document["service_definition_sha256"],
        attempts=attempts,
        sealed=document["sealed"],
        maximum_attempts=document["maximum_attempts"],
    )
    attempt_count = _bounded_integer(
        document["attempt_count"],
        "vision ledger attempt_count",
        maximum=MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS,
    )
    passed_attempt_count = _bounded_integer(
        document["passed_attempt_count"],
        "vision ledger passed_attempt_count",
        maximum=MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS,
    )
    if attempt_count != len(ledger.attempts):
        raise VirtualPixelVisionError(
            "vision ledger attempt_count does not match attempts"
        )
    if passed_attempt_count != ledger.passed_attempt_count:
        raise VirtualPixelVisionError(
            "vision ledger passed_attempt_count does not match attempts"
        )
    _require_literal(
        document["all_attempts_passed"],
        ledger.all_attempts_passed,
        "vision ledger all_attempts_passed",
    )
    _digest(document["ledger_hash"], "vision ledger ledger_hash")
    if document["ledger_hash"] != ledger.ledger_hash:
        raise VirtualPixelVisionError(
            "vision ledger_hash does not match its ledger"
        )
    _require_canonical_reconstruction(
        ledger.to_dict(), document, "virtual pixel vision attempt ledger"
    )
    return ledger


@dataclass(frozen=True, slots=True)
class VirtualPixelVisionService:
    """Construct and execute the restricted fixed-overview pixel pipeline."""

    context: SimulationContext = field(repr=False)
    quality_policy: VirtualPixelVisionQualityPolicy = field(
        default_factory=VirtualPixelVisionQualityPolicy
    )
    _normal_renderer: SyntheticOverviewRasterRenderer = field(init=False, repr=False)
    _tag_loss_renderer: SyntheticOverviewRasterRenderer = field(init=False, repr=False)
    _detector: AprilTag36h11PixelDetector = field(init=False, repr=False)
    _intrinsics: PinholeIntrinsics = field(init=False, repr=False)
    _tag_map: PlanarBoardTagMap = field(init=False, repr=False)
    _estimator: PlanarAprilTagBoardPoseEstimator = field(init=False, repr=False)
    _service_definition: dict[str, object] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, SimulationContext):
            raise TypeError("context must be SimulationContext")
        if not isinstance(self.quality_policy, VirtualPixelVisionQualityPolicy):
            raise TypeError("quality_policy must be VirtualPixelVisionQualityPolicy")
        revalidate_simulation_context(self.context)
        fixture = self.context.scenario.overview
        normal_config = SyntheticRasterConfig()
        tag_loss_config = SyntheticRasterConfig(occluded_tag_ids=WORLD_TAG_IDS)
        tag_root = self.context.rc03_root / "fiducials"
        normal = SyntheticOverviewRasterRenderer(
            self.context.scene,
            fixture.camera,
            fixture.camera_T_board,
            tag_root,
            normal_config,
            DEFAULT_APRILTAG_36H11_CODEBOOK,
        )
        tag_loss = SyntheticOverviewRasterRenderer(
            self.context.scene,
            fixture.camera,
            fixture.camera_T_board,
            tag_root,
            tag_loss_config,
            DEFAULT_APRILTAG_36H11_CODEBOOK,
        )
        detector = AprilTag36h11PixelDetector(
            AprilTagPixelDetectorConfiguration(
                host_clock="synthetic_host_monotonic"
            ),
            DEFAULT_APRILTAG_36H11_CODEBOOK,
        )
        intrinsics = PinholeIntrinsics(
            calibration_id="rc03.synthetic_fixed_overview.nominal",
            width_px=fixture.camera.width_px,
            height_px=fixture.camera.height_px,
            fx_px=fixture.camera.fx_px,
            fy_px=fixture.camera.fy_px,
            cx_px=fixture.camera.cx_px,
            cy_px=fixture.camera.cy_px,
            source_sha256=self.context.scenario.source_profile_sha256,
            camera_frame=fixture.camera.optical_frame,
        )
        map_hash = self.context.scene.source_hashes["fiducials/apriltag_map.json"]
        tags = tuple(
            PlanarBoardTag(
                tag=TagReference(tag.family, tag.tag_id),
                corners_board_mm=tag.corners(),
            )
            for tag in self.context.scene.fiducials
        )
        tag_map = PlanarBoardTagMap(
            map_id="rc03.freeze005.nominal_tag_plane",
            board_frame=self.context.scene.board_frame,
            tag_plane_z_board_mm=self.context.scenario.assumed_tag_plane_z_mm,
            tags=tags,
            source_sha256=map_hash,
        )
        estimator = PlanarAprilTagBoardPoseEstimator(
            PlanarPoseEstimatorConfig(
                maximum_tag_reprojection_rmse_px=(
                    self.quality_policy.maximum_inlier_rmse_px
                ),
                minimum_inlier_tags=len(WORLD_TAG_IDS),
            )
        )
        definition = {
            "schema": "rocell.virtual_pixel_vision_service_definition.v1",
            "processor_input_contract": "SEQUENCE_AND_CAPTURE_MODE_ONLY",
            "scenario_id": fixture.scenario_id,
            "normal_renderer_config_sha256": normal_config.config_sha256,
            "tag_loss_renderer_config_sha256": tag_loss_config.config_sha256,
            "tag_loss_occludes_world_tag_ids": list(WORLD_TAG_IDS),
            "tag_codebook_sha256": DEFAULT_APRILTAG_36H11_CODEBOOK.codebook_sha256,
            "detector": detector.detector_identity.to_dict(),
            "intrinsics": intrinsics.to_dict(),
            "intrinsics_sha256": intrinsics.content_hash,
            "tag_map": tag_map.to_dict(),
            "tag_map_sha256": tag_map.content_hash,
            "pose_estimator": {
                "id": "rocell.planar_apriltag_homography",
                "version": "1.0.0",
                "configuration_sha256": estimator.config.content_hash,
            },
            "quality_policy": self.quality_policy.to_dict(),
            "quality_policy_sha256": self.quality_policy.content_hash,
            "fixed_overview_fixture": True,
            "arm_mounted_camera_simulated": False,
            "robot_frame_correction_applied": False,
            "implementation_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "authority": _authority(),
        }
        object.__setattr__(self, "_normal_renderer", normal)
        object.__setattr__(self, "_tag_loss_renderer", tag_loss)
        object.__setattr__(self, "_detector", detector)
        object.__setattr__(self, "_intrinsics", intrinsics)
        object.__setattr__(self, "_tag_map", tag_map)
        object.__setattr__(self, "_estimator", estimator)
        object.__setattr__(self, "_service_definition", definition)

    @property
    def service_definition_sha256(self) -> str:
        return _stable_hash(self._service_definition)

    def definition_dict(self) -> dict[str, object]:
        return {
            **self._service_definition,
            "service_definition_sha256": self.service_definition_sha256,
        }

    def _failure(
        self,
        *,
        sequence: int,
        capture_mode: VirtualPixelCaptureMode,
        stage: VirtualPixelVisionStage,
        detail_code: str,
        frame: VirtualPixelFrameEvidence | None = None,
        detection_batch: AprilTagDetectionBatch | None = None,
    ) -> VirtualPixelVisionResult:
        return VirtualPixelVisionResult(
            sequence=sequence,
            capture_mode=capture_mode,
            status="FAULT",
            stage=stage,
            detail_code=detail_code,
            service_definition_sha256=self.service_definition_sha256,
            frame=frame,
            detection_batch=detection_batch,
        )

    def _quality(self, observation: AprilTagPoseObservation) -> VirtualPixelVisionQuality:
        fixture = self.context.scenario.overview
        expected = fixture.camera_T_board.matrix
        estimated = observation.pose
        dx = estimated.translation_mm.x - expected[3]
        dy = estimated.translation_mm.y - expected[7]
        dz = estimated.translation_mm.z - expected[11]
        translation_error = math.sqrt(dx * dx + dy * dy + dz * dz)
        expected_rotation = (
            expected[0],
            expected[1],
            expected[2],
            expected[4],
            expected[5],
            expected[6],
            expected[8],
            expected[9],
            expected[10],
        )
        # trace(R_est * R_expected^T) equals the elementwise dot product.
        trace = sum(
            left * right
            for left, right in zip(estimated.rotation.matrix, expected_rotation)
        )
        cosine = min(1.0, max(-1.0, (trace - 1.0) / 2.0))
        rotation_error = math.degrees(math.acos(cosine))
        detected = tuple(
            sorted(tag.tag_id for tag in observation.detection_batch.accepted_tags)
        )
        inliers = tuple(sorted(tag.tag_id for tag in observation.used_tags))
        world_passed = set(self.quality_policy.required_world_tag_ids).issubset(inliers)
        held_out_passed = set(
            self.quality_policy.required_held_out_tag_ids
        ).issubset(inliers)
        return VirtualPixelVisionQuality(
            detected_tag_ids=detected,
            inlier_tag_ids=inliers,
            inlier_rmse_px=observation.inlier_rmse_px,
            translation_error_mm=translation_error,
            rotation_error_deg=rotation_error,
            world_tags_passed=world_passed,
            held_out_tags_passed=held_out_passed,
            residual_passed=(
                observation.inlier_rmse_px
                <= self.quality_policy.maximum_inlier_rmse_px
            ),
            translation_passed=(
                translation_error
                <= self.quality_policy.maximum_translation_error_mm
            ),
            rotation_passed=(
                rotation_error <= self.quality_policy.maximum_rotation_error_deg
            ),
            policy_sha256=self.quality_policy.content_hash,
        )

    def process(
        self,
        *,
        sequence: int,
        capture_mode: VirtualPixelCaptureMode = VirtualPixelCaptureMode.NORMAL,
    ) -> VirtualPixelVisionResult:
        """Run the pixel boundary without receiving any action or target data."""

        selected_sequence = _bounded_integer(sequence, "pixel capture sequence")
        if not isinstance(capture_mode, VirtualPixelCaptureMode):
            raise TypeError("capture_mode must be VirtualPixelCaptureMode")
        if capture_mode is VirtualPixelCaptureMode.CAMERA_UNAVAILABLE:
            return self._failure(
                sequence=selected_sequence,
                capture_mode=capture_mode,
                stage=VirtualPixelVisionStage.CAPTURE,
                detail_code="PIXEL_CAMERA_UNAVAILABLE",
            )
        renderer = (
            self._tag_loss_renderer
            if capture_mode is VirtualPixelCaptureMode.TAG_LOSS
            else self._normal_renderer
        )
        try:
            rendered = renderer.render(sequence=selected_sequence)
        except (SyntheticRasterError, OSError):
            return self._failure(
                sequence=selected_sequence,
                capture_mode=capture_mode,
                stage=VirtualPixelVisionStage.CAPTURE,
                detail_code="PIXEL_FRAME_CAPTURE_FAILED",
            )
        frame_evidence = VirtualPixelFrameEvidence.from_rendered(rendered)
        try:
            batch = self._detector.detect(rendered.frame_packet)
        except AprilTagPixelDetectorError:
            return self._failure(
                sequence=selected_sequence,
                capture_mode=capture_mode,
                stage=VirtualPixelVisionStage.DETECTION,
                detail_code="PIXEL_TAG_DETECTION_FAILED",
                frame=frame_evidence,
            )
        try:
            pose = self._estimator.estimate(batch, self._intrinsics, self._tag_map)
        except PlanarPoseEstimationError:
            return self._failure(
                sequence=selected_sequence,
                capture_mode=capture_mode,
                stage=VirtualPixelVisionStage.POSE,
                detail_code="PIXEL_BOARD_POSE_FAILED",
                frame=frame_evidence,
                detection_batch=batch,
            )
        quality = self._quality(pose)
        if capture_mode is VirtualPixelCaptureMode.TAG_LOSS:
            # Reaching this branch means the intentionally occluded pixels did
            # not cause the expected natural pose/quality rejection.
            return VirtualPixelVisionResult(
                sequence=selected_sequence,
                capture_mode=capture_mode,
                status="FAULT",
                stage=VirtualPixelVisionStage.QUALITY,
                detail_code="PIXEL_TAG_LOSS_INJECTION_NOT_REJECTED",
                service_definition_sha256=self.service_definition_sha256,
                frame=frame_evidence,
                detection_batch=batch,
                pose_observation=pose,
                quality=quality,
            )
        if not quality.passed:
            return VirtualPixelVisionResult(
                sequence=selected_sequence,
                capture_mode=capture_mode,
                status="FAULT",
                stage=VirtualPixelVisionStage.QUALITY,
                detail_code="PIXEL_BOARD_POSE_QUALITY_REJECTED",
                service_definition_sha256=self.service_definition_sha256,
                frame=frame_evidence,
                detection_batch=batch,
                pose_observation=pose,
                quality=quality,
            )
        return VirtualPixelVisionResult(
            sequence=selected_sequence,
            capture_mode=capture_mode,
            status="PASS",
            stage=VirtualPixelVisionStage.COMPLETE,
            detail_code="PIXEL_BOARD_POSE_ACCEPTED",
            service_definition_sha256=self.service_definition_sha256,
            frame=frame_evidence,
            detection_batch=batch,
            pose_observation=pose,
            quality=quality,
        )


__all__ = [
    "HELD_OUT_STATION_TAG_IDS",
    "MAX_VIRTUAL_PIXEL_VISION_ATTEMPTS",
    "WORLD_TAG_IDS",
    "VirtualPixelCaptureMode",
    "VirtualPixelFrameEvidence",
    "VirtualPixelVisionAttempt",
    "VirtualPixelVisionAttemptLedger",
    "VirtualPixelVisionError",
    "VirtualPixelVisionQuality",
    "VirtualPixelVisionQualityPolicy",
    "VirtualPixelVisionResult",
    "VirtualPixelVisionService",
    "VirtualPixelVisionStage",
    "virtual_pixel_vision_attempt_ledger_from_dict",
]
