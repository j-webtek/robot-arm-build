"""Typed AprilTag pose-estimation records with explicit frame semantics.

This module records what a pose estimator concluded from an immutable
``AprilTagDetectionBatch``.  It does not run a detector, solve PnP, import an
image library, or communicate with hardware.  Every redundant fit summary is
derived from per-tag diagnostics so masks, residuals, and used/rejected tag
lists cannot disagree inside a constructed record.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3

from .detections import (
    AprilTagDetectionBatch,
    TagReference,
    VisionRecordError,
    _bounded_text,
    _canonical_hash,
    _digest,
    _exact_keys,
    _finite,
    _identifier,
    _mapping,
    _sequence,
    _validate_zero_authority,
    _zero_authority,
    april_tag_detection_batch_from_dict,
    tag_reference_from_dict,
)


POSE_OBSERVATION_SCHEMA = "rocell.apriltag_pose_observation.v1"
POSE_PARAMETER_ORDER = (
    "translation_x_mm",
    "translation_y_mm",
    "translation_z_mm",
    "rotation_x_rad",
    "rotation_y_rad",
    "rotation_z_rad",
)
MAX_COVARIANCE_MAGNITUDE = 1.0e18
MAX_REPROJECTION_RESIDUAL_PX = 1.0e6


def _transform_dict(value: RigidTransform) -> dict[str, Any]:
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


def _transform_from_dict(value: object) -> RigidTransform:
    document = _mapping(value, "pose.transform")
    _exact_keys(
        document,
        {"to_frame", "from_frame", "rotation_row_major", "translation_mm"},
        "pose.transform",
    )
    rotation = _sequence(
        document["rotation_row_major"],
        "pose.transform.rotation_row_major",
        length=9,
    )
    translation = _sequence(
        document["translation_mm"],
        "pose.transform.translation_mm",
        length=3,
    )
    try:
        return RigidTransform(
            parent_frame=document["to_frame"],  # type: ignore[arg-type]
            child_frame=document["from_frame"],  # type: ignore[arg-type]
            rotation=Rotation3(tuple(rotation)),  # type: ignore[arg-type]
            translation_mm=Vec3.from_iterable(translation),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, VisionRecordError):
            raise
        raise VisionRecordError(f"pose.transform is invalid: {exc}") from exc


@dataclass(frozen=True, slots=True)
class PoseEstimatorIdentity:
    """Pinned estimator identity independent of the upstream detector."""

    estimator_id: str
    version: str
    configuration_sha256: str
    implementation_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "estimator_id", _identifier(self.estimator_id, "estimator_id"))
        object.__setattr__(
            self,
            "version",
            _bounded_text(self.version, "estimator version", maximum=128),
        )
        _digest(self.configuration_sha256, "estimator configuration_sha256")
        _digest(self.implementation_sha256, "estimator implementation_sha256")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.estimator_id,
            "version": self.version,
            "configuration_sha256": self.configuration_sha256,
            "implementation_sha256": self.implementation_sha256,
        }


@dataclass(frozen=True, slots=True)
class PoseCovariance6:
    """Finite symmetric 6x6 covariance in :data:`POSE_PARAMETER_ORDER`.

    Mixed translation/rotation units are explicit in the parameter names.  A
    positive-semidefinite proof belongs in the numerical estimator; this data
    boundary enforces symmetry and non-negative diagonal variances without
    introducing a NumPy dependency.
    """

    row_major: tuple[float, ...]

    def __post_init__(self) -> None:
        values = tuple(
            _finite(
                value,
                "pose covariance element",
                minimum=-MAX_COVARIANCE_MAGNITUDE,
                maximum=MAX_COVARIANCE_MAGNITUDE,
            )
            for value in self.row_major
        )
        if len(values) != 36:
            raise VisionRecordError("pose covariance must contain exactly 36 values")
        for index in range(6):
            if values[index * 6 + index] < 0.0:
                raise VisionRecordError("pose covariance diagonal must be non-negative")
        for row in range(6):
            for column in range(row + 1, 6):
                left = values[row * 6 + column]
                right = values[column * 6 + row]
                tolerance = 1e-12 * max(1.0, abs(left), abs(right))
                if abs(left - right) > tolerance:
                    raise VisionRecordError("pose covariance must be symmetric")
        object.__setattr__(self, "row_major", values)

    @classmethod
    def diagonal(cls, variances: tuple[float, float, float, float, float, float]) -> "PoseCovariance6":
        """Build a diagonal covariance without relying on a matrix library."""

        if len(tuple(variances)) != 6:
            raise VisionRecordError("diagonal covariance requires six variances")
        values = tuple(variances)
        return cls(
            tuple(
                float(values[row]) if row == column else 0.0
                for row in range(6)
                for column in range(6)
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter_order": list(POSE_PARAMETER_ORDER),
            "row_major": list(self.row_major),
        }


@dataclass(frozen=True, slots=True)
class TagFitDiagnostic:
    """One pose-fit mask entry and its reprojection residual."""

    tag: TagReference
    inlier: bool
    reprojection_residual_px: float | None
    rejection_reason: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.tag, TagReference):
            raise TypeError("tag must be a TagReference")
        if not isinstance(self.inlier, bool):
            raise VisionRecordError("inlier must be boolean")
        if self.reprojection_residual_px is not None:
            object.__setattr__(
                self,
                "reprojection_residual_px",
                _finite(
                    self.reprojection_residual_px,
                    "reprojection_residual_px",
                    minimum=0.0,
                    maximum=MAX_REPROJECTION_RESIDUAL_PX,
                ),
            )
        if self.inlier:
            if self.reprojection_residual_px is None:
                raise VisionRecordError("An inlier requires a reprojection residual")
            if self.rejection_reason is not None:
                raise VisionRecordError("An inlier cannot have a rejection reason")
        else:
            if self.rejection_reason is None:
                raise VisionRecordError("A rejected tag requires a rejection reason")
            object.__setattr__(
                self,
                "rejection_reason",
                _bounded_text(
                    self.rejection_reason,
                    "pose-fit rejection_reason",
                    maximum=256,
                ),
            )


@dataclass(frozen=True, slots=True)
class AprilTagPoseObservation:
    """One pose result bound to raw frame/detection inputs and source hashes."""

    detection_batch: AprilTagDetectionBatch
    estimator: PoseEstimatorIdentity
    camera_intrinsics_sha256: str
    tag_map_sha256: str
    pose: RigidTransform
    covariance: PoseCovariance6
    fit_diagnostics: tuple[TagFitDiagnostic, ...]
    schema: str = POSE_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != POSE_OBSERVATION_SCHEMA:
            raise VisionRecordError(f"Unsupported pose-observation schema {self.schema!r}")
        if not isinstance(self.detection_batch, AprilTagDetectionBatch):
            raise TypeError("detection_batch must be an AprilTagDetectionBatch")
        if not isinstance(self.estimator, PoseEstimatorIdentity):
            raise TypeError("estimator must be a PoseEstimatorIdentity")
        _digest(self.camera_intrinsics_sha256, "camera_intrinsics_sha256")
        _digest(self.tag_map_sha256, "tag_map_sha256")
        if not isinstance(self.pose, RigidTransform):
            raise TypeError("pose must be a RigidTransform")
        if self.pose.parent_frame == self.pose.child_frame:
            raise VisionRecordError("Pose transform must identify two distinct frames")
        if not isinstance(self.covariance, PoseCovariance6):
            raise TypeError("covariance must be a PoseCovariance6")

        diagnostics = tuple(self.fit_diagnostics)
        if any(not isinstance(item, TagFitDiagnostic) for item in diagnostics):
            raise TypeError("fit_diagnostics must contain TagFitDiagnostic values")
        if len({item.tag for item in diagnostics}) != len(diagnostics):
            raise VisionRecordError("fit_diagnostics contains a duplicate tag")
        diagnostic_by_tag = {item.tag: item for item in diagnostics}
        expected_tags = tuple(
            detection.tag for detection in self.detection_batch.detections
        )
        if set(diagnostic_by_tag) != set(expected_tags):
            raise VisionRecordError(
                "fit_diagnostics must cover every detection exactly once"
            )
        ordered = tuple(diagnostic_by_tag[tag] for tag in expected_tags)
        detection_by_tag = {
            detection.tag: detection for detection in self.detection_batch.detections
        }
        for diagnostic in ordered:
            detection = detection_by_tag[diagnostic.tag]
            if not detection.detector_accepted and diagnostic.inlier:
                raise VisionRecordError(
                    f"Detector-rejected tag {diagnostic.tag.tag_id} cannot be a pose inlier"
                )
        if not any(item.inlier for item in ordered):
            raise VisionRecordError("A pose estimate requires at least one inlier tag")
        object.__setattr__(self, "fit_diagnostics", ordered)

    @property
    def inlier_mask(self) -> tuple[bool, ...]:
        return tuple(item.inlier for item in self.fit_diagnostics)

    @property
    def reprojection_residuals_px(self) -> tuple[float | None, ...]:
        return tuple(item.reprojection_residual_px for item in self.fit_diagnostics)

    @property
    def used_tags(self) -> tuple[TagReference, ...]:
        return tuple(item.tag for item in self.fit_diagnostics if item.inlier)

    @property
    def rejected_tags(self) -> tuple[TagReference, ...]:
        return tuple(item.tag for item in self.fit_diagnostics if not item.inlier)

    @property
    def inlier_rmse_px(self) -> float:
        residuals = tuple(
            item.reprojection_residual_px
            for item in self.fit_diagnostics
            if item.inlier and item.reprojection_residual_px is not None
        )
        # Construction guarantees at least one inlier and a finite residual
        # for every inlier.
        assert residuals
        return math.sqrt(sum(value**2 for value in residuals) / len(residuals))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "detection_batch": self.detection_batch.to_dict(),
            "detection_batch_sha256": self.detection_batch.content_hash,
            "estimator": self.estimator.to_dict(),
            "source_hashes": {
                "camera_intrinsics_sha256": self.camera_intrinsics_sha256,
                "tag_map_sha256": self.tag_map_sha256,
            },
            "pose": {
                "transform": _transform_dict(self.pose),
                "covariance_6x6": self.covariance.to_dict(),
            },
            "fit": {
                "tag_order": [item.tag.to_dict() for item in self.fit_diagnostics],
                "inlier_mask": list(self.inlier_mask),
                "reprojection_residuals_px": list(self.reprojection_residuals_px),
                "rejection_reasons": [
                    item.rejection_reason for item in self.fit_diagnostics
                ],
                "used_tags": [tag.to_dict() for tag in self.used_tags],
                "rejected_tags": [tag.to_dict() for tag in self.rejected_tags],
                "inlier_rmse_px": self.inlier_rmse_px,
            },
            "authority": _zero_authority(),
        }

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())


def pose_estimator_identity_from_dict(value: object) -> PoseEstimatorIdentity:
    document = _mapping(value, "estimator")
    _exact_keys(
        document,
        {"id", "version", "configuration_sha256", "implementation_sha256"},
        "estimator",
    )
    return PoseEstimatorIdentity(
        estimator_id=document["id"],  # type: ignore[arg-type]
        version=document["version"],  # type: ignore[arg-type]
        configuration_sha256=document["configuration_sha256"],  # type: ignore[arg-type]
        implementation_sha256=document["implementation_sha256"],  # type: ignore[arg-type]
    )


def pose_covariance6_from_dict(value: object) -> PoseCovariance6:
    document = _mapping(value, "pose.covariance_6x6")
    _exact_keys(document, {"parameter_order", "row_major"}, "pose.covariance_6x6")
    if tuple(
        _sequence(document["parameter_order"], "pose covariance parameter_order")
    ) != POSE_PARAMETER_ORDER:
        raise VisionRecordError("pose covariance parameter_order is unsupported")
    values = _sequence(
        document["row_major"],
        "pose.covariance_6x6.row_major",
        length=36,
    )
    return PoseCovariance6(tuple(values))  # type: ignore[arg-type]


def april_tag_pose_observation_from_dict(value: object) -> AprilTagPoseObservation:
    document = _mapping(value, "pose observation")
    _exact_keys(
        document,
        {
            "schema",
            "detection_batch",
            "detection_batch_sha256",
            "estimator",
            "source_hashes",
            "pose",
            "fit",
            "authority",
        },
        "pose observation",
    )
    _validate_zero_authority(document["authority"])
    batch = april_tag_detection_batch_from_dict(document["detection_batch"])
    if document["detection_batch_sha256"] != batch.content_hash:
        raise VisionRecordError("detection_batch_sha256 does not match detection_batch")
    sources = _mapping(document["source_hashes"], "source_hashes")
    _exact_keys(
        sources,
        {"camera_intrinsics_sha256", "tag_map_sha256"},
        "source_hashes",
    )
    pose_document = _mapping(document["pose"], "pose")
    _exact_keys(pose_document, {"transform", "covariance_6x6"}, "pose")
    fit = _mapping(document["fit"], "fit")
    _exact_keys(
        fit,
        {
            "tag_order",
            "inlier_mask",
            "reprojection_residuals_px",
            "rejection_reasons",
            "used_tags",
            "rejected_tags",
            "inlier_rmse_px",
        },
        "fit",
    )
    tag_values = _sequence(fit["tag_order"], "fit.tag_order")
    masks = _sequence(fit["inlier_mask"], "fit.inlier_mask")
    residuals = _sequence(
        fit["reprojection_residuals_px"],
        "fit.reprojection_residuals_px",
    )
    reasons = _sequence(fit["rejection_reasons"], "fit.rejection_reasons")
    if not len(tag_values) == len(masks) == len(residuals) == len(reasons):
        raise VisionRecordError("pose-fit parallel arrays have different lengths")
    diagnostics = tuple(
        TagFitDiagnostic(
            tag=tag_reference_from_dict(tag_value, label=f"fit.tag_order[{index}]"),
            inlier=masks[index],  # type: ignore[arg-type]
            reprojection_residual_px=residuals[index],  # type: ignore[arg-type]
            rejection_reason=reasons[index],  # type: ignore[arg-type]
        )
        for index, tag_value in enumerate(tag_values)
    )
    observation = AprilTagPoseObservation(
        schema=document["schema"],  # type: ignore[arg-type]
        detection_batch=batch,
        estimator=pose_estimator_identity_from_dict(document["estimator"]),
        camera_intrinsics_sha256=sources["camera_intrinsics_sha256"],  # type: ignore[arg-type]
        tag_map_sha256=sources["tag_map_sha256"],  # type: ignore[arg-type]
        pose=_transform_from_dict(pose_document["transform"]),
        covariance=pose_covariance6_from_dict(pose_document["covariance_6x6"]),
        fit_diagnostics=diagnostics,
    )
    # This full comparison validates redundant masks, residuals, used/rejected
    # lists, RMSE, source hashes, and zero-authority fields in one place.
    if observation.to_dict() != dict(document):
        raise VisionRecordError("Pose observation is not in canonical normalized form")
    return observation


__all__ = [
    "AprilTagPoseObservation",
    "MAX_REPROJECTION_RESIDUAL_PX",
    "POSE_OBSERVATION_SCHEMA",
    "POSE_PARAMETER_ORDER",
    "PoseCovariance6",
    "PoseEstimatorIdentity",
    "TagFitDiagnostic",
    "april_tag_pose_observation_from_dict",
    "pose_covariance6_from_dict",
    "pose_estimator_identity_from_dict",
]
