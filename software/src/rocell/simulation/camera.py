"""Dependency-free pinhole projection and deterministic synthetic tag observations."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Protocol, runtime_checkable

from rocell.models.frames import FrameMismatchError, Point3Mm

from ._validation import finite, identifier, positive
from .scene import NominalWorkcellScene, PlanarFiducial


class ProjectionError(ValueError):
    """A 3-D point cannot be projected by the configured camera."""


@dataclass(frozen=True, slots=True)
class DistortionCoefficients:
    """OpenCV-compatible Brown-Conrady radial/tangential coefficients."""

    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    k3: float = 0.0

    def __post_init__(self) -> None:
        for name in ("k1", "k2", "p1", "p2", "k3"):
            object.__setattr__(self, name, finite(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class ImagePoint:
    u_px: float
    v_px: float
    depth_mm: float
    in_bounds: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "u_px", finite(self.u_px, "u_px"))
        object.__setattr__(self, "v_px", finite(self.v_px, "v_px"))
        object.__setattr__(self, "depth_mm", positive(self.depth_mm, "depth_mm"))
        if not isinstance(self.in_bounds, bool):
            raise TypeError("in_bounds must be bool")

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "u_px": self.u_px,
            "v_px": self.v_px,
            "depth_mm": self.depth_mm,
            "in_bounds": self.in_bounds,
        }


@runtime_checkable
class ProjectionModel(Protocol):
    @property
    def optical_frame(self) -> str:
        """Label of the camera optical frame."""

    def project(self, point: Point3Mm) -> ImagePoint:
        """Project a point expressed in ``optical_frame``."""


@runtime_checkable
class PointTransform(Protocol):
    @property
    def to_frame(self) -> str:
        """Output frame label."""

    @property
    def from_frame(self) -> str:
        """Input frame label."""

    def transform_point(self, point: Point3Mm) -> Point3Mm:
        """Map a labelled 3-D point from ``from_frame`` to ``to_frame``."""


@dataclass(frozen=True, slots=True)
class PinholeCameraModel:
    """Camera convention: +X right, +Y down, +Z forward, millimetre depth."""

    width_px: int
    height_px: int
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    optical_frame: str = "camera_optical"
    distortion: DistortionCoefficients = field(default_factory=DistortionCoefficients)
    minimum_depth_mm: float = 1e-6

    def __post_init__(self) -> None:
        for name in ("width_px", "height_px"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("fx_px", "fy_px"):
            object.__setattr__(self, name, positive(getattr(self, name), name))
        for name in ("cx_px", "cy_px"):
            object.__setattr__(self, name, finite(getattr(self, name), name))
        object.__setattr__(
            self, "optical_frame", identifier(self.optical_frame, "optical frame")
        )
        if not isinstance(self.distortion, DistortionCoefficients):
            raise TypeError("distortion must be DistortionCoefficients")
        object.__setattr__(
            self,
            "minimum_depth_mm",
            positive(self.minimum_depth_mm, "minimum_depth_mm"),
        )

    def project(self, point: Point3Mm) -> ImagePoint:
        if point.frame != self.optical_frame:
            raise FrameMismatchError(
                f"Projection point is in {point.frame}, expected {self.optical_frame}"
            )
        if point.z <= self.minimum_depth_mm:
            raise ProjectionError(
                f"Point depth {point.z:g} mm is not in front of the camera"
            )
        x = point.x / point.z
        y = point.y / point.z
        r2 = x * x + y * y
        coefficients = self.distortion
        radial = 1.0 + coefficients.k1 * r2 + coefficients.k2 * r2**2 + coefficients.k3 * r2**3
        distorted_x = (
            x * radial
            + 2.0 * coefficients.p1 * x * y
            + coefficients.p2 * (r2 + 2.0 * x * x)
        )
        distorted_y = (
            y * radial
            + coefficients.p1 * (r2 + 2.0 * y * y)
            + 2.0 * coefficients.p2 * x * y
        )
        u = self.fx_px * distorted_x + self.cx_px
        v = self.fy_px * distorted_y + self.cy_px
        if not math.isfinite(u) or not math.isfinite(v):
            raise ProjectionError("Projection produced a non-finite image point")
        return ImagePoint(
            u,
            v,
            point.z,
            0.0 <= u < float(self.width_px) and 0.0 <= v < float(self.height_px),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "model": "pinhole_brown_conrady",
            "optical_frame": self.optical_frame,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "intrinsics_px": {
                "fx": self.fx_px,
                "fy": self.fy_px,
                "cx": self.cx_px,
                "cy": self.cy_px,
            },
            "distortion": {
                "k1": self.distortion.k1,
                "k2": self.distortion.k2,
                "p1": self.distortion.p1,
                "p2": self.distortion.p2,
                "k3": self.distortion.k3,
            },
            "minimum_depth_mm": self.minimum_depth_mm,
            "calibration_state": "SYNTHETIC_SCENARIO_NOT_PHYSICAL_CALIBRATION",
        }


@dataclass(frozen=True, slots=True)
class FiducialObservation:
    name: str
    tag_id: int
    family: str
    visible: bool
    visibility_reason: str
    center_px: ImagePoint | None
    corners_px: tuple[ImagePoint, ...]
    coordinate_source: str
    synthetic_source: str = "PERFECT_PROJECTION_NO_RASTER_NO_NOISE_NO_OCCLUSION"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", identifier(self.name, "observation name"))
        object.__setattr__(self, "family", identifier(self.family, "observation family"))
        object.__setattr__(
            self, "visibility_reason", identifier(self.visibility_reason, "visibility reason")
        )
        object.__setattr__(
            self, "coordinate_source", identifier(self.coordinate_source, "coordinate source")
        )
        object.__setattr__(
            self, "synthetic_source", identifier(self.synthetic_source, "synthetic source")
        )
        object.__setattr__(self, "corners_px", tuple(self.corners_px))
        if self.visible and (self.center_px is None or len(self.corners_px) != 4):
            raise ValueError("A visible fiducial requires its center and four corners")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "tag_id": self.tag_id,
            "family": self.family,
            "visible": self.visible,
            "visibility_reason": self.visibility_reason,
            "center_px": self.center_px.to_dict() if self.center_px is not None else None,
            "corners_px": [corner.to_dict() for corner in self.corners_px],
            "coordinate_source": self.coordinate_source,
            "synthetic_source": self.synthetic_source,
            "physical_detection_evidence": False,
        }


@dataclass(frozen=True, slots=True)
class SyntheticFiducialObserver:
    """Project ideal planar tags through injected transform and camera models."""

    projector: ProjectionModel
    board_to_camera: PointTransform

    def __post_init__(self) -> None:
        if not isinstance(self.projector, ProjectionModel):
            raise TypeError("projector must implement ProjectionModel")
        if not isinstance(self.board_to_camera, PointTransform):
            raise TypeError("board_to_camera must implement PointTransform")
        if self.board_to_camera.to_frame != self.projector.optical_frame:
            raise FrameMismatchError("Transform output and camera optical frames disagree")

    def observe_tag(self, tag: PlanarFiducial) -> FiducialObservation:
        if tag.center.frame != self.board_to_camera.from_frame:
            raise FrameMismatchError("Tag and board-to-camera input frames disagree")
        points = (tag.center, *tag.corners())
        projected: list[ImagePoint] = []
        try:
            for point in points:
                camera_point = self.board_to_camera.transform_point(point)
                projected.append(self.projector.project(camera_point))
        except ProjectionError:
            return FiducialObservation(
                tag.name,
                tag.tag_id,
                tag.family,
                False,
                "BEHIND_OR_ON_CAMERA_PLANE",
                None,
                (),
                tag.coordinate_source,
            )
        center = projected[0]
        corners = tuple(projected[1:])
        visible = center.in_bounds and all(corner.in_bounds for corner in corners)
        return FiducialObservation(
            tag.name,
            tag.tag_id,
            tag.family,
            visible,
            "VISIBLE" if visible else "CENTER_OR_CORNER_OUTSIDE_IMAGE",
            center,
            corners,
            tag.coordinate_source,
        )

    def observe_scene(self, scene: NominalWorkcellScene) -> tuple[FiducialObservation, ...]:
        if scene.board_frame != self.board_to_camera.from_frame:
            raise FrameMismatchError("Scene and board-to-camera input frames disagree")
        return tuple(
            self.observe_tag(tag)
            for tag in sorted(scene.fiducials, key=lambda item: (item.tag_id, item.name))
        )
