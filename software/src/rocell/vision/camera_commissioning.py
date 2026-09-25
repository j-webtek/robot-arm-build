"""Strict, zero-hardware commissioning rehearsal for the selected B0477.

This module validates a *synthetic* description of the checks that will later
be performed against the physical camera.  It deliberately has no camera or
OpenCV imports, cannot request a frame, and cannot grant commissioning or
physical-release authority.  Passing the rehearsal means only that our parser,
identity binding, native-mode checks, control checks, and reopen-stability gate
agree on a deterministic fake device.

The JSON boundary is intentionally narrow.  Every object has an exact field
set, input size is bounded, duplicate keys and cameras are rejected, numbers
must be finite, and the filesystem loader confines reads to a caller-supplied
fixture root.  Source-byte and canonical semantic digests are both retained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .camera_profile import CAMERA_PROFILE_SCHEMA, PurchasedCameraProfile


CAMERA_COMMISSIONING_REHEARSAL_SCHEMA = (
    "rocell.synthetic_b0477_camera_commissioning_rehearsal.v1"
)
CAMERA_COMMISSIONING_ASSESSMENT_SCHEMA = (
    "rocell.synthetic_b0477_camera_commissioning_assessment.v1"
)
MAX_CAMERA_COMMISSIONING_REHEARSAL_BYTES = 64 * 1024

_TARGET_PROFILE_ID = "arducam-b0477-imx283-16mm-purchased-001"
_FIXTURE_CLASS = "SYNTHETIC_ZERO_HARDWARE"
_EVIDENCE_ORIGIN = "SYNTHETIC_TEST_FIXTURE"
_EVIDENCE_AUTHORITY = "NO_PHYSICAL_EVIDENCE_AUTHORITY"
_CLAIM_SCOPE = (
    "parser and deterministic reopen-gate rehearsal only; no camera was accessed"
)
_NATIVE_BUS = "USB_3_2_GEN_1"
_NATIVE_WIDTH_PX = 5472
_NATIVE_HEIGHT_PX = 3648
_NATIVE_FPS = 9.0
_NATIVE_FOURCC = "YUY2"

_ROOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "rehearsal_id",
        "fixture_class",
        "target_profile",
        "evidence",
        "authority",
        "devices",
    }
)
_TARGET_FIELDS = frozenset(
    {"schema", "profile_id", "manufacturer", "model", "sensor"}
)
_EVIDENCE_FIELDS = frozenset({"origin", "authority", "claim_scope"})
_AUTHORITY_FIELDS = frozenset(
    {
        "commissioned",
        "hardware_accessed",
        "camera_frames_requested",
        "arm_commands",
        "physical_release_effect",
    }
)
_DEVICE_FIELDS = frozenset(
    {
        "device_id",
        "persistent_device_id",
        "identity_origin",
        "reopen_snapshots",
    }
)
_SNAPSHOT_FIELDS = frozenset(
    {
        "reopen_index",
        "phase",
        "persistent_device_id",
        "negotiated_bus",
        "mode",
        "controls",
    }
)
_MODE_FIELDS = frozenset({"width_px", "height_px", "fps", "fourcc"})
_CONTROL_FIELDS = frozenset(
    {
        "exposure_mode",
        "exposure_us",
        "white_balance_mode",
        "white_balance_kelvin",
        "gain_evidence",
        "gain_observed",
    }
)


class CameraCommissioningRehearsalError(ValueError):
    """A rehearsal fixture is unsafe, malformed, or internally inconsistent."""


def _canonical_bytes(document: object) -> bytes:
    """Encode validated JSON meaning independently of whitespace/key order."""

    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CameraCommissioningRehearsalError(
            "camera commissioning rehearsal cannot be canonicalized"
        ) from exc


def _sha256(document: object) -> str:
    return hashlib.sha256(_canonical_bytes(document)).hexdigest()


def _reject_constant(value: str) -> None:
    raise CameraCommissioningRehearsalError(
        f"camera commissioning rehearsal contains nonfinite constant {value!r}"
    )


def _object_without_duplicates(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CameraCommissioningRehearsalError(
                f"camera commissioning rehearsal contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CameraCommissioningRehearsalError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CameraCommissioningRehearsalError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact(value: object, expected: object, label: str) -> None:
    # JSON booleans are Python integers, so numeric equality is not sufficient.
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CameraCommissioningRehearsalError(
                f"{label} must be numeric value {expected!r}"
            )
        parsed = float(value)
        if not math.isfinite(parsed) or parsed != float(expected):
            raise CameraCommissioningRehearsalError(
                f"{label} must be {expected!r}, got {value!r}"
            )
        if isinstance(expected, int) and not isinstance(value, int):
            raise CameraCommissioningRehearsalError(
                f"{label} must be integer value {expected!r}"
            )
        return
    if type(value) is not type(expected) or value != expected:
        raise CameraCommissioningRehearsalError(
            f"{label} must be {expected!r}, got {value!r}"
        )


def _text(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise CameraCommissioningRehearsalError(
            f"{label} must be non-empty bounded trimmed text"
        )
    return value


def _synthetic_persistent_id(value: object, label: str) -> str:
    parsed = _text(value, label)
    if not parsed.startswith("synthetic://"):
        raise CameraCommissioningRehearsalError(
            f"{label} must use the synthetic:// namespace"
        )
    return parsed


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CameraCommissioningRehearsalError(f"{label} must be an integer")
    return value


def _finite_range(
    value: object, label: str, *, minimum: float, maximum: float
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CameraCommissioningRehearsalError(
            f"{label} must be a finite number"
        )
    parsed = float(value)
    if not math.isfinite(parsed):
        raise CameraCommissioningRehearsalError(f"{label} must be finite")
    if not minimum <= parsed <= maximum:
        raise CameraCommissioningRehearsalError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return parsed


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CameraCommissioningRehearsalError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


@dataclass(frozen=True, slots=True)
class SyntheticNativeMode:
    """The one B0477 native mode exercised by this synthetic rehearsal."""

    width_px: int
    height_px: int
    fps: float
    fourcc: str

    def __post_init__(self) -> None:
        _exact(self.width_px, _NATIVE_WIDTH_PX, "mode.width_px")
        _exact(self.height_px, _NATIVE_HEIGHT_PX, "mode.height_px")
        _exact(self.fps, _NATIVE_FPS, "mode.fps")
        _exact(self.fourcc, _NATIVE_FOURCC, "mode.fourcc")
        object.__setattr__(self, "fps", float(self.fps))

    def to_dict(self) -> dict[str, object]:
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "fps": self.fps,
            "fourcc": self.fourcc,
        }


@dataclass(frozen=True, slots=True)
class SyntheticCameraControls:
    """Capture-affecting values represented by the fake UVC snapshots."""

    exposure_mode: str
    exposure_us: float
    white_balance_mode: str
    white_balance_kelvin: float
    gain_evidence: str
    gain_observed: float

    def __post_init__(self) -> None:
        _exact(self.exposure_mode, "MANUAL", "controls.exposure_mode")
        _exact(
            self.white_balance_mode,
            "MANUAL",
            "controls.white_balance_mode",
        )
        _exact(
            self.gain_evidence,
            "SYNTHETIC_OBSERVATION",
            "controls.gain_evidence",
        )
        object.__setattr__(
            self,
            "exposure_us",
            _finite_range(
                self.exposure_us,
                "controls.exposure_us",
                minimum=1.0,
                maximum=1_000_000.0,
            ),
        )
        object.__setattr__(
            self,
            "white_balance_kelvin",
            _finite_range(
                self.white_balance_kelvin,
                "controls.white_balance_kelvin",
                minimum=1_000.0,
                maximum=20_000.0,
            ),
        )
        object.__setattr__(
            self,
            "gain_observed",
            _finite_range(
                self.gain_observed,
                "controls.gain_observed",
                minimum=0.0,
                maximum=1_024.0,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "exposure_mode": self.exposure_mode,
            "exposure_us": self.exposure_us,
            "white_balance_mode": self.white_balance_mode,
            "white_balance_kelvin": self.white_balance_kelvin,
            "gain_evidence": self.gain_evidence,
            "gain_observed": self.gain_observed,
        }


@dataclass(frozen=True, slots=True)
class SyntheticReopenSnapshot:
    """One fake post-close/reopen status snapshot; it is not a captured frame."""

    reopen_index: int
    phase: str
    persistent_device_id: str
    negotiated_bus: str
    mode: SyntheticNativeMode
    controls: SyntheticCameraControls

    def __post_init__(self) -> None:
        if self.reopen_index not in (1, 2):
            raise CameraCommissioningRehearsalError(
                "reopen_index must be 1 or 2"
            )
        _exact(self.phase, f"REOPEN_{self.reopen_index}", "snapshot.phase")
        _synthetic_persistent_id(
            self.persistent_device_id, "snapshot.persistent_device_id"
        )
        _exact(self.negotiated_bus, _NATIVE_BUS, "snapshot.negotiated_bus")
        if not isinstance(self.mode, SyntheticNativeMode):
            raise CameraCommissioningRehearsalError(
                "snapshot.mode must be SyntheticNativeMode"
            )
        if not isinstance(self.controls, SyntheticCameraControls):
            raise CameraCommissioningRehearsalError(
                "snapshot.controls must be SyntheticCameraControls"
            )

    @property
    def settings_sha256(self) -> str:
        """Hash the values that must survive a simulated close/reopen cycle."""

        return _sha256(
            {
                "negotiated_bus": self.negotiated_bus,
                "mode": self.mode.to_dict(),
                "controls": self.controls.to_dict(),
            }
        )


@dataclass(frozen=True, slots=True)
class SyntheticCameraDevice:
    """The sole fake device and its two deterministic reopen observations."""

    device_id: str
    persistent_device_id: str
    identity_origin: str
    reopen_snapshots: tuple[SyntheticReopenSnapshot, ...]

    def __post_init__(self) -> None:
        _text(self.device_id, "device.device_id", maximum=96)
        _synthetic_persistent_id(
            self.persistent_device_id, "device.persistent_device_id"
        )
        _exact(
            self.identity_origin,
            "SYNTHETIC_PERSISTENT_ID",
            "device.identity_origin",
        )
        if not isinstance(self.reopen_snapshots, tuple):
            raise CameraCommissioningRehearsalError(
                "device.reopen_snapshots must be an immutable tuple"
            )
        if len(self.reopen_snapshots) != 2:
            raise CameraCommissioningRehearsalError(
                "device must contain exactly two reopen snapshots"
            )
        if tuple(item.reopen_index for item in self.reopen_snapshots) != (1, 2):
            raise CameraCommissioningRehearsalError(
                "reopen snapshots must be ordered as indexes 1 and 2"
            )
        if any(
            item.persistent_device_id != self.persistent_device_id
            for item in self.reopen_snapshots
        ):
            raise CameraCommissioningRehearsalError(
                "persistent device identity drifted across reopen snapshots"
            )
        first, second = self.reopen_snapshots
        if (
            first.negotiated_bus != second.negotiated_bus
            or first.mode != second.mode
            or first.controls != second.controls
            or first.settings_sha256 != second.settings_sha256
        ):
            raise CameraCommissioningRehearsalError(
                "camera settings drifted across reopen snapshots"
            )

    @property
    def stable_settings_sha256(self) -> str:
        return self.reopen_snapshots[0].settings_sha256


@dataclass(frozen=True, slots=True)
class SyntheticCameraCommissioningRehearsal:
    """Immutable, digest-bound interpretation of a validated fake fixture."""

    source_path: Path | None
    source_file_sha256: str
    canonical_sha256: str
    rehearsal_id: str
    fixture_class: str
    target_profile_schema: str
    target_profile_id: str
    target_manufacturer: str
    target_model: str
    target_sensor: str
    evidence_origin: str
    evidence_authority: str
    claim_scope: str
    devices: tuple[SyntheticCameraDevice, ...]

    def __post_init__(self) -> None:
        _digest(self.source_file_sha256, "source_file_sha256")
        _digest(self.canonical_sha256, "canonical_sha256")
        _text(self.rehearsal_id, "rehearsal_id", maximum=96)
        _exact(self.fixture_class, _FIXTURE_CLASS, "fixture_class")
        _exact(
            self.target_profile_schema,
            CAMERA_PROFILE_SCHEMA,
            "target_profile.schema",
        )
        _exact(
            self.target_profile_id,
            _TARGET_PROFILE_ID,
            "target_profile.profile_id",
        )
        _exact(self.target_manufacturer, "Arducam", "target_profile.manufacturer")
        _exact(self.target_model, "B0477", "target_profile.model")
        _exact(self.target_sensor, "Sony IMX283", "target_profile.sensor")
        _exact(self.evidence_origin, _EVIDENCE_ORIGIN, "evidence.origin")
        _exact(
            self.evidence_authority, _EVIDENCE_AUTHORITY, "evidence.authority"
        )
        _exact(self.claim_scope, _CLAIM_SCOPE, "evidence.claim_scope")
        if not isinstance(self.devices, tuple) or len(self.devices) != 1:
            raise CameraCommissioningRehearsalError(
                "rehearsal must contain exactly one synthetic camera"
            )

    @property
    def camera(self) -> SyntheticCameraDevice:
        return self.devices[0]

    # These are semantic constants, not values trusted from fixture input.
    @property
    def commissioned(self) -> bool:
        return False

    @property
    def hardware_accessed(self) -> bool:
        return False

    @property
    def camera_frames_requested(self) -> int:
        return 0

    @property
    def arm_commands(self) -> int:
        return 0

    @property
    def physical_release_effect(self) -> str:
        return "NONE"


@dataclass(frozen=True, slots=True)
class CameraCommissioningRehearsalAssessment:
    """A passing software rehearsal that can never commission real hardware."""

    rehearsal_id: str
    fixture_canonical_sha256: str
    device_id: str
    persistent_device_id: str
    stable_settings_sha256: str
    reopen_snapshot_count: int
    passed: bool = field(init=False, default=True)
    status: str = field(
        init=False, default="SYNTHETIC_CAMERA_COMMISSIONING_REHEARSAL_PASS"
    )
    commissioned: bool = field(init=False, default=False)
    hardware_accessed: bool = field(init=False, default=False)
    camera_frames_requested: int = field(init=False, default=0)
    arm_commands: int = field(init=False, default=0)
    physical_release_effect: str = field(init=False, default="NONE")

    def __post_init__(self) -> None:
        _text(self.rehearsal_id, "assessment.rehearsal_id", maximum=96)
        _digest(
            self.fixture_canonical_sha256,
            "assessment.fixture_canonical_sha256",
        )
        _text(self.device_id, "assessment.device_id", maximum=96)
        _synthetic_persistent_id(
            self.persistent_device_id,
            "assessment.persistent_device_id",
        )
        _digest(
            self.stable_settings_sha256,
            "assessment.stable_settings_sha256",
        )
        _exact(
            self.reopen_snapshot_count,
            2,
            "assessment.reopen_snapshot_count",
        )

    def to_dict(self) -> dict[str, object]:
        """Return a canonicalizable report with explicit zero authority."""

        return {
            "schema": CAMERA_COMMISSIONING_ASSESSMENT_SCHEMA,
            "rehearsal_id": self.rehearsal_id,
            "fixture_canonical_sha256": self.fixture_canonical_sha256,
            "device_id": self.device_id,
            "persistent_device_id": self.persistent_device_id,
            "stable_settings_sha256": self.stable_settings_sha256,
            "reopen_snapshot_count": self.reopen_snapshot_count,
            "passed": self.passed,
            "status": self.status,
            "commissioned": self.commissioned,
            "hardware_accessed": self.hardware_accessed,
            "camera_frames_requested": self.camera_frames_requested,
            "arm_commands": self.arm_commands,
            "physical_release_effect": self.physical_release_effect,
        }

    @property
    def canonical_sha256(self) -> str:
        """Digest the complete assessment meaning, including its authority hold."""

        return _sha256(self.to_dict())


def _parse_mode(raw: object, label: str) -> SyntheticNativeMode:
    mode = _mapping(raw, label)
    _exact_fields(mode, _MODE_FIELDS, label)
    return SyntheticNativeMode(
        width_px=_integer(mode.get("width_px"), f"{label}.width_px"),
        height_px=_integer(mode.get("height_px"), f"{label}.height_px"),
        fps=_finite_range(
            mode.get("fps"), f"{label}.fps", minimum=0.001, maximum=1_000.0
        ),
        fourcc=_text(mode.get("fourcc"), f"{label}.fourcc", maximum=4),
    )


def _parse_controls(raw: object, label: str) -> SyntheticCameraControls:
    controls = _mapping(raw, label)
    _exact_fields(controls, _CONTROL_FIELDS, label)
    return SyntheticCameraControls(
        exposure_mode=_text(
            controls.get("exposure_mode"), f"{label}.exposure_mode"
        ),
        exposure_us=_finite_range(
            controls.get("exposure_us"),
            f"{label}.exposure_us",
            minimum=1.0,
            maximum=1_000_000.0,
        ),
        white_balance_mode=_text(
            controls.get("white_balance_mode"),
            f"{label}.white_balance_mode",
        ),
        white_balance_kelvin=_finite_range(
            controls.get("white_balance_kelvin"),
            f"{label}.white_balance_kelvin",
            minimum=1_000.0,
            maximum=20_000.0,
        ),
        gain_evidence=_text(
            controls.get("gain_evidence"), f"{label}.gain_evidence"
        ),
        gain_observed=_finite_range(
            controls.get("gain_observed"),
            f"{label}.gain_observed",
            minimum=0.0,
            maximum=1_024.0,
        ),
    )


def _parse_snapshot(raw: object, label: str) -> SyntheticReopenSnapshot:
    snapshot = _mapping(raw, label)
    _exact_fields(snapshot, _SNAPSHOT_FIELDS, label)
    return SyntheticReopenSnapshot(
        reopen_index=_integer(
            snapshot.get("reopen_index"), f"{label}.reopen_index"
        ),
        phase=_text(snapshot.get("phase"), f"{label}.phase"),
        persistent_device_id=_synthetic_persistent_id(
            snapshot.get("persistent_device_id"),
            f"{label}.persistent_device_id",
        ),
        negotiated_bus=_text(
            snapshot.get("negotiated_bus"), f"{label}.negotiated_bus"
        ),
        mode=_parse_mode(snapshot.get("mode"), f"{label}.mode"),
        controls=_parse_controls(
            snapshot.get("controls"), f"{label}.controls"
        ),
    )


def _parse_device(raw: object, index: int) -> SyntheticCameraDevice:
    label = f"devices[{index}]"
    device = _mapping(raw, label)
    _exact_fields(device, _DEVICE_FIELDS, label)
    raw_snapshots = device.get("reopen_snapshots")
    if not isinstance(raw_snapshots, list):
        raise CameraCommissioningRehearsalError(
            f"{label}.reopen_snapshots must be an array"
        )
    if len(raw_snapshots) != 2:
        raise CameraCommissioningRehearsalError(
            f"{label}.reopen_snapshots must contain exactly two snapshots"
        )
    snapshots = tuple(
        _parse_snapshot(item, f"{label}.reopen_snapshots[{snapshot_index}]")
        for snapshot_index, item in enumerate(raw_snapshots)
    )
    return SyntheticCameraDevice(
        device_id=_text(device.get("device_id"), f"{label}.device_id", maximum=96),
        persistent_device_id=_synthetic_persistent_id(
            device.get("persistent_device_id"),
            f"{label}.persistent_device_id",
        ),
        identity_origin=_text(
            device.get("identity_origin"), f"{label}.identity_origin"
        ),
        reopen_snapshots=snapshots,
    )


def parse_camera_commissioning_rehearsal_json(
    payload: bytes, *, source_path: Path | None = None
) -> SyntheticCameraCommissioningRehearsal:
    """Parse one bounded, exact-field synthetic B0477 rehearsal fixture.

    Parsing performs no hardware access.  The source digest binds exact bytes;
    the canonical digest binds JSON meaning and therefore survives harmless
    whitespace and object-key reordering.
    """

    if not isinstance(payload, bytes):
        raise CameraCommissioningRehearsalError(
            "camera commissioning rehearsal payload must be bytes"
        )
    if not payload:
        raise CameraCommissioningRehearsalError(
            "camera commissioning rehearsal is empty"
        )
    if len(payload) > MAX_CAMERA_COMMISSIONING_REHEARSAL_BYTES:
        raise CameraCommissioningRehearsalError(
            "camera commissioning rehearsal exceeds "
            f"{MAX_CAMERA_COMMISSIONING_REHEARSAL_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CameraCommissioningRehearsalError(
            "camera commissioning rehearsal must be UTF-8"
        ) from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except CameraCommissioningRehearsalError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise CameraCommissioningRehearsalError(
            f"invalid camera commissioning rehearsal JSON: {exc}"
        ) from exc

    document = _mapping(decoded, "root")
    _exact_fields(document, _ROOT_FIELDS, "root")
    _exact(
        document.get("schema"),
        CAMERA_COMMISSIONING_REHEARSAL_SCHEMA,
        "schema",
    )
    _exact(document.get("schema_version"), 1, "schema_version")
    rehearsal_id = _text(document.get("rehearsal_id"), "rehearsal_id", maximum=96)
    _exact(document.get("fixture_class"), _FIXTURE_CLASS, "fixture_class")

    target = _mapping(document.get("target_profile"), "target_profile")
    _exact_fields(target, _TARGET_FIELDS, "target_profile")
    expected_target = {
        "schema": CAMERA_PROFILE_SCHEMA,
        "profile_id": _TARGET_PROFILE_ID,
        "manufacturer": "Arducam",
        "model": "B0477",
        "sensor": "Sony IMX283",
    }
    for key, target_expected in expected_target.items():
        _exact(target.get(key), target_expected, f"target_profile.{key}")

    evidence = _mapping(document.get("evidence"), "evidence")
    _exact_fields(evidence, _EVIDENCE_FIELDS, "evidence")
    _exact(evidence.get("origin"), _EVIDENCE_ORIGIN, "evidence.origin")
    _exact(
        evidence.get("authority"), _EVIDENCE_AUTHORITY, "evidence.authority"
    )
    _exact(evidence.get("claim_scope"), _CLAIM_SCOPE, "evidence.claim_scope")

    authority = _mapping(document.get("authority"), "authority")
    _exact_fields(authority, _AUTHORITY_FIELDS, "authority")
    for key, authority_expected in {
        "commissioned": False,
        "hardware_accessed": False,
        "camera_frames_requested": 0,
        "arm_commands": 0,
        "physical_release_effect": "NONE",
    }.items():
        _exact(authority.get(key), authority_expected, f"authority.{key}")

    raw_devices = document.get("devices")
    if not isinstance(raw_devices, list):
        raise CameraCommissioningRehearsalError("devices must be an array")
    devices = tuple(_parse_device(item, index) for index, item in enumerate(raw_devices))
    device_ids = tuple(device.device_id for device in devices)
    persistent_ids = tuple(device.persistent_device_id for device in devices)
    if len(set(device_ids)) != len(device_ids) or len(set(persistent_ids)) != len(
        persistent_ids
    ):
        raise CameraCommissioningRehearsalError(
            "rehearsal contains duplicate cameras"
        )
    if len(devices) != 1:
        raise CameraCommissioningRehearsalError(
            "rehearsal must contain exactly one synthetic camera"
        )

    return SyntheticCameraCommissioningRehearsal(
        source_path=source_path.resolve() if source_path is not None else None,
        source_file_sha256=hashlib.sha256(payload).hexdigest(),
        canonical_sha256=hashlib.sha256(_canonical_bytes(document)).hexdigest(),
        rehearsal_id=rehearsal_id,
        fixture_class=_FIXTURE_CLASS,
        target_profile_schema=CAMERA_PROFILE_SCHEMA,
        target_profile_id=_TARGET_PROFILE_ID,
        target_manufacturer="Arducam",
        target_model="B0477",
        target_sensor="Sony IMX283",
        evidence_origin=_EVIDENCE_ORIGIN,
        evidence_authority=_EVIDENCE_AUTHORITY,
        claim_scope=_CLAIM_SCOPE,
        devices=devices,
    )


def load_camera_commissioning_rehearsal(
    path: Path | str, *, fixture_root: Path | str
) -> SyntheticCameraCommissioningRehearsal:
    """Load a fixture only when its resolved path remains below ``fixture_root``.

    Resolving before reading also rejects a symlink that points outside the
    fixture tree.  This function opens only the JSON file, never a camera node.
    """

    root = Path(fixture_root).resolve()
    selected = Path(path)
    if not selected.is_absolute():
        selected = root / selected
    selected = selected.resolve()
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise CameraCommissioningRehearsalError(
            "camera commissioning rehearsal path escapes fixture root"
        ) from exc
    try:
        payload = selected.read_bytes()
    except OSError as exc:
        raise CameraCommissioningRehearsalError(
            f"cannot read camera commissioning rehearsal {selected}: {exc}"
        ) from exc
    return parse_camera_commissioning_rehearsal_json(payload, source_path=selected)


def assess_camera_commissioning_rehearsal(
    rehearsal: SyntheticCameraCommissioningRehearsal,
    *,
    purchased_profile: PurchasedCameraProfile | None = None,
) -> CameraCommissioningRehearsalAssessment:
    """Return a pass for the software rehearsal, never for real commissioning.

    Supplying the purchase-time profile adds an in-memory identity binding.  It
    remains optional because the fixture already carries an exact schema/id
    binding, and neither path reads a device or requests an image.
    """

    if not isinstance(rehearsal, SyntheticCameraCommissioningRehearsal):
        raise TypeError("rehearsal must be SyntheticCameraCommissioningRehearsal")
    if purchased_profile is not None:
        if not isinstance(purchased_profile, PurchasedCameraProfile):
            raise TypeError("purchased_profile must be PurchasedCameraProfile")
        if (
            purchased_profile.profile_id != rehearsal.target_profile_id
            or purchased_profile.manufacturer != rehearsal.target_manufacturer
            or purchased_profile.model != rehearsal.target_model
            or purchased_profile.sensor != rehearsal.target_sensor
        ):
            raise CameraCommissioningRehearsalError(
                "synthetic rehearsal does not match the purchased camera profile"
            )
        if purchased_profile.live_ready:
            raise CameraCommissioningRehearsalError(
                "purchase-time profile unexpectedly carries live authority"
            )

    camera = rehearsal.camera
    return CameraCommissioningRehearsalAssessment(
        rehearsal_id=rehearsal.rehearsal_id,
        fixture_canonical_sha256=rehearsal.canonical_sha256,
        device_id=camera.device_id,
        persistent_device_id=camera.persistent_device_id,
        stable_settings_sha256=camera.stable_settings_sha256,
        reopen_snapshot_count=len(camera.reopen_snapshots),
    )


__all__ = [
    "CAMERA_COMMISSIONING_ASSESSMENT_SCHEMA",
    "CAMERA_COMMISSIONING_REHEARSAL_SCHEMA",
    "MAX_CAMERA_COMMISSIONING_REHEARSAL_BYTES",
    "CameraCommissioningRehearsalAssessment",
    "CameraCommissioningRehearsalError",
    "SyntheticCameraCommissioningRehearsal",
    "SyntheticCameraControls",
    "SyntheticCameraDevice",
    "SyntheticNativeMode",
    "SyntheticReopenSnapshot",
    "assess_camera_commissioning_rehearsal",
    "load_camera_commissioning_rehearsal",
    "parse_camera_commissioning_rehearsal_json",
]
