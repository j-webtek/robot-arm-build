"""Deterministic, dependency-free planar AprilTag board-pose estimation.

This module is the numerical service between typed detector output and
``AprilTagPoseObservation``.  It consumes only:

* an immutable :class:`~rocell.vision.detections.AprilTagDetectionBatch`;
* explicit undistorted pinhole intrinsics;
* an immutable, source-hashed planar board tag map; and
* bounded estimator policy.

It never receives simulator pose, projected-corner ground truth, robot state,
or a planned board pose.  Canonical detector corners 0,1,2,3 are paired with
map corners 0,1,2,3 without geometric re-sorting.  The convention is decoded
tag TL, TR, BR, BL in the upright tag image.

The implementation uses normalized planar homography fitting, deterministic
partial-pivot Gaussian elimination, bounded consensus hypotheses, and pinhole
homography decomposition.  It returns ``camera_optical_T_board``.  Tag corners
may lie on a small, explicit plane above the board origin; after decomposition
the plane-origin translation is corrected with
``t_board = t_plane - r3 * tag_plane_z_board_mm``.

This is a pose estimate and zero-authority evidence.  It is not a calibrated
physical release, a detector, a motion permit, or a physical covariance claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Iterable, Sequence

from rocell.geometry import Point3Mm, RigidTransform, Rotation3, Vec3

from .detections import (
    AprilTagDetection,
    AprilTagDetectionBatch,
    CORNER_ORDER,
    TagReference,
    VisionRecordError,
)
from .pose_estimation_records import (
    AprilTagPoseObservation,
    PoseCovariance6,
    PoseEstimatorIdentity,
    TagFitDiagnostic,
)


PLANAR_POSE_ESTIMATOR_ID = "rocell.planar_apriltag_homography"
PLANAR_POSE_ESTIMATOR_VERSION = "1.1.0"
CAMERA_OPTICAL_FRAME = "camera_optical"
TAG_MAP_CORNER_ORDER = CORNER_ORDER
MAX_BOARD_TAGS = 64
MAX_POSE_CORRESPONDENCES = 4 * MAX_BOARD_TAGS
MAX_POSE_HYPOTHESES = 1 + 2 * MAX_BOARD_TAGS
MAX_ESTIMATOR_IMPLEMENTATION_BYTES = 2_000_000
MAX_BOARD_COORDINATE_MM = 1_000_000.0
_COPLANAR_TOLERANCE_MM = 1e-9
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:/+-]+$")


class PlanarPoseEstimationError(VisionRecordError):
    """Inputs or numerical evidence cannot support a bounded planar pose."""


def _finite(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanarPoseEstimationError(f"{label} must be a real number")
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise PlanarPoseEstimationError(
            f"{label} must be finite and in [{minimum}, {maximum}]"
        )
    return parsed


def _integer(
    value: object,
    label: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise PlanarPoseEstimationError(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _identifier(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or _IDENTIFIER.fullmatch(value) is None
    ):
        raise PlanarPoseEstimationError(
            f"{label} must be 1..{maximum} characters matching "
            f"{_IDENTIFIER.pattern}"
        )
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PlanarPoseEstimationError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _canonical_hash(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PlanarPoseEstimationError(
            f"planar pose configuration is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class PinholeIntrinsics:
    """Undistorted pinhole calibration for one exact image mode.

    The estimator does not apply distortion correction.  Detector corners must
    already be expressed in this calibrated undistorted pixel space.
    ``source_sha256`` identifies the immutable source calibration artifact;
    ``content_hash`` additionally binds every normalized value below.
    """

    calibration_id: str
    width_px: int
    height_px: int
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    source_sha256: str
    skew_px: float = 0.0
    camera_frame: str = CAMERA_OPTICAL_FRAME
    pixel_space: str = "UNDISTORTED_PINHOLE_PIXELS"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "calibration_id",
            _identifier(self.calibration_id, "calibration_id"),
        )
        object.__setattr__(
            self,
            "width_px",
            _integer(self.width_px, "width_px", minimum=2, maximum=100_000),
        )
        object.__setattr__(
            self,
            "height_px",
            _integer(self.height_px, "height_px", minimum=2, maximum=100_000),
        )
        object.__setattr__(
            self,
            "fx_px",
            _finite(self.fx_px, "fx_px", minimum=1e-6, maximum=10_000_000.0),
        )
        object.__setattr__(
            self,
            "fy_px",
            _finite(self.fy_px, "fy_px", minimum=1e-6, maximum=10_000_000.0),
        )
        object.__setattr__(
            self,
            "cx_px",
            _finite(
                self.cx_px,
                "cx_px",
                minimum=0.0,
                maximum=float(self.width_px - 1),
            ),
        )
        object.__setattr__(
            self,
            "cy_px",
            _finite(
                self.cy_px,
                "cy_px",
                minimum=0.0,
                maximum=float(self.height_px - 1),
            ),
        )
        object.__setattr__(
            self,
            "skew_px",
            _finite(
                self.skew_px,
                "skew_px",
                minimum=-1_000_000.0,
                maximum=1_000_000.0,
            ),
        )
        _digest(self.source_sha256, "intrinsics source_sha256")
        object.__setattr__(
            self,
            "camera_frame",
            _identifier(self.camera_frame, "camera_frame"),
        )
        if not (
            self.camera_frame in (CAMERA_OPTICAL_FRAME, "C_arm")
            or self.camera_frame.endswith("_optical")
        ):
            raise PlanarPoseEstimationError(
                "camera_frame must be canonical C_arm or an explicit "
                "optical-frame name ending in '_optical'"
            )
        object.__setattr__(
            self,
            "pixel_space",
            _identifier(self.pixel_space, "pixel_space"),
        )
        if self.pixel_space != "UNDISTORTED_PINHOLE_PIXELS":
            raise PlanarPoseEstimationError(
                "planar estimator requires UNDISTORTED_PINHOLE_PIXELS"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.pinhole_intrinsics.v1",
            "calibration_id": self.calibration_id,
            "camera_frame": self.camera_frame,
            "pixel_space": self.pixel_space,
            "resolution_px": [self.width_px, self.height_px],
            "matrix_row_major": [
                self.fx_px,
                self.skew_px,
                self.cx_px,
                0.0,
                self.fy_px,
                self.cy_px,
                0.0,
                0.0,
                1.0,
            ],
            "source_sha256": self.source_sha256,
            "distortion_application": "NONE_INPUT_ALREADY_UNDISTORTED",
            "physical_release_effect": "NONE",
        }

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class PlanarBoardTag:
    """Canonical 0,1,2,3 board-frame corners for one decoded AprilTag."""

    tag: TagReference
    corners_board_mm: tuple[Point3Mm, Point3Mm, Point3Mm, Point3Mm]

    def __post_init__(self) -> None:
        if not isinstance(self.tag, TagReference):
            raise TypeError("tag must be a TagReference")
        if not isinstance(self.corners_board_mm, tuple) or len(self.corners_board_mm) != 4:
            raise PlanarPoseEstimationError(
                "corners_board_mm must be an immutable four-corner tuple"
            )
        if any(not isinstance(point, Point3Mm) for point in self.corners_board_mm):
            raise TypeError("corners_board_mm must contain Point3Mm values")
        frames = {point.frame for point in self.corners_board_mm}
        if len(frames) != 1:
            raise PlanarPoseEstimationError(
                "all tag-map corners must use one explicit board frame"
            )
        xy = tuple((point.x, point.y) for point in self.corners_board_mm)
        _validate_convex_ordered_quad(xy, f"tag {self.tag.tag_id} board corners")

    def to_dict(self) -> dict[str, object]:
        return {
            "tag": self.tag.to_dict(),
            "corner_order": TAG_MAP_CORNER_ORDER,
            "corners_board_mm": [
                {
                    "frame": point.frame,
                    "x": point.x,
                    "y": point.y,
                    "z": point.z,
                }
                for point in self.corners_board_mm
            ],
        }


@dataclass(frozen=True, slots=True)
class PlanarBoardTagMap:
    """Immutable coplanar tag-corner map bound to its source artifact hash."""

    map_id: str
    board_frame: str
    tag_plane_z_board_mm: float
    tags: tuple[PlanarBoardTag, ...]
    source_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "map_id", _identifier(self.map_id, "map_id"))
        object.__setattr__(
            self,
            "board_frame",
            _identifier(self.board_frame, "board_frame"),
        )
        object.__setattr__(
            self,
            "tag_plane_z_board_mm",
            _finite(
                self.tag_plane_z_board_mm,
                "tag_plane_z_board_mm",
                minimum=-MAX_BOARD_COORDINATE_MM,
                maximum=MAX_BOARD_COORDINATE_MM,
            ),
        )
        _digest(self.source_sha256, "tag-map source_sha256")
        if not isinstance(self.tags, tuple) or not self.tags:
            raise PlanarPoseEstimationError("tags must be a non-empty immutable tuple")
        if len(self.tags) > MAX_BOARD_TAGS:
            raise PlanarPoseEstimationError(
                f"tag map exceeds the {MAX_BOARD_TAGS}-tag resource limit"
            )
        if any(not isinstance(tag, PlanarBoardTag) for tag in self.tags):
            raise TypeError("tags must contain PlanarBoardTag values")
        references = tuple(tag.tag for tag in self.tags)
        if len(set(references)) != len(references):
            raise PlanarPoseEstimationError("tag map contains a duplicate tag reference")
        numeric_ids = tuple(tag.tag.tag_id for tag in self.tags)
        if len(set(numeric_ids)) != len(numeric_ids):
            raise PlanarPoseEstimationError(
                "tag map contains a duplicate numeric tag id"
            )
        ordered = tuple(sorted(self.tags, key=lambda item: item.tag))
        all_xy: list[tuple[float, float]] = []
        for definition in ordered:
            for point in definition.corners_board_mm:
                if point.frame != self.board_frame:
                    raise PlanarPoseEstimationError(
                        f"tag {definition.tag.tag_id} corner frame does not match "
                        "board_frame"
                    )
                if abs(point.z - self.tag_plane_z_board_mm) > _COPLANAR_TOLERANCE_MM:
                    raise PlanarPoseEstimationError(
                        f"tag {definition.tag.tag_id} corner is not coplanar with "
                        "tag_plane_z_board_mm"
                    )
                if abs(point.x) > MAX_BOARD_COORDINATE_MM or abs(point.y) > MAX_BOARD_COORDINATE_MM:
                    raise PlanarPoseEstimationError(
                        "tag-map board coordinate exceeds the bounded workspace"
                    )
                all_xy.append((point.x, point.y))
        if len(set(all_xy)) != len(all_xy):
            raise PlanarPoseEstimationError(
                "tag-map corner coordinates must be globally distinct"
            )
        object.__setattr__(self, "tags", ordered)

    def definition(self, reference: TagReference) -> PlanarBoardTag | None:
        if not isinstance(reference, TagReference):
            raise TypeError("reference must be a TagReference")
        for definition in self.tags:
            if definition.tag == reference:
                return definition
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.planar_apriltag_board_map.v1",
            "map_id": self.map_id,
            "board_frame": self.board_frame,
            "tag_plane_z_board_mm": self.tag_plane_z_board_mm,
            "corner_order": TAG_MAP_CORNER_ORDER,
            "tags": [tag.to_dict() for tag in self.tags],
            "source_sha256": self.source_sha256,
            "physical_release_effect": "NONE",
        }

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class PlanarPoseEstimatorConfig:
    """Strict numerical, consensus, and diagnostic bounds for one solve."""

    maximum_tag_reprojection_rmse_px: float = 2.0
    minimum_inlier_tags: int = 2
    maximum_refit_rounds: int = 4
    maximum_hypotheses: int = MAX_POSE_HYPOTHESES
    minimum_normal_equation_pivot_ratio: float = 1e-12
    minimum_relative_homography_determinant: float = 1e-12
    maximum_basis_orthogonality_error: float = 0.10
    maximum_basis_scale_relative_error: float = 0.15
    minimum_abs_board_normal_z: float = 0.025
    minimum_camera_depth_mm: float = 1.0
    maximum_translation_norm_mm: float = 1_000_000.0
    minimum_pixel_sigma_px: float = 0.25
    reject_ambiguous_consensus: bool = True

    def __post_init__(self) -> None:
        for field_name, lower, upper in (
            ("maximum_tag_reprojection_rmse_px", 1e-6, 10_000.0),
            ("minimum_normal_equation_pivot_ratio", 1e-16, 1e-3),
            ("minimum_relative_homography_determinant", 1e-16, 1e-3),
            ("maximum_basis_orthogonality_error", 1e-8, 0.5),
            ("maximum_basis_scale_relative_error", 1e-8, 0.5),
            ("minimum_abs_board_normal_z", 0.0, 1.0),
            ("minimum_camera_depth_mm", 1e-6, 1_000_000.0),
            ("maximum_translation_norm_mm", 1.0, 10_000_000.0),
            ("minimum_pixel_sigma_px", 1e-9, 1_000.0),
        ):
            object.__setattr__(
                self,
                field_name,
                _finite(
                    getattr(self, field_name),
                    field_name,
                    minimum=lower,
                    maximum=upper,
                ),
            )
        object.__setattr__(
            self,
            "minimum_inlier_tags",
            _integer(
                self.minimum_inlier_tags,
                "minimum_inlier_tags",
                minimum=1,
                maximum=MAX_BOARD_TAGS,
            ),
        )
        object.__setattr__(
            self,
            "maximum_refit_rounds",
            _integer(
                self.maximum_refit_rounds,
                "maximum_refit_rounds",
                minimum=1,
                maximum=8,
            ),
        )
        object.__setattr__(
            self,
            "maximum_hypotheses",
            _integer(
                self.maximum_hypotheses,
                "maximum_hypotheses",
                minimum=1,
                maximum=MAX_POSE_HYPOTHESES,
            ),
        )
        if not isinstance(self.reject_ambiguous_consensus, bool):
            raise PlanarPoseEstimationError(
                "reject_ambiguous_consensus must be boolean"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.planar_pose_estimator_config.v1",
            "algorithm": "NORMALIZED_HOMOGRAPHY_BOUNDED_TAG_CONSENSUS_V2",
            "corner_order": TAG_MAP_CORNER_ORDER,
            "output_transform": (
                "intrinsics.camera_frame_T_tag_map.board_frame"
            ),
            "plane_origin_correction": "t_board=t_plane-r3*tag_plane_z_board_mm",
            "maximum_tag_reprojection_rmse_px": (
                self.maximum_tag_reprojection_rmse_px
            ),
            "minimum_inlier_tags": self.minimum_inlier_tags,
            "maximum_refit_rounds": self.maximum_refit_rounds,
            "maximum_hypotheses": self.maximum_hypotheses,
            "minimum_normal_equation_pivot_ratio": (
                self.minimum_normal_equation_pivot_ratio
            ),
            "minimum_relative_homography_determinant": (
                self.minimum_relative_homography_determinant
            ),
            "maximum_basis_orthogonality_error": (
                self.maximum_basis_orthogonality_error
            ),
            "maximum_basis_scale_relative_error": (
                self.maximum_basis_scale_relative_error
            ),
            "minimum_abs_board_normal_z": self.minimum_abs_board_normal_z,
            "minimum_camera_depth_mm": self.minimum_camera_depth_mm,
            "maximum_translation_norm_mm": self.maximum_translation_norm_mm,
            "minimum_pixel_sigma_px": self.minimum_pixel_sigma_px,
            "reject_ambiguous_consensus": self.reject_ambiguous_consensus,
            "covariance_interpretation": (
                "DETERMINISTIC_FIRST_ORDER_DIAGNOSTIC_NOT_PHYSICAL_CALIBRATION"
            ),
            "physical_release_effect": "NONE",
        }

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class _EligibleTag:
    detection: AprilTagDetection
    definition: PlanarBoardTag


@dataclass(frozen=True, slots=True)
class _Correspondence:
    tag: TagReference
    board_xy_mm: tuple[float, float]
    pixel_xy: tuple[float, float]


@dataclass(frozen=True, slots=True)
class _PoseCandidate:
    seed_tags: tuple[TagReference, ...]
    pose: RigidTransform
    residuals_px: tuple[float, ...]
    inlier_mask: tuple[bool, ...]

    @property
    def inlier_count(self) -> int:
        return sum(self.inlier_mask)

    @property
    def inlier_rmse_px(self) -> float:
        values = tuple(
            residual
            for residual, inlier in zip(self.residuals_px, self.inlier_mask)
            if inlier
        )
        if not values:
            return math.inf
        return math.sqrt(sum(value * value for value in values) / len(values))


def _validate_convex_ordered_quad(
    points: Sequence[tuple[float, float]],
    label: str,
) -> None:
    if len(points) != 4 or len(set(points)) != 4:
        raise PlanarPoseEstimationError(
            f"{label} must contain four distinct canonical corners"
        )
    turns: list[float] = []
    for index in range(4):
        first = points[index]
        second = points[(index + 1) % 4]
        third = points[(index + 2) % 4]
        turns.append(
            (second[0] - first[0]) * (third[1] - second[1])
            - (second[1] - first[1]) * (third[0] - second[0])
        )
    scale = max(
        1.0,
        *(abs(coordinate) for point in points for coordinate in point),
    )
    tolerance = 1e-12 * scale * scale
    if any(abs(turn) <= tolerance for turn in turns) or not (
        all(turn > 0.0 for turn in turns) or all(turn < 0.0 for turn in turns)
    ):
        raise PlanarPoseEstimationError(
            f"{label} must be a non-degenerate convex ordered quadrilateral"
        )


def _implementation_sha256() -> str:
    path = Path(__file__).resolve()
    digest = hashlib.sha256()
    actual_bytes = 0
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(
                    min(
                        65_536,
                        MAX_ESTIMATOR_IMPLEMENTATION_BYTES - actual_bytes + 1,
                    )
                )
                if not chunk:
                    break
                actual_bytes += len(chunk)
                if actual_bytes > MAX_ESTIMATOR_IMPLEMENTATION_BYTES:
                    raise PlanarPoseEstimationError(
                        "planar pose estimator implementation exceeds its byte limit"
                    )
                digest.update(chunk)
    except OSError as exc:
        raise PlanarPoseEstimationError(
            "cannot bind planar pose estimator implementation bytes"
        ) from exc
    return digest.hexdigest()


def _normalization_matrix(
    points: Sequence[tuple[float, float]],
    label: str,
) -> tuple[tuple[float, ...], tuple[tuple[float, float], ...]]:
    if len(points) < 4:
        raise PlanarPoseEstimationError(f"{label} requires at least four points")
    centre_x = sum(point[0] for point in points) / len(points)
    centre_y = sum(point[1] for point in points) / len(points)
    rms_radius = math.sqrt(
        sum(
            (point[0] - centre_x) ** 2 + (point[1] - centre_y) ** 2
            for point in points
        )
        / len(points)
    )
    if not math.isfinite(rms_radius) or rms_radius <= 1e-12:
        raise PlanarPoseEstimationError(f"{label} point spread is degenerate")
    scale = math.sqrt(2.0) / rms_radius
    matrix = (
        scale,
        0.0,
        -scale * centre_x,
        0.0,
        scale,
        -scale * centre_y,
        0.0,
        0.0,
        1.0,
    )
    normalized = tuple(
        (scale * (point[0] - centre_x), scale * (point[1] - centre_y))
        for point in points
    )
    return matrix, normalized


def _matrix3_multiply(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> tuple[float, ...]:
    return tuple(
        sum(left[row * 3 + index] * right[index * 3 + column] for index in range(3))
        for row in range(3)
        for column in range(3)
    )


def _normalization_inverse(matrix: tuple[float, ...]) -> tuple[float, ...]:
    scale = matrix[0]
    if abs(scale) <= 1e-15:
        raise PlanarPoseEstimationError("normalization matrix is singular")
    return (
        1.0 / scale,
        0.0,
        -matrix[2] / scale,
        0.0,
        1.0 / scale,
        -matrix[5] / scale,
        0.0,
        0.0,
        1.0,
    )


def _solve_linear_system(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
    *,
    minimum_pivot_ratio: float,
) -> tuple[float, ...]:
    size = len(vector)
    if size == 0 or len(matrix) != size or any(len(row) != size for row in matrix):
        raise PlanarPoseEstimationError("linear system dimensions are incoherent")
    augmented = [
        [float(value) for value in row] + [float(vector[index])]
        for index, row in enumerate(matrix)
    ]
    scale = max(abs(value) for row in augmented for value in row[:-1])
    if not math.isfinite(scale) or scale <= 0.0:
        raise PlanarPoseEstimationError("homography normal equations are zero")
    minimum_pivot = scale * minimum_pivot_ratio
    for column in range(size):
        pivot_row = max(
            range(column, size),
            key=lambda row: abs(augmented[row][column]),
        )
        pivot = augmented[pivot_row][column]
        if not math.isfinite(pivot) or abs(pivot) <= minimum_pivot:
            raise PlanarPoseEstimationError(
                "homography normal equations are rank-deficient"
            )
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[column],
            )
        pivot = augmented[column][column]
        for index in range(column, size + 1):
            augmented[column][index] /= pivot
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for index in range(column, size + 1):
                augmented[row][index] -= factor * augmented[column][index]
    result = tuple(augmented[index][size] for index in range(size))
    if any(not math.isfinite(value) for value in result):
        raise PlanarPoseEstimationError("homography solve produced nonfinite values")
    return result


def _fit_homography(
    correspondences: Sequence[_Correspondence],
    config: PlanarPoseEstimatorConfig,
) -> tuple[float, ...]:
    if len(correspondences) < 4:
        raise PlanarPoseEstimationError(
            "homography requires at least four corner correspondences"
        )
    if len(correspondences) > MAX_POSE_CORRESPONDENCES:
        raise PlanarPoseEstimationError("homography correspondence budget exceeded")
    board_points = tuple(item.board_xy_mm for item in correspondences)
    pixel_points = tuple(item.pixel_xy for item in correspondences)
    board_transform, normalized_board = _normalization_matrix(
        board_points, "board"
    )
    pixel_transform, normalized_pixels = _normalization_matrix(
        pixel_points, "pixel"
    )

    rows: list[tuple[float, ...]] = []
    values: list[float] = []
    for (x_coord, y_coord), (u_coord, v_coord) in zip(
        normalized_board, normalized_pixels
    ):
        rows.append(
            (
                x_coord,
                y_coord,
                1.0,
                0.0,
                0.0,
                0.0,
                -u_coord * x_coord,
                -u_coord * y_coord,
            )
        )
        values.append(u_coord)
        rows.append(
            (
                0.0,
                0.0,
                0.0,
                x_coord,
                y_coord,
                1.0,
                -v_coord * x_coord,
                -v_coord * y_coord,
            )
        )
        values.append(v_coord)

    normal_matrix = [
        [
            sum(row[left] * row[right] for row in rows)
            for right in range(8)
        ]
        for left in range(8)
    ]
    normal_vector = [
        sum(row[column] * value for row, value in zip(rows, values))
        for column in range(8)
    ]
    solution = _solve_linear_system(
        normal_matrix,
        normal_vector,
        minimum_pivot_ratio=config.minimum_normal_equation_pivot_ratio,
    )
    normalized_h = (*solution, 1.0)
    homography = _matrix3_multiply(
        _matrix3_multiply(
            _normalization_inverse(pixel_transform), normalized_h
        ),
        board_transform,
    )
    scale = homography[8]
    magnitude = max(abs(value) for value in homography)
    if not math.isfinite(scale) or abs(scale) <= 1e-15 * max(1.0, magnitude):
        raise PlanarPoseEstimationError(
            "homography scale is singular after denormalization"
        )
    homography = tuple(value / scale for value in homography)
    determinant = _matrix3_determinant(homography)
    magnitude = max(abs(value) for value in homography)
    if abs(determinant) <= (
        config.minimum_relative_homography_determinant
        * max(1.0, magnitude**3)
    ):
        raise PlanarPoseEstimationError("homography is degenerate")
    return homography


def _matrix3_determinant(matrix: tuple[float, ...]) -> float:
    return (
        matrix[0] * (matrix[4] * matrix[8] - matrix[5] * matrix[7])
        - matrix[1] * (matrix[3] * matrix[8] - matrix[5] * matrix[6])
        + matrix[2] * (matrix[3] * matrix[7] - matrix[4] * matrix[6])
    )


def _matrix_vector(
    matrix: tuple[float, ...], vector: tuple[float, float, float]
) -> Vec3:
    return Vec3(
        sum(matrix[index] * vector[index] for index in range(3)),
        sum(matrix[3 + index] * vector[index] for index in range(3)),
        sum(matrix[6 + index] * vector[index] for index in range(3)),
    )


def _camera_matrix_inverse(intrinsics: PinholeIntrinsics) -> tuple[float, ...]:
    fx = intrinsics.fx_px
    fy = intrinsics.fy_px
    skew = intrinsics.skew_px
    return (
        1.0 / fx,
        -skew / (fx * fy),
        (skew * intrinsics.cy_px / fy - intrinsics.cx_px) / fx,
        0.0,
        1.0 / fy,
        -intrinsics.cy_px / fy,
        0.0,
        0.0,
        1.0,
    )


def _decompose_homography(
    homography: tuple[float, ...],
    intrinsics: PinholeIntrinsics,
    tag_map: PlanarBoardTagMap,
    config: PlanarPoseEstimatorConfig,
) -> RigidTransform:
    inverse_intrinsics = _camera_matrix_inverse(intrinsics)
    h1 = (homography[0], homography[3], homography[6])
    h2 = (homography[1], homography[4], homography[7])
    h3 = (homography[2], homography[5], homography[8])
    basis1 = _matrix_vector(inverse_intrinsics, h1)
    basis2 = _matrix_vector(inverse_intrinsics, h2)
    translation_direction = _matrix_vector(inverse_intrinsics, h3)
    norm1 = basis1.norm
    norm2 = basis2.norm
    if min(norm1, norm2) <= 1e-15:
        raise PlanarPoseEstimationError("homography pose basis has zero length")
    scale_error = abs(norm1 - norm2) / max(norm1, norm2)
    orthogonality_error = abs(basis1.dot(basis2) / (norm1 * norm2))
    if scale_error > config.maximum_basis_scale_relative_error:
        raise PlanarPoseEstimationError(
            "homography pose basis scale mismatch exceeds policy"
        )
    if orthogonality_error > config.maximum_basis_orthogonality_error:
        raise PlanarPoseEstimationError(
            "homography pose basis orthogonality error exceeds policy"
        )

    scale = 2.0 / (norm1 + norm2)
    if translation_direction.z * scale < 0.0:
        scale = -scale
    raw_r1 = basis1.scaled(scale)
    raw_r2 = basis2.scaled(scale)
    r1 = raw_r1.normalized()
    r2_rejected = raw_r2 - r1.scaled(raw_r2.dot(r1))
    if r2_rejected.norm <= 1e-12:
        raise PlanarPoseEstimationError("homography pose axes are collinear")
    r2 = r2_rejected.normalized()
    r3 = r1.cross(r2).normalized()
    if abs(r3.z) < config.minimum_abs_board_normal_z:
        raise PlanarPoseEstimationError(
            "estimated board plane is too close to grazing incidence"
        )
    translation_plane = translation_direction.scaled(scale)
    translation_board = translation_plane - r3.scaled(
        tag_map.tag_plane_z_board_mm
    )
    if translation_board.norm > config.maximum_translation_norm_mm:
        raise PlanarPoseEstimationError(
            "estimated translation exceeds the configured bound"
        )
    rotation = Rotation3(
        (
            r1.x,
            r2.x,
            r3.x,
            r1.y,
            r2.y,
            r3.y,
            r1.z,
            r2.z,
            r3.z,
        )
    )
    return RigidTransform(
        parent_frame=intrinsics.camera_frame,
        child_frame=tag_map.board_frame,
        rotation=rotation,
        translation_mm=translation_board,
    )


def _correspondences(tags: Iterable[_EligibleTag]) -> tuple[_Correspondence, ...]:
    result: list[_Correspondence] = []
    for item in tags:
        # Never sort corners: decoded detector and board-map canonical indices
        # are the semantic correspondence.
        for board_corner, pixel_corner in zip(
            item.definition.corners_board_mm,
            item.detection.corners_px,
        ):
            result.append(
                _Correspondence(
                    tag=item.detection.tag,
                    board_xy_mm=(board_corner.x, board_corner.y),
                    pixel_xy=(pixel_corner.x_px, pixel_corner.y_px),
                )
            )
    if len(result) > MAX_POSE_CORRESPONDENCES:
        raise PlanarPoseEstimationError("pose correspondence budget exceeded")
    return tuple(result)


def _project_point(
    point: Point3Mm,
    pose: RigidTransform,
    intrinsics: PinholeIntrinsics,
    config: PlanarPoseEstimatorConfig,
) -> tuple[float, float, float]:
    if point.frame != pose.child_frame:
        raise PlanarPoseEstimationError(
            "tag-map point frame does not match estimated board frame"
        )
    camera = pose.transform_position_mm(Vec3(point.x, point.y, point.z))
    if not math.isfinite(camera.z) or camera.z <= config.minimum_camera_depth_mm:
        raise PlanarPoseEstimationError(
            "estimated tag-map point is not in front of the camera"
        )
    normalized_x = camera.x / camera.z
    normalized_y = camera.y / camera.z
    pixel_x = (
        intrinsics.fx_px * normalized_x
        + intrinsics.skew_px * normalized_y
        + intrinsics.cx_px
    )
    pixel_y = intrinsics.fy_px * normalized_y + intrinsics.cy_px
    if not math.isfinite(pixel_x) or not math.isfinite(pixel_y):
        raise PlanarPoseEstimationError("pose reprojection produced nonfinite pixels")
    return pixel_x, pixel_y, camera.z


def _tag_residuals(
    eligible: Sequence[_EligibleTag],
    pose: RigidTransform,
    intrinsics: PinholeIntrinsics,
    config: PlanarPoseEstimatorConfig,
) -> tuple[float, ...]:
    residuals: list[float] = []
    for item in eligible:
        squared_error = 0.0
        for board_corner, detected_corner in zip(
            item.definition.corners_board_mm,
            item.detection.corners_px,
        ):
            projected_x, projected_y, _ = _project_point(
                board_corner, pose, intrinsics, config
            )
            squared_error += (
                (projected_x - detected_corner.x_px) ** 2
                + (projected_y - detected_corner.y_px) ** 2
            )
        residual = math.sqrt(squared_error / 4.0)
        if not math.isfinite(residual):
            raise PlanarPoseEstimationError("tag reprojection residual is nonfinite")
        residuals.append(residual)
    return tuple(residuals)


def _fit_pose(
    eligible: Sequence[_EligibleTag],
    intrinsics: PinholeIntrinsics,
    tag_map: PlanarBoardTagMap,
    config: PlanarPoseEstimatorConfig,
) -> RigidTransform:
    homography = _fit_homography(_correspondences(eligible), config)
    return _decompose_homography(homography, intrinsics, tag_map, config)


def _hypothesis_tag_sets(
    eligible: tuple[_EligibleTag, ...],
    config: PlanarPoseEstimatorConfig,
) -> tuple[tuple[TagReference, ...], ...]:
    references = tuple(item.detection.tag for item in eligible)
    hypotheses: list[tuple[TagReference, ...]] = []
    # Each decoded tag supplies four non-collinear corners and therefore one
    # minimal deterministic homography hypothesis.
    hypotheses.extend((reference,) for reference in references)
    hypotheses.append(references)
    if len(references) >= 3:
        hypotheses.extend(
            tuple(item for item in references if item != omitted)
            for omitted in references
        )
    unique: list[tuple[TagReference, ...]] = []
    seen: set[tuple[TagReference, ...]] = set()
    for hypothesis in hypotheses:
        if hypothesis not in seen:
            seen.add(hypothesis)
            unique.append(hypothesis)
    if len(unique) > config.maximum_hypotheses:
        raise PlanarPoseEstimationError(
            "pose hypothesis budget is smaller than the deterministic campaign"
        )
    return tuple(unique)


def _initial_consensus(
    eligible: tuple[_EligibleTag, ...],
    intrinsics: PinholeIntrinsics,
    tag_map: PlanarBoardTagMap,
    config: PlanarPoseEstimatorConfig,
) -> tuple[bool, ...]:
    by_tag = {item.detection.tag: item for item in eligible}
    candidates: list[_PoseCandidate] = []
    for seed_tags in _hypothesis_tag_sets(eligible, config):
        seed = tuple(by_tag[tag] for tag in seed_tags)
        try:
            pose = _fit_pose(seed, intrinsics, tag_map, config)
            residuals = _tag_residuals(eligible, pose, intrinsics, config)
        except (PlanarPoseEstimationError, ValueError):
            continue
        mask = tuple(
            residual <= config.maximum_tag_reprojection_rmse_px
            for residual in residuals
        )
        candidates.append(
            _PoseCandidate(seed_tags, pose, residuals, mask)
        )
    if not candidates:
        raise PlanarPoseEstimationError(
            "no bounded homography hypothesis produced a valid camera pose"
        )
    maximum_count = max(candidate.inlier_count for candidate in candidates)
    if maximum_count < config.minimum_inlier_tags:
        raise PlanarPoseEstimationError(
            "no homography consensus satisfies minimum_inlier_tags"
        )
    best_count_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.inlier_count == maximum_count
    )
    distinct_masks = {candidate.inlier_mask for candidate in best_count_candidates}
    if config.reject_ambiguous_consensus and len(distinct_masks) > 1:
        raise PlanarPoseEstimationError(
            "equal-support homography hypotheses have ambiguous inlier sets"
        )
    selected = min(
        best_count_candidates,
        key=lambda candidate: (
            candidate.inlier_rmse_px,
            tuple((tag.family, tag.tag_id) for tag in candidate.seed_tags),
        ),
    )
    return selected.inlier_mask


def _refine_consensus(
    eligible: tuple[_EligibleTag, ...],
    initial_mask: tuple[bool, ...],
    intrinsics: PinholeIntrinsics,
    tag_map: PlanarBoardTagMap,
    config: PlanarPoseEstimatorConfig,
) -> tuple[RigidTransform, tuple[float, ...], tuple[bool, ...]]:
    mask = initial_mask
    seen: set[tuple[bool, ...]] = set()
    for _ in range(config.maximum_refit_rounds):
        if mask in seen:
            raise PlanarPoseEstimationError("pose inlier refinement oscillated")
        seen.add(mask)
        selected = tuple(
            item for item, inlier in zip(eligible, mask) if inlier
        )
        if len(selected) < config.minimum_inlier_tags:
            raise PlanarPoseEstimationError(
                "pose refinement fell below minimum_inlier_tags"
            )
        pose = _fit_pose(selected, intrinsics, tag_map, config)
        residuals = _tag_residuals(eligible, pose, intrinsics, config)
        threshold_mask = tuple(
            residual <= config.maximum_tag_reprojection_rmse_px
            for residual in residuals
        )
        # Consensus refinement is deliberately monotonic.  The initial
        # hypothesis campaign has already selected a unique maximum-support
        # inlier set.  A refit may expose another outlier, but reintroducing a
        # previously excluded tag can alternate between two masks forever as
        # integer-pixel residuals cross the hard threshold.  Intersecting with
        # the current mask is conservative, deterministic, and bounded.
        updated = tuple(
            was_inlier and under_threshold
            for was_inlier, under_threshold in zip(mask, threshold_mask)
        )
        if sum(updated) < config.minimum_inlier_tags:
            raise PlanarPoseEstimationError(
                "refined pose has insufficient reprojection inliers"
            )
        if updated == mask:
            return pose, residuals, mask
        mask = updated
    raise PlanarPoseEstimationError(
        "pose inlier refinement did not converge within its round bound"
    )


def _pose_covariance(
    eligible: Sequence[_EligibleTag],
    mask: Sequence[bool],
    residuals_px: Sequence[float],
    pose: RigidTransform,
    intrinsics: PinholeIntrinsics,
    config: PlanarPoseEstimatorConfig,
) -> PoseCovariance6:
    selected = tuple(item for item, inlier in zip(eligible, mask) if inlier)
    selected_residuals = tuple(
        residual for residual, inlier in zip(residuals_px, mask) if inlier
    )
    points = tuple(
        point
        for item in selected
        for point in item.definition.corners_board_mm
    )
    if not points or not selected_residuals:
        raise PlanarPoseEstimationError("covariance requires pose inliers")
    x_span = max(point.x for point in points) - min(point.x for point in points)
    y_span = max(point.y for point in points) - min(point.y for point in points)
    board_span = math.hypot(x_span, y_span)
    if board_span <= 1e-9:
        raise PlanarPoseEstimationError("inlier board span is degenerate")
    depths = tuple(
        _project_point(point, pose, intrinsics, config)[2] for point in points
    )
    mean_depth = sum(depths) / len(depths)
    tag_rmse = math.sqrt(
        sum(value * value for value in selected_residuals)
        / len(selected_residuals)
    )
    pixel_sigma = max(tag_rmse, config.minimum_pixel_sigma_px)
    sample_scale = math.sqrt(len(points))
    focal = math.sqrt(intrinsics.fx_px * intrinsics.fy_px)
    lateral_sigma_mm = pixel_sigma * mean_depth / (focal * sample_scale)
    depth_sigma_mm = (
        pixel_sigma
        * mean_depth
        * mean_depth
        / (focal * board_span * sample_scale)
    )
    tilt_sigma_rad = (
        pixel_sigma * mean_depth / (focal * board_span * sample_scale)
    )
    yaw_sigma_rad = pixel_sigma / (focal * sample_scale)
    variances = (
        lateral_sigma_mm**2,
        lateral_sigma_mm**2,
        depth_sigma_mm**2,
        tilt_sigma_rad**2,
        tilt_sigma_rad**2,
        yaw_sigma_rad**2,
    )
    if any(not math.isfinite(value) or value < 0.0 for value in variances):
        raise PlanarPoseEstimationError(
            "diagnostic covariance calculation produced an invalid variance"
        )
    return PoseCovariance6.diagonal(variances)


def estimate_planar_board_pose(
    detection_batch: AprilTagDetectionBatch,
    intrinsics: PinholeIntrinsics,
    tag_map: PlanarBoardTagMap,
    config: PlanarPoseEstimatorConfig | None = None,
) -> AprilTagPoseObservation:
    """Estimate ``camera_optical_T_board`` from typed detector corners only."""

    if not isinstance(detection_batch, AprilTagDetectionBatch):
        raise TypeError("detection_batch must be an AprilTagDetectionBatch")
    if not isinstance(intrinsics, PinholeIntrinsics):
        raise TypeError("intrinsics must be PinholeIntrinsics")
    if not isinstance(tag_map, PlanarBoardTagMap):
        raise TypeError("tag_map must be PlanarBoardTagMap")
    selected_config = config or PlanarPoseEstimatorConfig()
    if not isinstance(selected_config, PlanarPoseEstimatorConfig):
        raise TypeError("config must be PlanarPoseEstimatorConfig or None")
    if (
        detection_batch.frame.width_px != intrinsics.width_px
        or detection_batch.frame.height_px != intrinsics.height_px
    ):
        raise PlanarPoseEstimationError(
            "detection frame resolution does not match pinhole intrinsics"
        )

    eligible = tuple(
        _EligibleTag(detection, definition)
        for detection in detection_batch.detections
        if detection.detector_accepted
        for definition in (tag_map.definition(detection.tag),)
        if definition is not None
    )
    if len(eligible) < selected_config.minimum_inlier_tags:
        raise PlanarPoseEstimationError(
            "accepted mapped detections are fewer than minimum_inlier_tags"
        )
    initial_mask = _initial_consensus(
        eligible, intrinsics, tag_map, selected_config
    )
    pose, residuals, final_mask = _refine_consensus(
        eligible,
        initial_mask,
        intrinsics,
        tag_map,
        selected_config,
    )
    covariance = _pose_covariance(
        eligible,
        final_mask,
        residuals,
        pose,
        intrinsics,
        selected_config,
    )
    residual_by_tag = {
        item.detection.tag: residual
        for item, residual in zip(eligible, residuals)
    }
    inlier_by_tag = {
        item.detection.tag: inlier
        for item, inlier in zip(eligible, final_mask)
    }
    diagnostics: list[TagFitDiagnostic] = []
    for detection in detection_batch.detections:
        if not detection.detector_accepted:
            diagnostics.append(
                TagFitDiagnostic(
                    tag=detection.tag,
                    inlier=False,
                    reprojection_residual_px=None,
                    rejection_reason=f"detector_rejected:{detection.rejection_reason}",
                )
            )
            continue
        if tag_map.definition(detection.tag) is None:
            diagnostics.append(
                TagFitDiagnostic(
                    tag=detection.tag,
                    inlier=False,
                    reprojection_residual_px=None,
                    rejection_reason="tag_not_in_board_map",
                )
            )
            continue
        residual = residual_by_tag[detection.tag]
        inlier = inlier_by_tag[detection.tag]
        diagnostics.append(
            TagFitDiagnostic(
                tag=detection.tag,
                inlier=inlier,
                reprojection_residual_px=residual,
                rejection_reason=(
                    None
                    if inlier
                    else (
                        "reprojection_residual_exceeds_threshold"
                        if residual
                        > selected_config.maximum_tag_reprojection_rmse_px
                        else "excluded_from_monotonic_consensus"
                    )
                ),
            )
        )

    estimator = PoseEstimatorIdentity(
        estimator_id=PLANAR_POSE_ESTIMATOR_ID,
        version=PLANAR_POSE_ESTIMATOR_VERSION,
        configuration_sha256=selected_config.content_hash,
        implementation_sha256=_implementation_sha256(),
    )
    return AprilTagPoseObservation(
        detection_batch=detection_batch,
        estimator=estimator,
        camera_intrinsics_sha256=intrinsics.content_hash,
        tag_map_sha256=tag_map.content_hash,
        pose=pose,
        covariance=covariance,
        fit_diagnostics=tuple(diagnostics),
    )


@dataclass(frozen=True, slots=True)
class PlanarAprilTagBoardPoseEstimator:
    """Reusable immutable service wrapper around :func:`estimate_planar_board_pose`."""

    config: PlanarPoseEstimatorConfig = PlanarPoseEstimatorConfig()

    def __post_init__(self) -> None:
        if not isinstance(self.config, PlanarPoseEstimatorConfig):
            raise TypeError("config must be PlanarPoseEstimatorConfig")

    def estimate(
        self,
        detection_batch: AprilTagDetectionBatch,
        intrinsics: PinholeIntrinsics,
        tag_map: PlanarBoardTagMap,
    ) -> AprilTagPoseObservation:
        return estimate_planar_board_pose(
            detection_batch,
            intrinsics,
            tag_map,
            self.config,
        )


__all__ = [
    "CAMERA_OPTICAL_FRAME",
    "MAX_BOARD_TAGS",
    "MAX_POSE_CORRESPONDENCES",
    "MAX_POSE_HYPOTHESES",
    "PLANAR_POSE_ESTIMATOR_ID",
    "PLANAR_POSE_ESTIMATOR_VERSION",
    "TAG_MAP_CORNER_ORDER",
    "PinholeIntrinsics",
    "PlanarAprilTagBoardPoseEstimator",
    "PlanarBoardTag",
    "PlanarBoardTagMap",
    "PlanarPoseEstimationError",
    "PlanarPoseEstimatorConfig",
    "estimate_planar_board_pose",
]
