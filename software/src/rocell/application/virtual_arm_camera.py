"""Plan-blind, joint-dependent arm-camera pixel simulation.

This module joins four independently checked boundaries:

* achieved six-joint feedback is projected through the pinned RoArm-M3 URDF;
* a settled capture bracket binds that pose to explicit synthetic timing;
* the resulting ``C_arm_T_board`` renders a real JPEG, including pixel faults;
* the existing independent detector and planar estimator recover board pose.

No action index, target ID, planned key/tap coordinate, or expected tag corner is
accepted by :meth:`VirtualArmCameraVisionService.process`.  The private board
truth is used only by the synthetic image source and is never serialized in a
result.  All records are permanently zero-authority simulation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from rocell.geometry import JointPosition, RigidTransform, Rotation3, Vec3
from rocell.simulation import (
    PinholeCameraModel,
    SyntheticCaptureTiming,
    SyntheticOverviewRasterRenderer,
    SyntheticRasterConfig,
    SyntheticRasterError,
    SyntheticRenderedFrame,
    VirtualArmFeedback,
)
from rocell.vision.apriltag_codebook import DEFAULT_APRILTAG_36H11_CODEBOOK
from rocell.vision.camera import TimestampQuality
from rocell.vision.detections import AprilTagDetectionBatch, FrameCaptureBinding
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
from rocell.vision.pose_estimation_records import AprilTagPoseObservation
from rocell.vision.detections import TagReference

from .arm_camera_pose import (
    ARM_CAMERA_BINDING_SOURCE_KEYS,
    ARM_CAMERA_JOINT_ORDER,
    AchievedJointStateSource,
    AchievedModelJointPositions,
    ArmCameraKinematicBinding,
    ArmCameraOpticalPose,
    ArmCameraPoseError,
    ArmCameraPoseProjector,
    ArmCameraTransformSource,
    achieved_joint_sample_sha256,
)
from .board_pose_correction import (
    ArmCameraBoardMeasurement,
    BoardRegistration,
)
from .context import SimulationContext, revalidate_simulation_context
from .reach_optimizer import ReachStudyInput
from .runtime_ports import (
    ArmFeedbackSample,
    RuntimeAuthority,
    RuntimeExecutionMode,
    RuntimeInstant,
)
from .virtual_board_truth import HiddenVirtualBoardTruth


VIRTUAL_ARM_CAMERA_CLOCK = "virtual_arm_camera_clock"
VIRTUAL_ARM_CAMERA_SCHEMA = "rocell.virtual_arm_camera_result.v1"
MAX_VIRTUAL_ARM_CAMERA_SEQUENCE = 1_000_000_000
_MAX_TIMESTAMP_NS = (1 << 63) - 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class VirtualArmCameraError(ValueError):
    """An arm-camera simulation contract is invalid or incoherent."""


class VirtualArmCameraCaptureMode(str, Enum):
    """Pixel/timing fault selected without any semantic target input."""

    NORMAL = "NORMAL"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    TAG_LOSS = "TAG_LOSS"
    EXCESS_BLUR = "EXCESS_BLUR"
    EXCESS_NOISE = "EXCESS_NOISE"
    UNQUALIFIED_TIMESTAMP = "UNQUALIFIED_TIMESTAMP"
    STALE_FRAME = "STALE_FRAME"


class VirtualArmCameraStage(str, Enum):
    JOINT_POSE = "JOINT_POSE"
    SYNCHRONIZATION = "SYNCHRONIZATION"
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
        raise VirtualArmCameraError(
            f"arm-camera value is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise VirtualArmCameraError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _bounded_integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_VIRTUAL_ARM_CAMERA_SEQUENCE,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VirtualArmCameraError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise VirtualArmCameraError(f"{label} must be within [{minimum}, {maximum}]")
    return value


def _bounded_float(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VirtualArmCameraError(f"{label} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise VirtualArmCameraError(f"{label} must be within [{minimum}, {maximum}]")
    return parsed


def _bounded_text(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise VirtualArmCameraError(f"{label} must be non-empty trimmed text")
    if len(value) > maximum or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise VirtualArmCameraError(f"{label} is not bounded printable text")
    return value


def _authority() -> RuntimeAuthority:
    return RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL)


def _authority_dict() -> dict[str, object]:
    authority = _authority()
    return {
        "execution_mode": authority.execution_mode.value,
        "hardware_accessed": authority.hardware_accessed,
        "hardware_commands_generated": authority.hardware_commands_generated,
        "live_motion_authorized": authority.live_motion_authorized,
        "physical_contact_authorized": authority.physical_contact_authorized,
        "physical_release_effect": authority.physical_release_effect,
        "can_release_physical_gates": False,
    }


def _transform_dict(transform: RigidTransform) -> dict[str, object]:
    return {
        "to_frame": transform.parent_frame,
        "from_frame": transform.child_frame,
        "rotation_row_major": list(transform.rotation.matrix),
        "translation_mm": [
            transform.translation_mm.x,
            transform.translation_mm.y,
            transform.translation_mm.z,
        ],
    }


def _instant_ns(instant: RuntimeInstant, label: str) -> int:
    if not isinstance(instant, RuntimeInstant):
        raise VirtualArmCameraError(f"{label} must be RuntimeInstant")
    if instant.tick_period_ns is None:
        raise VirtualArmCameraError(f"{label} has no declared tick period")
    nanoseconds = instant.tick * instant.tick_period_ns
    if nanoseconds > _MAX_TIMESTAMP_NS:
        raise VirtualArmCameraError(f"{label} exceeds the timestamp bound")
    return nanoseconds


def _rotation_difference_deg(left: Rotation3, right: Rotation3) -> float:
    # trace(R_left * R_right^T) equals their elementwise matrix dot product.
    trace = sum(a * b for a, b in zip(left.matrix, right.matrix))
    cosine = min(1.0, max(-1.0, (trace - 1.0) / 2.0))
    return math.degrees(math.acos(cosine))


@dataclass(frozen=True, slots=True)
class ArmCameraCaptureBracket:
    """Two achieved-state samples bracketing one declared exposure instant."""

    capture_sequence: int
    before_feedback: ArmFeedbackSample[AchievedModelJointPositions]
    after_feedback: ArmFeedbackSample[AchievedModelJointPositions]
    settled_since: RuntimeInstant
    exposure_at: RuntimeInstant

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capture_sequence",
            _bounded_integer(
                self.capture_sequence,
                "capture_sequence",
                minimum=1,
            ),
        )
        for name in ("before_feedback", "after_feedback"):
            sample = getattr(self, name)
            if not isinstance(sample, ArmFeedbackSample):
                raise TypeError(f"{name} must be ArmFeedbackSample")
            if not isinstance(sample.feedback, AchievedModelJointPositions):
                raise TypeError(
                    f"{name}.feedback must be AchievedModelJointPositions"
                )
        for name in ("settled_since", "exposure_at"):
            if not isinstance(getattr(self, name), RuntimeInstant):
                raise TypeError(f"{name} must be RuntimeInstant")

    @property
    def bracket_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        def instant(value: RuntimeInstant) -> dict[str, object]:
            return {
                "clock_id": value.clock_id,
                "tick": value.tick,
                "tick_period_ns": value.tick_period_ns,
            }

        return {
            "schema": "rocell.arm_camera_capture_bracket.v1",
            "capture_sequence": self.capture_sequence,
            "before_joint_sample_sha256": achieved_joint_sample_sha256(
                self.before_feedback
            ),
            "after_joint_sample_sha256": achieved_joint_sample_sha256(
                self.after_feedback
            ),
            "settled_since": instant(self.settled_since),
            "exposure_at": instant(self.exposure_at),
            "processor_received_target_or_action": False,
            "authority": _authority_dict(),
        }


@dataclass(frozen=True, slots=True)
class ArmCameraSynchronizationPolicy:
    """Bounded synthetic stop-and-look timing and motion policy."""

    clock_id: str = VIRTUAL_ARM_CAMERA_CLOCK
    minimum_settled_duration_ns: int = 20_000_000
    maximum_feedback_bracket_ns: int = 10_000_000
    maximum_joint_change_rad: float = 1e-5
    maximum_camera_translation_mm: float = 0.01
    maximum_camera_rotation_deg: float = 0.01

    def __post_init__(self) -> None:
        object.__setattr__(self, "clock_id", _bounded_text(self.clock_id, "clock_id"))
        for name in (
            "minimum_settled_duration_ns",
            "maximum_feedback_bracket_ns",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_integer(
                    getattr(self, name),
                    name,
                    minimum=1,
                    maximum=10_000_000_000,
                ),
            )
        for name, maximum in (
            ("maximum_joint_change_rad", 1.0),
            ("maximum_camera_translation_mm", 100.0),
            ("maximum_camera_rotation_deg", 180.0),
        ):
            object.__setattr__(
                self,
                name,
                _bounded_float(
                    getattr(self, name), name, minimum=0.0, maximum=maximum
                ),
            )

    @property
    def content_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.arm_camera_synchronization_policy.v1",
            "clock_id": self.clock_id,
            "minimum_settled_duration_ns": self.minimum_settled_duration_ns,
            "maximum_feedback_bracket_ns": self.maximum_feedback_bracket_ns,
            "maximum_joint_change_rad": self.maximum_joint_change_rad,
            "maximum_camera_translation_mm": self.maximum_camera_translation_mm,
            "maximum_camera_rotation_deg": self.maximum_camera_rotation_deg,
            "qualification": "SYNTHETIC_STOP_AND_LOOK_NOT_PHYSICAL_TIMING",
            "authority": _authority_dict(),
        }


@dataclass(frozen=True, slots=True)
class ArmCameraSynchronizationAssessment:
    passed: bool
    detail_code: str
    before_joint_sample_sha256: str
    after_joint_sample_sha256: str
    maximum_joint_change_rad: float | None
    camera_translation_change_mm: float | None
    camera_rotation_change_deg: float | None
    settled_duration_ns: int | None
    feedback_bracket_ns: int | None
    policy_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool):
            raise VirtualArmCameraError("synchronization passed must be boolean")
        object.__setattr__(
            self, "detail_code", _bounded_text(self.detail_code, "detail_code")
        )
        for name in (
            "before_joint_sample_sha256",
            "after_joint_sample_sha256",
            "policy_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        for name, maximum in (
            ("maximum_joint_change_rad", 10.0),
            ("camera_translation_change_mm", 1_000_000.0),
            ("camera_rotation_change_deg", 180.0),
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _bounded_float(value, name, minimum=0.0, maximum=maximum),
                )
        for name in ("settled_duration_ns", "feedback_bracket_ns"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _bounded_integer(
                        value, name, maximum=10_000_000_000
                    ),
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "detail_code": self.detail_code,
            "before_joint_sample_sha256": self.before_joint_sample_sha256,
            "after_joint_sample_sha256": self.after_joint_sample_sha256,
            "maximum_joint_change_rad": self.maximum_joint_change_rad,
            "camera_translation_change_mm": self.camera_translation_change_mm,
            "camera_rotation_change_deg": self.camera_rotation_change_deg,
            "settled_duration_ns": self.settled_duration_ns,
            "feedback_bracket_ns": self.feedback_bracket_ns,
            "policy_sha256": self.policy_sha256,
            "physical_timing_qualified": False,
        }


@dataclass(frozen=True, slots=True)
class ArmCameraVisionQualityPolicy:
    minimum_inlier_tags: int = 4
    maximum_inlier_rmse_px: float = 1.25
    maximum_covariance_diagonal: float = 1_000.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_inlier_tags",
            _bounded_integer(
                self.minimum_inlier_tags,
                "minimum_inlier_tags",
                minimum=2,
                maximum=6,
            ),
        )
        for name, maximum in (
            ("maximum_inlier_rmse_px", 100.0),
            ("maximum_covariance_diagonal", 1_000_000_000.0),
        ):
            # The planar estimator rejects RMSE limits below 1e-6.  Enforce
            # that same boundary here so an accepted quality policy can never
            # fail later merely because the downstream policy is narrower.
            minimum = 1e-6 if name == "maximum_inlier_rmse_px" else 1e-12
            object.__setattr__(
                self,
                name,
                _bounded_float(
                    getattr(self, name), name, minimum=minimum, maximum=maximum
                ),
            )

    @property
    def content_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.arm_camera_vision_quality_policy.v1",
            "minimum_inlier_tags": self.minimum_inlier_tags,
            "maximum_inlier_rmse_px": self.maximum_inlier_rmse_px,
            "maximum_covariance_diagonal": self.maximum_covariance_diagonal,
            "truth_error_used_for_acceptance": False,
            "physical_release_effect": "NONE",
        }


@dataclass(frozen=True, slots=True)
class ArmCameraVisionQuality:
    detected_tag_ids: tuple[int, ...]
    inlier_tag_ids: tuple[int, ...]
    inlier_rmse_px: float
    maximum_covariance_diagonal: float
    tag_count_passed: bool
    residual_passed: bool
    covariance_passed: bool
    policy_sha256: str

    def __post_init__(self) -> None:
        detected = tuple(
            _bounded_integer(value, "detected tag id", maximum=1_000_000)
            for value in self.detected_tag_ids
        )
        inliers = tuple(
            _bounded_integer(value, "inlier tag id", maximum=1_000_000)
            for value in self.inlier_tag_ids
        )
        if detected != tuple(sorted(set(detected))):
            raise VirtualArmCameraError("detected tag IDs must be sorted and unique")
        if inliers != tuple(sorted(set(inliers))) or not set(inliers).issubset(detected):
            raise VirtualArmCameraError("inlier tag IDs must be a detected subset")
        object.__setattr__(self, "detected_tag_ids", detected)
        object.__setattr__(self, "inlier_tag_ids", inliers)
        for name in ("inlier_rmse_px", "maximum_covariance_diagonal"):
            object.__setattr__(
                self,
                name,
                _bounded_float(
                    getattr(self, name), name, minimum=0.0, maximum=1e12
                ),
            )
        for name in ("tag_count_passed", "residual_passed", "covariance_passed"):
            if not isinstance(getattr(self, name), bool):
                raise VirtualArmCameraError(f"{name} must be boolean")
        object.__setattr__(
            self, "policy_sha256", _digest(self.policy_sha256, "policy_sha256")
        )

    @property
    def passed(self) -> bool:
        return self.tag_count_passed and self.residual_passed and self.covariance_passed

    def to_dict(self) -> dict[str, object]:
        return {
            "detected_tag_ids": list(self.detected_tag_ids),
            "inlier_tag_ids": list(self.inlier_tag_ids),
            "inlier_rmse_px": self.inlier_rmse_px,
            "maximum_covariance_diagonal": self.maximum_covariance_diagonal,
            "tag_count_passed": self.tag_count_passed,
            "residual_passed": self.residual_passed,
            "covariance_passed": self.covariance_passed,
            "passed": self.passed,
            "truth_error_used_for_acceptance": False,
            "policy_sha256": self.policy_sha256,
        }


def _quality_gate_flags(
    *,
    inlier_tag_count: int,
    inlier_rmse_px: float,
    maximum_covariance_diagonal: float,
    policy: ArmCameraVisionQualityPolicy,
) -> tuple[bool, bool, bool]:
    """Compute the three quality gates from measurements and one policy."""

    return (
        inlier_tag_count >= policy.minimum_inlier_tags,
        inlier_rmse_px <= policy.maximum_inlier_rmse_px,
        maximum_covariance_diagonal <= policy.maximum_covariance_diagonal,
    )


_VISION_RESULT_ISSUER_TOKEN = object()


@dataclass(frozen=True, slots=True)
class _VisionResultIssuer:
    """Private service identity needed to revalidate immutable result copies.

    ``dataclasses.replace`` carries this record into the replacement.  Result
    validation can therefore recompute policy decisions against the issuing
    service instead of trusting caller-editable booleans or status text.
    """

    _token: object = field(repr=False, compare=False)
    service_definition_sha256: str
    synchronization_policy_sha256: str
    quality_policy: ArmCameraVisionQualityPolicy
    arm_camera_binding_sha256: str
    camera_intrinsics_sha256: str
    tag_map_sha256: str
    detector_configuration_sha256: str
    estimator_configuration_sha256: str
    renderer_config_sha256_by_mode: tuple[
        tuple[VirtualArmCameraCaptureMode, str], ...
    ]

    def __post_init__(self) -> None:
        if self._token is not _VISION_RESULT_ISSUER_TOKEN:
            raise VirtualArmCameraError("invalid arm-camera result issuer token")
        for name in (
            "service_definition_sha256",
            "synchronization_policy_sha256",
            "arm_camera_binding_sha256",
            "camera_intrinsics_sha256",
            "tag_map_sha256",
            "detector_configuration_sha256",
            "estimator_configuration_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.quality_policy, ArmCameraVisionQualityPolicy):
            raise TypeError("quality_policy must be ArmCameraVisionQualityPolicy")
        if not isinstance(self.renderer_config_sha256_by_mode, tuple):
            raise VirtualArmCameraError(
                "renderer config identities must be an immutable tuple"
            )
        configs: dict[VirtualArmCameraCaptureMode, str] = {}
        for index, pair in enumerate(self.renderer_config_sha256_by_mode):
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise VirtualArmCameraError(
                    f"renderer config identity {index} must be an immutable pair"
                )
            mode, digest = pair
            if not isinstance(mode, VirtualArmCameraCaptureMode):
                raise TypeError("renderer config mode is invalid")
            if mode in configs:
                raise VirtualArmCameraError("renderer config modes must be unique")
            configs[mode] = _digest(digest, f"renderer config for {mode.value}")
        expected_modes = set(VirtualArmCameraCaptureMode) - {
            VirtualArmCameraCaptureMode.CAMERA_UNAVAILABLE
        }
        if set(configs) != expected_modes:
            raise VirtualArmCameraError(
                "renderer configs must cover every image-producing capture mode"
            )
        object.__setattr__(
            self,
            "renderer_config_sha256_by_mode",
            tuple(sorted(configs.items(), key=lambda item: item[0].value)),
        )

    def renderer_config_sha256(
        self, mode: VirtualArmCameraCaptureMode
    ) -> str | None:
        return dict(self.renderer_config_sha256_by_mode).get(mode)


@dataclass(frozen=True, slots=True)
class VirtualArmCameraVisionResult:
    _issuer: _VisionResultIssuer = field(repr=False, compare=False)
    capture_sequence: int
    capture_mode: VirtualArmCameraCaptureMode
    status: str
    stage: VirtualArmCameraStage
    detail_code: str
    service_definition_sha256: str
    capture_bracket_sha256: str
    synchronization: ArmCameraSynchronizationAssessment
    arm_camera_pose: ArmCameraOpticalPose | None = None
    rendered_frame: SyntheticRenderedFrame | None = field(default=None, repr=False)
    detection_batch: AprilTagDetectionBatch | None = None
    pose_observation: AprilTagPoseObservation | None = None
    quality: ArmCameraVisionQuality | None = None
    authority: RuntimeAuthority = field(init=False, default_factory=_authority)

    def __post_init__(self) -> None:
        if (
            not isinstance(self._issuer, _VisionResultIssuer)
            or self._issuer._token is not _VISION_RESULT_ISSUER_TOKEN
        ):
            raise VirtualArmCameraError(
                "arm-camera results may only be issued by the vision service"
            )
        object.__setattr__(
            self,
            "capture_sequence",
            _bounded_integer(self.capture_sequence, "capture_sequence", minimum=1),
        )
        if not isinstance(self.capture_mode, VirtualArmCameraCaptureMode):
            raise TypeError("capture_mode must be VirtualArmCameraCaptureMode")
        if self.status not in ("PASS", "FAULT"):
            raise VirtualArmCameraError("status must be PASS or FAULT")
        if not isinstance(self.stage, VirtualArmCameraStage):
            raise TypeError("stage must be VirtualArmCameraStage")
        object.__setattr__(
            self, "detail_code", _bounded_text(self.detail_code, "detail_code")
        )
        for name in ("service_definition_sha256", "capture_bracket_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if self.service_definition_sha256 != (
            self._issuer.service_definition_sha256
        ):
            raise VirtualArmCameraError(
                "result service definition differs from its issuing service"
            )
        if not isinstance(self.synchronization, ArmCameraSynchronizationAssessment):
            raise TypeError("synchronization must be ArmCameraSynchronizationAssessment")
        if self.synchronization.policy_sha256 != (
            self._issuer.synchronization_policy_sha256
        ):
            raise VirtualArmCameraError(
                "synchronization assessment uses a different service policy"
            )
        expected_types = (
            ("arm_camera_pose", self.arm_camera_pose, ArmCameraOpticalPose),
            ("rendered_frame", self.rendered_frame, SyntheticRenderedFrame),
            ("detection_batch", self.detection_batch, AprilTagDetectionBatch),
            ("pose_observation", self.pose_observation, AprilTagPoseObservation),
            ("quality", self.quality, ArmCameraVisionQuality),
        )
        for name, value, expected in expected_types:
            if value is not None and not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__} or None")

        if self.arm_camera_pose is not None and (
            self.arm_camera_pose.binding_sha256
            != self._issuer.arm_camera_binding_sha256
        ):
            raise VirtualArmCameraError(
                "arm-camera pose uses a different service binding"
            )
        if self.rendered_frame is not None:
            expected_renderer_config = self._issuer.renderer_config_sha256(
                self.capture_mode
            )
            if (
                expected_renderer_config is None
                or self.rendered_frame.renderer_config_sha256
                != expected_renderer_config
            ):
                raise VirtualArmCameraError(
                    "rendered frame does not match the capture-mode configuration"
                )
        if self.detection_batch is not None and (
            self.detection_batch.detector.configuration_sha256
            != self._issuer.detector_configuration_sha256
        ):
            raise VirtualArmCameraError(
                "detection batch uses a different service configuration"
            )
        if self.pose_observation is not None and (
            self.pose_observation.camera_intrinsics_sha256
            != self._issuer.camera_intrinsics_sha256
            or self.pose_observation.tag_map_sha256
            != self._issuer.tag_map_sha256
            or self.pose_observation.estimator.configuration_sha256
            != self._issuer.estimator_configuration_sha256
        ):
            raise VirtualArmCameraError(
                "pose observation uses different service calibration or policy"
            )

        # Pipeline records are prefix-ordered.  Applying this to fault results
        # as well as passes prevents a caller from attaching a quality record
        # to an earlier failure and then relabeling that copy as successful.
        if self.rendered_frame is not None and self.arm_camera_pose is None:
            raise VirtualArmCameraError("rendered frame requires an arm-camera pose")
        if self.detection_batch is not None and self.rendered_frame is None:
            raise VirtualArmCameraError("detection batch requires a rendered frame")
        if self.pose_observation is not None and self.detection_batch is None:
            raise VirtualArmCameraError("pose observation requires detections")
        if self.quality is not None and self.pose_observation is None:
            raise VirtualArmCameraError("quality assessment requires a pose observation")

        if self.arm_camera_pose is not None and (
            self.arm_camera_pose.joint_sample_sha256
            != self.synchronization.before_joint_sample_sha256
        ):
            raise VirtualArmCameraError(
                "arm-camera pose is not bound to synchronized before feedback"
            )
        if self.rendered_frame is not None and self.detection_batch is not None:
            packet = self.rendered_frame.frame_packet
            expected_frame_binding = FrameCaptureBinding.from_frame_packet(
                packet,
                host_clock=VIRTUAL_ARM_CAMERA_CLOCK,
            )
            if self.detection_batch.frame != expected_frame_binding:
                raise VirtualArmCameraError(
                    "detection batch is not bound to the rendered frame"
                )
        if self.detection_batch is not None and self.pose_observation is not None:
            if self.pose_observation.detection_batch.content_hash != (
                self.detection_batch.content_hash
            ):
                raise VirtualArmCameraError(
                    "pose observation is not bound to the detection batch"
                )
        if self.pose_observation is not None and self.quality is not None:
            covariance_diagonal = tuple(
                self.pose_observation.covariance.row_major[index * 6 + index]
                for index in range(6)
            )
            expected_detected = tuple(
                sorted(
                    tag.tag_id
                    for tag in self.pose_observation.detection_batch.accepted_tags
                )
            )
            expected_inliers = tuple(
                sorted(tag.tag_id for tag in self.pose_observation.used_tags)
            )
            if (
                self.pose_observation.pose.parent_frame != "C_arm"
                or self.pose_observation.pose.child_frame != "board"
                or self.quality.detected_tag_ids != expected_detected
                or self.quality.inlier_tag_ids != expected_inliers
                or self.quality.inlier_rmse_px
                != self.pose_observation.inlier_rmse_px
                or self.quality.maximum_covariance_diagonal
                != max(covariance_diagonal)
            ):
                raise VirtualArmCameraError(
                    "quality metrics contain a mixed or inconsistent pipeline record"
                )
        if self.quality is not None:
            if self.quality.policy_sha256 != self._issuer.quality_policy.content_hash:
                raise VirtualArmCameraError(
                    "quality assessment uses a different service policy"
                )
            expected_flags = _quality_gate_flags(
                inlier_tag_count=len(self.quality.inlier_tag_ids),
                inlier_rmse_px=self.quality.inlier_rmse_px,
                maximum_covariance_diagonal=(
                    self.quality.maximum_covariance_diagonal
                ),
                policy=self._issuer.quality_policy,
            )
            actual_flags = (
                self.quality.tag_count_passed,
                self.quality.residual_passed,
                self.quality.covariance_passed,
            )
            if actual_flags != expected_flags:
                raise VirtualArmCameraError(
                    "quality gate flags differ from deterministic policy evaluation"
                )

        complete_pipeline = (
            self.synchronization.passed
            and self.arm_camera_pose is not None
            and self.rendered_frame is not None
            and self.detection_batch is not None
            and self.pose_observation is not None
            and self.quality is not None
        )
        expected_pass = (
            complete_pipeline
            and self.capture_mode is VirtualArmCameraCaptureMode.NORMAL
            and self.quality is not None
            and self.quality.passed
        )
        if self.passed != expected_pass:
            raise VirtualArmCameraError(
                "result status differs from deterministic pipeline evaluation"
            )
        if expected_pass:
            assert self.rendered_frame is not None
            if (
                self.stage is not VirtualArmCameraStage.COMPLETE
                or self.detail_code != "ARM_CAMERA_BOARD_POSE_ACCEPTED"
                or self.rendered_frame.frame_packet.source_sequence
                != self.capture_sequence
            ):
                raise VirtualArmCameraError(
                    "PASS result is not a complete normal pipeline"
                )
        elif self.stage is VirtualArmCameraStage.COMPLETE:
            raise VirtualArmCameraError("FAULT result cannot use the COMPLETE stage")
        elif self.quality is not None:
            expected_detail = (
                "ARM_CAMERA_FAULT_INJECTION_NOT_REJECTED"
                if self.quality.passed
                else "ARM_CAMERA_BOARD_POSE_QUALITY_REJECTED"
            )
            if (
                self.stage is not VirtualArmCameraStage.QUALITY
                or self.detail_code != expected_detail
            ):
                raise VirtualArmCameraError(
                    "quality-stage fault status is inconsistent"
                )
        if not isinstance(self.authority, RuntimeAuthority) or (
            self.authority.execution_mode is not RuntimeExecutionMode.VIRTUAL
            or not self.authority.is_zero_authority
        ):
            raise VirtualArmCameraError("result authority must be virtual zero")

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def observed_Wv_T_board(self) -> RigidTransform | None:
        # A rejected estimate remains available as diagnostic evidence, but it
        # must never escape through the accessor consumed by correction logic.
        if (
            not self.passed
            or self.arm_camera_pose is None
            or self.pose_observation is None
        ):
            return None
        pose = self.pose_observation.pose
        if pose.parent_frame != "C_arm" or pose.child_frame != "board":
            raise VirtualArmCameraError("pose observation must be C_arm_T_board")
        return self.arm_camera_pose.Wv_T_C_arm.compose(pose)

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": VIRTUAL_ARM_CAMERA_SCHEMA,
            "capture_sequence": self.capture_sequence,
            "capture_mode": self.capture_mode.value,
            "status": self.status,
            "stage": self.stage.value,
            "detail_code": self.detail_code,
            "service_definition_sha256": self.service_definition_sha256,
            "capture_bracket_sha256": self.capture_bracket_sha256,
            "synchronization": self.synchronization.to_dict(),
            "arm_camera_pose": (
                None if self.arm_camera_pose is None else self.arm_camera_pose.to_dict()
            ),
            "rendered_frame": (
                None if self.rendered_frame is None else self.rendered_frame.to_dict()
            ),
            "detection_batch": (
                None if self.detection_batch is None else self.detection_batch.to_dict()
            ),
            "pose_observation": (
                None if self.pose_observation is None else self.pose_observation.to_dict()
            ),
            "quality": None if self.quality is None else self.quality.to_dict(),
            "processor_input_contract": "CAPTURE_BRACKET_AND_FAULT_MODE_ONLY",
            "target_or_action_received_by_processor": False,
            "synthetic_truth_transform_serialized": False,
            "jpeg_bytes_serialized": False,
            "arm_mounted_camera_simulated": True,
            "robot_frame_correction_applied": False,
            "authority": _authority_dict(),
        }

    @property
    def result_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "result_hash": self.result_hash}


def _synthetic_mount_rotation() -> Rotation3:
    """Return the screened fixed optical orientation without rounded-matrix drift."""

    forward = Vec3(-0.519972, 0.850588, 0.078289).normalized()
    right_hint = Vec3(-0.340978, -0.290726, 0.893987)
    right = (right_hint - forward.scaled(right_hint.dot(forward))).normalized()
    down = forward.cross(right)
    # Columns are camera +X/right, +Y/down, +Z/forward expressed in link2.
    return Rotation3(
        (
            right.x,
            down.x,
            forward.x,
            right.y,
            down.y,
            forward.y,
            right.z,
            down.z,
            forward.z,
        )
    )


def make_unmeasured_synthetic_arm_camera_binding(
    context: SimulationContext,
) -> ArmCameraKinematicBinding:
    """Build the screened simulation fixture without editing physical config."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be SimulationContext")
    frame_artifact = context.bundle_lock.artifact("arm_frame_contract")
    camera_artifact = context.bundle_lock.artifact("camera_manifest")
    model_artifact = context.bundle_lock.artifact("local_roarm_urdf")
    link2_T_E = RigidTransform(
        "link2",
        "E",
        Rotation3.identity(),
        Vec3(200.0, 0.0, 0.0),
    )
    E_T_C_arm = RigidTransform(
        "E",
        "C_arm",
        _synthetic_mount_rotation(),
        Vec3(10.0, 0.0, 15.0),
    )
    joint_binding = {
        "schema": "rocell.synthetic_joint_coordinate_binding.v1",
        "joint_order": list(ARM_CAMERA_JOINT_ORDER),
        "units": "rad",
        "offsets_applied": False,
        "controller_frame_correlated": False,
    }
    carrier_fixture = {
        "schema": "rocell.unmeasured_synthetic_carrier_fixture.v1",
        "link2_T_E": _transform_dict(link2_T_E),
        "physical_measurement": False,
    }
    extrinsic_fixture = {
        "schema": "rocell.unmeasured_synthetic_camera_extrinsic.v1",
        "E_T_C_arm": _transform_dict(E_T_C_arm),
        "physical_measurement": False,
    }
    hashes = {
        "arm_frame_contract": frame_artifact.sha256,
        "camera_manifest": camera_artifact.sha256,
        "carrier_kinematic_model": model_artifact.sha256,
        "carrier_registration": _stable_hash(carrier_fixture),
        "eye_on_arm_extrinsic": _stable_hash(extrinsic_fixture),
        "joint_coordinate_binding": _stable_hash(joint_binding),
    }
    return ArmCameraKinematicBinding(
        link2_T_E=link2_T_E,
        E_T_C_arm=E_T_C_arm,
        carrier_source_kind=ArmCameraTransformSource.SYNTHETIC_FIXTURE,
        extrinsic_source_kind=ArmCameraTransformSource.SYNTHETIC_FIXTURE,
        source_hashes=tuple(
            (key, hashes[key]) for key in ARM_CAMERA_BINDING_SOURCE_KEYS
        ),
    )


def planner_Wv_T_board(study_input: ReachStudyInput) -> RigidTransform:
    """Explicitly relabel the study's vendor ``world`` root as frozen ``Wv``."""

    if not isinstance(study_input, ReachStudyInput):
        raise TypeError("study_input must be ReachStudyInput")
    source = study_input.board_T_vendor_world
    if source.parent_frame != "board" or source.child_frame != "world":
        raise VirtualArmCameraError("study input must provide board_T_world")
    board_T_Wv = RigidTransform(
        "board", "Wv", source.rotation, source.translation_mm
    )
    return board_T_Wv.inverse()


def initial_planner_board_registration(
    study_input: ReachStudyInput,
) -> BoardRegistration:
    """Bind the nominal planner transform as immutable revision zero."""

    return BoardRegistration(
        revision=0,
        Wv_T_board=planner_Wv_T_board(study_input),
        source_hashes=(
            ("reach_study_input", _stable_hash(study_input.to_dict())),
        ),
    )


def offset_synthetic_board_truth(
    nominal_Wv_T_board: RigidTransform,
    *,
    translation_Wv_mm: Vec3 = Vec3.zero(),
    yaw_board_rad: float = 0.0,
) -> RigidTransform:
    """Create an injected virtual truth pose, never a physical calibration."""

    if not isinstance(nominal_Wv_T_board, RigidTransform):
        raise TypeError("nominal_Wv_T_board must be RigidTransform")
    if (
        nominal_Wv_T_board.parent_frame != "Wv"
        or nominal_Wv_T_board.child_frame != "board"
    ):
        raise VirtualArmCameraError("nominal transform must be Wv_T_board")
    if not isinstance(translation_Wv_mm, Vec3):
        raise TypeError("translation_Wv_mm must be Vec3")
    yaw = _bounded_float(
        yaw_board_rad,
        "yaw_board_rad",
        minimum=-math.pi,
        maximum=math.pi,
    )
    return RigidTransform(
        "Wv",
        "board",
        nominal_Wv_T_board.rotation.compose(Rotation3.from_rpy(0.0, 0.0, yaw)),
        nominal_Wv_T_board.translation_mm + translation_Wv_mm,
    )


def achieved_joint_sample_from_virtual_feedback(
    feedback: VirtualArmFeedback,
    *,
    fixed_gripper_position: JointPosition,
    sample_id: str,
    observed_at: RuntimeInstant,
    stale: bool = False,
) -> ArmFeedbackSample[AchievedModelJointPositions]:
    """Adapt plant feedback while explicitly adding the scenario gripper joint."""

    if not isinstance(feedback, VirtualArmFeedback):
        raise TypeError("feedback must be VirtualArmFeedback")
    if not isinstance(fixed_gripper_position, JointPosition):
        raise TypeError("fixed_gripper_position must be JointPosition")
    if feedback.last_waypoint_sequence is None:
        raise VirtualArmCameraError("virtual feedback has no achieved waypoint sequence")
    if not isinstance(observed_at, RuntimeInstant):
        raise TypeError("observed_at must be RuntimeInstant")
    arm_positions = dict(feedback.joint_positions_rad)
    positions = tuple(
        (
            name,
            fixed_gripper_position
            if name == ARM_CAMERA_JOINT_ORDER[-1]
            else JointPosition.radians(arm_positions[name]),
        )
        for name in ARM_CAMERA_JOINT_ORDER
    )
    source_hash = _stable_hash(
        {
            "schema": "rocell.virtual_feedback_to_achieved_joints.v1",
            "virtual_feedback": feedback.to_dict(),
            "fixed_gripper_position_rad": fixed_gripper_position.value,
            "fixed_gripper_source": "SIMULATION_SCENARIO_EXPLICIT_INPUT",
        }
    )
    return ArmFeedbackSample(
        sample_id=_bounded_text(sample_id, "sample_id"),
        observed_at=observed_at,
        sequence=feedback.last_waypoint_sequence,
        feedback=AchievedModelJointPositions(
            positions=positions,
            source_kind=AchievedJointStateSource.VIRTUAL_PLANT,
            source_state_sha256=source_hash,
        ),
        stale=stale,
    )


def correction_measurement_from_vision_result(
    result: VirtualArmCameraVisionResult,
    *,
    previous_source_sequence: int,
    previous_freshness_token: str,
    evaluated_at: RuntimeInstant,
) -> ArmCameraBoardMeasurement:
    """Adapt a passing plan-blind result into the pure correction contract.

    Action and target association still does not occur here.  The caller must
    supply the previous frame identity explicitly so freshness is evaluated by
    :func:`decide_board_pose_correction` rather than assumed by this adapter.
    """

    if not isinstance(result, VirtualArmCameraVisionResult):
        raise TypeError("result must be VirtualArmCameraVisionResult")
    if not result.passed:
        raise VirtualArmCameraError(
            "only a passing arm-camera result can become a correction measurement"
        )
    if (
        result.arm_camera_pose is None
        or result.rendered_frame is None
        or result.pose_observation is None
        or result.quality is None
        or result.synchronization.maximum_joint_change_rad is None
    ):
        raise VirtualArmCameraError("passing result lacks correction inputs")
    frame = result.rendered_frame.frame_packet
    if (
        frame.source_sequence is None
        or frame.source_timestamp_ns is None
        or frame.source_clock is None
        or frame.freshness_token is None
    ):
        raise VirtualArmCameraError("arm-camera frame lacks timing or freshness")
    if evaluated_at.clock_id != frame.source_clock:
        raise VirtualArmCameraError("evaluation clock differs from frame source clock")
    evaluated_ns = _instant_ns(evaluated_at, "evaluated_at")
    return ArmCameraBoardMeasurement(
        measurement_id=f"arm-camera-measurement-{result.capture_sequence:010d}",
        Wv_T_C_arm=result.arm_camera_pose.Wv_T_C_arm,
        C_arm_T_board=result.pose_observation.pose,
        timing_clock=frame.source_clock,
        timestamp_quality=frame.timestamp_quality,
        feedback_before_timestamp_ns=frame.host_request_ns,
        exposure_timestamp_ns=frame.source_timestamp_ns,
        feedback_after_timestamp_ns=frame.host_complete_ns,
        evaluated_at_timestamp_ns=evaluated_ns,
        maximum_joint_motion_during_bracket_rad=(
            result.synchronization.maximum_joint_change_rad
        ),
        source_sequence=frame.source_sequence,
        previous_source_sequence=_bounded_integer(
            previous_source_sequence,
            "previous_source_sequence",
            maximum=_MAX_TIMESTAMP_NS,
        ),
        freshness_token=frame.freshness_token,
        previous_freshness_token=_bounded_text(
            previous_freshness_token,
            "previous_freshness_token",
            maximum=1024,
        ),
        inlier_tag_count=len(result.quality.inlier_tag_ids),
        inlier_reprojection_rmse_px=result.quality.inlier_rmse_px,
        source_hashes=(
            ("arm_camera_binding", result.arm_camera_pose.binding_sha256),
            ("capture_bracket", result.capture_bracket_sha256),
            ("pose_observation", result.pose_observation.content_hash),
            ("service_definition", result.service_definition_sha256),
            ("vision_result", result.result_hash),
        ),
    )


@dataclass(frozen=True, slots=True)
class VirtualArmCameraVisionService:
    """Execute a bounded arm-camera JPEG/detector/pose pipeline."""

    context: SimulationContext = field(repr=False)
    binding: ArmCameraKinematicBinding
    truth: HiddenVirtualBoardTruth = field(repr=False)
    synchronization_policy: ArmCameraSynchronizationPolicy = field(
        default_factory=ArmCameraSynchronizationPolicy
    )
    quality_policy: ArmCameraVisionQualityPolicy = field(
        default_factory=ArmCameraVisionQualityPolicy
    )
    _projector: ArmCameraPoseProjector = field(init=False, repr=False)
    _camera: PinholeCameraModel = field(init=False, repr=False)
    _detector: AprilTag36h11PixelDetector = field(init=False, repr=False)
    _intrinsics: PinholeIntrinsics = field(init=False, repr=False)
    _tag_map: PlanarBoardTagMap = field(init=False, repr=False)
    _estimator: PlanarAprilTagBoardPoseEstimator = field(init=False, repr=False)
    _renderer_configs: Mapping[VirtualArmCameraCaptureMode, SyntheticRasterConfig] = field(
        init=False, repr=False
    )
    _service_definition: Mapping[str, object] = field(init=False, repr=False)
    _result_issuer: _VisionResultIssuer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, SimulationContext):
            raise TypeError("context must be SimulationContext")
        if not isinstance(self.binding, ArmCameraKinematicBinding):
            raise TypeError("binding must be ArmCameraKinematicBinding")
        if not isinstance(self.truth, HiddenVirtualBoardTruth):
            raise TypeError("truth must be HiddenVirtualBoardTruth")
        if self.truth.board_frame != self.context.scene.board_frame:
            raise VirtualArmCameraError("truth board frame differs from the scene")
        if not isinstance(self.synchronization_policy, ArmCameraSynchronizationPolicy):
            raise TypeError("synchronization_policy is invalid")
        if not isinstance(self.quality_policy, ArmCameraVisionQualityPolicy):
            raise TypeError("quality_policy is invalid")
        revalidate_simulation_context(self.context)

        projector = ArmCameraPoseProjector(
            model_path=self.context.scenario.model_path,
            binding=self.binding,
        )
        camera = PinholeCameraModel(
            width_px=1920,
            height_px=1080,
            fx_px=300.0,
            fy_px=300.0,
            cx_px=960.0,
            cy_px=540.0,
            optical_frame="C_arm",
        )
        detector = AprilTag36h11PixelDetector(
            AprilTagPixelDetectorConfiguration(host_clock=VIRTUAL_ARM_CAMERA_CLOCK),
            DEFAULT_APRILTAG_36H11_CODEBOOK,
        )
        intrinsics = PinholeIntrinsics(
            calibration_id="rc03.synthetic_arm_camera.unmeasured_wide_fov",
            width_px=camera.width_px,
            height_px=camera.height_px,
            fx_px=camera.fx_px,
            fy_px=camera.fy_px,
            cx_px=camera.cx_px,
            cy_px=camera.cy_px,
            source_sha256=_stable_hash(camera.to_dict()),
            camera_frame="C_arm",
        )
        tag_map = PlanarBoardTagMap(
            map_id="rc03.freeze005.synthetic_arm_camera_tag_plane",
            board_frame=self.context.scene.board_frame,
            tag_plane_z_board_mm=self.context.scenario.assumed_tag_plane_z_mm,
            tags=tuple(
                PlanarBoardTag(
                    tag=TagReference(tag.family, tag.tag_id),
                    corners_board_mm=tag.corners(),
                )
                for tag in self.context.scene.fiducials
            ),
            source_sha256=self.context.scene.source_hashes[
                "fiducials/apriltag_map.json"
            ],
        )
        estimator = PlanarAprilTagBoardPoseEstimator(
            PlanarPoseEstimatorConfig(
                minimum_inlier_tags=self.quality_policy.minimum_inlier_tags,
                maximum_tag_reprojection_rmse_px=(
                    self.quality_policy.maximum_inlier_rmse_px
                ),
            )
        )
        def renderer_config(
            *,
            occluded_tag_ids: tuple[int, ...] = (),
            gaussian_blur_radius_px: float = 0.0,
            horizontal_motion_blur_px: int = 0,
            noise_amplitude_gray: int = 0,
        ) -> SyntheticRasterConfig:
            return SyntheticRasterConfig(
                renderer_id="RC03_UNMEASURED_LINK2_ARM_CAMERA_GRAYSCALE_V1",
                allow_partial_scene=True,
                # A light off-board field keeps thresholding meaningful when a
                # moving view contains less board than the old fixed overview.
                background_gray=205,
                occluded_tag_ids=occluded_tag_ids,
                gaussian_blur_radius_px=gaussian_blur_radius_px,
                horizontal_motion_blur_px=horizontal_motion_blur_px,
                noise_amplitude_gray=noise_amplitude_gray,
            )

        configs = {
            VirtualArmCameraCaptureMode.NORMAL: renderer_config(),
            VirtualArmCameraCaptureMode.TAG_LOSS: renderer_config(
                occluded_tag_ids=tuple(range(6))
            ),
            VirtualArmCameraCaptureMode.EXCESS_BLUR: renderer_config(
                gaussian_blur_radius_px=5.0,
                horizontal_motion_blur_px=8,
            ),
            VirtualArmCameraCaptureMode.EXCESS_NOISE: renderer_config(
                noise_amplitude_gray=80
            ),
            VirtualArmCameraCaptureMode.UNQUALIFIED_TIMESTAMP: renderer_config(),
            VirtualArmCameraCaptureMode.STALE_FRAME: renderer_config(),
        }
        truth_hash = self.truth.content_hash
        definition = {
            "schema": "rocell.virtual_arm_camera_service_definition.v1",
            "processor_input_contract": "CAPTURE_BRACKET_AND_FAULT_MODE_ONLY",
            "target_or_action_received_by_processor": False,
            "accepted_joint_state_source": (
                AchievedJointStateSource.VIRTUAL_PLANT.value
            ),
            "controller_joint_intersection_rad": {
                name: list(
                    self.context.scenario.controller_joint_intersection_rad[name]
                )
                for name in ARM_CAMERA_JOINT_ORDER[:-1]
            },
            "controller_gripper_intersection_rad": list(
                self.context.scenario.controller_gripper_intersection_rad
            ),
            "binding_sha256": self.binding.binding_hash,
            "projector_implementation_sha256": projector.implementation_sha256,
            "camera": camera.to_dict(),
            "camera_state": "SYNTHETIC_WIDE_FOV_NOT_PHYSICAL_INTRINSICS",
            "intrinsics_sha256": intrinsics.content_hash,
            "tag_map_sha256": tag_map.content_hash,
            "detector": detector.detector_identity.to_dict(),
            "estimator_configuration_sha256": estimator.config.content_hash,
            "synchronization_policy": self.synchronization_policy.to_dict(),
            "synchronization_policy_sha256": (
                self.synchronization_policy.content_hash
            ),
            "quality_policy": self.quality_policy.to_dict(),
            "quality_policy_sha256": self.quality_policy.content_hash,
            "renderer_config_sha256_by_mode": {
                mode.value: config.config_sha256 for mode, config in configs.items()
            },
            "private_truth_registration_sha256": truth_hash,
            "private_truth_transform_serialized": False,
            "arm_mounted_camera_simulated": True,
            "mount_and_intrinsics_measured": False,
            "robot_frame_correction_applied": False,
            "implementation_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "authority": _authority_dict(),
        }
        object.__setattr__(self, "_projector", projector)
        object.__setattr__(self, "_camera", camera)
        object.__setattr__(self, "_detector", detector)
        object.__setattr__(self, "_intrinsics", intrinsics)
        object.__setattr__(self, "_tag_map", tag_map)
        object.__setattr__(self, "_estimator", estimator)
        object.__setattr__(self, "_renderer_configs", configs)
        object.__setattr__(self, "_service_definition", definition)
        object.__setattr__(
            self,
            "_result_issuer",
            _VisionResultIssuer(
                _token=_VISION_RESULT_ISSUER_TOKEN,
                service_definition_sha256=_stable_hash(definition),
                synchronization_policy_sha256=(
                    self.synchronization_policy.content_hash
                ),
                quality_policy=self.quality_policy,
                arm_camera_binding_sha256=self.binding.binding_hash,
                camera_intrinsics_sha256=intrinsics.content_hash,
                tag_map_sha256=tag_map.content_hash,
                detector_configuration_sha256=(
                    detector.detector_identity.configuration_sha256
                ),
                estimator_configuration_sha256=estimator.config.content_hash,
                renderer_config_sha256_by_mode=tuple(
                    (mode, config.config_sha256)
                    for mode, config in configs.items()
                ),
            ),
        )

    @property
    def service_definition_sha256(self) -> str:
        return _stable_hash(self._service_definition)

    def definition_dict(self) -> dict[str, object]:
        document = {
            **self._service_definition,
            "service_definition_sha256": self.service_definition_sha256,
        }
        # The internal definition contains nested dictionaries.  Never return
        # aliases that could mutate later evidence or its service hash.
        return json.loads(
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )

    def _assessment(
        self,
        bracket: ArmCameraCaptureBracket,
        *,
        passed: bool,
        detail_code: str,
        maximum_joint_change_rad: float | None = None,
        camera_translation_change_mm: float | None = None,
        camera_rotation_change_deg: float | None = None,
        settled_duration_ns: int | None = None,
        feedback_bracket_ns: int | None = None,
    ) -> ArmCameraSynchronizationAssessment:
        return ArmCameraSynchronizationAssessment(
            passed=passed,
            detail_code=detail_code,
            before_joint_sample_sha256=achieved_joint_sample_sha256(
                bracket.before_feedback
            ),
            after_joint_sample_sha256=achieved_joint_sample_sha256(
                bracket.after_feedback
            ),
            maximum_joint_change_rad=maximum_joint_change_rad,
            camera_translation_change_mm=camera_translation_change_mm,
            camera_rotation_change_deg=camera_rotation_change_deg,
            settled_duration_ns=settled_duration_ns,
            feedback_bracket_ns=feedback_bracket_ns,
            policy_sha256=self.synchronization_policy.content_hash,
        )

    def _synchronize(
        self, bracket: ArmCameraCaptureBracket
    ) -> tuple[
        ArmCameraSynchronizationAssessment,
        ArmCameraOpticalPose | None,
    ]:
        before = bracket.before_feedback
        after = bracket.after_feedback
        if before.stale or after.stale:
            return self._assessment(
                bracket, passed=False, detail_code="ARM_CAMERA_FEEDBACK_STALE"
            ), None
        if any(
            sample.feedback.source_kind is not AchievedJointStateSource.VIRTUAL_PLANT
            for sample in (before, after)
        ):
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_FEEDBACK_SOURCE_NOT_VIRTUAL_PLANT",
            ), None

        controller_bounds = self.context.scenario.controller_joint_intersection_rad
        gripper_bounds = self.context.scenario.controller_gripper_intersection_rad
        for sample in (before, after):
            positions = sample.feedback.positions_by_name
            arm_within_bounds = all(
                controller_bounds[name][0]
                <= positions[name].value
                <= controller_bounds[name][1]
                for name in ARM_CAMERA_JOINT_ORDER[:-1]
            )
            gripper = positions[ARM_CAMERA_JOINT_ORDER[-1]].value
            if not arm_within_bounds or not (
                gripper_bounds[0] <= gripper <= gripper_bounds[1]
            ):
                return self._assessment(
                    bracket,
                    passed=False,
                    detail_code="ARM_CAMERA_FEEDBACK_OUTSIDE_CONTROLLER_LIMITS",
                ), None
        if before.sequence != after.sequence:
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_FEEDBACK_SEQUENCE_MISMATCH",
            ), None
        if (
            before.sample_id == after.sample_id
            or achieved_joint_sample_sha256(before)
            == achieved_joint_sample_sha256(after)
        ):
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_FEEDBACK_BRACKET_NOT_DISTINCT",
            ), None
        instants = (
            bracket.settled_since,
            before.observed_at,
            bracket.exposure_at,
            after.observed_at,
        )
        if any(
            instant.clock_id != self.synchronization_policy.clock_id
            for instant in instants
        ):
            return self._assessment(
                bracket, passed=False, detail_code="ARM_CAMERA_CLOCK_MISMATCH"
            ), None
        periods = {instant.tick_period_ns for instant in instants}
        if None in periods or len(periods) != 1:
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_TICK_PERIOD_UNQUALIFIED",
            ), None
        try:
            settled_ns, before_ns, exposure_ns, after_ns = tuple(
                _instant_ns(instant, "capture instant") for instant in instants
            )
        except VirtualArmCameraError:
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_TIMESTAMP_OUT_OF_RANGE",
            ), None
        if not settled_ns <= before_ns < exposure_ns < after_ns:
            return self._assessment(
                bracket, passed=False, detail_code="ARM_CAMERA_BRACKET_ORDER_INVALID"
            ), None
        settled_duration = exposure_ns - settled_ns
        bracket_duration = after_ns - before_ns
        if settled_duration < self.synchronization_policy.minimum_settled_duration_ns:
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_SETTLING_TOO_SHORT",
                settled_duration_ns=settled_duration,
                feedback_bracket_ns=bracket_duration,
            ), None
        if bracket_duration > self.synchronization_policy.maximum_feedback_bracket_ns:
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_FEEDBACK_BRACKET_TOO_WIDE",
                settled_duration_ns=settled_duration,
                feedback_bracket_ns=bracket_duration,
            ), None
        before_positions = before.feedback.positions_by_name
        after_positions = after.feedback.positions_by_name
        joint_change = max(
            abs(before_positions[name].value - after_positions[name].value)
            for name in ARM_CAMERA_JOINT_ORDER
        )
        try:
            before_pose = self._projector.project(before)
            after_pose = self._projector.project(after)
        except ArmCameraPoseError:
            return self._assessment(
                bracket,
                passed=False,
                detail_code="ARM_CAMERA_JOINT_POSE_REJECTED",
                maximum_joint_change_rad=joint_change,
                settled_duration_ns=settled_duration,
                feedback_bracket_ns=bracket_duration,
            ), None
        translation_change = (
            before_pose.Wv_T_C_arm.translation_mm
            - after_pose.Wv_T_C_arm.translation_mm
        ).norm
        rotation_change = _rotation_difference_deg(
            before_pose.Wv_T_C_arm.rotation,
            after_pose.Wv_T_C_arm.rotation,
        )
        if joint_change > self.synchronization_policy.maximum_joint_change_rad:
            detail = "ARM_CAMERA_JOINTS_MOVED_DURING_CAPTURE"
            passed = False
        elif translation_change > self.synchronization_policy.maximum_camera_translation_mm:
            detail = "ARM_CAMERA_CARRIER_TRANSLATED_DURING_CAPTURE"
            passed = False
        elif rotation_change > self.synchronization_policy.maximum_camera_rotation_deg:
            detail = "ARM_CAMERA_CARRIER_ROTATED_DURING_CAPTURE"
            passed = False
        else:
            detail = "ARM_CAMERA_SETTLED_BRACKET_ACCEPTED"
            passed = True
        return self._assessment(
            bracket,
            passed=passed,
            detail_code=detail,
            maximum_joint_change_rad=joint_change,
            camera_translation_change_mm=translation_change,
            camera_rotation_change_deg=rotation_change,
            settled_duration_ns=settled_duration,
            feedback_bracket_ns=bracket_duration,
        ), before_pose if passed else None

    def _failure(
        self,
        bracket: ArmCameraCaptureBracket,
        mode: VirtualArmCameraCaptureMode,
        synchronization: ArmCameraSynchronizationAssessment,
        stage: VirtualArmCameraStage,
        detail_code: str,
        *,
        arm_pose: ArmCameraOpticalPose | None = None,
        rendered: SyntheticRenderedFrame | None = None,
        batch: AprilTagDetectionBatch | None = None,
        pose: AprilTagPoseObservation | None = None,
        quality: ArmCameraVisionQuality | None = None,
    ) -> VirtualArmCameraVisionResult:
        return VirtualArmCameraVisionResult(
            _issuer=self._result_issuer,
            capture_sequence=bracket.capture_sequence,
            capture_mode=mode,
            status="FAULT",
            stage=stage,
            detail_code=detail_code,
            service_definition_sha256=self.service_definition_sha256,
            capture_bracket_sha256=bracket.bracket_hash,
            synchronization=synchronization,
            arm_camera_pose=arm_pose,
            rendered_frame=rendered,
            detection_batch=batch,
            pose_observation=pose,
            quality=quality,
        )

    def _quality(self, pose: AprilTagPoseObservation) -> ArmCameraVisionQuality:
        diagonal = tuple(pose.covariance.row_major[index * 6 + index] for index in range(6))
        maximum_covariance = max(diagonal)
        detected = tuple(
            sorted(tag.tag_id for tag in pose.detection_batch.accepted_tags)
        )
        inliers = tuple(sorted(tag.tag_id for tag in pose.used_tags))
        tag_count_passed, residual_passed, covariance_passed = _quality_gate_flags(
            inlier_tag_count=len(inliers),
            inlier_rmse_px=pose.inlier_rmse_px,
            maximum_covariance_diagonal=maximum_covariance,
            policy=self.quality_policy,
        )
        return ArmCameraVisionQuality(
            detected_tag_ids=detected,
            inlier_tag_ids=inliers,
            inlier_rmse_px=pose.inlier_rmse_px,
            maximum_covariance_diagonal=maximum_covariance,
            tag_count_passed=tag_count_passed,
            residual_passed=residual_passed,
            covariance_passed=covariance_passed,
            policy_sha256=self.quality_policy.content_hash,
        )

    def process(
        self,
        *,
        bracket: ArmCameraCaptureBracket,
        capture_mode: VirtualArmCameraCaptureMode = VirtualArmCameraCaptureMode.NORMAL,
    ) -> VirtualArmCameraVisionResult:
        """Process achieved feedback and pixels without semantic plan inputs."""

        if not isinstance(bracket, ArmCameraCaptureBracket):
            raise TypeError("bracket must be ArmCameraCaptureBracket")
        if not isinstance(capture_mode, VirtualArmCameraCaptureMode):
            raise TypeError("capture_mode must be VirtualArmCameraCaptureMode")
        synchronization, arm_pose = self._synchronize(bracket)
        if not synchronization.passed or arm_pose is None:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.SYNCHRONIZATION,
                synchronization.detail_code,
            )
        if capture_mode is VirtualArmCameraCaptureMode.CAMERA_UNAVAILABLE:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.CAPTURE,
                "ARM_CAMERA_UNAVAILABLE",
                arm_pose=arm_pose,
            )

        C_arm_T_board = self.truth.camera_T_board(arm_pose.Wv_T_C_arm)
        config = self._renderer_configs[capture_mode]
        renderer = SyntheticOverviewRasterRenderer(
            scene=self.context.scene,
            camera=self._camera,
            camera_T_board=C_arm_T_board.to_transform(),
            tag_asset_root=self.context.rc03_root / "fiducials",
            config=config,
            codebook=DEFAULT_APRILTAG_36H11_CODEBOOK,
        )
        before_ns = _instant_ns(bracket.before_feedback.observed_at, "before feedback")
        exposure_ns = _instant_ns(bracket.exposure_at, "exposure")
        after_ns = _instant_ns(bracket.after_feedback.observed_at, "after feedback")
        timestamp_quality = (
            TimestampQuality.UNQUALIFIED
            if capture_mode is VirtualArmCameraCaptureMode.UNQUALIFIED_TIMESTAMP
            else TimestampQuality.SETTLED_BRACKET
        )
        render_sequence = (
            bracket.capture_sequence - 1
            if capture_mode is VirtualArmCameraCaptureMode.STALE_FRAME
            else bracket.capture_sequence
        )
        timing = SyntheticCaptureTiming(
            source_timestamp_ns=exposure_ns,
            source_clock=self.synchronization_policy.clock_id,
            host_request_ns=before_ns,
            host_first_byte_ns=exposure_ns,
            host_complete_ns=after_ns,
            timestamp_quality=timestamp_quality,
            freshness_token=(
                f"arm-camera:{render_sequence}:"
                f"{arm_pose.joint_sample_sha256}"
            ),
            freshness_basis="capture_sequence_and_achieved_joint_sample_sha256",
        )
        try:
            rendered = renderer.render(sequence=render_sequence, timing=timing)
        except (SyntheticRasterError, OSError):
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.CAPTURE,
                "ARM_CAMERA_FRAME_CAPTURE_FAILED",
                arm_pose=arm_pose,
            )
        frame = rendered.frame_packet
        if frame.source_sequence != bracket.capture_sequence:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.SYNCHRONIZATION,
                "ARM_CAMERA_FRAME_SEQUENCE_STALE",
                arm_pose=arm_pose,
                rendered=rendered,
            )
        if frame.timestamp_quality is not TimestampQuality.SETTLED_BRACKET:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.SYNCHRONIZATION,
                "ARM_CAMERA_FRAME_TIMESTAMP_UNQUALIFIED",
                arm_pose=arm_pose,
                rendered=rendered,
            )
        try:
            batch = self._detector.detect(frame)
        except AprilTagPixelDetectorError:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.DETECTION,
                "ARM_CAMERA_TAG_DETECTION_FAILED",
                arm_pose=arm_pose,
                rendered=rendered,
            )
        try:
            pose = self._estimator.estimate(batch, self._intrinsics, self._tag_map)
        except PlanarPoseEstimationError:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.POSE,
                "ARM_CAMERA_BOARD_POSE_FAILED",
                arm_pose=arm_pose,
                rendered=rendered,
                batch=batch,
            )
        quality = self._quality(pose)
        if not quality.passed:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.QUALITY,
                "ARM_CAMERA_BOARD_POSE_QUALITY_REJECTED",
                arm_pose=arm_pose,
                rendered=rendered,
                batch=batch,
                pose=pose,
                quality=quality,
            )
        if capture_mode is not VirtualArmCameraCaptureMode.NORMAL:
            return self._failure(
                bracket,
                capture_mode,
                synchronization,
                VirtualArmCameraStage.QUALITY,
                "ARM_CAMERA_FAULT_INJECTION_NOT_REJECTED",
                arm_pose=arm_pose,
                rendered=rendered,
                batch=batch,
                pose=pose,
                quality=quality,
            )
        return VirtualArmCameraVisionResult(
            _issuer=self._result_issuer,
            capture_sequence=bracket.capture_sequence,
            capture_mode=capture_mode,
            status="PASS",
            stage=VirtualArmCameraStage.COMPLETE,
            detail_code="ARM_CAMERA_BOARD_POSE_ACCEPTED",
            service_definition_sha256=self.service_definition_sha256,
            capture_bracket_sha256=bracket.bracket_hash,
            synchronization=synchronization,
            arm_camera_pose=arm_pose,
            rendered_frame=rendered,
            detection_batch=batch,
            pose_observation=pose,
            quality=quality,
        )


def make_hidden_virtual_board_truth(
    study_input: ReachStudyInput,
    *,
    translation_Wv_mm: Vec3 = Vec3.zero(),
    yaw_board_rad: float = 0.0,
) -> HiddenVirtualBoardTruth:
    """Create one opaque injected truth source for all virtual plant sensors."""

    return HiddenVirtualBoardTruth(
        offset_synthetic_board_truth(
            planner_Wv_T_board(study_input),
            translation_Wv_mm=translation_Wv_mm,
            yaw_board_rad=yaw_board_rad,
        )
    )


def make_virtual_arm_camera_service(
    context: SimulationContext,
    study_input: ReachStudyInput,
    *,
    truth: HiddenVirtualBoardTruth | None = None,
    truth_translation_Wv_mm: Vec3 = Vec3.zero(),
    truth_yaw_board_rad: float = 0.0,
) -> VirtualArmCameraVisionService:
    """Create the default unmeasured fixture around one locked study input.

    Passing an existing hidden truth lets the renderer and contact projector
    share an identical plant source/digest.  Offset arguments are a convenient
    test factory only and cannot be combined with an existing truth object.
    """

    if truth is not None and (
        truth_translation_Wv_mm != Vec3.zero() or truth_yaw_board_rad != 0.0
    ):
        raise VirtualArmCameraError(
            "an existing hidden truth cannot be combined with truth offsets"
        )
    selected_truth = truth
    if selected_truth is None:
        selected_truth = make_hidden_virtual_board_truth(
            study_input,
            translation_Wv_mm=truth_translation_Wv_mm,
            yaw_board_rad=truth_yaw_board_rad,
        )
    return VirtualArmCameraVisionService(
        context=context,
        binding=make_unmeasured_synthetic_arm_camera_binding(context),
        truth=selected_truth,
    )


__all__ = [
    "MAX_VIRTUAL_ARM_CAMERA_SEQUENCE",
    "VIRTUAL_ARM_CAMERA_CLOCK",
    "VIRTUAL_ARM_CAMERA_SCHEMA",
    "ArmCameraCaptureBracket",
    "ArmCameraSynchronizationAssessment",
    "ArmCameraSynchronizationPolicy",
    "ArmCameraVisionQuality",
    "ArmCameraVisionQualityPolicy",
    "VirtualArmCameraCaptureMode",
    "VirtualArmCameraError",
    "VirtualArmCameraStage",
    "VirtualArmCameraVisionResult",
    "VirtualArmCameraVisionService",
    "achieved_joint_sample_from_virtual_feedback",
    "correction_measurement_from_vision_result",
    "initial_planner_board_registration",
    "make_hidden_virtual_board_truth",
    "make_unmeasured_synthetic_arm_camera_binding",
    "make_virtual_arm_camera_service",
    "offset_synthetic_board_truth",
    "planner_Wv_T_board",
]
