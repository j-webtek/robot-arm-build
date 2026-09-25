"""Strict importer for simulation-only keyboard and phone target seeds.

The values loaded here are deliberately unable to masquerade as measured
calibration.  The importer cross-checks the target file against the controlled
RC03 workcell layout and rejects any profile that does not explicitly carry the
simulation-only/no-release markers.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.models.frames import Point3Mm


TARGET_SCHEMA = "rocell.nominal_target_profiles.v1"
TARGET_STATUS = "SIMULATION_ONLY_NOMINAL_UNMEASURED"


class TargetMapError(ValueError):
    """A nominal target profile is malformed or misaligned with RC03."""


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TargetMapError(f"Duplicate target-map field {key!r}")
        result[key] = value
    return result


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TargetMapError(f"{label} must be a JSON object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetMapError(f"{label} must be a non-empty string")
    return value.strip()


def _sha256(value: object, label: str) -> str:
    digest = _text(value, label).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise TargetMapError(f"{label} must be a SHA-256 digest")
    return digest


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TargetMapError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise TargetMapError(f"{label} must be a finite number")
    return result


def _pair(value: object, label: str, *, positive: bool = False) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise TargetMapError(f"{label} must contain exactly two numbers")
    result = (_number(value[0], f"{label}[0]"), _number(value[1], f"{label}[1]"))
    if positive and (result[0] <= 0.0 or result[1] <= 0.0):
        raise TargetMapError(f"{label} values must be greater than zero")
    return result


def _rectangle(value: object, label: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise TargetMapError(f"{label} must contain left, front, right, and rear")
    result = tuple(_number(item, f"{label}[{index}]") for index, item in enumerate(value))
    if result[0] >= result[2] or result[1] >= result[3]:
        raise TargetMapError(f"{label} must have positive area")
    return result[0], result[1], result[2], result[3]


def _sequence_text(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TargetMapError(f"{label} must be a non-empty array")
    return tuple(_text(item, f"{label} item") for item in value)


def _close(left: float, right: float, *, tolerance: float = 1e-9) -> bool:
    return abs(left - right) <= tolerance


@dataclass(frozen=True, slots=True)
class TargetRegion:
    """One conservative rectangular target in the RC03 board frame."""

    device: str
    target_id: str
    center: Point3Mm
    half_extent_x_mm: float
    half_extent_y_mm: float
    source_state: str = TARGET_STATUS

    def __post_init__(self) -> None:
        if self.device not in {"keyboard", "phone"}:
            raise TargetMapError("device must be keyboard or phone")
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        if self.center.frame != "board":
            raise TargetMapError("nominal target center must be in the board frame")
        for label, value in (
            ("half_extent_x_mm", self.half_extent_x_mm),
            ("half_extent_y_mm", self.half_extent_y_mm),
        ):
            result = _number(value, label)
            if result <= 0.0:
                raise TargetMapError(f"{label} must be greater than zero")
            object.__setattr__(self, label, result)
        if self.source_state != TARGET_STATUS:
            raise TargetMapError("nominal target must retain its simulation-only source state")

    @property
    def safe_rectangle_board_mm(self) -> tuple[float, float, float, float]:
        return (
            self.center.x - self.half_extent_x_mm,
            self.center.y - self.half_extent_y_mm,
            self.center.x + self.half_extent_x_mm,
            self.center.y + self.half_extent_y_mm,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "target_id": self.target_id,
            "center_board_mm": [self.center.x, self.center.y, self.center.z],
            "half_extent_mm": [self.half_extent_x_mm, self.half_extent_y_mm],
            "source_state": self.source_state,
            "physical_execution_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class NominalTargetCatalog:
    profile_path: Path
    workcell_layout_path: Path
    design_revision: str
    keyboard_profile_id: str
    phone_profile_id: str
    keyboard_semantic_profile_id: str
    phone_semantic_profile_id: str
    keyboard_semantic_profile_sha256: str
    phone_semantic_profile_sha256: str
    keyboard_origin_board_xy_mm: tuple[float, float]
    phone_origin_board_xy_mm: tuple[float, float]
    keyboard_target_plane_z_board_mm: float
    phone_target_plane_z_board_mm: float
    keyboard_targets: Mapping[str, TargetRegion]
    phone_targets: Mapping[str, TargetRegion]
    content_sha256: str
    schema: str = TARGET_SCHEMA
    status: str = TARGET_STATUS
    simulation_only: bool = True

    def __post_init__(self) -> None:
        if self.schema != TARGET_SCHEMA or self.status != TARGET_STATUS:
            raise TargetMapError("target catalog lost its simulation-only contract")
        if self.simulation_only is not True:
            raise TargetMapError("target catalog must always be simulation-only")
        for field_name in (
            "keyboard_profile_id",
            "phone_profile_id",
            "keyboard_semantic_profile_id",
            "phone_semantic_profile_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        for field_name in (
            "keyboard_semantic_profile_sha256",
            "phone_semantic_profile_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _sha256(getattr(self, field_name), field_name),
            )
        for field_name in (
            "keyboard_origin_board_xy_mm",
            "phone_origin_board_xy_mm",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or len(value) != 2:
                raise TargetMapError(f"{field_name} must be an immutable XY pair")
            object.__setattr__(
                self,
                field_name,
                tuple(_number(item, field_name) for item in value),
            )
        for field_name in (
            "keyboard_target_plane_z_board_mm",
            "phone_target_plane_z_board_mm",
        ):
            object.__setattr__(
                self,
                field_name,
                _number(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "keyboard_targets", MappingProxyType(dict(self.keyboard_targets)))
        object.__setattr__(self, "phone_targets", MappingProxyType(dict(self.phone_targets)))

    def resolve(self, device: str, target_id: str) -> TargetRegion:
        mapping = self.keyboard_targets if device == "keyboard" else self.phone_targets if device == "phone" else None
        if mapping is None:
            raise TargetMapError(f"Unknown device {device!r}")
        try:
            return mapping[target_id]
        except KeyError as exc:
            raise TargetMapError(f"Unknown {device} target {target_id!r}") from exc

    def semantic_profile_id_for(self, device: str) -> str:
        """Return the semantic compiler profile explicitly bound to a target map."""

        if device == "keyboard":
            return self.keyboard_semantic_profile_id
        if device == "phone":
            return self.phone_semantic_profile_id
        raise TargetMapError(f"Unknown device {device!r}")

    def local_to_board(self, point: Point3Mm, *, device: str) -> Point3Mm:
        """Project a nominal device-local surface point into the board frame.

        This translation-only mapping is suitable for simulation and model-contract
        evaluation. It is not a measured placement transform and grants no physical
        authority.
        """

        if not isinstance(point, Point3Mm):
            raise TypeError("point must be a Point3Mm")
        if device == "keyboard":
            expected_frame = "keyboard_local"
            origin = self.keyboard_origin_board_xy_mm
            plane_z = self.keyboard_target_plane_z_board_mm
        elif device == "phone":
            expected_frame = "phone_screen_local"
            origin = self.phone_origin_board_xy_mm
            plane_z = self.phone_target_plane_z_board_mm
        else:
            raise TargetMapError(f"Unknown device {device!r}")
        if point.frame != expected_frame:
            raise TargetMapError(
                f"{device} local point must use frame {expected_frame!r}, got {point.frame!r}"
            )
        return Point3Mm(
            "board",
            origin[0] + point.x,
            origin[1] + point.y,
            plane_z + point.z,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "simulation_only": True,
            "physical_release_effect": "NONE",
            "design_revision": self.design_revision,
            "profile_sha256": self.content_sha256,
            "profiles": {
                "keyboard": {
                    "profile_id": self.keyboard_profile_id,
                    "semantic_profile_id": self.keyboard_semantic_profile_id,
                    "semantic_profile_sha256": self.keyboard_semantic_profile_sha256,
                    "target_count": len(self.keyboard_targets),
                    "origin_board_xy_mm": list(self.keyboard_origin_board_xy_mm),
                    "target_plane_z_board_mm": self.keyboard_target_plane_z_board_mm,
                },
                "phone": {
                    "profile_id": self.phone_profile_id,
                    "semantic_profile_id": self.phone_semantic_profile_id,
                    "semantic_profile_sha256": self.phone_semantic_profile_sha256,
                    "target_count": len(self.phone_targets),
                    "origin_board_xy_mm": list(self.phone_origin_board_xy_mm),
                    "target_plane_z_board_mm": self.phone_target_plane_z_board_mm,
                },
            },
        }


def _load_json(path: Path, label: str) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TargetMapError(f"Could not read {label} {path}: {exc}") from exc
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                TargetMapError(f"Nonfinite target-map value {constant!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TargetMapError) as exc:
        raise TargetMapError(f"Could not parse {label} {path}: {exc}") from exc
    return _object(value, label), raw


def _device_targets(
    *,
    device_name: str,
    profile: Mapping[str, Any],
    layout_device: Mapping[str, Any],
) -> tuple[
    str,
    str,
    str,
    tuple[float, float],
    float,
    Mapping[str, TargetRegion],
]:
    profile_id = _text(profile.get("profile_id"), f"{device_name}.profile_id")
    semantic_profile_id = _text(
        profile.get("semantic_profile_id"),
        f"{device_name}.semantic_profile_id",
    )
    semantic_profile_sha256 = _sha256(
        profile.get("semantic_profile_sha256"),
        f"{device_name}.semantic_profile_sha256",
    )
    source_state = _text(profile.get("source_state"), f"{device_name}.source_state")
    if not source_state.startswith("SYNTHETIC_"):
        raise TargetMapError(f"{device_name}.source_state must remain synthetic")

    expected_frame = (
        "keyboard_nominal" if device_name == "keyboard" else "phone_screen_nominal"
    )
    expected_definition = (
        "x from device left, y from device front, z up"
        if device_name == "keyboard"
        else "x from device left, y from USB/device front, z normal to screen"
    )
    if profile.get("coordinate_frame") != expected_frame:
        raise TargetMapError(f"{device_name} coordinate_frame changed")
    if profile.get("coordinate_definition") != expected_definition:
        raise TargetMapError(f"{device_name} coordinate_definition changed")

    profile_origin = _pair(
        profile.get("device_origin_board_xy_mm"),
        f"{device_name}.device_origin_board_xy_mm",
    )
    layout_origin = _pair(
        layout_device.get("nominal_origin_xy"),
        f"layout.devices.{device_name}.nominal_origin_xy",
    )
    if any(not _close(left, right) for left, right in zip(profile_origin, layout_origin)):
        raise TargetMapError(f"{device_name} origin is not aligned with workcell_layout.json")

    if device_name == "keyboard":
        profile_size_value = profile.get("device_size_mm")
        layout_size_value = layout_device.get("nominal_size")
    else:
        profile_size_value = profile.get("device_size_width_length_thickness_mm")
        layout_size_value = layout_device.get("configured_size")
    if not isinstance(profile_size_value, list) or len(profile_size_value) != 3:
        raise TargetMapError(f"{device_name} size must contain three numbers")
    if not isinstance(layout_size_value, list) or len(layout_size_value) != 3:
        raise TargetMapError(f"layout {device_name} size must contain three numbers")
    size = tuple(_number(value, f"{device_name} size") for value in profile_size_value)
    layout_size = tuple(_number(value, f"layout {device_name} size") for value in layout_size_value)
    if any(not _close(left, right) for left, right in zip(size, layout_size)):
        raise TargetMapError(f"{device_name} size is not aligned with workcell_layout.json")

    target_z = _number(profile.get("target_plane_z_board_mm"), f"{device_name}.target_plane_z")
    expected_z = (
        _number(layout_device.get("support_plane_z"), "keyboard support plane") + size[2]
        if device_name == "keyboard"
        else _number(layout_device.get("nominal_screen_plane_z"), "phone screen plane")
    )
    if not _close(target_z, expected_z):
        raise TargetMapError(f"{device_name} target plane is not aligned with workcell_layout.json")

    default_half_extent = _pair(
        profile.get("key_half_extent_mm"),
        f"{device_name}.key_half_extent_mm",
        positive=True,
    )
    keyboard_pitch = None
    phone_target_region = None
    if device_name == "keyboard":
        keyboard_pitch = _number(profile.get("pitch_mm"), "keyboard.pitch_mm")
        if keyboard_pitch <= 0.0:
            raise TargetMapError("keyboard.pitch_mm must be positive")
    else:
        if profile.get("orientation") != "portrait_usb_at_device_front":
            raise TargetMapError("phone orientation changed")
        if profile.get("ui_state_id") != "KEYBOARD_LOWER":
            raise TargetMapError("phone UI state must be KEYBOARD_LOWER")
        phone_target_region = _rectangle(
            profile.get("synthetic_gboard_region_local_rect_mm"),
            "phone.synthetic_gboard_region_local_rect_mm",
        )
        if (
            phone_target_region[0] < 0.0
            or phone_target_region[1] < 0.0
            or phone_target_region[2] > size[0]
            or phone_target_region[3] > size[1]
        ):
            raise TargetMapError("Synthetic Gboard region leaves the phone envelope")
    result: dict[str, TargetRegion] = {}

    def add(target_id: str, local_xy: tuple[float, float], half_extent: tuple[float, float]) -> None:
        if target_id in result:
            raise TargetMapError(f"Duplicate {device_name} target {target_id!r}")
        left = local_xy[0] - half_extent[0]
        front = local_xy[1] - half_extent[1]
        right = local_xy[0] + half_extent[0]
        rear = local_xy[1] + half_extent[1]
        if left < 0.0 or front < 0.0 or right > size[0] or rear > size[1]:
            raise TargetMapError(f"{device_name} target {target_id!r} leaves its device envelope")
        if phone_target_region is not None and not (
            phone_target_region[0] <= left <= right <= phone_target_region[2]
            and phone_target_region[1] <= front <= rear <= phone_target_region[3]
        ):
            raise TargetMapError(
                f"phone target {target_id!r} leaves the declared synthetic Gboard region"
            )
        result[target_id] = TargetRegion(
            device=device_name,
            target_id=target_id,
            center=Point3Mm(
                "board",
                profile_origin[0] + local_xy[0],
                profile_origin[1] + local_xy[1],
                target_z,
            ),
            half_extent_x_mm=half_extent[0],
            half_extent_y_mm=half_extent[1],
        )

    rows = profile.get("rows")
    if not isinstance(rows, list) or not rows:
        raise TargetMapError(f"{device_name}.rows must be a non-empty array")
    identifier_field = "key_ids" if device_name == "keyboard" else "target_ids"
    for row_index, raw_row in enumerate(rows):
        row = _object(raw_row, f"{device_name}.rows[{row_index}]")
        identifiers = _sequence_text(
            row.get(identifier_field),
            f"{device_name}.rows[{row_index}].{identifier_field}",
        )
        first = _pair(row.get("first_center_xy_mm"), "first_center_xy_mm")
        step = _pair(row.get("step_xy_mm"), "step_xy_mm")
        if _close(step[0], 0.0) and _close(step[1], 0.0):
            raise TargetMapError("target row step must be nonzero")
        if keyboard_pitch is not None and (
            not _close(step[0], keyboard_pitch) or not _close(step[1], 0.0)
        ):
            raise TargetMapError("keyboard row spacing must match pitch_mm along +X")
        for index, identifier in enumerate(identifiers):
            add(
                identifier,
                (first[0] + index * step[0], first[1] + index * step[1]),
                default_half_extent,
            )

    explicit = _object(profile.get("explicit_targets"), f"{device_name}.explicit_targets")
    for identifier, raw_target in explicit.items():
        target = _object(raw_target, f"{device_name}.explicit_targets.{identifier}")
        center = _pair(target.get("center_xy_mm"), f"{identifier}.center_xy_mm")
        half_extent = _pair(
            target.get("half_extent_mm", list(default_half_extent)),
            f"{identifier}.half_extent_mm",
            positive=True,
        )
        add(_text(identifier, "explicit target id"), center, half_extent)
    return (
        profile_id,
        semantic_profile_id,
        semantic_profile_sha256,
        profile_origin,
        target_z,
        MappingProxyType(result),
    )


def load_nominal_target_catalog(
    workspace: Path,
    profile_path: Path | None = None,
) -> NominalTargetCatalog:
    """Load and cross-check the frozen simulation target seed."""

    root = Path(workspace).resolve()
    selected_profile_path = (
        Path(profile_path).resolve()
        if profile_path is not None
        else root / "software/config/nominal_target_profiles.json"
    )
    document, raw = _load_json(selected_profile_path, "nominal target profile")
    if document.get("schema") != TARGET_SCHEMA:
        raise TargetMapError(f"Unsupported target schema {document.get('schema')!r}")
    if document.get("status") != TARGET_STATUS:
        raise TargetMapError("Target profile is not explicitly simulation-only")
    if document.get("physical_release_effect") != "NONE":
        raise TargetMapError("Target profile must have no physical release effect")

    binding = _object(document.get("binding"), "binding")
    design_revision = _text(binding.get("design_revision"), "binding.design_revision")
    layout_relative = _text(binding.get("workcell_layout"), "binding.workcell_layout")
    layout_path = (root / layout_relative).resolve()
    try:
        layout_path.relative_to(root)
    except ValueError as exc:
        raise TargetMapError("workcell layout path escapes the workspace") from exc
    layout, _ = _load_json(layout_path, "workcell layout")
    if layout.get("release_revision") != design_revision:
        raise TargetMapError("Target profile and workcell layout revisions differ")
    if layout.get("units") != "mm":
        raise TargetMapError("Workcell layout must use millimetres")
    devices = _object(layout.get("devices"), "layout.devices")

    (
        keyboard_profile,
        keyboard_semantic_profile,
        keyboard_semantic_profile_sha256,
        keyboard_origin,
        keyboard_target_plane_z,
        keyboard_targets,
    ) = _device_targets(
        device_name="keyboard",
        profile=_object(document.get("keyboard"), "keyboard"),
        layout_device=_object(devices.get("keyboard"), "layout.devices.keyboard"),
    )
    (
        phone_profile,
        phone_semantic_profile,
        phone_semantic_profile_sha256,
        phone_origin,
        phone_target_plane_z,
        phone_targets,
    ) = _device_targets(
        device_name="phone",
        profile=_object(document.get("phone"), "phone"),
        layout_device=_object(devices.get("phone"), "layout.devices.phone"),
    )
    return NominalTargetCatalog(
        profile_path=selected_profile_path,
        workcell_layout_path=layout_path,
        design_revision=design_revision,
        keyboard_profile_id=keyboard_profile,
        phone_profile_id=phone_profile,
        keyboard_semantic_profile_id=keyboard_semantic_profile,
        phone_semantic_profile_id=phone_semantic_profile,
        keyboard_semantic_profile_sha256=keyboard_semantic_profile_sha256,
        phone_semantic_profile_sha256=phone_semantic_profile_sha256,
        keyboard_origin_board_xy_mm=keyboard_origin,
        phone_origin_board_xy_mm=phone_origin,
        keyboard_target_plane_z_board_mm=keyboard_target_plane_z,
        phone_target_plane_z_board_mm=phone_target_plane_z,
        keyboard_targets=keyboard_targets,
        phone_targets=phone_targets,
        content_sha256=hashlib.sha256(raw).hexdigest(),
    )
