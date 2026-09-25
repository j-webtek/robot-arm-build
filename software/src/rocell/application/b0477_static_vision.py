"""B0477 static-overhead pixel rehearsal with zero physical authority.

This module is an additive pre-hardware path for the user-purchased Arducam
B0477 / Sony IMX283 / included nominal 16 mm lens.  It deliberately does not
reuse the historical eye-on-arm camera binding.  Instead it reloads the exact
purchase profile and static-support design, renders the existing six-tag RC03
scene, and exercises the production-shaped pixel boundary:

``synthetic JPEG -> AprilTag pixel detector -> planar board-pose estimator``.

The projection uses the published horizontal FOV plus native 3:2 aspect, which
matches the conservative support-coverage rule instead of treating the
incompatible published horizontal/vertical pair as independent focal lengths.
A non-zero synthetic lens warp exercises a hash-bound capture-to-undistorted
pixel transform.  Neither that stress warp nor the projection is a physical
intrinsic or static-extrinsic calibration.  Board registration is fit from the
four world tags T0--T3 only; station tags K0/P0 are then projected through that
already-fitted pose and scored as held-out checks.  No code in this module
opens USB/video devices, imports OpenCV, sends an arm command, or grants motion
or contact authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from rocell.models.frames import Transform
from rocell.simulation.camera import DistortionCoefficients, PinholeCameraModel
from rocell.simulation.scene import (
    DEFAULT_SIMULATED_TAG_PLANE_Z_MM,
    NominalWorkcellScene,
    load_rc03_nominal_scene,
)
from rocell.simulation.synthetic_raster import (
    MAX_SYNTHETIC_JPEG_BYTES,
    SyntheticOverviewRasterRenderer,
    SyntheticRasterConfig,
)
from rocell.vision.apriltag_codebook import DEFAULT_APRILTAG_36H11_CODEBOOK
from rocell.vision.camera_profile import (
    PurchasedCameraProfile,
    load_camera_profile,
)
from rocell.vision.detections import AprilTagDetectionBatch, TagReference
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
from rocell.workcell.static_camera_support import (
    StaticCameraSupportDesign,
    load_static_camera_support_design,
)

from .b0477_optical_contract import (
    B0477_CAPTURE_PIXEL_SPACE,
    B0477_ESTIMATOR_PIXEL_SPACE,
    B0477_PHASE1_OPTICAL_FRAME,
    B0477OpticalContractError,
    B0477SyntheticOpticalContract,
    build_b0477_synthetic_optical_contract,
)


B0477_STATIC_VISION_SCHEMA = "rocell.b0477_static_vision_rehearsal.v2"
B0477_STATIC_VISION_CAPTURE_SCHEMA = "rocell.b0477_static_vision_capture.v1"
# Retain the established public symbol while aligning its value with the
# Phase-1 architecture's canonical static eye-to-hand optical frame.
B0477_OPTICAL_FRAME = B0477_PHASE1_OPTICAL_FRAME
MAX_B0477_REHEARSAL_SEQUENCE = 1_000_000_000
B0477_POSE_FIT_TAG_IDS = (0, 1, 2, 3)
B0477_HELD_OUT_STATION_TAG_IDS = (4, 5)
B0477_MAX_HELD_OUT_STATION_RMSE_PX = 2.0
B0477_MAX_HELD_OUT_STATION_CORNER_ERROR_PX = 3.0
B0477_MAX_TRANSLATION_ERROR_MM = 1.0
B0477_MAX_ROTATION_ERROR_DEG = 0.1
B0477_MAX_INLIER_REPROJECTION_RMSE_PX = 1.0

_PROFILE_RELATIVE_PATH = Path(
    "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
)
_SUPPORT_RELATIVE_PATH = Path(
    "hardware/static_overhead_camera/config/support_design.json"
)
_RC03_RELATIVE_ROOT = Path("active-project/RoCell_v0_3")
_EXPECTED_TAG_IDS = B0477_POSE_FIT_TAG_IDS + B0477_HELD_OUT_STATION_TAG_IDS
_TAG_LOSS_IDS = B0477_POSE_FIT_TAG_IDS
_HELD_OUT_STATION_NAMES = {4: "K0", 5: "P0"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class B0477StaticVisionError(ValueError):
    """The B0477 rehearsal inputs or cross-source contracts are incoherent."""


class B0477StaticVisionMode(str, Enum):
    """Bounded synthetic scenarios accepted by the rehearsal."""

    NORMAL = "NORMAL"
    TAG_LOSS = "TAG_LOSS"


def _canonical_hash(value: object) -> str:
    """Hash one JSON-safe value with deterministic key and number encoding."""

    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise B0477StaticVisionError(
            f"B0477 rehearsal report is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise B0477StaticVisionError(f"{label} must be a lowercase SHA-256")
    return value


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise B0477StaticVisionError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise B0477StaticVisionError(f"{label} must be finite and non-negative")
    return result


def _bounded_sequence(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= MAX_B0477_REHEARSAL_SEQUENCE
    ):
        raise B0477StaticVisionError(
            "sequence must be an integer within "
            f"[0, {MAX_B0477_REHEARSAL_SEQUENCE}]"
        )
    return value


def _contained_path(root: Path, selected: Path, label: str) -> Path:
    """Resolve a selected source while retaining the workspace as a boundary."""

    candidate = selected if selected.is_absolute() else root / selected
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise B0477StaticVisionError(f"{label} escapes the workspace") from exc
    if not resolved.is_file():
        raise B0477StaticVisionError(f"{label} is not a file: {resolved}")
    return resolved


@dataclass(frozen=True, slots=True)
class B0477NominalProjection:
    """Nominal eye-to-hand projection, never a measured calibration."""

    optical_frame: str
    resolution_px: tuple[int, int]
    intrinsics_row_major: tuple[float, ...]
    camera_T_board_row_major: tuple[float, ...]
    camera_axis_xy_board_mm: tuple[float, float]
    entrance_pupil_z_board_mm: float
    tag_plane_z_board_mm: float
    nominal_working_distance_mm: float
    published_fov_deg: tuple[float, float]
    effective_rectilinear_fov_deg: tuple[float, float]
    distortion_coefficients: tuple[float, float, float, float, float]
    intrinsics_source_sha256: str
    undistortion_map_sha256: str
    optical_contract_sha256: str
    capture_pixel_space: str = B0477_CAPTURE_PIXEL_SPACE
    estimator_pixel_space: str = B0477_ESTIMATOR_PIXEL_SPACE
    derivation_state: str = (
        "NOMINAL_ASPECT_CONSISTENT_FROM_PUBLISHED_HORIZONTAL_FOV"
    )
    distortion_assumption: str = (
        "NONZERO_SYNTHETIC_STRESS_FIXTURE_NOT_MEASURED_B0477_LENS"
    )

    def __post_init__(self) -> None:
        if self.optical_frame != B0477_OPTICAL_FRAME:
            raise B0477StaticVisionError("unexpected B0477 optical frame")
        if self.resolution_px != (2736, 1824):
            raise B0477StaticVisionError("B0477 proxy resolution must be 2736x1824")
        if len(self.intrinsics_row_major) != 9:
            raise B0477StaticVisionError("intrinsics must contain nine values")
        if len(self.camera_T_board_row_major) != 16:
            raise B0477StaticVisionError("camera_T_board must contain sixteen values")
        if self.camera_axis_xy_board_mm != (305.0, 228.5):
            raise B0477StaticVisionError("camera axis must remain centered over RC03")
        for label, value in (
            ("entrance pupil z", self.entrance_pupil_z_board_mm),
            ("tag plane z", self.tag_plane_z_board_mm),
            ("working distance", self.nominal_working_distance_mm),
        ):
            _finite_nonnegative(value, label)
        if self.nominal_working_distance_mm <= 0.0:
            raise B0477StaticVisionError("working distance must be positive")
        if self.published_fov_deg != (49.0, 38.0):
            raise B0477StaticVisionError("published nominal FOV must remain 49x38 deg")
        try:
            contract = self.optical_contract
        except (TypeError, ValueError) as exc:
            raise B0477StaticVisionError(
                f"B0477 optical contract is invalid: {exc}"
            ) from exc
        if self.intrinsics_row_major != contract.intrinsics_row_major:
            raise B0477StaticVisionError(
                "projection intrinsics differ from the bound optical contract"
            )
        if self.effective_rectilinear_fov_deg != (
            contract.effective_horizontal_fov_deg,
            contract.effective_vertical_fov_deg,
        ):
            raise B0477StaticVisionError(
                "effective FOV differs from the bound optical contract"
            )
        if self.undistortion_map_sha256 != contract.undistortion_map_sha256:
            raise B0477StaticVisionError("undistortion map hash drift detected")
        if self.optical_contract_sha256 != contract.content_sha256:
            raise B0477StaticVisionError("optical contract hash drift detected")

    @property
    def optical_contract(self) -> B0477SyntheticOpticalContract:
        """Reconstruct and revalidate the exact pixel-space contract."""

        k1, k2, p1, p2, k3 = self.distortion_coefficients
        return B0477SyntheticOpticalContract(
            optical_frame=self.optical_frame,
            width_px=self.resolution_px[0],
            height_px=self.resolution_px[1],
            fx_px=self.intrinsics_row_major[0],
            fy_px=self.intrinsics_row_major[4],
            cx_px=self.intrinsics_row_major[2],
            cy_px=self.intrinsics_row_major[5],
            published_horizontal_fov_deg=self.published_fov_deg[0],
            published_vertical_fov_deg=self.published_fov_deg[1],
            effective_horizontal_fov_deg=self.effective_rectilinear_fov_deg[0],
            effective_vertical_fov_deg=self.effective_rectilinear_fov_deg[1],
            distortion=DistortionCoefficients(k1, k2, p1, p2, k3),
            intrinsics_source_sha256=self.intrinsics_source_sha256,
            capture_pixel_space=self.capture_pixel_space,
            estimator_pixel_space=self.estimator_pixel_space,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "optical_frame": self.optical_frame,
            "frame_convention": {
                "board": "+x right, +y rear/toward arm, +z up",
                "camera_optical": "+x image right, +y image down, +z from camera toward board",
                "transform": "camera_T_board",
            },
            "resolution_px": list(self.resolution_px),
            "intrinsics_row_major": list(self.intrinsics_row_major),
            "camera_T_board_row_major": list(self.camera_T_board_row_major),
            "camera_axis_xy_board_mm": list(self.camera_axis_xy_board_mm),
            "entrance_pupil_z_board_mm": self.entrance_pupil_z_board_mm,
            "tag_plane_z_board_mm": self.tag_plane_z_board_mm,
            "nominal_working_distance_mm": self.nominal_working_distance_mm,
            "published_fov_deg": {
                "horizontal": self.published_fov_deg[0],
                "vertical": self.published_fov_deg[1],
                "evidence_state": "MANUFACTURER_PUBLISHED_UNMEASURED",
            },
            "effective_rectilinear_fov_deg": {
                "horizontal": self.effective_rectilinear_fov_deg[0],
                "vertical": self.effective_rectilinear_fov_deg[1],
                "derivation": "HORIZONTAL_PUBLISHED_PLUS_NATIVE_3_TO_2_ASPECT",
            },
            "pixel_spaces": {
                "capture": self.capture_pixel_space,
                "pose_estimator": self.estimator_pixel_space,
            },
            "distortion": {
                "model": "BROWN_CONRADY_5",
                "coefficients_k1_k2_p1_p2_k3": list(
                    self.distortion_coefficients
                ),
                "evidence_state": (
                    "SYNTHETIC_STRESS_FIXTURE_NOT_MEASURED_B0477_LENS"
                ),
            },
            "intrinsics_source_sha256": self.intrinsics_source_sha256,
            "undistortion_map_sha256": self.undistortion_map_sha256,
            "optical_contract_sha256": self.optical_contract_sha256,
            "derivation_state": self.derivation_state,
            "distortion_assumption": self.distortion_assumption,
            "physical_calibration_authority": False,
        }


@dataclass(frozen=True, slots=True)
class B0477PixelStatistics:
    """Compact statistics taken from the rendered JPEG and decoded tags."""

    width_px: int
    height_px: int
    pixel_count: int
    jpeg_byte_count: int
    jpeg_sha256: str
    minimum_gray: int
    maximum_gray: int
    mean_gray: float
    dark_fraction_below_128: float
    accepted_tag_edge_min_px: float | None
    accepted_tag_edge_mean_px: float | None
    accepted_tag_edge_max_px: float | None

    def __post_init__(self) -> None:
        if (self.width_px, self.height_px) != (2736, 1824):
            raise B0477StaticVisionError("pixel statistics resolution is not B0477 proxy")
        if self.pixel_count != self.width_px * self.height_px:
            raise B0477StaticVisionError("pixel_count disagrees with resolution")
        if self.jpeg_byte_count <= 0:
            raise B0477StaticVisionError("jpeg_byte_count must be positive")
        _digest(self.jpeg_sha256, "JPEG SHA-256")
        if not 0 <= self.minimum_gray <= self.maximum_gray <= 255:
            raise B0477StaticVisionError("grayscale range is invalid")
        _finite_nonnegative(self.mean_gray, "mean_gray")
        dark_fraction = _finite_nonnegative(
            self.dark_fraction_below_128, "dark_fraction_below_128"
        )
        if dark_fraction > 1.0:
            raise B0477StaticVisionError("dark fraction cannot exceed one")
        edge_values = (
            self.accepted_tag_edge_min_px,
            self.accepted_tag_edge_mean_px,
            self.accepted_tag_edge_max_px,
        )
        if all(value is None for value in edge_values):
            return
        if any(value is None for value in edge_values):
            raise B0477StaticVisionError("tag edge statistics must be all present or null")
        minimum, mean, maximum = (float(value) for value in edge_values if value is not None)
        if not (0.0 < minimum <= mean <= maximum):
            raise B0477StaticVisionError("tag edge statistics are not ordered positive values")

    def to_dict(self) -> dict[str, object]:
        return {
            "resolution_px": [self.width_px, self.height_px],
            "pixel_count": self.pixel_count,
            "jpeg_byte_count": self.jpeg_byte_count,
            "jpeg_sha256": self.jpeg_sha256,
            "grayscale": {
                "minimum": self.minimum_gray,
                "maximum": self.maximum_gray,
                "mean": self.mean_gray,
                "fraction_below_128": self.dark_fraction_below_128,
            },
            "accepted_tag_edge_px": {
                "minimum": self.accepted_tag_edge_min_px,
                "mean": self.accepted_tag_edge_mean_px,
                "maximum": self.accepted_tag_edge_max_px,
            },
        }


@dataclass(frozen=True, slots=True)
class B0477PoseComparison:
    """Error between nominal synthetic truth and the pixel-estimated pose."""

    estimate_available: bool
    translation_error_mm: float | None
    rotation_error_deg: float | None
    inlier_reprojection_rmse_px: float | None

    def __post_init__(self) -> None:
        values = (
            self.translation_error_mm,
            self.rotation_error_deg,
            self.inlier_reprojection_rmse_px,
        )
        if self.estimate_available:
            if any(value is None for value in values):
                raise B0477StaticVisionError("available pose estimate requires all errors")
            for label, value in zip(
                ("translation error", "rotation error", "reprojection RMSE"), values
            ):
                _finite_nonnegative(value, label)
        elif any(value is not None for value in values):
            raise B0477StaticVisionError("unavailable pose estimate cannot report errors")

    def to_dict(self) -> dict[str, object]:
        return {
            "comparison": "PIXEL_ESTIMATE_VS_NOMINAL_SYNTHETIC_CAMERA_T_BOARD",
            "estimate_available": self.estimate_available,
            "translation_error_mm": self.translation_error_mm,
            "rotation_error_deg": self.rotation_error_deg,
            "inlier_reprojection_rmse_px": self.inlier_reprojection_rmse_px,
            "physical_accuracy_claim": False,
        }


@dataclass(frozen=True, slots=True)
class B0477HeldOutStationResidual:
    """Independent K0/P0 reprojection check for a T0--T3-only pose fit."""

    station_name: str
    tag_id: int
    corner_rmse_px: float
    maximum_corner_error_px: float

    def __post_init__(self) -> None:
        if isinstance(self.tag_id, bool) or not isinstance(self.tag_id, int):
            raise B0477StaticVisionError(
                "held-out station tag_id must be an integer"
            )
        expected_name = _HELD_OUT_STATION_NAMES.get(self.tag_id)
        if expected_name is None or self.station_name != expected_name:
            raise B0477StaticVisionError(
                "held-out station must identify K0/tag 4 or P0/tag 5"
            )
        rmse = _finite_nonnegative(self.corner_rmse_px, "held-out corner RMSE")
        maximum = _finite_nonnegative(
            self.maximum_corner_error_px,
            "held-out maximum corner error",
        )
        if maximum < rmse:
            raise B0477StaticVisionError(
                "held-out maximum corner error cannot be smaller than RMSE"
            )
        object.__setattr__(self, "corner_rmse_px", rmse)
        object.__setattr__(self, "maximum_corner_error_px", maximum)

    @property
    def passed(self) -> bool:
        """Apply synthetic rehearsal limits, never physical tolerances."""

        return (
            self.corner_rmse_px <= B0477_MAX_HELD_OUT_STATION_RMSE_PX
            and self.maximum_corner_error_px
            <= B0477_MAX_HELD_OUT_STATION_CORNER_ERROR_PX
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "station_name": self.station_name,
            "tag_id": self.tag_id,
            "used_for_pose_fit": False,
            "corner_rmse_px": self.corner_rmse_px,
            "maximum_corner_error_px": self.maximum_corner_error_px,
            "synthetic_limits": {
                "maximum_corner_rmse_px": (
                    B0477_MAX_HELD_OUT_STATION_RMSE_PX
                ),
                "maximum_corner_error_px": (
                    B0477_MAX_HELD_OUT_STATION_CORNER_ERROR_PX
                ),
                "physical_acceptance_limit": False,
            },
            "passed": self.passed,
            "physical_accuracy_claim": False,
        }


@dataclass(frozen=True, slots=True)
class B0477RehearsalAuthority:
    """Explicit fail-closed authority carried by every rehearsal report."""

    simulation_only: bool = True
    physical_camera_accessed: bool = False
    hardware_presence_authority: bool = False
    live_capture_authority: bool = False
    physical_calibration_authority: bool = False
    physical_static_extrinsic_authority: bool = False
    robot_motion_authority: bool = False
    contact_authority: bool = False
    hardware_commands_generated: int = 0

    def __post_init__(self) -> None:
        if self.simulation_only is not True:
            raise B0477StaticVisionError("rehearsal must remain simulation-only")
        flags = (
            self.physical_camera_accessed,
            self.hardware_presence_authority,
            self.live_capture_authority,
            self.physical_calibration_authority,
            self.physical_static_extrinsic_authority,
            self.robot_motion_authority,
            self.contact_authority,
        )
        if any(flag is not False for flag in flags):
            raise B0477StaticVisionError("rehearsal cannot grant physical authority")
        if self.hardware_commands_generated != 0:
            raise B0477StaticVisionError("rehearsal cannot generate hardware commands")

    def to_dict(self) -> dict[str, object]:
        return {
            "simulation_only": self.simulation_only,
            "physical_camera_accessed": self.physical_camera_accessed,
            "hardware_presence_authority": self.hardware_presence_authority,
            "live_capture_authority": self.live_capture_authority,
            "physical_calibration_authority": self.physical_calibration_authority,
            "physical_static_extrinsic_authority": (
                self.physical_static_extrinsic_authority
            ),
            "robot_motion_authority": self.robot_motion_authority,
            "contact_authority": self.contact_authority,
            "hardware_commands_generated": self.hardware_commands_generated,
        }


@dataclass(frozen=True, slots=True)
class B0477StaticVisionReport:
    """Immutable, canonical-hashable evidence from one pixel rehearsal."""

    sequence: int
    mode: B0477StaticVisionMode
    status: str
    detail_code: str
    profile_id: str
    support_design_id: str
    source_hashes: tuple[tuple[str, str], ...]
    nominal_projection: B0477NominalProjection
    visible_tag_ids: tuple[int, ...]
    detected_tag_ids: tuple[int, ...]
    inlier_tag_ids: tuple[int, ...]
    pixel_statistics: B0477PixelStatistics
    pose_comparison: B0477PoseComparison
    held_out_station_residuals: tuple[B0477HeldOutStationResidual, ...] = ()
    authority: B0477RehearsalAuthority = B0477RehearsalAuthority()
    schema: str = B0477_STATIC_VISION_SCHEMA

    def __post_init__(self) -> None:
        _bounded_sequence(self.sequence)
        if not isinstance(self.mode, B0477StaticVisionMode):
            raise TypeError("mode must be B0477StaticVisionMode")
        if self.schema != B0477_STATIC_VISION_SCHEMA:
            raise B0477StaticVisionError("unsupported B0477 report schema")
        if self.status not in {"PASS", "REJECTED"}:
            raise B0477StaticVisionError("status must be PASS or REJECTED")
        if not self.detail_code or len(self.detail_code) > 128:
            raise B0477StaticVisionError("detail_code must be bounded non-empty text")
        sources = tuple(self.source_hashes)
        if not sources or len({key for key, _ in sources}) != len(sources):
            raise B0477StaticVisionError("source hashes must be non-empty and unique")
        if sources != tuple(sorted(sources)):
            raise B0477StaticVisionError("source hashes must use canonical key order")
        for key, digest in sources:
            if not key or len(key) > 256:
                raise B0477StaticVisionError("source hash key is invalid")
            _digest(digest, f"source hash {key}")
        for label, ids in (
            ("visible", self.visible_tag_ids),
            ("detected", self.detected_tag_ids),
            ("inlier", self.inlier_tag_ids),
        ):
            if ids != tuple(sorted(set(ids))) or any(
                isinstance(tag_id, bool)
                or not isinstance(tag_id, int)
                or tag_id not in _EXPECTED_TAG_IDS
                for tag_id in ids
            ):
                raise B0477StaticVisionError(f"{label} tag IDs are invalid")
        if not set(self.detected_tag_ids).issubset(self.visible_tag_ids):
            raise B0477StaticVisionError("detected tags must be visible in this fixture")
        if not set(self.inlier_tag_ids).issubset(self.detected_tag_ids):
            raise B0477StaticVisionError("pose inliers must be detected tags")
        if any(tag_id not in B0477_POSE_FIT_TAG_IDS for tag_id in self.inlier_tag_ids):
            raise B0477StaticVisionError(
                "K0/P0 held-out station tags cannot be pose inliers"
            )
        residuals = tuple(self.held_out_station_residuals)
        if any(
            not isinstance(item, B0477HeldOutStationResidual)
            for item in residuals
        ):
            raise TypeError(
                "held_out_station_residuals must contain "
                "B0477HeldOutStationResidual values"
            )
        residual_ids = tuple(item.tag_id for item in residuals)
        if residual_ids != tuple(sorted(set(residual_ids))):
            raise B0477StaticVisionError(
                "held-out station residuals must be unique and tag ordered"
            )
        expected_residual_ids = (
            tuple(
                tag_id
                for tag_id in B0477_HELD_OUT_STATION_TAG_IDS
                if tag_id in self.detected_tag_ids
            )
            if self.pose_comparison.estimate_available
            else ()
        )
        if residual_ids != expected_residual_ids:
            raise B0477StaticVisionError(
                "held-out station residuals must cover every detected K0/P0 tag "
                "only after a pose is available"
            )
        object.__setattr__(self, "held_out_station_residuals", residuals)
        expected_visible = (
            _EXPECTED_TAG_IDS
            if self.mode is B0477StaticVisionMode.NORMAL
            else B0477_HELD_OUT_STATION_TAG_IDS
        )
        if self.visible_tag_ids != expected_visible:
            raise B0477StaticVisionError(
                "visible tags differ from the selected synthetic mode"
            )
        if self.mode is B0477StaticVisionMode.NORMAL:
            expected_status = "PASS" if self.passes_nominal_policy else "REJECTED"
            expected_detail = (
                "B0477_STATIC_PIXEL_POSE_ACCEPTED"
                if self.passes_nominal_policy
                else "B0477_STATIC_PIXEL_POSE_QUALITY_REJECTED"
            )
        else:
            expected_status = "REJECTED"
            expected_detail = (
                "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
                if not self.pose_comparison.estimate_available
                else "B0477_STATIC_TAG_LOSS_INJECTION_NOT_REJECTED"
            )
        if self.status != expected_status or self.detail_code != expected_detail:
            raise B0477StaticVisionError(
                "status/detail do not follow the complete synthetic acceptance "
                "policy, including passing K0/P0 checks"
            )

    @property
    def held_out_station_checks_passed(self) -> bool:
        return (
            tuple(item.tag_id for item in self.held_out_station_residuals)
            == B0477_HELD_OUT_STATION_TAG_IDS
            and all(item.passed for item in self.held_out_station_residuals)
        )

    @property
    def passes_nominal_policy(self) -> bool:
        """Evaluate every numerical and structural synthetic PASS condition."""

        comparison = self.pose_comparison
        return (
            self.mode is B0477StaticVisionMode.NORMAL
            and self.visible_tag_ids == _EXPECTED_TAG_IDS
            and self.detected_tag_ids == _EXPECTED_TAG_IDS
            and self.inlier_tag_ids == B0477_POSE_FIT_TAG_IDS
            and comparison.estimate_available
            and comparison.translation_error_mm is not None
            and comparison.translation_error_mm
            <= B0477_MAX_TRANSLATION_ERROR_MM
            and comparison.rotation_error_deg is not None
            and comparison.rotation_error_deg <= B0477_MAX_ROTATION_ERROR_DEG
            and comparison.inlier_reprojection_rmse_px is not None
            and comparison.inlier_reprojection_rmse_px
            <= B0477_MAX_INLIER_REPROJECTION_RMSE_PX
            and self.held_out_station_checks_passed
        )

    @property
    def content_sha256(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "sequence": self.sequence,
            "mode": self.mode.value,
            "status": self.status,
            "detail_code": self.detail_code,
            "camera": {
                "profile_id": self.profile_id,
                "support_design_id": self.support_design_id,
                "identity": "Arducam B0477 / Sony IMX283 / included nominal 16 mm C-mount lens",
                "mounting_architecture": "STATIC_OVERHEAD_EYE_TO_HAND",
                "received_hardware_verified": False,
            },
            "source_hashes": dict(self.source_hashes),
            "nominal_projection": self.nominal_projection.to_dict(),
            "tag_ids": {
                "visible_in_synthetic_scene": list(self.visible_tag_ids),
                "detected_from_jpeg_pixels": list(self.detected_tag_ids),
                "planar_pose_inliers": list(self.inlier_tag_ids),
            },
            "board_registration": {
                "fit_policy": "T0_T1_T2_T3_ONLY",
                "pose_fit_tag_ids": list(B0477_POSE_FIT_TAG_IDS),
                "pose_fit_inlier_tag_ids": list(self.inlier_tag_ids),
                "held_out_station_policy": "K0_P0_EXCLUDED_FROM_FIT",
                "held_out_station_tag_ids": list(
                    B0477_HELD_OUT_STATION_TAG_IDS
                ),
                "held_out_station_tags_used_for_pose_fit": False,
                "held_out_station_residuals": [
                    item.to_dict() for item in self.held_out_station_residuals
                ],
                "held_out_station_checks_passed": (
                    self.held_out_station_checks_passed
                ),
                "physical_acceptance_claim": False,
            },
            "pixel_statistics": self.pixel_statistics.to_dict(),
            "pose_comparison": self.pose_comparison.to_dict(),
            "processing_boundary": {
                "pipeline": (
                    "SYNTHETIC_DISTORTED_JPEG_TO_PIXEL_DETECTOR_TO_"
                    "BOUND_RECTIFIER_TO_PLANAR_POSE"
                ),
                "capture_pixel_space": self.nominal_projection.capture_pixel_space,
                "pose_estimator_pixel_space": (
                    self.nominal_projection.estimator_pixel_space
                ),
                "optical_contract_sha256": (
                    self.nominal_projection.optical_contract_sha256
                ),
                "undistortion_map_sha256": (
                    self.nominal_projection.undistortion_map_sha256
                ),
                "distortion_exercised": True,
                "distortion_is_measured_b0477_calibration": False,
                "detector_received_scene_truth": False,
                "detector_received_expected_corners": False,
                "opencv_or_cv2_required": False,
            },
            "authority": self.authority.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class B0477StaticVisionCapture:
    """Exact synthetic pixels and perception records behind one report.

    The long-standing report API intentionally contains no frame bytes.  This
    companion value exposes those bytes only to evidence recorders while
    retaining the already validated detector, rectifier, and pose objects.
    It is still a synthetic rehearsal value: construction cannot discover a
    camera, send a controller message, or grant any physical authority.
    """

    report: B0477StaticVisionReport
    jpeg_bytes: bytes
    raw_detection_batch: AprilTagDetectionBatch
    rectified_detection_batch: AprilTagDetectionBatch
    optical_contract: B0477SyntheticOpticalContract
    pose_observation: AprilTagPoseObservation | None
    schema: str = B0477_STATIC_VISION_CAPTURE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_STATIC_VISION_CAPTURE_SCHEMA:
            raise B0477StaticVisionError("unsupported B0477 capture schema")
        if not isinstance(self.report, B0477StaticVisionReport):
            raise TypeError("report must be B0477StaticVisionReport")
        if (
            not isinstance(self.jpeg_bytes, bytes)
            or not self.jpeg_bytes
            or len(self.jpeg_bytes) > MAX_SYNTHETIC_JPEG_BYTES
        ):
            raise B0477StaticVisionError("capture JPEG must be non-empty bytes")
        if not isinstance(self.raw_detection_batch, AprilTagDetectionBatch):
            raise TypeError("raw_detection_batch must be AprilTagDetectionBatch")
        if not isinstance(self.rectified_detection_batch, AprilTagDetectionBatch):
            raise TypeError(
                "rectified_detection_batch must be AprilTagDetectionBatch"
            )
        if not isinstance(self.optical_contract, B0477SyntheticOpticalContract):
            raise TypeError("optical_contract must be B0477SyntheticOpticalContract")
        if self.pose_observation is not None and not isinstance(
            self.pose_observation, AprilTagPoseObservation
        ):
            raise TypeError(
                "pose_observation must be AprilTagPoseObservation or None"
            )

        frame = self.raw_detection_batch.frame
        if len(self.jpeg_bytes) != self.report.pixel_statistics.jpeg_byte_count:
            raise B0477StaticVisionError(
                "capture JPEG byte count differs from the report"
            )
        jpeg_sha256 = hashlib.sha256(self.jpeg_bytes).hexdigest()
        if (
            frame.jpeg_sha256 != jpeg_sha256
            or self.report.pixel_statistics.jpeg_sha256 != jpeg_sha256
        ):
            raise B0477StaticVisionError(
                "capture JPEG differs from the detector/report byte binding"
            )
        if frame.source_sequence != self.report.sequence:
            raise B0477StaticVisionError(
                "capture frame sequence differs from the report sequence"
            )
        if self.rectified_detection_batch.frame != frame:
            raise B0477StaticVisionError(
                "raw and rectified batches must bind the same encoded frame"
            )
        if tuple(
            sorted(tag.tag_id for tag in self.rectified_detection_batch.accepted_tags)
        ) != self.report.detected_tag_ids:
            raise B0477StaticVisionError(
                "rectified detections differ from the report tag IDs"
            )

        source_hashes = dict(self.report.source_hashes)
        required = {
            "raw_detected_batch": self.raw_detection_batch.content_hash,
            "rectified_detection_batch": (
                self.rectified_detection_batch.content_hash
            ),
            "optical_contract": self.optical_contract.content_sha256,
        }
        for name, expected in required.items():
            if source_hashes.get(name) != expected:
                raise B0477StaticVisionError(
                    f"capture {name} differs from report provenance"
                )
        if (
            self.report.nominal_projection.optical_contract_sha256
            != self.optical_contract.content_sha256
            or self.report.nominal_projection.undistortion_map_sha256
            != self.optical_contract.undistortion_map_sha256
        ):
            raise B0477StaticVisionError(
                "capture optical contract differs from nominal projection"
            )

        has_pose = self.pose_observation is not None
        if has_pose != self.report.pose_comparison.estimate_available:
            raise B0477StaticVisionError(
                "capture pose availability differs from the report"
            )
        if self.pose_observation is None:
            if "pose_observation" in source_hashes:
                raise B0477StaticVisionError(
                    "capture has no pose but report provenance names one"
                )
        else:
            if source_hashes.get("pose_observation") != self.pose_observation.content_hash:
                raise B0477StaticVisionError(
                    "capture pose differs from report provenance"
                )
            if tuple(
                sorted(tag.tag_id for tag in self.pose_observation.used_tags)
            ) != self.report.inlier_tag_ids:
                raise B0477StaticVisionError(
                    "capture pose inliers differ from the report"
                )
            if self.pose_observation.detection_batch != _pose_fit_batch(
                self.rectified_detection_batch
            ):
                raise B0477StaticVisionError(
                    "capture pose input differs from the exact T0-T3 fit batch"
                )
            if (
                self.pose_observation.pose.parent_frame
                != self.report.nominal_projection.optical_frame
            ):
                raise B0477StaticVisionError(
                    "capture pose parent frame differs from the optical frame"
                )
            expected_comparison = _pose_comparison(
                self.pose_observation,
                Transform(
                    to_frame=self.report.nominal_projection.optical_frame,
                    from_frame=self.pose_observation.pose.child_frame,
                    matrix=(
                        self.report.nominal_projection.camera_T_board_row_major
                    ),
                ),
            )
            if self.report.pose_comparison != expected_comparison:
                raise B0477StaticVisionError(
                    "capture pose comparison was not derived from its observation"
                )

    @property
    def jpeg_sha256(self) -> str:
        return hashlib.sha256(self.jpeg_bytes).hexdigest()

    @property
    def content_sha256(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return byte hashes and provenance, never the multi-megabyte bytes."""

        return {
            "schema": self.schema,
            "report_sha256": self.report.content_sha256,
            "jpeg": {
                "sha256": self.jpeg_sha256,
                "bytes": len(self.jpeg_bytes),
                "encoding": "JPEG_GRAYSCALE",
            },
            "raw_detection_batch_sha256": self.raw_detection_batch.content_hash,
            "rectified_detection_batch_sha256": (
                self.rectified_detection_batch.content_hash
            ),
            "pose_observation_sha256": (
                self.pose_observation.content_hash
                if self.pose_observation is not None
                else None
            ),
            "optical_contract_sha256": self.optical_contract.content_sha256,
            "undistortion_map_sha256": (
                self.optical_contract.undistortion_map_sha256
            ),
            "authority": self.report.authority.to_dict(),
        }


def _validate_profile_support_link(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
) -> None:
    """Prove both freshly validated inputs describe the selected catalog unit."""

    expected_profile_hash = support.source_sha256.get("purchased_camera_profile")
    if expected_profile_hash is None:
        raise B0477StaticVisionError(
            "static support does not lock the purchased_camera_profile source"
        )
    if expected_profile_hash != profile.source_file_sha256:
        raise B0477StaticVisionError(
            "static support purchased-camera source lock differs from profile bytes"
        )
    if (profile.manufacturer, profile.model, profile.sensor) != (
        "Arducam",
        "B0477",
        "Sony IMX283",
    ):
        raise B0477StaticVisionError("camera profile is not the exact selected B0477")
    if (support.camera_model, support.sensor) != ("Arducam B0477", "Sony IMX283"):
        raise B0477StaticVisionError("support design camera identity differs from B0477")
    native_mode = profile.published_mode("USB_3_2_GEN_1", 5472, 3648)
    if native_mode is None or support.native_mode != (
        native_mode.width_px,
        native_mode.height_px,
        native_mode.maximum_fps,
        native_mode.pixel_format,
    ):
        raise B0477StaticVisionError("support and profile native-mode claims differ")
    if profile.record_state != "PURCHASED_PENDING_RECEIPT":
        raise B0477StaticVisionError("purchase-time profile state changed unexpectedly")
    if profile.live_ready or any(profile.authority.values()):
        raise B0477StaticVisionError("purchase profile unexpectedly grants live authority")


def _load_inputs(
    workspace_root: Path,
    camera_profile_path: Path | None,
    support_design_path: Path | None,
) -> tuple[Path, PurchasedCameraProfile, StaticCameraSupportDesign, NominalWorkcellScene]:
    if not isinstance(workspace_root, Path):
        raise TypeError("workspace_root must be pathlib.Path")
    root = workspace_root.resolve()
    if not root.is_dir():
        raise B0477StaticVisionError("workspace_root must be an existing directory")
    profile_path = _contained_path(
        root,
        camera_profile_path or _PROFILE_RELATIVE_PATH,
        "camera profile path",
    )
    support_path = _contained_path(
        root,
        support_design_path or _SUPPORT_RELATIVE_PATH,
        "support design path",
    )
    profile = load_camera_profile(profile_path)
    support = load_static_camera_support_design(root, support_path)
    _validate_profile_support_link(profile, support)

    rc03_root = (root / _RC03_RELATIVE_ROOT).resolve()
    try:
        rc03_root.relative_to(root)
    except ValueError as exc:  # pragma: no cover - constant is workspace-relative
        raise B0477StaticVisionError("RC03 root escapes workspace") from exc
    scene = load_rc03_nominal_scene(rc03_root)
    if tuple(sorted(tag.tag_id for tag in scene.fiducials)) != _EXPECTED_TAG_IDS:
        raise B0477StaticVisionError("RC03 scene must contain exactly tag36h11 IDs 0-5")
    if scene.source_hashes.get("config/workcell_layout.json") != support.source_sha256.get(
        "workcell_layout"
    ):
        raise B0477StaticVisionError("support and scene workcell-layout hashes differ")
    board_size = (
        scene.board.maximum.x - scene.board.minimum.x,
        scene.board.maximum.y - scene.board.minimum.y,
        scene.board.maximum.z - scene.board.minimum.z,
    )
    if board_size != support.board_size_mm:
        raise B0477StaticVisionError("support and RC03 board dimensions differ")
    board_center = (
        (scene.board.minimum.x + scene.board.maximum.x) / 2.0,
        (scene.board.minimum.y + scene.board.maximum.y) / 2.0,
    )
    if board_center != support.camera_axis_xy_mm:
        raise B0477StaticVisionError("support optical axis is not centered on RC03")
    return root, profile, support, scene


def _nominal_camera(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    scene: NominalWorkcellScene,
) -> tuple[
    B0477SyntheticOpticalContract,
    PinholeCameraModel,
    Transform,
    PinholeIntrinsics,
    B0477NominalProjection,
]:
    proxy = profile.simulation_proxy
    if not proxy.within_current_raster_limits:
        raise B0477StaticVisionError("B0477 simulation proxy exceeds resource limits")
    try:
        optical_contract = build_b0477_synthetic_optical_contract(profile, support)
    except B0477OpticalContractError as exc:
        raise B0477StaticVisionError(str(exc)) from exc
    axis_x, axis_y = support.camera_axis_xy_mm
    entrance_z = support.nominal_entrance_pupil_z_mm
    tag_plane_z = DEFAULT_SIMULATED_TAG_PLANE_Z_MM

    # camera_T_board uses the existing RC03 board convention (+Y rear, +Z up)
    # and the pinhole optical convention (+Y image-down, +Z toward the board).
    matrix = (
        1.0,
        0.0,
        0.0,
        -axis_x,
        0.0,
        -1.0,
        0.0,
        axis_y,
        0.0,
        0.0,
        -1.0,
        entrance_z,
        0.0,
        0.0,
        0.0,
        1.0,
    )
    camera = optical_contract.capture_camera()
    camera_T_board = Transform(B0477_OPTICAL_FRAME, scene.board_frame, matrix)
    intrinsics = optical_contract.estimator_intrinsics()
    distortion = optical_contract.distortion
    projection = B0477NominalProjection(
        optical_frame=B0477_OPTICAL_FRAME,
        resolution_px=(proxy.width_px, proxy.height_px),
        intrinsics_row_major=optical_contract.intrinsics_row_major,
        camera_T_board_row_major=matrix,
        camera_axis_xy_board_mm=support.camera_axis_xy_mm,
        entrance_pupil_z_board_mm=entrance_z,
        tag_plane_z_board_mm=tag_plane_z,
        nominal_working_distance_mm=entrance_z - tag_plane_z,
        published_fov_deg=(proxy.horizontal_fov_deg, proxy.vertical_fov_deg),
        effective_rectilinear_fov_deg=(
            optical_contract.effective_horizontal_fov_deg,
            optical_contract.effective_vertical_fov_deg,
        ),
        distortion_coefficients=(
            distortion.k1,
            distortion.k2,
            distortion.p1,
            distortion.p2,
            distortion.k3,
        ),
        intrinsics_source_sha256=optical_contract.intrinsics_source_sha256,
        undistortion_map_sha256=optical_contract.undistortion_map_sha256,
        optical_contract_sha256=optical_contract.content_sha256,
    )
    return optical_contract, camera, camera_T_board, intrinsics, projection


def _tag_map(
    scene: NominalWorkcellScene,
    *,
    tag_ids: tuple[int, ...],
    map_id: str,
) -> PlanarBoardTagMap:
    scene_tags_by_id = {tag.tag_id: tag for tag in scene.fiducials}
    if set(scene_tags_by_id) != set(_EXPECTED_TAG_IDS):
        raise B0477StaticVisionError("RC03 scene tag namespace changed unexpectedly")
    tags = tuple(
        PlanarBoardTag(
            tag=TagReference(tag.family, tag.tag_id),
            corners_board_mm=tag.corners(),
        )
        for tag_id in tag_ids
        for tag in (scene_tags_by_id[tag_id],)
    )
    if tuple(tag.tag.tag_id for tag in tags) != tag_ids:
        raise B0477StaticVisionError(
            f"tag map {map_id!r} does not contain its exact required tag IDs"
        )
    return PlanarBoardTagMap(
        map_id=map_id,
        board_frame=scene.board_frame,
        tag_plane_z_board_mm=DEFAULT_SIMULATED_TAG_PLANE_Z_MM,
        tags=tags,
        source_sha256=scene.source_hashes["fiducials/apriltag_map.json"],
    )


def _pose_fit_batch(batch: AprilTagDetectionBatch) -> AprilTagDetectionBatch:
    """Remove K0/P0 before pose estimation, retaining the exact frame binding."""

    return AprilTagDetectionBatch(
        frame=batch.frame,
        detector=batch.detector,
        detections=tuple(
            detection
            for detection in batch.detections
            if detection.tag.tag_id in B0477_POSE_FIT_TAG_IDS
        ),
    )


def _held_out_station_residuals(
    batch: AprilTagDetectionBatch,
    observation: AprilTagPoseObservation | None,
    intrinsics: PinholeIntrinsics,
    held_out_map: PlanarBoardTagMap,
) -> tuple[B0477HeldOutStationResidual, ...]:
    """Score detected K0/P0 pixels without exposing them to the pose solver."""

    if observation is None:
        return ()
    detections = {
        detection.tag.tag_id: detection
        for detection in batch.detections
        if detection.detector_accepted
        and detection.tag.tag_id in B0477_HELD_OUT_STATION_TAG_IDS
    }
    residuals: list[B0477HeldOutStationResidual] = []
    for tag_id in B0477_HELD_OUT_STATION_TAG_IDS:
        detection = detections.get(tag_id)
        if detection is None:
            continue
        definition = held_out_map.definition(detection.tag)
        if definition is None:
            raise B0477StaticVisionError(
                f"held-out station tag {tag_id} is absent from its map"
            )
        corner_errors: list[float] = []
        for board_corner, detected_corner in zip(
            definition.corners_board_mm,
            detection.corners_px,
        ):
            camera_corner = observation.pose.transform_point(board_corner)
            if not math.isfinite(camera_corner.z) or camera_corner.z <= 0.0:
                raise B0477StaticVisionError(
                    "held-out station projected behind the synthetic camera"
                )
            normalized_x = camera_corner.x / camera_corner.z
            normalized_y = camera_corner.y / camera_corner.z
            projected_x = (
                intrinsics.fx_px * normalized_x
                + intrinsics.skew_px * normalized_y
                + intrinsics.cx_px
            )
            projected_y = intrinsics.fy_px * normalized_y + intrinsics.cy_px
            error = math.hypot(
                projected_x - detected_corner.x_px,
                projected_y - detected_corner.y_px,
            )
            if not math.isfinite(error):
                raise B0477StaticVisionError(
                    "held-out station reprojection produced a nonfinite error"
                )
            corner_errors.append(error)
        residuals.append(
            B0477HeldOutStationResidual(
                station_name=_HELD_OUT_STATION_NAMES[tag_id],
                tag_id=tag_id,
                corner_rmse_px=math.sqrt(
                    sum(value * value for value in corner_errors)
                    / len(corner_errors)
                ),
                maximum_corner_error_px=max(corner_errors),
            )
        )
    return tuple(residuals)


def _decoded_pixel_statistics(
    batch: AprilTagDetectionBatch,
    jpeg_bytes: bytes,
    jpeg_sha256: str,
    width_px: int,
    height_px: int,
) -> B0477PixelStatistics:
    """Summarize real decoded JPEG pixels without exposing them to the detector."""

    try:
        from PIL import Image
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
        raise B0477StaticVisionError("B0477 pixel statistics require Pillow") from exc
    try:
        image = Image.open(BytesIO(jpeg_bytes)).convert("L")
        image.load()
    except Exception as exc:
        raise B0477StaticVisionError("rendered B0477 JPEG could not be decoded") from exc
    if image.size != (width_px, height_px):
        raise B0477StaticVisionError("decoded JPEG dimensions differ from frame metadata")
    histogram = image.histogram()
    pixel_count = width_px * height_px
    populated = tuple(index for index, count in enumerate(histogram) if count)
    if not populated or sum(histogram) != pixel_count:
        raise B0477StaticVisionError("decoded JPEG histogram is incoherent")
    mean_gray = sum(index * count for index, count in enumerate(histogram)) / pixel_count
    dark_fraction = sum(histogram[:128]) / pixel_count

    edges: list[float] = []
    for detection in batch.detections:
        if not detection.detector_accepted:
            continue
        corners = detection.corners_px
        edges.extend(
            math.hypot(
                corners[(index + 1) % 4].x_px - corners[index].x_px,
                corners[(index + 1) % 4].y_px - corners[index].y_px,
            )
            for index in range(4)
        )
    return B0477PixelStatistics(
        width_px=width_px,
        height_px=height_px,
        pixel_count=pixel_count,
        jpeg_byte_count=len(jpeg_bytes),
        jpeg_sha256=jpeg_sha256,
        minimum_gray=populated[0],
        maximum_gray=populated[-1],
        mean_gray=mean_gray,
        dark_fraction_below_128=dark_fraction,
        accepted_tag_edge_min_px=min(edges) if edges else None,
        accepted_tag_edge_mean_px=(sum(edges) / len(edges)) if edges else None,
        accepted_tag_edge_max_px=max(edges) if edges else None,
    )


def _pose_comparison(
    observation: AprilTagPoseObservation | None,
    nominal_camera_T_board: Transform,
) -> B0477PoseComparison:
    if observation is None:
        return B0477PoseComparison(False, None, None, None)
    expected = nominal_camera_T_board.matrix
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
    trace = sum(
        left * right
        for left, right in zip(estimated.rotation.matrix, expected_rotation)
    )
    cosine = min(1.0, max(-1.0, (trace - 1.0) / 2.0))
    return B0477PoseComparison(
        estimate_available=True,
        translation_error_mm=translation_error,
        rotation_error_deg=math.degrees(math.acos(cosine)),
        inlier_reprojection_rmse_px=observation.inlier_rmse_px,
    )


def _source_hashes(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    scene: NominalWorkcellScene,
    optical_contract: B0477SyntheticOpticalContract,
    renderer_config_sha256: str,
    renderer_source_bundle_sha256: str,
    renderer_definition_sha256: str,
    detector: AprilTag36h11PixelDetector,
    intrinsics: PinholeIntrinsics,
    raw_detected_batch: AprilTagDetectionBatch,
    detected_batch: AprilTagDetectionBatch,
    fit_batch: AprilTagDetectionBatch,
    fit_tag_map: PlanarBoardTagMap,
    held_out_tag_map: PlanarBoardTagMap,
    observation: AprilTagPoseObservation | None,
) -> tuple[tuple[str, str], ...]:
    values: dict[str, str] = {
        "camera_profile_canonical": profile.canonical_sha256,
        "camera_profile_file": profile.source_file_sha256,
        "support_design": support.content_sha256,
        "renderer_config": renderer_config_sha256,
        "renderer_source_bundle": renderer_source_bundle_sha256,
        "renderer_definition": renderer_definition_sha256,
        "detector_configuration": detector.detector_identity.configuration_sha256,
        "detector_implementation": detector.detector_identity.implementation_sha256,
        "optical_contract": optical_contract.content_sha256,
        "synthetic_undistortion_map": (
            optical_contract.undistortion_map_sha256
        ),
        "rectifier_configuration": detected_batch.detector.configuration_sha256,
        "rectifier_implementation": (
            optical_contract.rectifier_implementation_sha256
        ),
        "raw_detected_batch": raw_detected_batch.content_hash,
        "rectified_detection_batch": detected_batch.content_hash,
        "detected_batch": detected_batch.content_hash,
        "fit_detection_batch": fit_batch.content_hash,
        "nominal_intrinsics": intrinsics.content_hash,
        "nominal_tag_map": fit_tag_map.content_hash,
        "nominal_fit_tag_map": fit_tag_map.content_hash,
        "nominal_held_out_station_map": held_out_tag_map.content_hash,
    }
    values.update(
        {f"support_source:{key}": value for key, value in support.source_sha256.items()}
    )
    values.update({f"scene_source:{key}": value for key, value in scene.source_hashes.items()})
    if observation is not None:
        values["pose_observation"] = observation.content_hash
    return tuple(sorted(values.items()))


def run_b0477_static_vision_capture_rehearsal(
    workspace_root: Path,
    *,
    sequence: int = 0,
    mode: B0477StaticVisionMode = B0477StaticVisionMode.NORMAL,
    camera_profile_path: Path | None = None,
    support_design_path: Path | None = None,
) -> B0477StaticVisionCapture:
    """Run one bounded static-camera rehearsal without touching hardware.

    The only scenario inputs are a bounded sequence and an enum.  In
    ``TAG_LOSS``, IDs 0-3 are removed from the rendered pixels.  The detector
    is not told which tags remain.  Only those four world tags are ever passed
    to the pose estimator, so K0/P0 cannot rescue the fit and the empty fit
    batch is rejected naturally.
    """

    selected_sequence = _bounded_sequence(sequence)
    if not isinstance(mode, B0477StaticVisionMode):
        raise TypeError("mode must be B0477StaticVisionMode")
    root, profile, support, scene = _load_inputs(
        workspace_root, camera_profile_path, support_design_path
    )
    optical_contract, camera, camera_T_board, intrinsics, projection = _nominal_camera(
        profile, support, scene
    )
    occluded = _TAG_LOSS_IDS if mode is B0477StaticVisionMode.TAG_LOSS else ()
    render_config = SyntheticRasterConfig(
        renderer_id="RC03_B0477_STATIC_OVERHEAD_PROXY_V1",
        occluded_tag_ids=occluded,
        # One gray level of deterministic sequence-seeded noise makes two
        # synthetic captures distinct at the encoded-byte boundary.  This is
        # a freshness test signal only, not a model of physical sensor noise.
        noise_amplitude_gray=1,
    )
    renderer = SyntheticOverviewRasterRenderer(
        scene=scene,
        camera=camera,
        camera_T_board=camera_T_board,
        tag_asset_root=(root / _RC03_RELATIVE_ROOT / "fiducials"),
        config=render_config,
        codebook=DEFAULT_APRILTAG_36H11_CODEBOOK,
    )
    rendered = renderer.render(sequence=selected_sequence)
    detector = AprilTag36h11PixelDetector(
        AprilTagPixelDetectorConfiguration(
            host_clock="b0477_static_synthetic_host_monotonic",
            maximum_image_pixels=profile.simulation_proxy.pixel_detector_maximum_image_pixels,
        ),
        DEFAULT_APRILTAG_36H11_CODEBOOK,
    )
    frame = rendered.frame_packet
    try:
        raw_batch = detector.detect(frame)
        batch = optical_contract.rectify_detection_batch(raw_batch)
    except (AprilTagPixelDetectorError, B0477OpticalContractError) as exc:
        raise B0477StaticVisionError(
            "B0477 detector/rectifier could not produce a bounded batch: "
            f"{exc}"
        ) from exc
    detected_ids = tuple(sorted(tag.tag_id for tag in batch.accepted_tags))
    visible_ids = tuple(tag_id for tag_id in _EXPECTED_TAG_IDS if tag_id not in occluded)
    fit_batch = _pose_fit_batch(batch)
    fit_tag_map = _tag_map(
        scene,
        tag_ids=B0477_POSE_FIT_TAG_IDS,
        map_id="rc03.nominal_t0_t3_fit.for_b0477_static_rehearsal",
    )
    held_out_tag_map = _tag_map(
        scene,
        tag_ids=B0477_HELD_OUT_STATION_TAG_IDS,
        map_id="rc03.nominal_k0_p0_held_out.for_b0477_static_rehearsal",
    )
    estimator = PlanarAprilTagBoardPoseEstimator(
        PlanarPoseEstimatorConfig(
            maximum_tag_reprojection_rmse_px=2.0,
            minimum_inlier_tags=len(B0477_POSE_FIT_TAG_IDS),
        )
    )
    observation: AprilTagPoseObservation | None
    try:
        observation = estimator.estimate(fit_batch, intrinsics, fit_tag_map)
    except PlanarPoseEstimationError:
        observation = None
    inlier_ids = (
        tuple(sorted(tag.tag_id for tag in observation.used_tags))
        if observation is not None
        else ()
    )
    comparison = _pose_comparison(observation, camera_T_board)
    held_out_residuals = _held_out_station_residuals(
        batch,
        observation,
        intrinsics,
        held_out_tag_map,
    )
    held_out_checks_passed = (
        tuple(item.tag_id for item in held_out_residuals)
        == B0477_HELD_OUT_STATION_TAG_IDS
        and all(item.passed for item in held_out_residuals)
    )
    if mode is B0477StaticVisionMode.NORMAL:
        passed = (
            detected_ids == _EXPECTED_TAG_IDS
            and inlier_ids == B0477_POSE_FIT_TAG_IDS
            and observation is not None
            and held_out_checks_passed
            and comparison.translation_error_mm is not None
            and comparison.translation_error_mm <= B0477_MAX_TRANSLATION_ERROR_MM
            and comparison.rotation_error_deg is not None
            and comparison.rotation_error_deg <= B0477_MAX_ROTATION_ERROR_DEG
            and comparison.inlier_reprojection_rmse_px is not None
            and comparison.inlier_reprojection_rmse_px
            <= B0477_MAX_INLIER_REPROJECTION_RMSE_PX
        )
        status = "PASS" if passed else "REJECTED"
        detail = (
            "B0477_STATIC_PIXEL_POSE_ACCEPTED"
            if passed
            else "B0477_STATIC_PIXEL_POSE_QUALITY_REJECTED"
        )
    else:
        status = "REJECTED"
        detail = (
            "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
            if observation is None
            else "B0477_STATIC_TAG_LOSS_INJECTION_NOT_REJECTED"
        )
    statistics = _decoded_pixel_statistics(
        raw_batch,
        frame.jpeg_bytes,
        frame.sha256,
        frame.width_px,
        frame.height_px,
    )
    report = B0477StaticVisionReport(
        sequence=selected_sequence,
        mode=mode,
        status=status,
        detail_code=detail,
        profile_id=profile.profile_id,
        support_design_id=support.design_id,
        source_hashes=_source_hashes(
            profile,
            support,
            scene,
            optical_contract,
            rendered.renderer_config_sha256,
            rendered.source_bundle_sha256,
            rendered.renderer_definition_sha256,
            detector,
            intrinsics,
            raw_batch,
            batch,
            fit_batch,
            fit_tag_map,
            held_out_tag_map,
            observation,
        ),
        nominal_projection=projection,
        visible_tag_ids=visible_ids,
        detected_tag_ids=detected_ids,
        inlier_tag_ids=inlier_ids,
        pixel_statistics=statistics,
        pose_comparison=comparison,
        held_out_station_residuals=held_out_residuals,
    )
    return B0477StaticVisionCapture(
        report=report,
        jpeg_bytes=frame.jpeg_bytes,
        raw_detection_batch=raw_batch,
        rectified_detection_batch=batch,
        optical_contract=optical_contract,
        pose_observation=observation,
    )


def run_b0477_static_vision_rehearsal(
    workspace_root: Path,
    *,
    sequence: int = 0,
    mode: B0477StaticVisionMode = B0477StaticVisionMode.NORMAL,
    camera_profile_path: Path | None = None,
    support_design_path: Path | None = None,
) -> B0477StaticVisionReport:
    """Return the established byte-free report for one synthetic rehearsal."""

    return run_b0477_static_vision_capture_rehearsal(
        workspace_root,
        sequence=sequence,
        mode=mode,
        camera_profile_path=camera_profile_path,
        support_design_path=support_design_path,
    ).report


__all__ = [
    "B0477_OPTICAL_FRAME",
    "B0477_STATIC_VISION_SCHEMA",
    "B0477_STATIC_VISION_CAPTURE_SCHEMA",
    "B0477_HELD_OUT_STATION_TAG_IDS",
    "B0477_MAX_HELD_OUT_STATION_CORNER_ERROR_PX",
    "B0477_MAX_HELD_OUT_STATION_RMSE_PX",
    "B0477_MAX_INLIER_REPROJECTION_RMSE_PX",
    "B0477_MAX_ROTATION_ERROR_DEG",
    "B0477_MAX_TRANSLATION_ERROR_MM",
    "B0477_POSE_FIT_TAG_IDS",
    "MAX_B0477_REHEARSAL_SEQUENCE",
    "B0477HeldOutStationResidual",
    "B0477NominalProjection",
    "B0477PixelStatistics",
    "B0477PoseComparison",
    "B0477RehearsalAuthority",
    "B0477StaticVisionCapture",
    "B0477StaticVisionError",
    "B0477StaticVisionMode",
    "B0477StaticVisionReport",
    "run_b0477_static_vision_capture_rehearsal",
    "run_b0477_static_vision_rehearsal",
]
