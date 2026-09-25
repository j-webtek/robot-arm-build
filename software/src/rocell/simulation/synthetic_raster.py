"""Deterministic grayscale pixel rendering for RC03 camera simulations.

Unlike :mod:`rocell.simulation.camera`, this module produces pixels rather than
ideal corner observations.  The returned :class:`~rocell.vision.camera.FramePacket`
contains no tag IDs, projected corners, or expected detections.  A detector must
recover those facts from JPEG bytes.  Pillow is imported lazily by ``render`` so
importing the simulation package remains dependency- and side-effect-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from rocell.models.frames import FrameMismatchError, Point3Mm, Transform
from rocell.vision.apriltag_codebook import (
    AprilTagPatternCodebook,
    DEFAULT_APRILTAG_36H11_CODEBOOK,
)
from rocell.vision.camera import FramePacket, TimestampQuality

from .camera import PinholeCameraModel, ProjectionError
from .scene import NominalWorkcellScene, PlanarFiducial


MAX_SYNTHETIC_RASTER_WIDTH_PX = 4096
MAX_SYNTHETIC_RASTER_HEIGHT_PX = 4096
MAX_SYNTHETIC_RASTER_PIXELS = 16_777_216
MAX_SYNTHETIC_JPEG_BYTES = 16 * 1024 * 1024
MAX_TAG_ASSET_BYTES = 1024 * 1024
MAX_SYNTHETIC_PROJECTED_COORDINATE_PX = 1_000_000.0
MAX_SYNTHETIC_NOISE_AMPLITUDE_GRAY = 96
MAX_SYNTHETIC_GAUSSIAN_BLUR_RADIUS_PX = 16.0
MAX_SYNTHETIC_MOTION_BLUR_PX = 32

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SyntheticRasterError(RuntimeError):
    """Base failure at the simulation-only raster boundary."""


class SyntheticRasterBackendUnavailable(SyntheticRasterError):
    """The optional Pillow raster/JPEG backend is not installed."""


class SyntheticRasterValidationError(SyntheticRasterError, ValueError):
    """Renderer configuration, geometry, or controlled artwork is invalid."""


class SyntheticRasterResourceLimitError(SyntheticRasterError):
    """A bounded image or source artifact would exceed its configured limit."""


def _stable_hash(value: Mapping[str, Any]) -> str:
    try:
        payload = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SyntheticRasterValidationError(
            f"renderer provenance is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise SyntheticRasterValidationError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _bounded_int(
    value: object,
    label: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SyntheticRasterValidationError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise SyntheticRasterValidationError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return value


def _bounded_float(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SyntheticRasterValidationError(f"{label} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise SyntheticRasterValidationError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return parsed


def _bounded_text(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SyntheticRasterValidationError(f"{label} must be non-empty text")
    parsed = value.strip()
    if parsed != value or len(parsed) > maximum:
        raise SyntheticRasterValidationError(
            f"{label} must be trimmed text of at most {maximum} characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in parsed):
        raise SyntheticRasterValidationError(f"{label} contains a control character")
    return parsed


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


def _load_pillow() -> tuple[Any, Any, str]:
    """Import the optional backend only when a caller requests pixels."""

    try:
        from PIL import Image, ImageDraw, __version__ as pillow_version
    except (ImportError, ModuleNotFoundError) as exc:
        raise SyntheticRasterBackendUnavailable(
            "Synthetic pixel rendering requires the optional Pillow package"
        ) from exc
    return Image, ImageDraw, str(pillow_version)


@dataclass(frozen=True, slots=True)
class SyntheticRasterConfig:
    """Content-addressed render policy, including pixel-domain faults.

    Defaults preserve the original clean, complete fixed-overview image.
    Arm-mounted simulations opt in to partial-scene clipping.  Every image
    perturbation is deterministic and therefore replayable; none supplies
    detection truth to the downstream detector.
    """

    renderer_id: str = "RC03_FIXED_OVERVIEW_GRAYSCALE_V1"
    background_gray: int = 24
    board_gray: int = 205
    device_gray: int = 145
    tile_gray: int = 255
    black_gray: int = 0
    jpeg_quality: int = 95
    maximum_jpeg_bytes: int = MAX_SYNTHETIC_JPEG_BYTES
    occluded_tag_ids: tuple[int, ...] = ()
    allow_partial_scene: bool = False
    noise_amplitude_gray: int = 0
    gaussian_blur_radius_px: float = 0.0
    horizontal_motion_blur_px: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.renderer_id, str) or not self.renderer_id.strip():
            raise SyntheticRasterValidationError("renderer_id must be non-empty text")
        if len(self.renderer_id) > 128:
            raise SyntheticRasterValidationError("renderer_id exceeds 128 characters")
        object.__setattr__(self, "renderer_id", self.renderer_id.strip())
        for name in (
            "background_gray",
            "board_gray",
            "device_gray",
            "tile_gray",
            "black_gray",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, minimum=0, maximum=255),
            )
        if self.black_gray >= self.tile_gray:
            raise SyntheticRasterValidationError(
                "black_gray must be darker than tile_gray"
            )
        object.__setattr__(
            self,
            "jpeg_quality",
            _bounded_int(self.jpeg_quality, "jpeg_quality", minimum=80, maximum=100),
        )
        object.__setattr__(
            self,
            "maximum_jpeg_bytes",
            _bounded_int(
                self.maximum_jpeg_bytes,
                "maximum_jpeg_bytes",
                minimum=1024,
                maximum=MAX_SYNTHETIC_JPEG_BYTES,
            ),
        )
        occluded = tuple(
            _bounded_int(tag_id, "occluded tag id", minimum=0, maximum=1_000_000)
            for tag_id in self.occluded_tag_ids
        )
        if len(occluded) != len(set(occluded)):
            raise SyntheticRasterValidationError("occluded tag ids must be unique")
        if len(occluded) > 6:
            raise SyntheticRasterValidationError("at most six RC03 tags may be occluded")
        object.__setattr__(self, "occluded_tag_ids", tuple(sorted(occluded)))
        if not isinstance(self.allow_partial_scene, bool):
            raise SyntheticRasterValidationError("allow_partial_scene must be boolean")
        object.__setattr__(
            self,
            "noise_amplitude_gray",
            _bounded_int(
                self.noise_amplitude_gray,
                "noise_amplitude_gray",
                minimum=0,
                maximum=MAX_SYNTHETIC_NOISE_AMPLITUDE_GRAY,
            ),
        )
        object.__setattr__(
            self,
            "gaussian_blur_radius_px",
            _bounded_float(
                self.gaussian_blur_radius_px,
                "gaussian_blur_radius_px",
                minimum=0.0,
                maximum=MAX_SYNTHETIC_GAUSSIAN_BLUR_RADIUS_PX,
            ),
        )
        object.__setattr__(
            self,
            "horizontal_motion_blur_px",
            _bounded_int(
                self.horizontal_motion_blur_px,
                "horizontal_motion_blur_px",
                minimum=0,
                maximum=MAX_SYNTHETIC_MOTION_BLUR_PX,
            ),
        )

    @property
    def config_sha256(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.synthetic_raster_config.v2",
            "renderer_id": self.renderer_id,
            "grayscale": {
                "background": self.background_gray,
                "board": self.board_gray,
                "device": self.device_gray,
                "tile": self.tile_gray,
                "black": self.black_gray,
            },
            "jpeg": {
                "quality": self.jpeg_quality,
                "optimize": False,
                "progressive": False,
                "subsampling": 0,
                "maximum_bytes": self.maximum_jpeg_bytes,
            },
            "occluded_tag_ids": list(self.occluded_tag_ids),
            "scene_clipping": {
                "allow_partial_scene": self.allow_partial_scene,
                "maximum_projected_coordinate_abs_px": (
                    MAX_SYNTHETIC_PROJECTED_COORDINATE_PX
                ),
            },
            "pixel_perturbations": {
                "deterministic": True,
                "noise_amplitude_gray": self.noise_amplitude_gray,
                "gaussian_blur_radius_px": self.gaussian_blur_radius_px,
                "horizontal_motion_blur_px": self.horizontal_motion_blur_px,
                "noise_seed_basis": "SEQUENCE_AND_RENDERER_CONFIG_SHA256",
            },
            "corner_convention": "MARKED_TL_TR_BR_BL_TO_PATTERN_TL_TR_BR_BL",
            "pixel_coordinate_convention": (
                "PINHOLE_U_RIGHT_V_DOWN_CONTINUOUS_THEN_NEAREST_INTEGER_VERTEX"
            ),
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class SyntheticCaptureTiming:
    """Explicit timing attached to one synthetic frame.

    This type only records when the simulator says request/receipt events
    occurred.  It cannot establish physical exposure timing.  In particular,
    arm-camera simulations must use ``SETTLED_BRACKET`` or ``UNQUALIFIED`` and
    never claim ``DEVICE_EXPOSURE``.
    """

    source_timestamp_ns: int | None
    source_clock: str | None
    host_request_ns: int
    host_first_byte_ns: int
    host_complete_ns: int
    timestamp_quality: TimestampQuality
    freshness_token: str
    freshness_basis: str = "synthetic_explicit_capture_timing"

    def __post_init__(self) -> None:
        maximum_tick = (1 << 63) - 1
        if self.source_timestamp_ns is not None:
            object.__setattr__(
                self,
                "source_timestamp_ns",
                _bounded_int(
                    self.source_timestamp_ns,
                    "source_timestamp_ns",
                    minimum=0,
                    maximum=maximum_tick,
                ),
            )
            if self.source_clock is None:
                raise SyntheticRasterValidationError(
                    "source_clock is required with source_timestamp_ns"
                )
            object.__setattr__(
                self,
                "source_clock",
                _bounded_text(self.source_clock, "source_clock"),
            )
        elif self.source_clock is not None:
            raise SyntheticRasterValidationError(
                "source_clock requires source_timestamp_ns"
            )
        for name in ("host_request_ns", "host_first_byte_ns", "host_complete_ns"):
            object.__setattr__(
                self,
                name,
                _bounded_int(
                    getattr(self, name), name, minimum=0, maximum=maximum_tick
                ),
            )
        if not (
            self.host_request_ns
            <= self.host_first_byte_ns
            <= self.host_complete_ns
        ):
            raise SyntheticRasterValidationError(
                "synthetic host frame timestamps are out of order"
            )
        if not isinstance(self.timestamp_quality, TimestampQuality):
            raise SyntheticRasterValidationError(
                "timestamp_quality must be TimestampQuality"
            )
        if self.timestamp_quality is TimestampQuality.DEVICE_EXPOSURE:
            raise SyntheticRasterValidationError(
                "synthetic timing cannot claim DEVICE_EXPOSURE quality"
            )
        object.__setattr__(
            self,
            "freshness_token",
            _bounded_text(self.freshness_token, "freshness_token", maximum=1024),
        )
        object.__setattr__(
            self,
            "freshness_basis",
            _bounded_text(self.freshness_basis, "freshness_basis", maximum=512),
        )

    @classmethod
    def from_sequence(cls, sequence: int) -> "SyntheticCaptureTiming":
        """Construct the legacy deterministic unqualified timing envelope."""

        selected = _bounded_int(
            sequence,
            "synthetic frame sequence",
            minimum=0,
            maximum=1_000_000_000,
        )
        base_tick = selected * 1_000_000
        return cls(
            source_timestamp_ns=base_tick,
            source_clock="synthetic_render_sequence",
            host_request_ns=base_tick,
            host_first_byte_ns=base_tick + 1,
            host_complete_ns=base_tick + 2,
            timestamp_quality=TimestampQuality.UNQUALIFIED,
            freshness_token=f"synthetic-render:{selected}",
            freshness_basis="deterministic_sequence_and_jpeg_sha256",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.synthetic_capture_timing.v1",
            "source_timestamp_ns": self.source_timestamp_ns,
            "source_clock": self.source_clock,
            "host_request_ns": self.host_request_ns,
            "host_first_byte_ns": self.host_first_byte_ns,
            "host_complete_ns": self.host_complete_ns,
            "timestamp_quality": self.timestamp_quality.value,
            "freshness_token": self.freshness_token,
            "freshness_basis": self.freshness_basis,
            "physical_exposure_qualified": False,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class SyntheticRenderedFrame:
    """Frame plus redacted renderer provenance; no detection truth is carried."""

    frame_packet: FramePacket = field(repr=False)
    renderer_config_sha256: str
    source_bundle_sha256: str
    renderer_definition_sha256: str
    backend_id: str
    backend_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.frame_packet, FramePacket):
            raise TypeError("frame_packet must be a FramePacket")
        for name in (
            "renderer_config_sha256",
            "source_bundle_sha256",
            "renderer_definition_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if self.frame_packet.settings_hash != self.renderer_definition_sha256:
            raise SyntheticRasterValidationError(
                "Frame settings hash does not bind the renderer definition"
            )
        for name in ("backend_id", "backend_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise SyntheticRasterValidationError(
                    f"{name} must be bounded non-empty text"
                )
            object.__setattr__(self, name, value.strip())

    @property
    def render_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.synthetic_rendered_frame.v1",
            "frame": {
                "capture_id": self.frame_packet.capture_id,
                "jpeg_sha256": self.frame_packet.sha256,
                "jpeg_byte_count": len(self.frame_packet.jpeg_bytes),
                "width_px": self.frame_packet.width_px,
                "height_px": self.frame_packet.height_px,
                "settings_hash": self.frame_packet.settings_hash,
                "timestamp_quality": self.frame_packet.timestamp_quality.value,
            },
            "renderer_config_sha256": self.renderer_config_sha256,
            "source_bundle_sha256": self.source_bundle_sha256,
            "renderer_definition_sha256": self.renderer_definition_sha256,
            "backend": {"id": self.backend_id, "version": self.backend_version},
            "detector_input_contract": "FRAME_PACKET_JPEG_BYTES_ONLY",
            "embedded_detection_truth": False,
            "physical_camera_accessed": False,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class SyntheticOverviewRasterRenderer:
    """Render the complete six-tag nominal RC03 scene through a pinhole model."""

    scene: NominalWorkcellScene
    camera: PinholeCameraModel
    camera_T_board: Transform
    tag_asset_root: Path
    config: SyntheticRasterConfig = field(default_factory=SyntheticRasterConfig)
    codebook: AprilTagPatternCodebook = DEFAULT_APRILTAG_36H11_CODEBOOK

    def __post_init__(self) -> None:
        if not isinstance(self.scene, NominalWorkcellScene):
            raise TypeError("scene must be a NominalWorkcellScene")
        if not isinstance(self.camera, PinholeCameraModel):
            raise TypeError("camera must be a PinholeCameraModel")
        if not isinstance(self.camera_T_board, Transform):
            raise TypeError("camera_T_board must be a Transform")
        if self.camera_T_board.from_frame != self.scene.board_frame:
            raise FrameMismatchError(
                "camera_T_board input frame must match the scene board frame"
            )
        if self.camera_T_board.to_frame != self.camera.optical_frame:
            raise FrameMismatchError(
                "camera_T_board output frame must match camera optical frame"
            )
        if not isinstance(self.tag_asset_root, Path):
            raise TypeError("tag_asset_root must be a pathlib.Path")
        if not isinstance(self.config, SyntheticRasterConfig):
            raise TypeError("config must be SyntheticRasterConfig")
        if not isinstance(self.codebook, AprilTagPatternCodebook):
            raise TypeError("codebook must be AprilTagPatternCodebook")
        if self.camera.width_px > MAX_SYNTHETIC_RASTER_WIDTH_PX:
            raise SyntheticRasterResourceLimitError("camera width exceeds raster bound")
        if self.camera.height_px > MAX_SYNTHETIC_RASTER_HEIGHT_PX:
            raise SyntheticRasterResourceLimitError("camera height exceeds raster bound")
        if self.camera.width_px * self.camera.height_px > MAX_SYNTHETIC_RASTER_PIXELS:
            raise SyntheticRasterResourceLimitError("camera pixel count exceeds raster bound")
        scene_ids = tuple(sorted(tag.tag_id for tag in self.scene.fiducials))
        if scene_ids != self.codebook.tag_ids or scene_ids != tuple(range(6)):
            raise SyntheticRasterValidationError(
                "fixed RC03 overview requires exactly released tag36h11 IDs 0-5"
            )
        if any(tag.family != self.codebook.family for tag in self.scene.fiducials):
            raise SyntheticRasterValidationError(
                "scene fiducial family differs from the renderer codebook"
            )
        unknown_occlusions = set(self.config.occluded_tag_ids) - set(scene_ids)
        if unknown_occlusions:
            raise SyntheticRasterValidationError(
                f"occluded tag ids are not in the scene: {sorted(unknown_occlusions)}"
            )

    def _project(self, point: Point3Mm) -> tuple[float, float]:
        try:
            projected = self.camera.project(self.camera_T_board.transform_point(point))
        except ProjectionError as exc:
            raise SyntheticRasterValidationError(
                "synthetic scene geometry projects behind the camera"
            ) from exc
        if not self.config.allow_partial_scene and not projected.in_bounds:
            raise SyntheticRasterValidationError(
                "synthetic scene geometry leaves the configured raster"
            )
        if (
            abs(projected.u_px) > MAX_SYNTHETIC_PROJECTED_COORDINATE_PX
            or abs(projected.v_px) > MAX_SYNTHETIC_PROJECTED_COORDINATE_PX
        ):
            raise SyntheticRasterResourceLimitError(
                "projected scene coordinate exceeds the rasterization bound"
            )
        return projected.u_px, projected.v_px

    @staticmethod
    def _integer_polygon(
        points: tuple[tuple[float, float], ...],
    ) -> tuple[tuple[int, int], ...]:
        # Pinhole coordinates describe continuous pixel centers.  Pillow's
        # polygon vertices are integer sample sites, so use explicit nearest
        # integer rounding instead of backend-dependent float conversion.
        return tuple(
            (int(math.floor(u + 0.5)), int(math.floor(v + 0.5)))
            for u, v in points
        )

    def _project_board_rectangle(
        self,
        left: float,
        front: float,
        right: float,
        rear: float,
        z_mm: float,
    ) -> tuple[tuple[int, int], ...]:
        frame = self.scene.board_frame
        points = tuple(
            self._project(Point3Mm(frame, x, y, z_mm))
            for x, y in (
                (left, rear),
                (right, rear),
                (right, front),
                (left, front),
            )
        )
        return self._integer_polygon(points)

    def _tag_local_point(
        self,
        tag: PlanarFiducial,
        local_x_mm: float,
        local_y_mm: float,
    ) -> Point3Mm:
        cosine = math.cos(tag.yaw_rad)
        sine = math.sin(tag.yaw_rad)
        return Point3Mm(
            tag.center.frame,
            tag.center.x + cosine * local_x_mm - sine * local_y_mm,
            tag.center.y + sine * local_x_mm + cosine * local_y_mm,
            tag.center.z,
        )

    def _tag_polygon(
        self,
        tag: PlanarFiducial,
        local_bounds: tuple[float, float, float, float],
    ) -> tuple[tuple[int, int], ...]:
        left, bottom, right, top = local_bounds
        # Order is marked TL, TR, BR, BL.  Row zero of the codebook maps to
        # +local Y (marked top), exactly matching PlanarFiducial.corners().
        points = tuple(
            self._project(self._tag_local_point(tag, x, y))
            for x, y in (
                (left, top),
                (right, top),
                (right, bottom),
                (left, bottom),
            )
        )
        return self._integer_polygon(points)

    def _validate_assets(self, Image: Any) -> tuple[tuple[str, str], ...]:
        root = self.tag_asset_root.resolve(strict=True)
        if not root.is_dir() or self.tag_asset_root.is_symlink():
            raise SyntheticRasterValidationError(
                "tag_asset_root must be a real controlled directory"
            )
        hashes: list[tuple[str, str]] = []
        for tag_id in self.codebook.tag_ids:
            name = f"tag36h11_id{tag_id:02d}_tile55_marker40.png"
            source = root / name
            if source.is_symlink() or not source.is_file():
                raise SyntheticRasterValidationError(
                    f"controlled tag artwork is missing or symbolic: {name}"
                )
            resolved = source.resolve(strict=True)
            if resolved.parent != root:
                raise SyntheticRasterValidationError(
                    f"controlled tag artwork escapes its root: {name}"
                )
            byte_count = resolved.stat().st_size
            if byte_count <= 0 or byte_count > MAX_TAG_ASSET_BYTES:
                raise SyntheticRasterResourceLimitError(
                    f"controlled tag artwork {name} exceeds its byte bound"
                )
            payload = resolved.read_bytes()
            hashes.append((name, hashlib.sha256(payload).hexdigest()))
            try:
                image = Image.open(BytesIO(payload)).convert("L")
                image.load()
            except Exception as exc:
                raise SyntheticRasterValidationError(
                    f"controlled tag artwork cannot be decoded: {name}"
                ) from exc
            width, height = image.size
            if width != height or width <= 0 or width > 4096:
                raise SyntheticRasterValidationError(
                    f"controlled tag artwork has invalid dimensions: {name}"
                )
            marker_pixels = int(round(width * 40.0 / 55.0))
            quiet_pixels = (width - marker_pixels) // 2
            expected = self.codebook.pattern(tag_id)
            for row in range(8):
                for column in range(8):
                    x = quiet_pixels + int(round((column + 0.5) * marker_pixels / 8.0))
                    y = quiet_pixels + int(round((row + 0.5) * marker_pixels / 8.0))
                    observed = 1 if image.getpixel((x, y)) >= 128 else 0
                    if observed != expected[row][column]:
                        raise SyntheticRasterValidationError(
                            f"controlled tag artwork/codebook mismatch: {name}"
                        )
            if image.getpixel((0, 0)) < 128:
                raise SyntheticRasterValidationError(
                    f"controlled tag artwork lacks its white quiet tile: {name}"
                )
        return tuple(hashes)

    def _source_bundle_hash(
        self,
        asset_hashes: tuple[tuple[str, str], ...],
    ) -> str:
        implementation_path = Path(__file__).resolve(strict=True)
        implementation_bytes = implementation_path.read_bytes()
        source_hashes = {
            **dict(sorted(self.scene.source_hashes.items())),
            "scene_projection_sha256": _stable_hash(self.scene.to_dict()),
            "tag_asset_bundle_sha256": _stable_hash(
                {
                    "schema": "rocell.rc03_tag_asset_bundle.v1",
                    "assets": dict(asset_hashes),
                }
            ),
            "tag_codebook_sha256": self.codebook.codebook_sha256,
            "renderer_implementation_sha256": hashlib.sha256(
                implementation_bytes
            ).hexdigest(),
        }
        return _stable_hash(
            {
                "schema": "rocell.synthetic_raster_source_bundle.v1",
                "source_hashes": source_hashes,
                "authority": _authority(),
            }
        )

    def _apply_perturbations(self, Image: Any, image: Any, sequence: int) -> Any:
        """Apply bounded deterministic image-only effects before JPEG coding."""

        motion = self.config.horizontal_motion_blur_px
        if motion:
            # Average at most 17 shifted rasters.  The sample cap keeps the
            # simulation resource-bounded even at the maximum configured blur.
            sample_count = min(17, motion * 2 + 1)
            offsets = tuple(
                sorted(
                    {
                        int(round(-motion + 2.0 * motion * index / (sample_count - 1)))
                        for index in range(sample_count)
                    }
                )
            )
            transform_kind = getattr(getattr(Image, "Transform", Image), "AFFINE")
            resample_kind = getattr(getattr(Image, "Resampling", Image), "NEAREST")
            accumulator = None
            accumulated = 0
            for offset in offsets:
                shifted = image.transform(
                    image.size,
                    transform_kind,
                    (1.0, 0.0, float(offset), 0.0, 1.0, 0.0),
                    resample=resample_kind,
                    fillcolor=self.config.background_gray,
                )
                accumulated += 1
                accumulator = (
                    shifted
                    if accumulator is None
                    else Image.blend(accumulator, shifted, 1.0 / accumulated)
                )
            image = accumulator

        if self.config.gaussian_blur_radius_px:
            # Imported here to retain the module's optional/lazy Pillow boundary.
            try:
                from PIL import ImageFilter
            except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
                raise SyntheticRasterBackendUnavailable(
                    "Synthetic pixel perturbations require Pillow ImageFilter"
                ) from exc
            image = image.filter(
                ImageFilter.GaussianBlur(self.config.gaussian_blur_radius_px)
            )

        amplitude = self.config.noise_amplitude_gray
        if amplitude:
            # Xorshift32 is used as a tiny reproducible generator.  It is not a
            # claim about a physical sensor noise distribution; it simply makes
            # the pixel boundary exercise real corruption with stable replay.
            seed_material = (
                f"{sequence}:{self.config.config_sha256}:deterministic-gray-noise"
            ).encode("ascii")
            state = int.from_bytes(hashlib.sha256(seed_material).digest()[:4], "big")
            state = state or 0x6D2B79F5
            span = amplitude * 2 + 1
            pixels = bytearray(image.tobytes())
            for index, gray in enumerate(pixels):
                state ^= (state << 13) & 0xFFFFFFFF
                state ^= state >> 17
                state ^= (state << 5) & 0xFFFFFFFF
                delta = (state % span) - amplitude
                pixels[index] = max(0, min(255, gray + delta))
            image = Image.frombytes("L", image.size, bytes(pixels))
        return image

    def render(
        self,
        *,
        sequence: int = 0,
        timing: SyntheticCaptureTiming | None = None,
    ) -> SyntheticRenderedFrame:
        """Render one repeatable JPEG with optional explicit capture timing.

        With the default clean configuration, sequence changes provenance but
        not pixels.  With deterministic noise enabled, sequence is part of the
        declared noise seed and therefore intentionally changes the pixels.
        """

        selected_sequence = _bounded_int(
            sequence,
            "synthetic frame sequence",
            minimum=0,
            maximum=1_000_000_000,
        )
        if timing is not None and not isinstance(timing, SyntheticCaptureTiming):
            raise TypeError("timing must be SyntheticCaptureTiming or None")
        Image, ImageDraw, pillow_version = _load_pillow()
        asset_hashes = self._validate_assets(Image)
        source_bundle_hash = self._source_bundle_hash(asset_hashes)
        definition_hash = _stable_hash(
            {
                "schema": "rocell.synthetic_overview_renderer_definition.v1",
                "renderer_config_sha256": self.config.config_sha256,
                "source_bundle_sha256": source_bundle_hash,
                "camera": self.camera.to_dict(),
                "camera_T_board": {
                    "to_frame": self.camera_T_board.to_frame,
                    "from_frame": self.camera_T_board.from_frame,
                    "matrix_row_major": list(self.camera_T_board.matrix),
                },
                "backend": {"id": "Pillow", "version": pillow_version},
                "authority": _authority(),
            }
        )

        image = Image.new(
            "L",
            (self.camera.width_px, self.camera.height_px),
            color=self.config.background_gray,
        )
        draw = ImageDraw.Draw(image)
        board = self.scene.board
        draw.polygon(
            self._project_board_rectangle(
                board.minimum.x,
                board.minimum.y,
                board.maximum.x,
                board.maximum.y,
                board.maximum.z,
            ),
            fill=self.config.board_gray,
        )
        for device in sorted(self.scene.devices.values(), key=lambda value: value.device_id):
            envelope = device.envelope
            draw.polygon(
                self._project_board_rectangle(
                    envelope.minimum.x,
                    envelope.minimum.y,
                    envelope.maximum.x,
                    envelope.maximum.y,
                    envelope.maximum.z,
                ),
                fill=self.config.device_gray,
            )

        occluded = frozenset(self.config.occluded_tag_ids)
        for tag in sorted(self.scene.fiducials, key=lambda value: value.tag_id):
            if tag.tag_id in occluded:
                continue
            tile_half = tag.tile_edge_mm / 2.0
            draw.polygon(
                self._tag_polygon(
                    tag,
                    (-tile_half, -tile_half, tile_half, tile_half),
                ),
                fill=self.config.tile_gray,
            )
            marker_half = tag.detection_edge_mm / 2.0
            cell_edge = tag.detection_edge_mm / 8.0
            grid = self.codebook.pattern(tag.tag_id)
            # Paint only black cells over the white marker/tile.  Each cell is
            # separately projected, so perspective is encoded in pixels rather
            # than supplied later as ideal detector metadata.
            for row in range(8):
                top = marker_half - row * cell_edge
                bottom = top - cell_edge
                for column in range(8):
                    if grid[row][column] != 0:
                        continue
                    left = -marker_half + column * cell_edge
                    right = left + cell_edge
                    draw.polygon(
                        self._tag_polygon(tag, (left, bottom, right, top)),
                        fill=self.config.black_gray,
                    )

        image = self._apply_perturbations(Image, image, selected_sequence)
        output = BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=self.config.jpeg_quality,
            optimize=False,
            progressive=False,
            subsampling=0,
        )
        jpeg_bytes = output.getvalue()
        if len(jpeg_bytes) > self.config.maximum_jpeg_bytes:
            raise SyntheticRasterResourceLimitError(
                "rendered JPEG exceeds the configured byte bound"
            )
        jpeg_hash = hashlib.sha256(jpeg_bytes).hexdigest()
        selected_timing = timing or SyntheticCaptureTiming.from_sequence(
            selected_sequence
        )
        freshness_token = selected_timing.freshness_token
        if timing is None:
            # Preserve the prior strong freshness identity for default renders.
            freshness_token = f"{freshness_token}:{jpeg_hash}"
        frame = FramePacket(
            capture_id=(
                f"synthetic-overview-{selected_sequence:010d}-{jpeg_hash[:16]}"
            ),
            jpeg_bytes=jpeg_bytes,
            width_px=self.camera.width_px,
            height_px=self.camera.height_px,
            source_sequence=selected_sequence,
            source_timestamp_ns=selected_timing.source_timestamp_ns,
            source_clock=selected_timing.source_clock,
            host_request_ns=selected_timing.host_request_ns,
            host_first_byte_ns=selected_timing.host_first_byte_ns,
            host_complete_ns=selected_timing.host_complete_ns,
            settings_hash=definition_hash,
            timestamp_quality=selected_timing.timestamp_quality,
            freshness_token=freshness_token,
            freshness_basis=selected_timing.freshness_basis,
        )
        return SyntheticRenderedFrame(
            frame_packet=frame,
            renderer_config_sha256=self.config.config_sha256,
            source_bundle_sha256=source_bundle_hash,
            renderer_definition_sha256=definition_hash,
            backend_id="Pillow",
            backend_version=pillow_version,
        )


__all__ = [
    "MAX_SYNTHETIC_GAUSSIAN_BLUR_RADIUS_PX",
    "MAX_SYNTHETIC_JPEG_BYTES",
    "MAX_SYNTHETIC_MOTION_BLUR_PX",
    "MAX_SYNTHETIC_NOISE_AMPLITUDE_GRAY",
    "MAX_SYNTHETIC_PROJECTED_COORDINATE_PX",
    "MAX_SYNTHETIC_RASTER_HEIGHT_PX",
    "MAX_SYNTHETIC_RASTER_PIXELS",
    "MAX_SYNTHETIC_RASTER_WIDTH_PX",
    "SyntheticOverviewRasterRenderer",
    "SyntheticCaptureTiming",
    "SyntheticRasterBackendUnavailable",
    "SyntheticRasterConfig",
    "SyntheticRasterError",
    "SyntheticRasterResourceLimitError",
    "SyntheticRasterValidationError",
    "SyntheticRenderedFrame",
]
