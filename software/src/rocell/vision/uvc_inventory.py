"""Provider-neutral UVC inventory evidence for the purchased Arducam B0477.

This module is deliberately below every operating-system and image-capture
adapter.  It describes what a future UVC enumerator must report, provides a
deterministic fake at the same seam, and assesses that evidence against the
strict :class:`~rocell.vision.camera_profile.PurchasedCameraProfile`.

No code here enumerates USB devices, opens a camera, imports OpenCV, requests a
frame, or grants physical authority.  A passing assessment means only that an
inventory/probe implementation produced internally consistent diagnostic
evidence.  Receipt inspection, live mode proof, calibration, robot motion, and
contact remain separate physical gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .camera_profile import PurchasedCameraProfile


UVC_INVENTORY_SCHEMA = "rocell.uvc_inventory.v1"
UVC_INVENTORY_ASSESSMENT_SCHEMA = "rocell.uvc_inventory_assessment.v1"
DETERMINISTIC_FAKE_PROVIDER_ID = "deterministic_fake"

# These are parser/model safety bounds, not camera capability claims.
MAX_UVC_INVENTORY_BYTES = 256 * 1024
MAX_REOPEN_SNAPSHOTS = 8
MAX_DEVICES_PER_SNAPSHOT = 32
MAX_MODES_PER_DEVICE = 128
MAX_CONTROLS_PER_SNAPSHOT = 64
MAX_TEXT_BYTES = 1024
MAX_DIMENSION_PX = 16_384
MAX_FRAME_RATE_FPS = 1_000.0

_PURPOSE = "DIAGNOSTIC_REHEARSAL_ONLY"
_USB3 = "USB_3_2_GEN_1"
_TARGET_WIDTH = 5472
_TARGET_HEIGHT = 3648
_TARGET_FPS = 9.0
_TARGET_FOURCC = "YUY2"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX4_RE = re.compile(r"^[0-9a-f]{4}$")
_FOURCC_RE = re.compile(r"^[A-Z0-9 ]{4}$")
_CONTROL_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_BUSES = frozenset({_USB3, "USB_2_0"})

_ROOT_FIELDS = frozenset(
    {
        "schema",
        "purpose",
        "profile_binding",
        "provider",
        "selector",
        "reopen_snapshots",
        "authority",
    }
)
_PROFILE_FIELDS = frozenset({"profile_id", "profile_sha256"})
_PROVIDER_FIELDS = frozenset({"provider_id", "hardware_accessed"})
_SELECTOR_FIELDS = frozenset({"kind", "value"})
_SNAPSHOT_FIELDS = frozenset(
    {
        "reopen_ordinal",
        "devices",
        "negotiated_bus",
        "selected_mode",
        "controls",
    }
)
_DEVICE_FIELDS = frozenset({"identity", "modes"})
_IDENTITY_FIELDS = frozenset(
    {"vid", "pid", "serial_number", "persistent_path", "manufacturer", "product"}
)
_MODE_FIELDS = frozenset(
    {"width_px", "height_px", "fps", "fourcc", "host_bus"}
)
_CONTROL_FIELDS = frozenset({"control_id", "mode", "value", "unit"})
_AUTHORITY_FIELDS = frozenset(
    {
        "commissioned",
        "live_capture_authority",
        "robot_motion_authority",
        "contact_authority",
    }
)


class UvcInventoryError(ValueError):
    """Inventory evidence is malformed, unsafe, ambiguous, or inconsistent."""


def _text(value: object, label: str, *, maximum_bytes: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise UvcInventoryError(f"{label} must be non-empty, trimmed text")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise UvcInventoryError(f"{label} cannot contain control characters")
    if len(value.encode("utf-8")) > maximum_bytes:
        raise UvcInventoryError(f"{label} exceeds {maximum_bytes} UTF-8 bytes")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _integer(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UvcInventoryError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise UvcInventoryError(f"{label} must be in [{minimum}, {maximum}]")
    return value


def _finite_number(
    value: object, label: str, *, minimum: float, maximum: float
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UvcInventoryError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise UvcInventoryError(f"{label} must be finite and in [{minimum}, {maximum}]")
    return parsed


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise UvcInventoryError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UvcInventoryError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise UvcInventoryError(f"{label} must be an array")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise UvcInventoryError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise UvcInventoryError("inventory is not canonical JSON") from exc
    return encoded.encode("utf-8")


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class UvcDeviceIdentity:
    """Stable USB identity fields; a numeric capture index is never identity."""

    vid: str
    pid: str
    serial_number: str | None
    persistent_path: str | None
    manufacturer: str
    product: str

    def __post_init__(self) -> None:
        if not isinstance(self.vid, str) or _HEX4_RE.fullmatch(self.vid) is None:
            raise UvcInventoryError("identity.vid must be four lowercase hex digits")
        if not isinstance(self.pid, str) or _HEX4_RE.fullmatch(self.pid) is None:
            raise UvcInventoryError("identity.pid must be four lowercase hex digits")
        _optional_text(self.serial_number, "identity.serial_number")
        path = _optional_text(self.persistent_path, "identity.persistent_path")
        if path is not None and path.isdecimal():
            raise UvcInventoryError(
                "identity.persistent_path cannot be a numeric camera index"
            )
        _text(self.manufacturer, "identity.manufacturer")
        _text(self.product, "identity.product")

    def to_dict(self) -> dict[str, object]:
        return {
            "vid": self.vid,
            "pid": self.pid,
            "serial_number": self.serial_number,
            "persistent_path": self.persistent_path,
            "manufacturer": self.manufacturer,
            "product": self.product,
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @property
    def usb_identity_tuple(self) -> tuple[str, str, str | None]:
        return self.vid, self.pid, self.serial_number


@dataclass(frozen=True, slots=True)
class UvcMode:
    """One provider-normalized UVC format/frame/interval combination."""

    width_px: int
    height_px: int
    fps: float
    fourcc: str
    host_bus: str

    def __post_init__(self) -> None:
        _integer(
            self.width_px,
            "mode.width_px",
            minimum=1,
            maximum=MAX_DIMENSION_PX,
        )
        _integer(
            self.height_px,
            "mode.height_px",
            minimum=1,
            maximum=MAX_DIMENSION_PX,
        )
        parsed_fps = _finite_number(
            self.fps,
            "mode.fps",
            minimum=0.001,
            maximum=MAX_FRAME_RATE_FPS,
        )
        object.__setattr__(self, "fps", parsed_fps)
        if not isinstance(self.fourcc, str) or _FOURCC_RE.fullmatch(self.fourcc) is None:
            raise UvcInventoryError(
                "mode.fourcc must be exactly four normalized uppercase characters"
            )
        if not isinstance(self.host_bus, str) or self.host_bus not in _BUSES:
            raise UvcInventoryError(f"mode.host_bus must be one of {sorted(_BUSES)}")

    def to_dict(self) -> dict[str, object]:
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "fps": self.fps,
            "fourcc": self.fourcc,
            "host_bus": self.host_bus,
        }

    @property
    def key(self) -> tuple[str, int, int, float, str]:
        return self.host_bus, self.width_px, self.height_px, self.fps, self.fourcc


@dataclass(frozen=True, slots=True)
class UvcCaptureControl:
    """One read-back capture setting, including its automatic/manual state."""

    control_id: str
    mode: str
    value: float
    unit: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.control_id, str)
            or _CONTROL_ID_RE.fullmatch(self.control_id) is None
        ):
            raise UvcInventoryError(
                "control.control_id must be lowercase snake-case text"
            )
        if not isinstance(self.mode, str) or self.mode not in {"manual", "automatic"}:
            raise UvcInventoryError("control.mode must be 'manual' or 'automatic'")
        parsed_value = _finite_number(
            self.value,
            "control.value",
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
        )
        object.__setattr__(self, "value", parsed_value)
        _text(self.unit, "control.unit", maximum_bytes=64)

    @property
    def automatic(self) -> bool:
        return self.mode == "automatic"

    def to_dict(self) -> dict[str, object]:
        return {
            "control_id": self.control_id,
            "mode": self.mode,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class UvcDevice:
    """One enumerated UVC device and its normalized advertised modes."""

    identity: UvcDeviceIdentity
    modes: tuple[UvcMode, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, UvcDeviceIdentity):
            raise UvcInventoryError("device.identity must be a UvcDeviceIdentity")
        if not isinstance(self.modes, tuple):
            raise UvcInventoryError("device.modes must be an immutable tuple")
        if not 1 <= len(self.modes) <= MAX_MODES_PER_DEVICE:
            raise UvcInventoryError(
                f"device.modes must contain 1..{MAX_MODES_PER_DEVICE} entries"
            )
        if any(not isinstance(mode, UvcMode) for mode in self.modes):
            raise UvcInventoryError("device.modes contains an invalid entry")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity.to_dict(),
            "modes": [mode.to_dict() for mode in sorted(self.modes, key=lambda m: m.key)],
        }


@dataclass(frozen=True, slots=True)
class UvcReopenSnapshot:
    """Inventory and read-back settings from one open/reopen cycle."""

    reopen_ordinal: int
    devices: tuple[UvcDevice, ...]
    negotiated_bus: str
    selected_mode: UvcMode
    controls: tuple[UvcCaptureControl, ...]

    def __post_init__(self) -> None:
        _integer(
            self.reopen_ordinal,
            "snapshot.reopen_ordinal",
            minimum=0,
            maximum=MAX_REOPEN_SNAPSHOTS - 1,
        )
        if not isinstance(self.devices, tuple):
            raise UvcInventoryError("snapshot.devices must be an immutable tuple")
        if not 1 <= len(self.devices) <= MAX_DEVICES_PER_SNAPSHOT:
            raise UvcInventoryError(
                f"snapshot.devices must contain 1..{MAX_DEVICES_PER_SNAPSHOT} entries"
            )
        if any(not isinstance(device, UvcDevice) for device in self.devices):
            raise UvcInventoryError("snapshot.devices contains an invalid entry")
        if (
            not isinstance(self.negotiated_bus, str)
            or self.negotiated_bus not in _BUSES
        ):
            raise UvcInventoryError(
                f"snapshot.negotiated_bus must be one of {sorted(_BUSES)}"
            )
        if not isinstance(self.selected_mode, UvcMode):
            raise UvcInventoryError("snapshot.selected_mode must be a UvcMode")
        if not isinstance(self.controls, tuple):
            raise UvcInventoryError("snapshot.controls must be an immutable tuple")
        if not 1 <= len(self.controls) <= MAX_CONTROLS_PER_SNAPSHOT:
            raise UvcInventoryError(
                f"snapshot.controls must contain 1..{MAX_CONTROLS_PER_SNAPSHOT} entries"
            )
        if any(not isinstance(control, UvcCaptureControl) for control in self.controls):
            raise UvcInventoryError("snapshot.controls contains an invalid entry")

    @property
    def settings_sha256(self) -> str:
        """Hash mode, bus, and all read-back controls independent of list order."""

        return _canonical_sha256(
            {
                "negotiated_bus": self.negotiated_bus,
                "selected_mode": self.selected_mode.to_dict(),
                "controls": [
                    control.to_dict()
                    for control in sorted(self.controls, key=lambda item: item.control_id)
                ],
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "reopen_ordinal": self.reopen_ordinal,
            "devices": [
                device.to_dict()
                for device in sorted(
                    self.devices,
                    key=lambda item: (
                        item.identity.persistent_path or "",
                        item.identity.canonical_sha256,
                    ),
                )
            ],
            "negotiated_bus": self.negotiated_bus,
            "selected_mode": self.selected_mode.to_dict(),
            "controls": [
                control.to_dict()
                for control in sorted(self.controls, key=lambda item: item.control_id)
            ],
        }


@dataclass(frozen=True, slots=True)
class UvcInventory:
    """Bounded inventory evidence from a provider, never commissioning evidence."""

    profile_id: str
    profile_sha256: str
    provider_id: str
    hardware_accessed: bool
    selector_kind: str
    selector_value: str
    reopen_snapshots: tuple[UvcReopenSnapshot, ...]
    source_file_sha256: str | None = None
    schema: str = UVC_INVENTORY_SCHEMA
    purpose: str = _PURPOSE
    commissioned: bool = False
    live_capture_authority: bool = False
    robot_motion_authority: bool = False
    contact_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema != UVC_INVENTORY_SCHEMA:
            raise UvcInventoryError(f"schema must be {UVC_INVENTORY_SCHEMA!r}")
        if self.purpose != _PURPOSE:
            raise UvcInventoryError(f"purpose must be {_PURPOSE!r}")
        if (
            not isinstance(self.profile_id, str)
            or _PROFILE_ID_RE.fullmatch(self.profile_id) is None
        ):
            raise UvcInventoryError("profile_id has an invalid format")
        _sha256(self.profile_sha256, "profile_sha256")
        _text(self.provider_id, "provider_id", maximum_bytes=128)
        if not isinstance(self.hardware_accessed, bool):
            raise UvcInventoryError("hardware_accessed must be boolean")
        if self.selector_kind != "persistent_path":
            raise UvcInventoryError(
                "selector_kind must be 'persistent_path'; numeric camera indices are forbidden"
            )
        _text(self.selector_value, "selector_value")
        if self.selector_value.isdecimal():
            raise UvcInventoryError("selector_value cannot be a numeric camera index")
        if not isinstance(self.reopen_snapshots, tuple):
            raise UvcInventoryError("reopen_snapshots must be an immutable tuple")
        if not 2 <= len(self.reopen_snapshots) <= MAX_REOPEN_SNAPSHOTS:
            raise UvcInventoryError(
                f"reopen_snapshots must contain 2..{MAX_REOPEN_SNAPSHOTS} entries"
            )
        if any(
            not isinstance(snapshot, UvcReopenSnapshot)
            for snapshot in self.reopen_snapshots
        ):
            raise UvcInventoryError("reopen_snapshots contains an invalid entry")
        ordinals = tuple(snapshot.reopen_ordinal for snapshot in self.reopen_snapshots)
        if ordinals != tuple(range(len(self.reopen_snapshots))):
            raise UvcInventoryError(
                "reopen snapshot ordinals must be contiguous and ordered from zero"
            )
        if self.source_file_sha256 is not None:
            _sha256(self.source_file_sha256, "source_file_sha256")
        for label, value in (
            ("commissioned", self.commissioned),
            ("live_capture_authority", self.live_capture_authority),
            ("robot_motion_authority", self.robot_motion_authority),
            ("contact_authority", self.contact_authority),
        ):
            if value is not False:
                raise UvcInventoryError(f"{label} must remain false for inventory evidence")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "purpose": self.purpose,
            "profile_binding": {
                "profile_id": self.profile_id,
                "profile_sha256": self.profile_sha256,
            },
            "provider": {
                "provider_id": self.provider_id,
                "hardware_accessed": self.hardware_accessed,
            },
            "selector": {
                "kind": self.selector_kind,
                "value": self.selector_value,
            },
            "reopen_snapshots": [
                snapshot.to_dict() for snapshot in self.reopen_snapshots
            ],
            "authority": {
                "commissioned": self.commissioned,
                "live_capture_authority": self.live_capture_authority,
                "robot_motion_authority": self.robot_motion_authority,
                "contact_authority": self.contact_authority,
            },
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@runtime_checkable
class UvcInventoryProvider(Protocol):
    """Seam for a future OS enumerator and the deterministic fake provider."""

    @property
    def provider_id(self) -> str: ...

    @property
    def hardware_accessed(self) -> bool: ...

    def collect_inventory(self) -> UvcInventory: ...


class DeterministicFakeUvcInventoryProvider:
    """Replay immutable inventory evidence without performing any device I/O."""

    def __init__(self, inventory: UvcInventory) -> None:
        if not isinstance(inventory, UvcInventory):
            raise UvcInventoryError("fake provider requires a UvcInventory")
        if inventory.provider_id != DETERMINISTIC_FAKE_PROVIDER_ID:
            raise UvcInventoryError(
                "fake inventory provider_id must be 'deterministic_fake'"
            )
        if inventory.hardware_accessed:
            raise UvcInventoryError("fake inventory cannot claim hardware access")
        self._inventory = inventory

    @property
    def provider_id(self) -> str:
        return DETERMINISTIC_FAKE_PROVIDER_ID

    @property
    def hardware_accessed(self) -> bool:
        return False

    def collect_inventory(self) -> UvcInventory:
        return self._inventory


def collect_uvc_inventory(provider: UvcInventoryProvider) -> UvcInventory:
    """Collect through the provider seam and verify its provenance claims."""

    if not isinstance(provider, UvcInventoryProvider):
        raise UvcInventoryError("provider does not implement UvcInventoryProvider")
    inventory = provider.collect_inventory()
    if not isinstance(inventory, UvcInventory):
        raise UvcInventoryError("provider returned an invalid inventory type")
    if inventory.provider_id != provider.provider_id:
        raise UvcInventoryError("provider_id differs from returned inventory")
    if inventory.hardware_accessed is not provider.hardware_accessed:
        raise UvcInventoryError("hardware_accessed differs from returned inventory")
    return inventory


@dataclass(frozen=True, slots=True)
class UvcAssessmentCheck:
    """One deterministic, user-auditable inventory gate."""

    check_id: str
    passed: bool
    message: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.check_id, str)
            or _CONTROL_ID_RE.fullmatch(self.check_id) is None
        ):
            raise UvcInventoryError("assessment check_id has an invalid format")
        if not isinstance(self.passed, bool):
            raise UvcInventoryError("assessment passed must be boolean")
        _text(self.message, "assessment.message", maximum_bytes=2048)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class UvcInventoryAssessment:
    """Diagnostic result that can never commission a camera or release motion."""

    profile_id: str
    profile_sha256: str
    inventory_sha256: str
    checks: tuple[UvcAssessmentCheck, ...]
    hardware_accessed: bool
    status: str
    commissioned: bool = False
    live_capture_authority: bool = False
    live_capture_performed: bool = False
    camera_frames_requested: int = 0
    arm_commands: int = 0
    robot_motion_authority: bool = False
    contact_authority: bool = False
    physical_release_effect: str = "NONE"
    schema: str = UVC_INVENTORY_ASSESSMENT_SCHEMA
    purpose: str = _PURPOSE

    def __post_init__(self) -> None:
        if self.schema != UVC_INVENTORY_ASSESSMENT_SCHEMA:
            raise UvcInventoryError("assessment schema is invalid")
        if self.purpose != _PURPOSE:
            raise UvcInventoryError("assessment purpose is invalid")
        _text(self.profile_id, "assessment.profile_id", maximum_bytes=128)
        _sha256(self.profile_sha256, "assessment.profile_sha256")
        _sha256(self.inventory_sha256, "assessment.inventory_sha256")
        if not isinstance(self.checks, tuple) or not self.checks or any(
            not isinstance(check, UvcAssessmentCheck) for check in self.checks
        ):
            raise UvcInventoryError("assessment checks must be non-empty")
        check_ids = tuple(check.check_id for check in self.checks)
        if len(check_ids) != len(set(check_ids)):
            raise UvcInventoryError("assessment check ids must be unique")
        expected_status = (
            "DIAGNOSTIC_REHEARSAL_PASS"
            if all(check.passed for check in self.checks)
            else "DIAGNOSTIC_REHEARSAL_BLOCKED"
        )
        if self.status != expected_status:
            raise UvcInventoryError("assessment status disagrees with checks")
        if not isinstance(self.hardware_accessed, bool):
            raise UvcInventoryError("assessment.hardware_accessed must be boolean")
        if (
            self.commissioned is not False
            or self.live_capture_authority is not False
            or self.live_capture_performed is not False
            or self.camera_frames_requested != 0
            or self.arm_commands != 0
            or self.robot_motion_authority is not False
            or self.contact_authority is not False
            or self.physical_release_effect != "NONE"
        ):
            raise UvcInventoryError(
                "diagnostic assessment cannot claim capture, commissioning, motion, or contact"
            )

    @property
    def passed(self) -> bool:
        return self.status == "DIAGNOSTIC_REHEARSAL_PASS"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "purpose": self.purpose,
            "status": self.status,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "inventory_sha256": self.inventory_sha256,
            "checks": [check.to_dict() for check in self.checks],
            "execution": {
                "hardware_accessed": self.hardware_accessed,
                "live_capture_performed": self.live_capture_performed,
                "camera_frames_requested": self.camera_frames_requested,
                "arm_commands": self.arm_commands,
            },
            "authority": {
                "commissioned": self.commissioned,
                "live_capture_authority": self.live_capture_authority,
                "robot_motion_authority": self.robot_motion_authority,
                "contact_authority": self.contact_authority,
                "physical_release_effect": self.physical_release_effect,
            },
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _selected_devices(
    snapshot: UvcReopenSnapshot, selector_value: str
) -> tuple[UvcDevice, ...]:
    return tuple(
        device
        for device in snapshot.devices
        if device.identity.persistent_path == selector_value
    )


def _target_mode(mode: UvcMode) -> bool:
    return mode.key == (
        _USB3,
        _TARGET_WIDTH,
        _TARGET_HEIGHT,
        _TARGET_FPS,
        _TARGET_FOURCC,
    )


def _control(snapshot: UvcReopenSnapshot, control_id: str) -> UvcCaptureControl | None:
    matches = tuple(
        control for control in snapshot.controls if control.control_id == control_id
    )
    return matches[0] if len(matches) == 1 else None


def assess_uvc_inventory(
    profile: PurchasedCameraProfile, inventory: UvcInventory
) -> UvcInventoryAssessment:
    """Bind UVC diagnostics to the strict profile and fail every unsafe gate.

    The result deliberately remains ``commissioned == False`` even when all
    checks pass.  This assessor consumes provider reports; it does not prove
    that the provider is truthful or that a physical device was operated.
    """

    if not isinstance(profile, PurchasedCameraProfile):
        raise UvcInventoryError("profile must be a PurchasedCameraProfile")
    if not isinstance(inventory, UvcInventory):
        raise UvcInventoryError("inventory must be a UvcInventory")

    snapshots = inventory.reopen_snapshots
    selected = tuple(
        _selected_devices(snapshot, inventory.selector_value) for snapshot in snapshots
    )

    binding_ok = (
        inventory.profile_id == profile.profile_id
        and inventory.profile_sha256 == profile.canonical_sha256
    )

    unique_ok = True
    for snapshot in snapshots:
        paths = [
            device.identity.persistent_path
            for device in snapshot.devices
            if device.identity.persistent_path is not None
        ]
        usb_ids = [device.identity.usb_identity_tuple for device in snapshot.devices]
        mode_sets_unique = all(
            len(device.modes) == len({mode.key for mode in device.modes})
            for device in snapshot.devices
        )
        controls_unique = len(snapshot.controls) == len(
            {control.control_id for control in snapshot.controls}
        )
        unique_ok = unique_ok and (
            len(paths) == len(set(paths))
            and len(usb_ids) == len(set(usb_ids))
            and mode_sets_unique
            and controls_unique
        )

    selector_ok = all(len(matches) == 1 for matches in selected)
    selected_devices = tuple(matches[0] for matches in selected if len(matches) == 1)

    identity_policy_ok = selector_ok and all(
        device.identity.persistent_path is not None
        and device.identity.persistent_path == inventory.selector_value
        and device.identity.serial_number is not None
        for device in selected_devices
    )
    product_ok = selector_ok and all(
        device.identity.manufacturer.casefold() == profile.manufacturer.casefold()
        and profile.model.casefold() in device.identity.product.casefold()
        for device in selected_devices
    )
    advertised_mode_ok = selector_ok and all(
        any(_target_mode(mode) for mode in device.modes)
        for device in selected_devices
    )
    selected_mode_ok = all(_target_mode(snapshot.selected_mode) for snapshot in snapshots)
    selected_mode_enumerated_ok = selector_ok and all(
        snapshot.selected_mode.key in {mode.key for mode in matches[0].modes}
        for snapshot, matches in zip(snapshots, selected)
        if len(matches) == 1
    )
    usb3_ok = all(
        snapshot.negotiated_bus == _USB3
        and snapshot.selected_mode.host_bus == _USB3
        for snapshot in snapshots
    )
    manual_exposure_ok = all(
        (control := _control(snapshot, "exposure")) is not None
        and not control.automatic
        for snapshot in snapshots
    )
    manual_white_balance_ok = all(
        (control := _control(snapshot, "white_balance")) is not None
        and not control.automatic
        for snapshot in snapshots
    )
    settings_stable = len({snapshot.settings_sha256 for snapshot in snapshots}) == 1
    identity_stable = selector_ok and len(
        {device.identity.canonical_sha256 for device in selected_devices}
    ) == 1

    check_values = (
        (
            "profile_binding",
            binding_ok,
            "inventory profile id and canonical digest match the purchased profile",
        ),
        (
            "unique_inventory",
            unique_ok,
            "device identities, persistent paths, modes, and controls are unambiguous",
        ),
        (
            "persistent_selector",
            selector_ok,
            "the persistent selector resolves exactly one device in every snapshot",
        ),
        (
            "identity_policy",
            identity_policy_ok,
            "the selected device has both a persistent path and serial descriptor",
        ),
        (
            "profile_product",
            product_ok,
            "selected manufacturer and product identify Arducam B0477",
        ),
        (
            "native_mode_advertised",
            advertised_mode_ok,
            "5472x3648 at 9 fps YUY2 over USB3 is enumerated",
        ),
        (
            "native_mode_selected",
            selected_mode_ok and selected_mode_enumerated_ok,
            "the exact native mode is selected and was enumerated",
        ),
        (
            "usb3_negotiated",
            usb3_ok,
            "every open/reopen cycle remains on USB 3.2 Gen 1",
        ),
        (
            "manual_exposure",
            manual_exposure_ok,
            "exposure read-back is present, unique, and manual in every snapshot",
        ),
        (
            "manual_white_balance",
            manual_white_balance_ok,
            "white-balance read-back is present, unique, and manual in every snapshot",
        ),
        (
            "settings_stability",
            settings_stable,
            "selected mode, bus, and capture-control values are stable after reopen",
        ),
        (
            "reconnect_identity",
            identity_stable,
            "VID/PID, serial, persistent path, manufacturer, and product remain stable",
        ),
    )
    checks = tuple(
        UvcAssessmentCheck(check_id=check_id, passed=passed, message=message)
        for check_id, passed, message in check_values
    )
    status = (
        "DIAGNOSTIC_REHEARSAL_PASS"
        if all(check.passed for check in checks)
        else "DIAGNOSTIC_REHEARSAL_BLOCKED"
    )
    return UvcInventoryAssessment(
        profile_id=profile.profile_id,
        profile_sha256=profile.canonical_sha256,
        inventory_sha256=inventory.canonical_sha256,
        checks=checks,
        hardware_accessed=inventory.hardware_accessed,
        status=status,
    )


def _reject_constant(value: str) -> None:
    raise UvcInventoryError(f"inventory contains invalid JSON constant {value!r}")


def _object_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UvcInventoryError(f"inventory contains duplicate key {key!r}")
        result[key] = value
    return result


def _parse_identity(value: object, label: str) -> UvcDeviceIdentity:
    document = _mapping(value, label)
    _exact_fields(document, _IDENTITY_FIELDS, label)
    return UvcDeviceIdentity(
        vid=document["vid"],
        pid=document["pid"],
        serial_number=document["serial_number"],
        persistent_path=document["persistent_path"],
        manufacturer=document["manufacturer"],
        product=document["product"],
    )


def _parse_mode(value: object, label: str) -> UvcMode:
    document = _mapping(value, label)
    _exact_fields(document, _MODE_FIELDS, label)
    return UvcMode(
        width_px=document["width_px"],
        height_px=document["height_px"],
        fps=document["fps"],
        fourcc=document["fourcc"],
        host_bus=document["host_bus"],
    )


def _parse_control(value: object, label: str) -> UvcCaptureControl:
    document = _mapping(value, label)
    _exact_fields(document, _CONTROL_FIELDS, label)
    return UvcCaptureControl(
        control_id=document["control_id"],
        mode=document["mode"],
        value=document["value"],
        unit=document["unit"],
    )


def _parse_device(value: object, label: str) -> UvcDevice:
    document = _mapping(value, label)
    _exact_fields(document, _DEVICE_FIELDS, label)
    modes = _array(document["modes"], f"{label}.modes")
    if len(modes) > MAX_MODES_PER_DEVICE:
        raise UvcInventoryError(f"{label}.modes exceeds resource limit")
    return UvcDevice(
        identity=_parse_identity(document["identity"], f"{label}.identity"),
        modes=tuple(
            _parse_mode(mode, f"{label}.modes[{index}]")
            for index, mode in enumerate(modes)
        ),
    )


def _parse_snapshot(value: object, label: str) -> UvcReopenSnapshot:
    document = _mapping(value, label)
    _exact_fields(document, _SNAPSHOT_FIELDS, label)
    devices = _array(document["devices"], f"{label}.devices")
    controls = _array(document["controls"], f"{label}.controls")
    if len(devices) > MAX_DEVICES_PER_SNAPSHOT:
        raise UvcInventoryError(f"{label}.devices exceeds resource limit")
    if len(controls) > MAX_CONTROLS_PER_SNAPSHOT:
        raise UvcInventoryError(f"{label}.controls exceeds resource limit")
    return UvcReopenSnapshot(
        reopen_ordinal=document["reopen_ordinal"],
        devices=tuple(
            _parse_device(device, f"{label}.devices[{index}]")
            for index, device in enumerate(devices)
        ),
        negotiated_bus=document["negotiated_bus"],
        selected_mode=_parse_mode(document["selected_mode"], f"{label}.selected_mode"),
        controls=tuple(
            _parse_control(control, f"{label}.controls[{index}]")
            for index, control in enumerate(controls)
        ),
    )


def parse_uvc_inventory_json(payload: bytes) -> UvcInventory:
    """Parse a bounded, duplicate-key-safe inventory document."""

    if not isinstance(payload, bytes):
        raise UvcInventoryError("inventory payload must be bytes")
    if not payload:
        raise UvcInventoryError("inventory payload is empty")
    if len(payload) > MAX_UVC_INVENTORY_BYTES:
        raise UvcInventoryError(
            f"inventory payload exceeds {MAX_UVC_INVENTORY_BYTES} bytes"
        )
    source_sha256 = hashlib.sha256(payload).hexdigest()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UvcInventoryError("inventory payload must be UTF-8") from exc
    try:
        raw = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except UvcInventoryError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise UvcInventoryError("inventory payload is not valid bounded JSON") from exc

    document = _mapping(raw, "inventory")
    _exact_fields(document, _ROOT_FIELDS, "inventory")
    if document["schema"] != UVC_INVENTORY_SCHEMA:
        raise UvcInventoryError(f"schema must be {UVC_INVENTORY_SCHEMA!r}")
    if document["purpose"] != _PURPOSE:
        raise UvcInventoryError(f"purpose must be {_PURPOSE!r}")

    profile = _mapping(document["profile_binding"], "profile_binding")
    provider = _mapping(document["provider"], "provider")
    selector = _mapping(document["selector"], "selector")
    authority = _mapping(document["authority"], "authority")
    _exact_fields(profile, _PROFILE_FIELDS, "profile_binding")
    _exact_fields(provider, _PROVIDER_FIELDS, "provider")
    _exact_fields(selector, _SELECTOR_FIELDS, "selector")
    _exact_fields(authority, _AUTHORITY_FIELDS, "authority")
    for field in _AUTHORITY_FIELDS:
        if authority[field] is not False:
            raise UvcInventoryError(f"authority.{field} must remain false")

    snapshots = _array(document["reopen_snapshots"], "reopen_snapshots")
    if len(snapshots) > MAX_REOPEN_SNAPSHOTS:
        raise UvcInventoryError("reopen_snapshots exceeds resource limit")
    return UvcInventory(
        profile_id=profile["profile_id"],
        profile_sha256=profile["profile_sha256"],
        provider_id=provider["provider_id"],
        hardware_accessed=provider["hardware_accessed"],
        selector_kind=selector["kind"],
        selector_value=selector["value"],
        reopen_snapshots=tuple(
            _parse_snapshot(snapshot, f"reopen_snapshots[{index}]")
            for index, snapshot in enumerate(snapshots)
        ),
        source_file_sha256=source_sha256,
    )


def assessment_checks_by_id(
    assessment: UvcInventoryAssessment,
) -> Mapping[str, UvcAssessmentCheck]:
    """Expose checks read-only for CLI/report adapters and focused tests."""

    return MappingProxyType({check.check_id: check for check in assessment.checks})


__all__ = [
    "DETERMINISTIC_FAKE_PROVIDER_ID",
    "MAX_CONTROLS_PER_SNAPSHOT",
    "MAX_DEVICES_PER_SNAPSHOT",
    "MAX_MODES_PER_DEVICE",
    "MAX_REOPEN_SNAPSHOTS",
    "MAX_UVC_INVENTORY_BYTES",
    "UVC_INVENTORY_ASSESSMENT_SCHEMA",
    "UVC_INVENTORY_SCHEMA",
    "DeterministicFakeUvcInventoryProvider",
    "UvcAssessmentCheck",
    "UvcCaptureControl",
    "UvcDevice",
    "UvcDeviceIdentity",
    "UvcInventory",
    "UvcInventoryAssessment",
    "UvcInventoryError",
    "UvcInventoryProvider",
    "UvcMode",
    "UvcReopenSnapshot",
    "assess_uvc_inventory",
    "assessment_checks_by_id",
    "collect_uvc_inventory",
    "parse_uvc_inventory_json",
]
