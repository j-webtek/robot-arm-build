"""Canonical synthetic optical contract for the Phase-1 B0477 camera.

The purchased camera's published 49 degree horizontal and 38 degree vertical
field-of-view claims cannot both describe its native 3:2 image as a centered
rectilinear camera with square pixels.  The static-support screening already
uses the conservative, aspect-consistent vertical angle derived from the
horizontal claim.  This module makes that same choice at the pixel renderer
and pose-estimator boundary.

The non-zero Brown-Conrady coefficients below are a deterministic *stress
fixture*.  They are not measurements of the delivered lens.  Rendering uses
those coefficients in capture pixels, while pose estimation receives corners
mapped back into the explicitly named undistorted pinhole pixel space.  Every
number and the inverse-map algorithm are content addressed.  Nothing in this
module opens a camera or grants physical calibration, motion, or contact
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re

from rocell.simulation.camera import DistortionCoefficients, PinholeCameraModel
from rocell.vision.camera_profile import PurchasedCameraProfile
from rocell.vision.detections import (
    AprilTagDetection,
    AprilTagDetectionBatch,
    DetectorIdentity,
    PixelCorner,
)
from rocell.vision.planar_pose_estimator import PinholeIntrinsics
from rocell.workcell.static_camera_support import StaticCameraSupportDesign


B0477_PHASE1_OPTICAL_FRAME = "C_overhead_optical"
B0477_CAPTURE_PIXEL_SPACE = "B0477_SYNTHETIC_DISTORTED_PROXY_PIXELS"
B0477_ESTIMATOR_PIXEL_SPACE = "UNDISTORTED_PINHOLE_PIXELS"
B0477_OPTICAL_CONTRACT_SCHEMA = "rocell.b0477_synthetic_optical_contract.v1"
B0477_UNDISTORTION_MAP_SCHEMA = "rocell.b0477_analytic_undistortion_map.v1"
B0477_PIXEL_SPACE_PROVENANCE_SCHEMA = (
    "rocell.b0477_detection_pixel_space_provenance.v1"
)

_CAPTURE_DETECTOR_ID = "rocell.apriltag36h11.pixel"
_CAPTURE_DETECTOR_VERSION = "1.0.0"
_RECTIFIED_DETECTOR_ID = "rocell.apriltag36h11_pixel_detector.b0477_rectified"
_RECTIFIED_DETECTOR_VERSION = "1"

_EXPECTED_RESOLUTION = (2736, 1824)
_EXPECTED_PUBLISHED_FOV_DEG = (49.0, 38.0)
_INVERSE_ALGORITHM = "FIXED_POINT_INVERSE_BROWN_CONRADY_V1"
_INVERSE_ITERATIONS = 16
_INVERSE_TOLERANCE_PX = 1e-7
_DIGEST = re.compile(r"^[0-9a-f]{64}$")

# A deliberately modest, non-zero synthetic lens warp.  These values exercise
# the capture-to-estimator map without masquerading as delivered-lens data.
_SYNTHETIC_STRESS_DISTORTION = DistortionCoefficients(
    k1=-0.04,
    k2=0.006,
    p1=0.0003,
    p2=-0.0002,
    k3=-0.0005,
)


class B0477OpticalContractError(ValueError):
    """The bounded synthetic B0477 pixel contract is incoherent."""


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
        raise B0477OpticalContractError(
            f"optical contract is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise B0477OpticalContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise B0477OpticalContractError(f"{label} must be finite")
    return result


def _distortion_dict(coefficients: DistortionCoefficients) -> dict[str, float]:
    return {
        "k1": coefficients.k1,
        "k2": coefficients.k2,
        "p1": coefficients.p1,
        "p2": coefficients.p2,
        "k3": coefficients.k3,
    }


def _validate_capture_detector_identity(detector: DetectorIdentity) -> None:
    """Require the one detector boundary that consumes capture-space pixels.

    ``AprilTagDetectionBatch`` predates explicit pixel-space records.  For the
    B0477 rehearsal, its detector identity is therefore the immutable marker
    at that legacy boundary: only the pixel detector that reads the encoded
    capture may enter the rectifier.  In particular, a rectifier output or an
    unclassified third-party detector cannot be silently treated as distorted
    capture coordinates.
    """

    if not isinstance(detector, DetectorIdentity):
        raise TypeError("detector must be DetectorIdentity")
    if (
        detector.detector_id != _CAPTURE_DETECTOR_ID
        or detector.version != _CAPTURE_DETECTOR_VERSION
    ):
        raise B0477OpticalContractError(
            "rectifier input must carry the exact B0477 capture-pixel "
            "detector identity; estimator-space or unclassified batches are "
            "not valid rectifier inputs"
        )


@dataclass(frozen=True, slots=True)
class B0477DetectionPixelSpaceProvenance:
    """Immutable source-to-destination marker for rectified detections.

    The marker is included in the rectifier configuration digest.  It makes
    the pixel-space transition independently inspectable while retaining an
    ``AprilTagDetectionBatch``-compatible result for existing pose code.
    """

    source_detector: DetectorIdentity
    optical_contract_sha256: str
    undistortion_map_sha256: str
    rectifier_implementation_sha256: str
    source_pixel_space: str = B0477_CAPTURE_PIXEL_SPACE
    destination_pixel_space: str = B0477_ESTIMATOR_PIXEL_SPACE
    physical_authority: str = "NONE"
    schema: str = B0477_PIXEL_SPACE_PROVENANCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_PIXEL_SPACE_PROVENANCE_SCHEMA:
            raise B0477OpticalContractError(
                "unsupported B0477 pixel-space provenance schema"
            )
        if self.source_pixel_space != B0477_CAPTURE_PIXEL_SPACE:
            raise B0477OpticalContractError(
                "B0477 rectifier source must be the exact capture pixel space"
            )
        if self.destination_pixel_space != B0477_ESTIMATOR_PIXEL_SPACE:
            raise B0477OpticalContractError(
                "B0477 rectifier destination must be the exact estimator pixel space"
            )
        if self.source_pixel_space == self.destination_pixel_space:
            raise B0477OpticalContractError(
                "B0477 rectifier pixel-space transition cannot be an identity"
            )
        _validate_capture_detector_identity(self.source_detector)
        for label, digest in (
            ("optical_contract_sha256", self.optical_contract_sha256),
            ("undistortion_map_sha256", self.undistortion_map_sha256),
            (
                "rectifier_implementation_sha256",
                self.rectifier_implementation_sha256,
            ),
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise B0477OpticalContractError(
                    f"{label} must be a lowercase SHA-256"
                )
        if self.physical_authority != "NONE":
            raise B0477OpticalContractError(
                "B0477 synthetic pixel-space provenance must have no physical authority"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_pixel_space": self.source_pixel_space,
            "destination_pixel_space": self.destination_pixel_space,
            "source_detector": self.source_detector.to_dict(),
            "optical_contract_sha256": self.optical_contract_sha256,
            "undistortion_map_sha256": self.undistortion_map_sha256,
            "rectifier_implementation_sha256": (
                self.rectifier_implementation_sha256
            ),
            "map_application": "ANALYTIC_PER_DETECTION_CORNER",
            "physical_authority": self.physical_authority,
        }

    @property
    def content_sha256(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class B0477RectifiedDetectionBatch(AprilTagDetectionBatch):
    """Detection batch whose coordinates are proven estimator-space pixels.

    This subtype intentionally remains usable anywhere an
    :class:`AprilTagDetectionBatch` is expected.  The additional frozen marker
    prevents this exact object from being passed through the B0477 rectifier a
    second time, even if a caller attempts to replace its detector identity.
    """

    pixel_space_provenance: B0477DetectionPixelSpaceProvenance | None = None

    def __post_init__(self) -> None:
        # Explicit super arguments avoid the zero-argument ``super`` edge case
        # in slotted dataclass inheritance on supported Python versions.
        super(B0477RectifiedDetectionBatch, self).__post_init__()
        provenance = self.pixel_space_provenance
        if not isinstance(provenance, B0477DetectionPixelSpaceProvenance):
            raise TypeError(
                "pixel_space_provenance must be B0477DetectionPixelSpaceProvenance"
            )
        expected_detector = DetectorIdentity(
            detector_id=_RECTIFIED_DETECTOR_ID,
            version=_RECTIFIED_DETECTOR_VERSION,
            configuration_sha256=provenance.content_sha256,
            implementation_sha256=provenance.rectifier_implementation_sha256,
        )
        if self.detector != expected_detector:
            raise B0477OpticalContractError(
                "rectified detector identity does not bind its pixel-space provenance"
            )

    @property
    def pixel_space(self) -> str:
        """Return the exact coordinates carried by this batch."""

        assert self.pixel_space_provenance is not None
        return self.pixel_space_provenance.destination_pixel_space


@dataclass(frozen=True, slots=True)
class B0477SyntheticOpticalContract:
    """One exact, zero-authority pixel contract used by the B0477 rehearsal."""

    optical_frame: str
    width_px: int
    height_px: int
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    published_horizontal_fov_deg: float
    published_vertical_fov_deg: float
    effective_horizontal_fov_deg: float
    effective_vertical_fov_deg: float
    distortion: DistortionCoefficients
    intrinsics_source_sha256: str
    capture_pixel_space: str = B0477_CAPTURE_PIXEL_SPACE
    estimator_pixel_space: str = B0477_ESTIMATOR_PIXEL_SPACE
    inverse_algorithm: str = _INVERSE_ALGORITHM
    inverse_iterations: int = _INVERSE_ITERATIONS
    inverse_tolerance_px: float = _INVERSE_TOLERANCE_PX
    schema: str = B0477_OPTICAL_CONTRACT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_OPTICAL_CONTRACT_SCHEMA:
            raise B0477OpticalContractError("unsupported B0477 optical contract schema")
        if self.optical_frame != B0477_PHASE1_OPTICAL_FRAME:
            raise B0477OpticalContractError(
                "B0477 optical frame must be canonical C_overhead_optical"
            )
        if (self.width_px, self.height_px) != _EXPECTED_RESOLUTION:
            raise B0477OpticalContractError("B0477 proxy resolution must be 2736x1824")
        if (
            self.capture_pixel_space != B0477_CAPTURE_PIXEL_SPACE
            or self.estimator_pixel_space != B0477_ESTIMATOR_PIXEL_SPACE
        ):
            raise B0477OpticalContractError("B0477 pixel-space names changed")
        if self.inverse_algorithm != _INVERSE_ALGORITHM:
            raise B0477OpticalContractError("B0477 inverse-map algorithm changed")
        if self.inverse_iterations != _INVERSE_ITERATIONS:
            raise B0477OpticalContractError("B0477 inverse-map iteration count changed")
        tolerance = _finite(self.inverse_tolerance_px, "inverse_tolerance_px")
        if tolerance != _INVERSE_TOLERANCE_PX:
            raise B0477OpticalContractError("B0477 inverse-map tolerance changed")
        if _DIGEST.fullmatch(self.intrinsics_source_sha256) is None:
            raise B0477OpticalContractError(
                "intrinsics_source_sha256 must be a lowercase SHA-256"
            )
        if not isinstance(self.distortion, DistortionCoefficients):
            raise TypeError("distortion must be DistortionCoefficients")
        if self.distortion != _SYNTHETIC_STRESS_DISTORTION:
            raise B0477OpticalContractError(
                "B0477 synthetic stress-distortion fixture changed"
            )

        numeric = {
            "fx_px": self.fx_px,
            "fy_px": self.fy_px,
            "cx_px": self.cx_px,
            "cy_px": self.cy_px,
            "published_horizontal_fov_deg": self.published_horizontal_fov_deg,
            "published_vertical_fov_deg": self.published_vertical_fov_deg,
            "effective_horizontal_fov_deg": self.effective_horizontal_fov_deg,
            "effective_vertical_fov_deg": self.effective_vertical_fov_deg,
        }
        normalized = {name: _finite(value, name) for name, value in numeric.items()}
        published = (
            normalized["published_horizontal_fov_deg"],
            normalized["published_vertical_fov_deg"],
        )
        if published != _EXPECTED_PUBLISHED_FOV_DEG:
            raise B0477OpticalContractError("published B0477 FOV claims changed")

        expected_fx = self.width_px / (
            2.0
            * math.tan(math.radians(self.published_horizontal_fov_deg / 2.0))
        )
        expected_vertical = math.degrees(
            2.0 * math.atan(self.height_px / (2.0 * expected_fx))
        )
        exact_expectations = (
            (self.fx_px, expected_fx, "fx_px"),
            (self.fy_px, expected_fx, "fy_px"),
            (self.cx_px, self.width_px / 2.0, "cx_px"),
            (self.cy_px, self.height_px / 2.0, "cy_px"),
            (
                self.effective_horizontal_fov_deg,
                self.published_horizontal_fov_deg,
                "effective_horizontal_fov_deg",
            ),
            (
                self.effective_vertical_fov_deg,
                expected_vertical,
                "effective_vertical_fov_deg",
            ),
        )
        for actual, expected, label in exact_expectations:
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
                raise B0477OpticalContractError(
                    f"{label} differs from the aspect-consistent projection"
                )

    @property
    def intrinsics_row_major(self) -> tuple[float, ...]:
        return (
            self.fx_px,
            0.0,
            self.cx_px,
            0.0,
            self.fy_px,
            self.cy_px,
            0.0,
            0.0,
            1.0,
        )

    def undistortion_map_dict(self) -> dict[str, object]:
        """Describe the analytic map without claiming a physical dense map."""

        return {
            "schema": B0477_UNDISTORTION_MAP_SCHEMA,
            "source_pixel_space": self.capture_pixel_space,
            "destination_pixel_space": self.estimator_pixel_space,
            "resolution_px": [self.width_px, self.height_px],
            "intrinsics_row_major": list(self.intrinsics_row_major),
            "distortion_model": "BROWN_CONRADY_5",
            "distortion_coefficients": _distortion_dict(self.distortion),
            "inverse_algorithm": self.inverse_algorithm,
            "iterations": self.inverse_iterations,
            "maximum_round_trip_error_px": self.inverse_tolerance_px,
            "map_representation": "ANALYTIC_NOT_DENSE_PIXEL_ARRAY",
            "evidence_state": "SYNTHETIC_STRESS_FIXTURE_NOT_PHYSICAL_CALIBRATION",
            "physical_calibration_authority": False,
        }

    @property
    def undistortion_map_sha256(self) -> str:
        return _canonical_hash(self.undistortion_map_dict())

    @property
    def rectifier_implementation_sha256(self) -> str:
        return _canonical_hash(
            {
                "implementation": _INVERSE_ALGORITHM,
                "normalization": "K_INVERSE_THEN_K_FORWARD",
                "iteration_equation": "REMOVE_TANGENTIAL_THEN_DIVIDE_RADIAL",
                "bounded_iterations": _INVERSE_ITERATIONS,
                "round_trip_guard_px": _INVERSE_TOLERANCE_PX,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "optical_frame": self.optical_frame,
            "resolution_px": [self.width_px, self.height_px],
            "published_fov_deg": {
                "horizontal": self.published_horizontal_fov_deg,
                "vertical": self.published_vertical_fov_deg,
                "evidence_state": "MANUFACTURER_PUBLISHED_UNMEASURED",
            },
            "effective_rectilinear_fov_deg": {
                "horizontal": self.effective_horizontal_fov_deg,
                "vertical": self.effective_vertical_fov_deg,
                "derivation": "HORIZONTAL_PUBLISHED_PLUS_NATIVE_3_TO_2_ASPECT",
            },
            "rectified_intrinsics_row_major": list(self.intrinsics_row_major),
            "capture_distortion": {
                "model": "BROWN_CONRADY_5",
                "coefficients": _distortion_dict(self.distortion),
                "evidence_state": "SYNTHETIC_STRESS_FIXTURE_NOT_MEASURED_B0477_LENS",
            },
            "capture_pixel_space": self.capture_pixel_space,
            "estimator_pixel_space": self.estimator_pixel_space,
            "intrinsics_source_sha256": self.intrinsics_source_sha256,
            "undistortion_map_sha256": self.undistortion_map_sha256,
            "rectifier_implementation_sha256": self.rectifier_implementation_sha256,
            "authority": {
                "physical_calibration_authority": False,
                "live_capture_authority": False,
                "robot_motion_authority": False,
                "contact_authority": False,
            },
        }

    @property
    def content_sha256(self) -> str:
        return _canonical_hash(self.to_dict())

    def capture_camera(self) -> PinholeCameraModel:
        """Construct the exact distorted camera consumed by the renderer."""

        return PinholeCameraModel(
            width_px=self.width_px,
            height_px=self.height_px,
            fx_px=self.fx_px,
            fy_px=self.fy_px,
            cx_px=self.cx_px,
            cy_px=self.cy_px,
            optical_frame=self.optical_frame,
            distortion=self.distortion,
        )

    def estimator_intrinsics(self) -> PinholeIntrinsics:
        """Construct the exact undistorted intrinsics consumed by pose fitting."""

        return PinholeIntrinsics(
            calibration_id="b0477.synthetic_proxy.aspect_consistent_rectified.v1",
            width_px=self.width_px,
            height_px=self.height_px,
            fx_px=self.fx_px,
            fy_px=self.fy_px,
            cx_px=self.cx_px,
            cy_px=self.cy_px,
            source_sha256=self.intrinsics_source_sha256,
            camera_frame=self.optical_frame,
            pixel_space=self.estimator_pixel_space,
        )

    def distort_rectified_pixel(self, u_px: float, v_px: float) -> tuple[float, float]:
        """Apply the capture-space Brown-Conrady map to one ideal pixel."""

        u = _finite(u_px, "u_px")
        v = _finite(v_px, "v_px")
        x = (u - self.cx_px) / self.fx_px
        y = (v - self.cy_px) / self.fy_px
        xd, yd = self._distort_normalized(x, y)
        return self.fx_px * xd + self.cx_px, self.fy_px * yd + self.cy_px

    def undistort_capture_pixel(self, u_px: float, v_px: float) -> tuple[float, float]:
        """Invert the synthetic capture map and enforce its round-trip bound."""

        u = _finite(u_px, "u_px")
        v = _finite(v_px, "v_px")
        xd = (u - self.cx_px) / self.fx_px
        yd = (v - self.cy_px) / self.fy_px
        x = xd
        y = yd
        coefficients = self.distortion
        for _ in range(self.inverse_iterations):
            r2 = x * x + y * y
            radial = (
                1.0
                + coefficients.k1 * r2
                + coefficients.k2 * r2**2
                + coefficients.k3 * r2**3
            )
            if not math.isfinite(radial) or abs(radial) <= 1e-12:
                raise B0477OpticalContractError(
                    "synthetic undistortion encountered a singular radial term"
                )
            tangential_x = (
                2.0 * coefficients.p1 * x * y
                + coefficients.p2 * (r2 + 2.0 * x * x)
            )
            tangential_y = (
                coefficients.p1 * (r2 + 2.0 * y * y)
                + 2.0 * coefficients.p2 * x * y
            )
            x = (xd - tangential_x) / radial
            y = (yd - tangential_y) / radial
        rectified_u = self.fx_px * x + self.cx_px
        rectified_v = self.fy_px * y + self.cy_px
        round_trip_u, round_trip_v = self.distort_rectified_pixel(
            rectified_u, rectified_v
        )
        error_px = math.hypot(round_trip_u - u, round_trip_v - v)
        if not math.isfinite(error_px) or error_px > self.inverse_tolerance_px:
            raise B0477OpticalContractError(
                "synthetic undistortion did not meet its round-trip pixel bound"
            )
        return rectified_u, rectified_v

    def _distort_normalized(self, x: float, y: float) -> tuple[float, float]:
        coefficients = self.distortion
        r2 = x * x + y * y
        radial = (
            1.0
            + coefficients.k1 * r2
            + coefficients.k2 * r2**2
            + coefficients.k3 * r2**3
        )
        return (
            x * radial
            + 2.0 * coefficients.p1 * x * y
            + coefficients.p2 * (r2 + 2.0 * x * x),
            y * radial
            + coefficients.p1 * (r2 + 2.0 * y * y)
            + 2.0 * coefficients.p2 * x * y,
        )

    def rectify_detection_batch(
        self, batch: AprilTagDetectionBatch
    ) -> B0477RectifiedDetectionBatch:
        """Map capture-detector corners into the estimator pixel space once.

        The generic detector batch type has no coordinate-space field.  The
        canonical capture detector identity is therefore required at entry,
        and the returned subtype carries an immutable provenance marker bound
        into its rectifier identity.  Passing the result (or an untyped copy
        that retains its rectifier identity) back into this method fails before
        any coordinate is transformed.
        """

        if not isinstance(batch, AprilTagDetectionBatch):
            raise TypeError("batch must be AprilTagDetectionBatch")
        if isinstance(batch, B0477RectifiedDetectionBatch):
            self.assert_rectified_detection_batch(batch)
            raise B0477OpticalContractError(
                "detection batch is already in the estimator pixel space; "
                "double rectification is forbidden"
            )
        _validate_capture_detector_identity(batch.detector)
        if (batch.frame.width_px, batch.frame.height_px) != (
            self.width_px,
            self.height_px,
        ):
            raise B0477OpticalContractError(
                "detection frame resolution differs from the optical contract"
            )
        detections: list[AprilTagDetection] = []
        for detection in batch.detections:
            coordinates = tuple(
                self.undistort_capture_pixel(corner.x_px, corner.y_px)
                for corner in detection.corners_px
            )
            detections.append(
                AprilTagDetection(
                    tag=detection.tag,
                    corners_px=tuple(
                        PixelCorner(x_px, y_px) for x_px, y_px in coordinates
                    ),  # type: ignore[arg-type]
                    decision_margin=detection.decision_margin,
                    hamming=detection.hamming,
                    rejection_reason=detection.rejection_reason,
                )
            )
        provenance = self.pixel_space_provenance(batch.detector)
        return B0477RectifiedDetectionBatch(
            frame=batch.frame,
            detector=DetectorIdentity(
                detector_id=_RECTIFIED_DETECTOR_ID,
                version=_RECTIFIED_DETECTOR_VERSION,
                configuration_sha256=provenance.content_sha256,
                implementation_sha256=self.rectifier_implementation_sha256,
            ),
            detections=tuple(detections),
            pixel_space_provenance=provenance,
        )

    def pixel_space_provenance(
        self, raw_detector: DetectorIdentity
    ) -> B0477DetectionPixelSpaceProvenance:
        """Build the exact zero-authority capture-to-estimator marker."""

        _validate_capture_detector_identity(raw_detector)
        return B0477DetectionPixelSpaceProvenance(
            source_detector=raw_detector,
            optical_contract_sha256=self.content_sha256,
            undistortion_map_sha256=self.undistortion_map_sha256,
            rectifier_implementation_sha256=(
                self.rectifier_implementation_sha256
            ),
        )

    def assert_rectified_detection_batch(
        self, batch: B0477RectifiedDetectionBatch
    ) -> None:
        """Fail closed unless ``batch`` is this contract's estimator output."""

        if not isinstance(batch, B0477RectifiedDetectionBatch):
            raise TypeError("batch must be B0477RectifiedDetectionBatch")
        provenance = batch.pixel_space_provenance
        assert provenance is not None
        if provenance != self.pixel_space_provenance(provenance.source_detector):
            raise B0477OpticalContractError(
                "rectified batch pixel-space provenance differs from this contract"
            )
        expected_detector = self.rectifier_identity(provenance.source_detector)
        if batch.detector != expected_detector:
            raise B0477OpticalContractError(
                "rectified batch detector identity differs from this contract"
            )

    def rectifier_identity(self, raw_detector: DetectorIdentity) -> DetectorIdentity:
        """Content-address the detector-plus-rectifier processing chain."""

        provenance = self.pixel_space_provenance(raw_detector)
        return DetectorIdentity(
            detector_id=_RECTIFIED_DETECTOR_ID,
            version=_RECTIFIED_DETECTOR_VERSION,
            configuration_sha256=provenance.content_sha256,
            implementation_sha256=self.rectifier_implementation_sha256,
        )


def build_b0477_synthetic_optical_contract(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
) -> B0477SyntheticOpticalContract:
    """Derive the one Phase-1 proxy contract from validated source objects."""

    if not isinstance(profile, PurchasedCameraProfile):
        raise TypeError("profile must be PurchasedCameraProfile")
    if not isinstance(support, StaticCameraSupportDesign):
        raise TypeError("support must be StaticCameraSupportDesign")
    proxy = profile.simulation_proxy
    if (proxy.width_px, proxy.height_px) != _EXPECTED_RESOLUTION:
        raise B0477OpticalContractError("profile proxy resolution changed")
    if (proxy.horizontal_fov_deg, proxy.vertical_fov_deg) != (
        support.field_of_view_deg[0],
        support.field_of_view_deg[1],
    ):
        raise B0477OpticalContractError("profile and support published FOV claims differ")
    fx_px = proxy.width_px / (
        2.0 * math.tan(math.radians(proxy.horizontal_fov_deg / 2.0))
    )
    effective_vertical_fov_deg = math.degrees(
        2.0 * math.atan(proxy.height_px / (2.0 * fx_px))
    )
    if not math.isclose(
        effective_vertical_fov_deg,
        support.metrics.aspect_conservative_vertical_fov_deg,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise B0477OpticalContractError(
            "support coverage and B0477 renderer vertical FOV differ"
        )
    return B0477SyntheticOpticalContract(
        optical_frame=B0477_PHASE1_OPTICAL_FRAME,
        width_px=proxy.width_px,
        height_px=proxy.height_px,
        fx_px=fx_px,
        fy_px=fx_px,
        cx_px=proxy.width_px / 2.0,
        cy_px=proxy.height_px / 2.0,
        published_horizontal_fov_deg=proxy.horizontal_fov_deg,
        published_vertical_fov_deg=proxy.vertical_fov_deg,
        effective_horizontal_fov_deg=proxy.horizontal_fov_deg,
        effective_vertical_fov_deg=effective_vertical_fov_deg,
        distortion=_SYNTHETIC_STRESS_DISTORTION,
        intrinsics_source_sha256=profile.canonical_sha256,
    )


__all__ = [
    "B0477_CAPTURE_PIXEL_SPACE",
    "B0477_ESTIMATOR_PIXEL_SPACE",
    "B0477_OPTICAL_CONTRACT_SCHEMA",
    "B0477_PHASE1_OPTICAL_FRAME",
    "B0477_PIXEL_SPACE_PROVENANCE_SCHEMA",
    "B0477_UNDISTORTION_MAP_SCHEMA",
    "B0477DetectionPixelSpaceProvenance",
    "B0477OpticalContractError",
    "B0477RectifiedDetectionBatch",
    "B0477SyntheticOpticalContract",
    "build_b0477_synthetic_optical_contract",
]
