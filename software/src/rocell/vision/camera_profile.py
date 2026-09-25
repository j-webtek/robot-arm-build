"""Strict purchase-time profile for the selected Arducam B0477 camera.

The profile intentionally separates three kinds of knowledge:

* the user's purchase report;
* manufacturer-published claims that have not been measured locally; and
* physical, USB, and calibration observations, which remain open and null.

Loading this file cannot open a camera or grant any live-system authority.  The
schema is deliberately exact and specific to the purchased B0477 combination:
unknown keys, missing keys, duplicate JSON keys, non-finite numbers, altered
published claims, or prematurely populated observation fields fail closed.
When hardware arrives, measurements belong in a later commissioned schema and
must not be written into this purchase-time record by changing nulls in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence


CAMERA_PROFILE_SCHEMA = "rocell.purchased_camera_profile.v1"
MAX_CAMERA_PROFILE_BYTES = 64 * 1024
DEFAULT_B0477_CAMERA_PROFILE = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "camera_profiles"
    / "arducam_b0477_imx283_16mm.json"
)

_PUBLISHED = "MANUFACTURER_PUBLISHED_UNMEASURED"
_PUBLISHED_SOURCE = "PUBLISHED_NOT_MEASURED"
_PURCHASED = "PURCHASED_PENDING_RECEIPT"
_PURCHASE_EVIDENCE = "USER_REPORTED_PURCHASE_NOT_RECEIPT_VERIFIED"
_PURCHASE_SOURCE_EVIDENCE = "USER_REPORTED_NOT_RECEIPT_VERIFIED"
_PRODUCT_TITLE = (
    "Arducam USB 3.0 Camera, 120fps High-Speed Camera, 20MP Webcam with "
    "60°(D) 16mm C-Mount Lens and Metal Case, Compatible with Windows and Linux OS"
)
_AUTHORITY_NOTE = (
    "This purchase record and manufacturer-published specification profile does "
    "not prove receipt, identity, mode, focus, calibration, installation, live "
    "capture, robot motion, or contact readiness."
)

_ROOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "profile_id",
        "record_state",
        "authority",
        "purchase",
        "published_identity",
        "published_interface",
        "published_optics",
        "published_native_modes",
        "published_package",
        "simulation_proxy",
        "provenance",
        "physical_observation",
        "usb_observation",
        "commissioning",
        "open_blockers",
    }
)
_AUTHORITY_FIELDS = frozenset(
    {
        "allowed_use",
        "hardware_presence_authority",
        "live_capture_authority",
        "calibration_authority",
        "robot_motion_authority",
        "contact_authority",
        "note",
    }
)
_PURCHASE_FIELDS = frozenset(
    {
        "state",
        "evidence_state",
        "reported_product_title",
        "order_reference",
        "received_utc",
        "receipt_photo_sha256",
    }
)
_IDENTITY_FIELDS = frozenset(
    {
        "evidence_state",
        "manufacturer",
        "model",
        "sensor",
        "sensor_megapixels",
        "sensor_optical_format",
        "sensor_active_width_px",
        "sensor_active_height_px",
        "pixel_size_um",
        "shutter",
        "color",
    }
)
_INTERFACE_FIELDS = frozenset(
    {
        "evidence_state",
        "device_interface",
        "host_backward_compatibility",
        "connector",
        "uvc_compliant",
        "output_pixel_format",
        "supported_operating_systems",
    }
)
_OPTICS_FIELDS = frozenset(
    {
        "evidence_state",
        "lens_supply",
        "lens_mount",
        "focal_length_mm",
        "focus_type",
        "default_focus_range",
        "aperture_type",
        "aperture_min_f_number",
        "aperture_max_f_number",
        "field_of_view_diagonal_deg",
        "field_of_view_horizontal_deg",
        "field_of_view_vertical_deg",
        "integral_ir_cut_filter",
    }
)
_MODE_FIELDS = frozenset(
    {
        "evidence_state",
        "host_bus",
        "width_px",
        "height_px",
        "maximum_fps",
        "pixel_format",
    }
)
_PACKAGE_FIELDS = frozenset(
    {
        "evidence_state",
        "metal_case_included",
        "usb_a_to_type_c_cable_included",
        "included_cable_length_m",
        "camera_board_width_mm",
        "camera_board_height_mm",
    }
)
_SIMULATION_PROXY_FIELDS = frozenset(
    {
        "state",
        "source_mode",
        "scale",
        "width_px",
        "height_px",
        "field_of_view",
        "projection",
        "resource_limits",
        "authority",
    }
)
_PROXY_SCALE_FIELDS = frozenset({"numerator", "denominator"})
_PROXY_FOV_FIELDS = frozenset(
    {"evidence_state", "horizontal_deg", "vertical_deg", "preservation"}
)
_PROXY_PROJECTION_FIELDS = frozenset(
    {"model", "intrinsics_derivation", "distortion_assumption", "calibration_state"}
)
_PROXY_RESOURCE_FIELDS = frozenset(
    {
        "synthetic_raster_max_width_px",
        "synthetic_raster_max_height_px",
        "synthetic_raster_max_pixels",
        "pixel_detector_maximum_image_pixels",
    }
)
_PROXY_AUTHORITY_FIELDS = frozenset(
    {
        "physical_calibration_authority",
        "live_capture_authority",
        "robot_motion_authority",
        "contact_authority",
    }
)
_PROVENANCE_FIELDS = frozenset(
    {
        "source_id",
        "source_kind",
        "publisher",
        "url",
        "accessed_date",
        "evidence_state",
        "claim_scope",
    }
)
_PHYSICAL_FIELDS = frozenset(
    {
        "state",
        "received",
        "manufacturer_label",
        "model_label",
        "sensor_label",
        "lens_marking",
        "case_width_mm",
        "case_height_mm",
        "case_depth_mm",
        "mass_g",
        "mount_pattern",
        "one_metre_focus_verified",
    }
)
_USB_FIELDS = frozenset(
    {
        "state",
        "vid",
        "pid",
        "serial_number",
        "persistent_device_path",
        "negotiated_bus_speed",
        "descriptor_snapshot_sha256",
    }
)
_COMMISSIONING_FIELDS = frozenset(
    {
        "state",
        "commissioned_mode",
        "camera_controls_snapshot_sha256",
        "measured_focus_distance_mm",
        "measured_field_of_view_deg",
        "measured_usable_coverage_mm",
        "intrinsics_artifact_sha256",
        "distortion_model",
        "static_extrinsic_artifact_sha256",
    }
)

_MODES = (
    ("USB_3_2_GEN_1", 1280, 720, 120.0, "YUY2"),
    ("USB_3_2_GEN_1", 1920, 1080, 60.0, "YUY2"),
    ("USB_3_2_GEN_1", 2720, 1536, 40.0, "YUY2"),
    ("USB_3_2_GEN_1", 3840, 2160, 20.0, "YUY2"),
    ("USB_3_2_GEN_1", 5472, 3648, 9.0, "YUY2"),
    ("USB_2_0", 1280, 720, 10.0, "YUY2"),
)
_PROVENANCE = (
    (
        "arducam_b0477_datasheet",
        "MANUFACTURER_DATASHEET",
        "Arducam",
        "https://www.arducam.com/downloads/datasheet/B0477_20MP_IMX283_USB3.0_Camera_Datasheet.pdf",
        "2026-09-05",
        _PUBLISHED_SOURCE,
        "published identity, sensor, interface, optics, modes, and electrical/mechanical specifications",
    ),
    (
        "arducam_b0477_product_page",
        "MANUFACTURER_PRODUCT_PAGE",
        "Arducam",
        "https://www.arducam.com/arducam-20mp-usb-3-0-camera-module-with-16mm-c-mount-lens-b0477.html",
        "2026-09-05",
        _PUBLISHED_SOURCE,
        "published package contents and product specifications",
    ),
    (
        "user_purchase_confirmation_2026_09_05",
        "USER_REPORT",
        "workspace user",
        None,
        "2026-09-05",
        _PURCHASE_SOURCE_EVIDENCE,
        "purchase state and reported seller product title only",
    ),
)
_OPEN_BLOCKERS = (
    "receive and photograph the exact delivered camera, lens, case, cable, labels, and package contents",
    "measure the case, mass, mount pattern, fastener thread and depth, lens projection, connector, and entrance-pupil offset",
    "record stable USB VID, PID, serial descriptor, persistent device path, descriptor snapshot, and negotiated USB bus speed",
    "prove the exact requested UVC mode and YUY2 format after close, reopen, host reboot, and cable reconnect",
    "prove that the included 16 mm lens focuses and mechanically locks at the installed working distance",
    "measure usable field of view, crop, orientation, distortion, corner illumination, glare, exposure, latency, buffering, and settling behavior",
    "commission and bind camera controls, intrinsics, distortion, static eye-to-hand extrinsic, support witness, and visibility evidence",
    "complete physical mounting, cable strain-relief, structural, collision, and held-out end-to-end qualification before live motion or contact",
)


class CameraProfileError(ValueError):
    """A purchased-camera profile is malformed, altered, or overclaims evidence."""


@dataclass(frozen=True, slots=True)
class PublishedCameraMode:
    """One manufacturer-published, locally unverified UVC mode."""

    host_bus: str
    width_px: int
    height_px: int
    maximum_fps: float
    pixel_format: str
    evidence_state: str = _PUBLISHED


@dataclass(frozen=True, slots=True)
class CameraProfileProvenance:
    """Source and evidence class for a bounded group of profile claims."""

    source_id: str
    source_kind: str
    publisher: str
    url: str | None
    accessed_date: date
    evidence_state: str
    claim_scope: str


@dataclass(frozen=True, slots=True)
class SyntheticCameraProjection:
    """Published-FOV-derived projection used only by bounded simulation.

    The two published FOV axes are preserved independently.  They are not
    treated as a physical intrinsic calibration, even if they imply different
    horizontal and vertical focal lengths in pixels.
    """

    source_width_px: int
    source_height_px: int
    scale_numerator: int
    scale_denominator: int
    width_px: int
    height_px: int
    horizontal_fov_deg: float
    vertical_fov_deg: float
    fx_px: float
    fy_px: float
    cx_px: float
    cy_px: float
    synthetic_raster_max_width_px: int
    synthetic_raster_max_height_px: int
    synthetic_raster_max_pixels: int
    pixel_detector_maximum_image_pixels: int
    state: str = "SYNTHETIC_ONLY_NOT_PHYSICAL_CALIBRATION"
    calibration_state: str = "DERIVED_NOMINAL_NOT_PHYSICAL_CALIBRATION"

    @property
    def pixel_count(self) -> int:
        return self.width_px * self.height_px

    @property
    def scale(self) -> float:
        return self.scale_numerator / self.scale_denominator

    @property
    def aspect_ratio(self) -> float:
        return self.width_px / self.height_px

    @property
    def within_current_raster_limits(self) -> bool:
        """Whether this proxy fits both renderer and detector pixel bounds."""

        return (
            self.width_px <= self.synthetic_raster_max_width_px
            and self.height_px <= self.synthetic_raster_max_height_px
            and self.pixel_count <= self.synthetic_raster_max_pixels
            and self.pixel_count <= self.pixel_detector_maximum_image_pixels
        )

    def recovered_field_of_view_deg(self) -> tuple[float, float]:
        """Recover H/V FOV from the derived nominal intrinsics."""

        horizontal = math.degrees(
            2.0 * math.atan(self.width_px / (2.0 * self.fx_px))
        )
        vertical = math.degrees(
            2.0 * math.atan(self.height_px / (2.0 * self.fy_px))
        )
        return horizontal, vertical


@dataclass(frozen=True, slots=True)
class PurchasedCameraProfile:
    """Immutable, zero-live-authority view of the purchased B0477 profile."""

    source_path: Path | None
    source_file_sha256: str
    canonical_sha256: str
    profile_id: str
    record_state: str
    reported_product_title: str
    manufacturer: str
    model: str
    sensor: str
    lens_mount: str
    focal_length_mm: float
    published_modes: tuple[PublishedCameraMode, ...]
    simulation_proxy: SyntheticCameraProjection
    provenance: tuple[CameraProfileProvenance, ...]
    physical_observation_state: str
    usb_observation_state: str
    commissioning_state: str
    open_blockers: tuple[str, ...]
    authority: Mapping[str, bool]

    @property
    def live_ready(self) -> bool:
        """Always false for this purchase-time schema."""

        return False

    def published_mode(
        self, host_bus: str, width_px: int, height_px: int
    ) -> PublishedCameraMode | None:
        """Return a published claim, never a measurement or commissioned mode."""

        return next(
            (
                mode
                for mode in self.published_modes
                if mode.host_bus == host_bus
                and mode.width_px == width_px
                and mode.height_px == height_px
            ),
            None,
        )


def _reject_constant(value: str) -> None:
    raise CameraProfileError(f"camera profile contains invalid JSON constant {value!r}")


def _object_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CameraProfileError(f"camera profile contains duplicate key {key!r}")
        result[key] = value
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CameraProfileError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual == expected:
        return
    raise CameraProfileError(
        f"{label} fields differ; missing={sorted(expected - actual)}, "
        f"unknown={sorted(actual - expected)}"
    )


def _exact(value: object, expected: object, label: str) -> None:
    # bool is an int subclass, so explicitly prevent True from matching 1.
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CameraProfileError(f"{label} must be numeric value {expected!r}")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric != float(expected):
            raise CameraProfileError(f"{label} must be {expected!r}, got {value!r}")
        if isinstance(expected, int) and not isinstance(value, int):
            raise CameraProfileError(f"{label} must be integer value {expected!r}")
        return
    if type(value) is not type(expected) or value != expected:
        raise CameraProfileError(f"{label} must be {expected!r}, got {value!r}")


def _must_be_null(value: object, label: str) -> None:
    if value is not None:
        raise CameraProfileError(
            f"{label} must remain null in PURCHASED_PENDING_RECEIPT state"
        )


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    """Encode one validated document independently of source formatting."""

    try:
        encoded = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CameraProfileError("camera profile cannot be canonicalized") from exc
    return encoded.encode("utf-8")


def _validate_authority(document: Mapping[str, Any]) -> Mapping[str, bool]:
    authority = _mapping(document.get("authority"), "authority")
    _exact_fields(authority, _AUTHORITY_FIELDS, "authority")
    _exact(authority.get("allowed_use"), "REFERENCE_ONLY", "authority.allowed_use")
    authority_flags: dict[str, bool] = {}
    for field in (
        "hardware_presence_authority",
        "live_capture_authority",
        "calibration_authority",
        "robot_motion_authority",
        "contact_authority",
    ):
        _exact(authority.get(field), False, f"authority.{field}")
        authority_flags[field] = False
    _exact(authority.get("note"), _AUTHORITY_NOTE, "authority.note")
    return MappingProxyType(authority_flags)


def _validate_purchase(document: Mapping[str, Any]) -> str:
    purchase = _mapping(document.get("purchase"), "purchase")
    _exact_fields(purchase, _PURCHASE_FIELDS, "purchase")
    _exact(purchase.get("state"), _PURCHASED, "purchase.state")
    _exact(
        purchase.get("evidence_state"),
        _PURCHASE_EVIDENCE,
        "purchase.evidence_state",
    )
    _exact(
        purchase.get("reported_product_title"),
        _PRODUCT_TITLE,
        "purchase.reported_product_title",
    )
    for field in ("order_reference", "received_utc", "receipt_photo_sha256"):
        _must_be_null(purchase.get(field), f"purchase.{field}")
    return _PRODUCT_TITLE


def _validate_published_identity(document: Mapping[str, Any]) -> tuple[str, str, str]:
    identity = _mapping(document.get("published_identity"), "published_identity")
    _exact_fields(identity, _IDENTITY_FIELDS, "published_identity")
    expected = {
        "evidence_state": _PUBLISHED,
        "manufacturer": "Arducam",
        "model": "B0477",
        "sensor": "Sony IMX283",
        "sensor_megapixels": 20.0,
        "sensor_optical_format": "1-inch",
        "sensor_active_width_px": 5496,
        "sensor_active_height_px": 3672,
        "pixel_size_um": 2.4,
        "shutter": "rolling",
        "color": True,
    }
    for field, value in expected.items():
        _exact(identity.get(field), value, f"published_identity.{field}")
    return "Arducam", "B0477", "Sony IMX283"


def _validate_published_interface(document: Mapping[str, Any]) -> None:
    interface = _mapping(document.get("published_interface"), "published_interface")
    _exact_fields(interface, _INTERFACE_FIELDS, "published_interface")
    expected = {
        "evidence_state": _PUBLISHED,
        "device_interface": "USB 3.2 Gen 1",
        "host_backward_compatibility": "USB 2.0",
        "connector": "USB Type-C",
        "uvc_compliant": True,
        "output_pixel_format": "YUY2",
    }
    for field, value in expected.items():
        _exact(interface.get(field), value, f"published_interface.{field}")
    operating_systems = interface.get("supported_operating_systems")
    if not isinstance(operating_systems, list):
        raise CameraProfileError(
            "published_interface.supported_operating_systems must be an array"
        )
    if tuple(operating_systems) != ("Windows", "Linux") or any(
        not isinstance(item, str) for item in operating_systems
    ):
        raise CameraProfileError(
            "published_interface.supported_operating_systems must be exactly "
            "['Windows', 'Linux']"
        )


def _validate_published_optics(document: Mapping[str, Any]) -> tuple[str, float]:
    optics = _mapping(document.get("published_optics"), "published_optics")
    _exact_fields(optics, _OPTICS_FIELDS, "published_optics")
    expected = {
        "evidence_state": _PUBLISHED,
        "lens_supply": "included",
        "lens_mount": "C-mount",
        "focal_length_mm": 16.0,
        "focus_type": "manual",
        "default_focus_range": "5m-infinity",
        "aperture_type": "manual",
        "aperture_min_f_number": 1.4,
        "aperture_max_f_number": 16.0,
        "field_of_view_diagonal_deg": 60.0,
        "field_of_view_horizontal_deg": 49.0,
        "field_of_view_vertical_deg": 38.0,
        "integral_ir_cut_filter": True,
    }
    for field, value in expected.items():
        _exact(optics.get(field), value, f"published_optics.{field}")
    return "C-mount", 16.0


def _validate_modes(document: Mapping[str, Any]) -> tuple[PublishedCameraMode, ...]:
    raw_modes = document.get("published_native_modes")
    if not isinstance(raw_modes, list):
        raise CameraProfileError("published_native_modes must be an array")
    if len(raw_modes) != len(_MODES):
        raise CameraProfileError(
            f"published_native_modes must contain exactly {len(_MODES)} modes"
        )
    result: list[PublishedCameraMode] = []
    for index, expected in enumerate(_MODES):
        mode = _mapping(raw_modes[index], f"published_native_modes[{index}]")
        _exact_fields(mode, _MODE_FIELDS, f"published_native_modes[{index}]")
        _exact(
            mode.get("evidence_state"),
            _PUBLISHED,
            f"published_native_modes[{index}].evidence_state",
        )
        for field, value in zip(
            ("host_bus", "width_px", "height_px", "maximum_fps", "pixel_format"),
            expected,
        ):
            _exact(mode.get(field), value, f"published_native_modes[{index}].{field}")
        result.append(
            PublishedCameraMode(
                host_bus=expected[0],
                width_px=expected[1],
                height_px=expected[2],
                maximum_fps=expected[3],
                pixel_format=expected[4],
            )
        )
    return tuple(result)


def _validate_published_package(document: Mapping[str, Any]) -> None:
    package = _mapping(document.get("published_package"), "published_package")
    _exact_fields(package, _PACKAGE_FIELDS, "published_package")
    expected = {
        "evidence_state": _PUBLISHED,
        "metal_case_included": True,
        "usb_a_to_type_c_cable_included": True,
        "included_cable_length_m": 1.0,
        "camera_board_width_mm": 34.0,
        "camera_board_height_mm": 34.0,
    }
    for field, value in expected.items():
        _exact(package.get(field), value, f"published_package.{field}")


def _validate_simulation_proxy(document: Mapping[str, Any]) -> SyntheticCameraProjection:
    """Validate and derive an explicitly non-calibrated half-scale projection."""

    proxy = _mapping(document.get("simulation_proxy"), "simulation_proxy")
    _exact_fields(proxy, _SIMULATION_PROXY_FIELDS, "simulation_proxy")
    state = "SYNTHETIC_ONLY_NOT_PHYSICAL_CALIBRATION"
    _exact(proxy.get("state"), state, "simulation_proxy.state")

    source_mode = _mapping(proxy.get("source_mode"), "simulation_proxy.source_mode")
    _exact_fields(source_mode, _MODE_FIELDS, "simulation_proxy.source_mode")
    source_expected = (_PUBLISHED, "USB_3_2_GEN_1", 5472, 3648, 9.0, "YUY2")
    for field, value in zip(
        (
            "evidence_state",
            "host_bus",
            "width_px",
            "height_px",
            "maximum_fps",
            "pixel_format",
        ),
        source_expected,
    ):
        _exact(source_mode.get(field), value, f"simulation_proxy.source_mode.{field}")

    scale = _mapping(proxy.get("scale"), "simulation_proxy.scale")
    _exact_fields(scale, _PROXY_SCALE_FIELDS, "simulation_proxy.scale")
    _exact(scale.get("numerator"), 1, "simulation_proxy.scale.numerator")
    _exact(scale.get("denominator"), 2, "simulation_proxy.scale.denominator")
    width = 2736
    height = 1824
    _exact(proxy.get("width_px"), width, "simulation_proxy.width_px")
    _exact(proxy.get("height_px"), height, "simulation_proxy.height_px")
    if width * 2 != source_expected[2] or height * 2 != source_expected[3]:
        raise CameraProfileError("simulation proxy must be an exact 1/2 source-mode scale")
    if width * source_expected[3] != height * source_expected[2]:
        raise CameraProfileError("simulation proxy must preserve native aspect exactly")

    field_of_view = _mapping(
        proxy.get("field_of_view"), "simulation_proxy.field_of_view"
    )
    _exact_fields(field_of_view, _PROXY_FOV_FIELDS, "simulation_proxy.field_of_view")
    fov_expected = {
        "evidence_state": "COPIED_FROM_MANUFACTURER_PUBLISHED_UNMEASURED",
        "horizontal_deg": 49.0,
        "vertical_deg": 38.0,
        "preservation": "UNCHANGED_FROM_PUBLISHED_CLAIM",
    }
    for field, value in fov_expected.items():
        _exact(field_of_view.get(field), value, f"simulation_proxy.field_of_view.{field}")

    projection = _mapping(proxy.get("projection"), "simulation_proxy.projection")
    _exact_fields(projection, _PROXY_PROJECTION_FIELDS, "simulation_proxy.projection")
    projection_expected = {
        "model": "centered_pinhole",
        "intrinsics_derivation": (
            "fx=width/(2*tan(horizontal_fov/2)); "
            "fy=height/(2*tan(vertical_fov/2)); cx=width/2; cy=height/2"
        ),
        "distortion_assumption": "ZERO_FOR_SYNTHETIC_PROXY_ONLY",
        "calibration_state": "DERIVED_NOMINAL_NOT_PHYSICAL_CALIBRATION",
    }
    for field, value in projection_expected.items():
        _exact(projection.get(field), value, f"simulation_proxy.projection.{field}")

    limits = _mapping(
        proxy.get("resource_limits"), "simulation_proxy.resource_limits"
    )
    _exact_fields(limits, _PROXY_RESOURCE_FIELDS, "simulation_proxy.resource_limits")
    limit_expected = {
        "synthetic_raster_max_width_px": 4096,
        "synthetic_raster_max_height_px": 4096,
        "synthetic_raster_max_pixels": 16_777_216,
        "pixel_detector_maximum_image_pixels": 12_000_000,
    }
    for field, value in limit_expected.items():
        _exact(limits.get(field), value, f"simulation_proxy.resource_limits.{field}")

    authority = _mapping(proxy.get("authority"), "simulation_proxy.authority")
    _exact_fields(authority, _PROXY_AUTHORITY_FIELDS, "simulation_proxy.authority")
    for field in _PROXY_AUTHORITY_FIELDS:
        _exact(authority.get(field), False, f"simulation_proxy.authority.{field}")

    fx = width / (2.0 * math.tan(math.radians(49.0 / 2.0)))
    fy = height / (2.0 * math.tan(math.radians(38.0 / 2.0)))
    typed = SyntheticCameraProjection(
        source_width_px=source_expected[2],
        source_height_px=source_expected[3],
        scale_numerator=1,
        scale_denominator=2,
        width_px=width,
        height_px=height,
        horizontal_fov_deg=49.0,
        vertical_fov_deg=38.0,
        fx_px=fx,
        fy_px=fy,
        cx_px=width / 2.0,
        cy_px=height / 2.0,
        synthetic_raster_max_width_px=limit_expected[
            "synthetic_raster_max_width_px"
        ],
        synthetic_raster_max_height_px=limit_expected[
            "synthetic_raster_max_height_px"
        ],
        synthetic_raster_max_pixels=limit_expected["synthetic_raster_max_pixels"],
        pixel_detector_maximum_image_pixels=limit_expected[
            "pixel_detector_maximum_image_pixels"
        ],
    )
    if not typed.within_current_raster_limits:
        raise CameraProfileError("simulation proxy exceeds a current raster limit")
    return typed


def _validate_provenance(
    document: Mapping[str, Any],
) -> tuple[CameraProfileProvenance, ...]:
    raw_sources = document.get("provenance")
    if not isinstance(raw_sources, list) or len(raw_sources) != len(_PROVENANCE):
        raise CameraProfileError("provenance must contain exactly three source records")
    result: list[CameraProfileProvenance] = []
    for index, expected in enumerate(_PROVENANCE):
        source = _mapping(raw_sources[index], f"provenance[{index}]")
        _exact_fields(source, _PROVENANCE_FIELDS, f"provenance[{index}]")
        fields = (
            "source_id",
            "source_kind",
            "publisher",
            "url",
            "accessed_date",
            "evidence_state",
            "claim_scope",
        )
        for field, value in zip(fields, expected):
            _exact(source.get(field), value, f"provenance[{index}].{field}")
        try:
            accessed = date.fromisoformat(expected[4])
        except ValueError as exc:  # pragma: no cover - constants are test-pinned
            raise CameraProfileError("invalid built-in provenance date") from exc
        result.append(
            CameraProfileProvenance(
                source_id=expected[0],
                source_kind=expected[1],
                publisher=expected[2],
                url=expected[3],
                accessed_date=accessed,
                evidence_state=expected[5],
                claim_scope=expected[6],
            )
        )
    return tuple(result)


def _validate_open_observations(document: Mapping[str, Any]) -> tuple[str, str, str]:
    physical = _mapping(document.get("physical_observation"), "physical_observation")
    _exact_fields(physical, _PHYSICAL_FIELDS, "physical_observation")
    physical_state = "OPEN_PENDING_RECEIPT_INSPECTION"
    _exact(physical.get("state"), physical_state, "physical_observation.state")
    for field in _PHYSICAL_FIELDS - {"state"}:
        _must_be_null(physical.get(field), f"physical_observation.{field}")

    usb = _mapping(document.get("usb_observation"), "usb_observation")
    _exact_fields(usb, _USB_FIELDS, "usb_observation")
    usb_state = "OPEN_PENDING_ENUMERATION"
    _exact(usb.get("state"), usb_state, "usb_observation.state")
    for field in _USB_FIELDS - {"state"}:
        _must_be_null(usb.get(field), f"usb_observation.{field}")

    commissioning = _mapping(document.get("commissioning"), "commissioning")
    _exact_fields(commissioning, _COMMISSIONING_FIELDS, "commissioning")
    commissioning_state = "OPEN_NOT_COMMISSIONED"
    _exact(commissioning.get("state"), commissioning_state, "commissioning.state")
    for field in _COMMISSIONING_FIELDS - {"state"}:
        _must_be_null(commissioning.get(field), f"commissioning.{field}")
    return physical_state, usb_state, commissioning_state


def _validate_open_blockers(document: Mapping[str, Any]) -> tuple[str, ...]:
    blockers = document.get("open_blockers")
    if not isinstance(blockers, list) or any(not isinstance(item, str) for item in blockers):
        raise CameraProfileError("open_blockers must be an array of strings")
    if tuple(blockers) != _OPEN_BLOCKERS:
        raise CameraProfileError("open_blockers must retain the exact purchase-time holds")
    return _OPEN_BLOCKERS


def parse_camera_profile_json(
    payload: bytes, *, source_path: Path | None = None
) -> PurchasedCameraProfile:
    """Parse bounded UTF-8 JSON and enforce the exact B0477 purchase schema.

    ``source_file_sha256`` binds the original bytes. ``canonical_sha256`` binds
    the JSON meaning and therefore remains stable across whitespace or key
    ordering changes. Neither digest implies that any camera was observed.
    """

    if not isinstance(payload, bytes):
        raise CameraProfileError("camera profile payload must be bytes")
    if not payload:
        raise CameraProfileError("camera profile is empty")
    if len(payload) > MAX_CAMERA_PROFILE_BYTES:
        raise CameraProfileError(
            f"camera profile exceeds {MAX_CAMERA_PROFILE_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CameraProfileError("camera profile must be UTF-8") from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise CameraProfileError(f"invalid camera profile JSON: {exc}") from exc
    document = _mapping(decoded, "root")
    _exact_fields(document, _ROOT_FIELDS, "root")
    _exact(document.get("schema"), CAMERA_PROFILE_SCHEMA, "schema")
    _exact(document.get("schema_version"), 1, "schema_version")
    _exact(
        document.get("profile_id"),
        "arducam-b0477-imx283-16mm-purchased-001",
        "profile_id",
    )
    _exact(document.get("record_state"), _PURCHASED, "record_state")

    authority = _validate_authority(document)
    product_title = _validate_purchase(document)
    manufacturer, model, sensor = _validate_published_identity(document)
    _validate_published_interface(document)
    lens_mount, focal_length_mm = _validate_published_optics(document)
    modes = _validate_modes(document)
    _validate_published_package(document)
    simulation_proxy = _validate_simulation_proxy(document)
    provenance = _validate_provenance(document)
    physical_state, usb_state, commissioning_state = _validate_open_observations(
        document
    )
    blockers = _validate_open_blockers(document)

    raw_digest = hashlib.sha256(payload).hexdigest()
    canonical_digest = hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return PurchasedCameraProfile(
        source_path=source_path.resolve() if source_path is not None else None,
        source_file_sha256=raw_digest,
        canonical_sha256=canonical_digest,
        profile_id="arducam-b0477-imx283-16mm-purchased-001",
        record_state=_PURCHASED,
        reported_product_title=product_title,
        manufacturer=manufacturer,
        model=model,
        sensor=sensor,
        lens_mount=lens_mount,
        focal_length_mm=focal_length_mm,
        published_modes=modes,
        simulation_proxy=simulation_proxy,
        provenance=provenance,
        physical_observation_state=physical_state,
        usb_observation_state=usb_state,
        commissioning_state=commissioning_state,
        open_blockers=blockers,
        authority=authority,
    )


def load_camera_profile(
    path: Path | str = DEFAULT_B0477_CAMERA_PROFILE,
) -> PurchasedCameraProfile:
    """Read and validate the selected camera profile without touching hardware."""

    source_path = Path(path)
    try:
        payload = source_path.read_bytes()
    except OSError as exc:
        raise CameraProfileError(f"cannot read camera profile {source_path}: {exc}") from exc
    return parse_camera_profile_json(payload, source_path=source_path)


__all__ = [
    "CAMERA_PROFILE_SCHEMA",
    "DEFAULT_B0477_CAMERA_PROFILE",
    "MAX_CAMERA_PROFILE_BYTES",
    "CameraProfileError",
    "CameraProfileProvenance",
    "PublishedCameraMode",
    "PurchasedCameraProfile",
    "SyntheticCameraProjection",
    "load_camera_profile",
    "parse_camera_profile_json",
]
