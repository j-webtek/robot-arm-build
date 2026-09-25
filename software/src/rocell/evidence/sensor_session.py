"""Immutable raw sensor-session evidence for hardware-free commissioning tests.

This module deliberately has no camera, OpenCV, or serial adapter.  It records
bytes that a *fake* provider already produced and replays only those bytes.  A
separate future physical acquisition layer may create an equivalent evidence
input, but importing or calling this module can never discover a device, send a
wire command, move the arm, or release a physical gate.

The package is content addressed and manifest-last.  Verification is strict:
the directory, artifact order, filenames, byte counts, hashes, canonical JSON,
camera contract, event order, freshness bounds, perception bindings, wire
framing, and zero-authority declarations must all agree.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import InitVar, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
from types import MappingProxyType
from typing import Any

from rocell.arm.feedback_wire import FeedbackWireError, validate_feedback_response_line
from rocell.arm.protocol import FEEDBACK_REQUEST_TYPE, ProtocolError, decode_line


MANIFEST_SCHEMA = "rocell.raw_sensor_session_manifest.v2"
CONTENT_SCHEMA = "rocell.raw_sensor_session_content.v2"
CONTRACT_SCHEMA = "rocell.raw_sensor_session_contract.v2"
CAMERA_SCHEMA = "rocell.raw_sensor_session_camera.v2"
TIMING_SCHEMA = "rocell.raw_sensor_session_timing.v2"
PERCEPTION_SCHEMA = "rocell.raw_sensor_session_perception.v2"
REPLAY_SCHEMA = "rocell.raw_sensor_session_replay.v2"
PIXEL_LAYOUT_SCHEMA = "rocell.raw_sensor_session_pixel_layout.v2"

# Native 20 MP YUY2 is about 40 MiB and decoded RGB is about 60 MiB.  These
# explicit ceilings support one B0477-sized frame at every image boundary while
# preventing unbounded allocations during record or replay.
MAX_FRAME_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_JSON_ARTIFACT_BYTES = 1024 * 1024
MAX_WIRE_LINE_BYTES = 16 * 1024
MAX_PACKAGE_BYTES = 192 * 1024 * 1024
MAX_JSON_NODES = 20_000
MAX_JSON_DEPTH = 20

_MAX_NS = 2**63 - 1
_DEFAULT_MAX_STAGE_DURATION_NS = 1_000_000_000
_DEFAULT_MAX_SESSION_DURATION_NS = 5_000_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_USB_ID = re.compile(r"^[0-9a-f]{4}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+/-]{0,127}$")
_RECORD_ID = re.compile(r"^sensor-session-([0-9a-f]{64})$")
_VERIFIED_FACTORY_TOKEN = object()
_REPLAY_FACTORY_TOKEN = object()

_AUTHORITY = {
    "simulation_only": True,
    "hardware_accessed": False,
    "hardware_commands_generated": 0,
    # A T=105 byte string is stored as synthetic evidence.  It was not sent to
    # a controller and therefore is not a hardware command or hardware query.
    "synthetic_t105_request_lines_recorded": 1,
    "physical_t105_requests_sent": 0,
    "physical_t104_motion_requests_sent": 0,
    "physical_release_effect": "NONE",
    "can_release_physical_gates": False,
}
_AUTHORITY_FIELDS = frozenset(_AUTHORITY)

_ARTIFACT_ROLES: tuple[tuple[str, str, str, int], ...] = (
    ("contract.json", "SYNTHETIC_SESSION_CONTRACT", "application/json", MAX_JSON_ARTIFACT_BYTES),
    ("camera.json", "FAKE_CAMERA_SNAPSHOTS", "application/json", MAX_JSON_ARTIFACT_BYTES),
    ("timing.json", "MONOTONIC_TIMING_BRACKET", "application/json", MAX_JSON_ARTIFACT_BYTES),
    ("raw-frame.bin", "RAW_FRAME_BYTES", "application/octet-stream", MAX_FRAME_ARTIFACT_BYTES),
    ("decoded-frame.bin", "DECODED_FRAME_BYTES", "application/octet-stream", MAX_FRAME_ARTIFACT_BYTES),
    ("undistorted-frame.bin", "UNDISTORTED_FRAME_BYTES", "application/octet-stream", MAX_FRAME_ARTIFACT_BYTES),
    ("perception.json", "DETECTOR_AND_POSE_RECORDS", "application/json", MAX_JSON_ARTIFACT_BYTES),
    ("t105-request.line", "SYNTHETIC_UNSENT_T105_REQUEST_LINE", "application/octet-stream", MAX_WIRE_LINE_BYTES),
    ("t1051-response.line", "RECORDED_SYNTHETIC_T1051_LINE", "application/octet-stream", MAX_WIRE_LINE_BYTES),
)
_EXPECTED_FILES = frozenset(
    {name for name, _, _, _ in _ARTIFACT_ROLES} | {"manifest.json"}
)
_JSON_ARTIFACTS = frozenset(
    {"contract.json", "camera.json", "timing.json", "perception.json"}
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "record_id",
        "content_sha256",
        "artifact_count",
        "total_artifact_bytes",
        "artifacts",
        "complete",
        "manifest_written_last",
        "authority",
        "package_sha256",
    }
)
_ROW_FIELDS = frozenset({"path", "role", "media_type", "sha256", "bytes"})
_TIMING_EVENT_NAMES = (
    "SESSION_STARTED",
    "FRAME_REQUESTED",
    "EXPOSURE_STARTED",
    "FRAME_CAPTURED",
    "FRAME_RECEIVED",
    "PERCEPTION_COMPLETED",
    "FEEDBACK_REQUEST_SENT",
    "FEEDBACK_RESPONSE_RECEIVED",
    "SESSION_COMPLETED",
)


class SensorSessionEvidenceError(ValueError):
    """A sensor record is unsafe, stale, incomplete, or inconsistent."""


def _stable_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SensorSessionEvidenceError(
            f"value is not finite canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SensorSessionEvidenceError(
            f"value is not canonical JSON: {exc}"
        ) from exc


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SensorSessionEvidenceError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise SensorSessionEvidenceError(f"nonfinite JSON number {value!r}")
    return result


def _validate_json_tree(value: object) -> None:
    """Bound opaque detector/pose data beyond the outer byte-size bound."""

    pending: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise SensorSessionEvidenceError("JSON payload has too many values")
        if depth > MAX_JSON_DEPTH:
            raise SensorSessionEvidenceError("JSON payload nesting is too deep")
        if current is None or isinstance(current, (str, bool, int)):
            if isinstance(current, str) and len(current) > 16_384:
                raise SensorSessionEvidenceError("JSON string is too long")
            continue
        if isinstance(current, float):
            if not math.isfinite(current):
                raise SensorSessionEvidenceError("JSON payload contains a nonfinite number")
            continue
        if isinstance(current, Mapping):
            for key, child in current.items():
                if not isinstance(key, str) or len(key) > 256:
                    raise SensorSessionEvidenceError("JSON object key is invalid")
                pending.append((child, depth + 1))
            continue
        if isinstance(current, (list, tuple)):
            pending.extend((child, depth + 1) for child in current)
            continue
        raise SensorSessionEvidenceError(
            f"JSON payload contains unsupported {type(current).__name__}"
        )


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _deep_freeze(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(child) for child in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_deep_thaw(child) for child in value]
    return value


def _exact_mapping(value: object, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise SensorSessionEvidenceError(f"{label} fields are not exact")
    return value


def _text(value: object, label: str, *, maximum: int = 128) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise SensorSessionEvidenceError(f"{label} must be bounded printable text")
    return value


def _token(value: object, label: str) -> str:
    result = _text(value, label)
    if _TOKEN.fullmatch(result) is None:
        raise SensorSessionEvidenceError(f"{label} must be a safe token")
    return result


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = _MAX_NS,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise SensorSessionEvidenceError(f"{label} must be a bounded integer")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SensorSessionEvidenceError(f"{label} must be lowercase SHA-256")
    return value


def _authority(value: object, label: str) -> None:
    authority = _exact_mapping(value, _AUTHORITY_FIELDS, label)
    if dict(authority) != _AUTHORITY:
        raise SensorSessionEvidenceError(f"{label} grants nonzero physical authority")


@dataclass(frozen=True, slots=True)
class SyntheticCameraIdentity:
    """Exact identity emitted by a fake UVC provider, never a live probe."""

    manufacturer: str
    model: str
    sensor: str
    vid: str
    pid: str
    serial_number: str
    device_key: str

    def __post_init__(self) -> None:
        for name in ("manufacturer", "model", "sensor", "serial_number", "device_key"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        for name in ("vid", "pid"):
            value = getattr(self, name)
            if not isinstance(value, str) or _USB_ID.fullmatch(value) is None:
                raise SensorSessionEvidenceError(f"{name} must be four lowercase hex digits")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_kind": "FAKE_UVC",
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sensor": self.sensor,
            "vid": self.vid,
            "pid": self.pid,
            "serial_number": self.serial_number,
            "device_key": self.device_key,
        }

    @classmethod
    def from_dict(cls, value: object) -> SyntheticCameraIdentity:
        fields = frozenset(
            {"source_kind", "manufacturer", "model", "sensor", "vid", "pid", "serial_number", "device_key"}
        )
        document = _exact_mapping(value, fields, "camera identity")
        if document["source_kind"] != "FAKE_UVC":
            raise SensorSessionEvidenceError("camera identity is not from a fake UVC provider")
        return cls(
            manufacturer=document["manufacturer"],  # type: ignore[arg-type]
            model=document["model"],  # type: ignore[arg-type]
            sensor=document["sensor"],  # type: ignore[arg-type]
            vid=document["vid"],  # type: ignore[arg-type]
            pid=document["pid"],  # type: ignore[arg-type]
            serial_number=document["serial_number"],  # type: ignore[arg-type]
            device_key=document["device_key"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class PixelBufferLayout:
    """Exact byte layout for one supported synthetic image buffer.

    The current evidence format intentionally supports only the two layouts
    exercised by the fake B0477 path: byte-packed YUY2 input and interleaved
    RGB8 derived images.  Both are single-byte channel formats, so endianness
    is explicitly recorded as not applicable rather than silently assumed.
    Color primaries, transfer function, matrix/range, chroma siting, and row
    origin are also part of the byte interpretation contract; two buffers with
    identical bytes but different values for any of those fields are different
    evidence.  Row padding is rejected; accepting it would require separately
    binding the active-pixel offset and padding contents.
    """

    pixel_format: str
    pixel_layout: str
    width_px: int
    height_px: int
    row_stride_bytes: int
    channels: tuple[str, ...]
    bits_per_channel: int
    endianness: str
    color_primaries: str
    transfer_characteristics: str
    matrix_coefficients: str
    quantization_range: str
    chroma_siting: str
    row_origin: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "pixel_format", _token(self.pixel_format, "pixel_format"))
        object.__setattr__(self, "pixel_layout", _token(self.pixel_layout, "pixel_layout"))
        object.__setattr__(
            self,
            "width_px",
            _integer(self.width_px, "layout width_px", minimum=1, maximum=16_384),
        )
        object.__setattr__(
            self,
            "height_px",
            _integer(self.height_px, "layout height_px", minimum=1, maximum=16_384),
        )
        object.__setattr__(
            self,
            "row_stride_bytes",
            _integer(
                self.row_stride_bytes,
                "row_stride_bytes",
                minimum=1,
                maximum=MAX_FRAME_ARTIFACT_BYTES,
            ),
        )
        if not isinstance(self.channels, tuple) or not self.channels:
            raise SensorSessionEvidenceError("channels must be a nonempty immutable tuple")
        parsed_channels = tuple(_token(value, "channel") for value in self.channels)
        if len(parsed_channels) != len(set(parsed_channels)):
            raise SensorSessionEvidenceError("channels contains a duplicate")
        object.__setattr__(self, "channels", parsed_channels)
        object.__setattr__(
            self,
            "bits_per_channel",
            _integer(
                self.bits_per_channel,
                "bits_per_channel",
                minimum=1,
                maximum=64,
            ),
        )
        object.__setattr__(self, "endianness", _token(self.endianness, "endianness"))
        for name in (
            "color_primaries",
            "transfer_characteristics",
            "matrix_coefficients",
            "quantization_range",
            "chroma_siting",
            "row_origin",
        ):
            object.__setattr__(self, name, _token(getattr(self, name), name))

        if self.pixel_format == "YUY2":
            if self.width_px % 2:
                raise SensorSessionEvidenceError("YUY2 width must be even")
            expected = (
                "PACKED_Y0_U0_Y1_V0_422",
                self.width_px * 2,
                ("Y", "U", "V"),
                8,
                "NOT_APPLICABLE_8_BIT",
                "SRGB_BT709",
                "SRGB",
                "BT601_YCBCR",
                "FULL_Y0_255_C0_255",
                "COSITED_LEFT_422",
                "TOP_LEFT",
            )
        elif self.pixel_format == "RGB8":
            expected = (
                "INTERLEAVED_R_G_B",
                self.width_px * 3,
                ("R", "G", "B"),
                8,
                "NOT_APPLICABLE_8_BIT",
                "SRGB_BT709",
                "SRGB",
                "IDENTITY_RGB",
                "FULL_0_255",
                "NOT_APPLICABLE_RGB",
                "TOP_LEFT",
            )
        else:
            raise SensorSessionEvidenceError(
                f"unsupported synthetic pixel format {self.pixel_format!r}"
            )
        observed = (
            self.pixel_layout,
            self.row_stride_bytes,
            self.channels,
            self.bits_per_channel,
            self.endianness,
            self.color_primaries,
            self.transfer_characteristics,
            self.matrix_coefficients,
            self.quantization_range,
            self.chroma_siting,
            self.row_origin,
        )
        if observed != expected:
            raise SensorSessionEvidenceError(
                f"{self.pixel_format} layout metadata is not exact"
            )
        if self.expected_byte_length > MAX_FRAME_ARTIFACT_BYTES:
            raise SensorSessionEvidenceError("pixel buffer exceeds frame artifact limit")

    @property
    def expected_byte_length(self) -> int:
        return self.row_stride_bytes * self.height_px

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": PIXEL_LAYOUT_SCHEMA,
            "pixel_format": self.pixel_format,
            "pixel_layout": self.pixel_layout,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "row_stride_bytes": self.row_stride_bytes,
            "channels": list(self.channels),
            "channel_count": self.channel_count,
            "bits_per_channel": self.bits_per_channel,
            "endianness": self.endianness,
            "color_primaries": self.color_primaries,
            "transfer_characteristics": self.transfer_characteristics,
            "matrix_coefficients": self.matrix_coefficients,
            "quantization_range": self.quantization_range,
            "chroma_siting": self.chroma_siting,
            "row_origin": self.row_origin,
            "expected_byte_length": self.expected_byte_length,
        }

    @classmethod
    def from_dict(cls, value: object) -> PixelBufferLayout:
        fields = frozenset(
            {
                "schema",
                "pixel_format",
                "pixel_layout",
                "width_px",
                "height_px",
                "row_stride_bytes",
                "channels",
                "channel_count",
                "bits_per_channel",
                "endianness",
                "color_primaries",
                "transfer_characteristics",
                "matrix_coefficients",
                "quantization_range",
                "chroma_siting",
                "row_origin",
                "expected_byte_length",
            }
        )
        document = _exact_mapping(value, fields, "pixel layout")
        if document["schema"] != PIXEL_LAYOUT_SCHEMA:
            raise SensorSessionEvidenceError("pixel layout schema is invalid")
        raw_channels = document["channels"]
        if not isinstance(raw_channels, list):
            raise SensorSessionEvidenceError("pixel layout channels must be a JSON list")
        result = cls(
            pixel_format=document["pixel_format"],  # type: ignore[arg-type]
            pixel_layout=document["pixel_layout"],  # type: ignore[arg-type]
            width_px=document["width_px"],  # type: ignore[arg-type]
            height_px=document["height_px"],  # type: ignore[arg-type]
            row_stride_bytes=document["row_stride_bytes"],  # type: ignore[arg-type]
            channels=tuple(raw_channels),  # type: ignore[arg-type]
            bits_per_channel=document["bits_per_channel"],  # type: ignore[arg-type]
            endianness=document["endianness"],  # type: ignore[arg-type]
            color_primaries=document["color_primaries"],  # type: ignore[arg-type]
            transfer_characteristics=document["transfer_characteristics"],  # type: ignore[arg-type]
            matrix_coefficients=document["matrix_coefficients"],  # type: ignore[arg-type]
            quantization_range=document["quantization_range"],  # type: ignore[arg-type]
            chroma_siting=document["chroma_siting"],  # type: ignore[arg-type]
            row_origin=document["row_origin"],  # type: ignore[arg-type]
        )
        if document["expected_byte_length"] != result.expected_byte_length:
            raise SensorSessionEvidenceError("pixel layout expected byte length mismatch")
        if document["channel_count"] != result.channel_count:
            raise SensorSessionEvidenceError("pixel layout channel count mismatch")
        return result

    @classmethod
    def packed_yuy2(cls, width_px: int, height_px: int) -> PixelBufferLayout:
        return cls(
            pixel_format="YUY2",
            pixel_layout="PACKED_Y0_U0_Y1_V0_422",
            width_px=width_px,
            height_px=height_px,
            row_stride_bytes=width_px * 2,
            channels=("Y", "U", "V"),
            bits_per_channel=8,
            endianness="NOT_APPLICABLE_8_BIT",
            color_primaries="SRGB_BT709",
            transfer_characteristics="SRGB",
            matrix_coefficients="BT601_YCBCR",
            quantization_range="FULL_Y0_255_C0_255",
            chroma_siting="COSITED_LEFT_422",
            row_origin="TOP_LEFT",
        )

    @classmethod
    def interleaved_rgb8(cls, width_px: int, height_px: int) -> PixelBufferLayout:
        return cls(
            pixel_format="RGB8",
            pixel_layout="INTERLEAVED_R_G_B",
            width_px=width_px,
            height_px=height_px,
            row_stride_bytes=width_px * 3,
            channels=("R", "G", "B"),
            bits_per_channel=8,
            endianness="NOT_APPLICABLE_8_BIT",
            color_primaries="SRGB_BT709",
            transfer_characteristics="SRGB",
            matrix_coefficients="IDENTITY_RGB",
            quantization_range="FULL_0_255",
            chroma_siting="NOT_APPLICABLE_RGB",
            row_origin="TOP_LEFT",
        )


@dataclass(frozen=True, slots=True)
class FramePixelLayouts:
    """Raw, decoded, and undistorted layouts bound as one mode contract."""

    raw: PixelBufferLayout
    decoded: PixelBufferLayout
    undistorted: PixelBufferLayout

    def __post_init__(self) -> None:
        for name in ("raw", "decoded", "undistorted"):
            if not isinstance(getattr(self, name), PixelBufferLayout):
                raise TypeError(f"{name} must be PixelBufferLayout")
        dimensions = {
            (item.width_px, item.height_px)
            for item in (self.raw, self.decoded, self.undistorted)
        }
        if len(dimensions) != 1:
            raise SensorSessionEvidenceError(
                "raw, decoded, and undistorted layouts must share dimensions"
            )
        if self.decoded.pixel_format != "RGB8" or self.undistorted.pixel_format != "RGB8":
            raise SensorSessionEvidenceError(
                "decoded and undistorted synthetic layouts must be RGB8"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "raw": self.raw.to_dict(),
            "decoded": self.decoded.to_dict(),
            "undistorted": self.undistorted.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> FramePixelLayouts:
        document = _exact_mapping(
            value, frozenset({"raw", "decoded", "undistorted"}), "frame layouts"
        )
        return cls(
            raw=PixelBufferLayout.from_dict(document["raw"]),
            decoded=PixelBufferLayout.from_dict(document["decoded"]),
            undistorted=PixelBufferLayout.from_dict(document["undistorted"]),
        )


@dataclass(frozen=True, slots=True)
class CameraModeSnapshot:
    """One exact, rational-fps synthetic video mode."""

    width_px: int
    height_px: int
    fps_numerator: int
    fps_denominator: int
    pixel_format: str
    pixel_layouts: FramePixelLayouts = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "width_px", _integer(self.width_px, "width_px", minimum=1, maximum=16_384))
        object.__setattr__(self, "height_px", _integer(self.height_px, "height_px", minimum=1, maximum=16_384))
        object.__setattr__(self, "fps_numerator", _integer(self.fps_numerator, "fps_numerator", minimum=1, maximum=100_000))
        object.__setattr__(self, "fps_denominator", _integer(self.fps_denominator, "fps_denominator", minimum=1, maximum=100_000))
        object.__setattr__(self, "pixel_format", _token(self.pixel_format, "pixel_format"))
        if self.pixel_format != "YUY2":
            raise SensorSessionEvidenceError(
                "the synthetic raw sensor-session format currently supports YUY2 only"
            )
        object.__setattr__(
            self,
            "pixel_layouts",
            FramePixelLayouts(
                raw=PixelBufferLayout.packed_yuy2(self.width_px, self.height_px),
                decoded=PixelBufferLayout.interleaved_rgb8(
                    self.width_px, self.height_px
                ),
                undistorted=PixelBufferLayout.interleaved_rgb8(
                    self.width_px, self.height_px
                ),
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "transport": "SIMULATED_USB",
            "width_px": self.width_px,
            "height_px": self.height_px,
            "fps_numerator": self.fps_numerator,
            "fps_denominator": self.fps_denominator,
            "pixel_format": self.pixel_format,
            "pixel_layouts": self.pixel_layouts.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> CameraModeSnapshot:
        fields = frozenset(
            {"transport", "width_px", "height_px", "fps_numerator", "fps_denominator", "pixel_format", "pixel_layouts"}
        )
        document = _exact_mapping(value, fields, "camera mode")
        if document["transport"] != "SIMULATED_USB":
            raise SensorSessionEvidenceError("camera mode is not simulated")
        result = cls(
            width_px=document["width_px"],  # type: ignore[arg-type]
            height_px=document["height_px"],  # type: ignore[arg-type]
            fps_numerator=document["fps_numerator"],  # type: ignore[arg-type]
            fps_denominator=document["fps_denominator"],  # type: ignore[arg-type]
            pixel_format=document["pixel_format"],  # type: ignore[arg-type]
        )
        if FramePixelLayouts.from_dict(document["pixel_layouts"]) != result.pixel_layouts:
            raise SensorSessionEvidenceError(
                "camera mode pixel layouts do not match its dimensions/format"
            )
        return result


@dataclass(frozen=True, slots=True)
class CameraControlSnapshot:
    """Stable manual-control snapshot suitable for fake UVC readback."""

    exposure_us: int
    gain_milli_db: int
    white_balance_kelvin: int
    focus_position: int
    auto_exposure: bool = False
    auto_white_balance: bool = False
    autofocus: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "exposure_us", _integer(self.exposure_us, "exposure_us", minimum=1, maximum=10_000_000))
        object.__setattr__(self, "gain_milli_db", _integer(self.gain_milli_db, "gain_milli_db", maximum=240_000))
        object.__setattr__(self, "white_balance_kelvin", _integer(self.white_balance_kelvin, "white_balance_kelvin", minimum=1_000, maximum=20_000))
        object.__setattr__(self, "focus_position", _integer(self.focus_position, "focus_position", maximum=1_000_000))
        for name in ("auto_exposure", "auto_white_balance", "autofocus"):
            if not isinstance(getattr(self, name), bool):
                raise SensorSessionEvidenceError(f"{name} must be boolean")

    def to_dict(self) -> dict[str, object]:
        return {
            "exposure_us": self.exposure_us,
            "gain_milli_db": self.gain_milli_db,
            "white_balance_kelvin": self.white_balance_kelvin,
            "focus_position": self.focus_position,
            "auto_exposure": self.auto_exposure,
            "auto_white_balance": self.auto_white_balance,
            "autofocus": self.autofocus,
        }

    @classmethod
    def from_dict(cls, value: object) -> CameraControlSnapshot:
        fields = frozenset(
            {"exposure_us", "gain_milli_db", "white_balance_kelvin", "focus_position", "auto_exposure", "auto_white_balance", "autofocus"}
        )
        document = _exact_mapping(value, fields, "camera controls")
        return cls(
            exposure_us=document["exposure_us"],  # type: ignore[arg-type]
            gain_milli_db=document["gain_milli_db"],  # type: ignore[arg-type]
            white_balance_kelvin=document["white_balance_kelvin"],  # type: ignore[arg-type]
            focus_position=document["focus_position"],  # type: ignore[arg-type]
            auto_exposure=document["auto_exposure"],  # type: ignore[arg-type]
            auto_white_balance=document["auto_white_balance"],  # type: ignore[arg-type]
            autofocus=document["autofocus"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class SensorTimingBracket:
    """Ordered monotonic timestamps surrounding camera and feedback evidence."""

    frame_sequence: int
    event_monotonic_ns: tuple[int, ...]
    feedback_receive_buffer_bytes_before_request: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_sequence", _integer(self.frame_sequence, "frame_sequence", minimum=1))
        if not isinstance(self.event_monotonic_ns, tuple) or len(self.event_monotonic_ns) != len(_TIMING_EVENT_NAMES):
            raise SensorSessionEvidenceError("timing bracket must contain every event exactly once")
        parsed = tuple(
            _integer(value, f"timing event {name}")
            for name, value in zip(_TIMING_EVENT_NAMES, self.event_monotonic_ns, strict=True)
        )
        if any(later <= earlier for earlier, later in zip(parsed, parsed[1:])):
            raise SensorSessionEvidenceError("timing events must be strictly increasing")
        object.__setattr__(self, "event_monotonic_ns", parsed)
        buffered = _integer(
            self.feedback_receive_buffer_bytes_before_request,
            "feedback receive-buffer byte count",
            maximum=MAX_WIRE_LINE_BYTES,
        )
        if buffered != 0:
            raise SensorSessionEvidenceError("feedback input was already buffered and is stale")

    def timestamp(self, event: str) -> int:
        try:
            return self.event_monotonic_ns[_TIMING_EVENT_NAMES.index(event)]
        except ValueError as exc:
            raise SensorSessionEvidenceError(f"unknown timing event {event!r}") from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": TIMING_SCHEMA,
            "clock": "SYNTHETIC_MONOTONIC_NS",
            "frame_sequence": self.frame_sequence,
            "events": [
                {"event": name, "monotonic_ns": timestamp}
                for name, timestamp in zip(
                    _TIMING_EVENT_NAMES, self.event_monotonic_ns, strict=True
                )
            ],
            "feedback_receive_buffer_bytes_before_request": self.feedback_receive_buffer_bytes_before_request,
            "authority": dict(_AUTHORITY),
        }

    @classmethod
    def from_dict(cls, value: object) -> SensorTimingBracket:
        fields = frozenset(
            {"schema", "clock", "frame_sequence", "events", "feedback_receive_buffer_bytes_before_request", "authority"}
        )
        document = _exact_mapping(value, fields, "timing artifact")
        if document["schema"] != TIMING_SCHEMA or document["clock"] != "SYNTHETIC_MONOTONIC_NS":
            raise SensorSessionEvidenceError("timing schema or clock is invalid")
        _authority(document["authority"], "timing authority")
        raw_events = document["events"]
        if not isinstance(raw_events, list) or len(raw_events) != len(_TIMING_EVENT_NAMES):
            raise SensorSessionEvidenceError("timing event list is not exact")
        timestamps: list[int] = []
        for expected_name, raw in zip(_TIMING_EVENT_NAMES, raw_events, strict=True):
            event = _exact_mapping(raw, frozenset({"event", "monotonic_ns"}), "timing event")
            if event["event"] != expected_name:
                raise SensorSessionEvidenceError("timing events are reordered or duplicated")
            timestamps.append(event["monotonic_ns"])  # type: ignore[arg-type]
        return cls(
            frame_sequence=document["frame_sequence"],  # type: ignore[arg-type]
            event_monotonic_ns=tuple(timestamps),
            feedback_receive_buffer_bytes_before_request=document[
                "feedback_receive_buffer_bytes_before_request"
            ],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class SensorSessionContract:
    """Expected fake source plus bounded freshness and duration policy.

    ``maximum_frame_age_ns`` covers capture through completed perception.  It
    is intentionally not merely a transport receive-latency threshold.
    ``maximum_stage_duration_ns`` bounds every adjacent event interval and
    ``maximum_session_duration_ns`` bounds the complete bracket.
    """

    identity: SyntheticCameraIdentity
    mode: CameraModeSnapshot
    controls: CameraControlSnapshot
    calibration_sha256: str
    minimum_frame_sequence_exclusive: int
    not_before_monotonic_ns: int
    maximum_frame_age_ns: int
    maximum_feedback_latency_ns: int
    maximum_stage_duration_ns: int = _DEFAULT_MAX_STAGE_DURATION_NS
    maximum_session_duration_ns: int = _DEFAULT_MAX_SESSION_DURATION_NS

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SyntheticCameraIdentity):
            raise TypeError("identity must be SyntheticCameraIdentity")
        if not isinstance(self.mode, CameraModeSnapshot):
            raise TypeError("mode must be CameraModeSnapshot")
        if not isinstance(self.controls, CameraControlSnapshot):
            raise TypeError("controls must be CameraControlSnapshot")
        object.__setattr__(self, "calibration_sha256", _digest(self.calibration_sha256, "calibration_sha256"))
        object.__setattr__(self, "minimum_frame_sequence_exclusive", _integer(self.minimum_frame_sequence_exclusive, "minimum_frame_sequence_exclusive"))
        object.__setattr__(self, "not_before_monotonic_ns", _integer(self.not_before_monotonic_ns, "not_before_monotonic_ns"))
        object.__setattr__(self, "maximum_frame_age_ns", _integer(self.maximum_frame_age_ns, "maximum_frame_age_ns", minimum=1))
        object.__setattr__(self, "maximum_feedback_latency_ns", _integer(self.maximum_feedback_latency_ns, "maximum_feedback_latency_ns", minimum=1))
        object.__setattr__(
            self,
            "maximum_stage_duration_ns",
            _integer(
                self.maximum_stage_duration_ns,
                "maximum_stage_duration_ns",
                minimum=1,
            ),
        )
        object.__setattr__(
            self,
            "maximum_session_duration_ns",
            _integer(
                self.maximum_session_duration_ns,
                "maximum_session_duration_ns",
                minimum=1,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": CONTRACT_SCHEMA,
            "source_kind": "SYNTHETIC_SENSOR_FIXTURE_ONLY",
            "identity": self.identity.to_dict(),
            "mode": self.mode.to_dict(),
            "controls": self.controls.to_dict(),
            "calibration_sha256": self.calibration_sha256,
            "minimum_frame_sequence_exclusive": self.minimum_frame_sequence_exclusive,
            "not_before_monotonic_ns": self.not_before_monotonic_ns,
            "maximum_frame_age_ns": self.maximum_frame_age_ns,
            "maximum_feedback_latency_ns": self.maximum_feedback_latency_ns,
            "maximum_stage_duration_ns": self.maximum_stage_duration_ns,
            "maximum_session_duration_ns": self.maximum_session_duration_ns,
            "authority": dict(_AUTHORITY),
        }

    @classmethod
    def from_dict(cls, value: object) -> SensorSessionContract:
        fields = frozenset(
            {"schema", "source_kind", "identity", "mode", "controls", "calibration_sha256", "minimum_frame_sequence_exclusive", "not_before_monotonic_ns", "maximum_frame_age_ns", "maximum_feedback_latency_ns", "maximum_stage_duration_ns", "maximum_session_duration_ns", "authority"}
        )
        document = _exact_mapping(value, fields, "session contract")
        if document["schema"] != CONTRACT_SCHEMA or document["source_kind"] != "SYNTHETIC_SENSOR_FIXTURE_ONLY":
            raise SensorSessionEvidenceError("session contract is not simulation-only v2")
        _authority(document["authority"], "contract authority")
        return cls(
            identity=SyntheticCameraIdentity.from_dict(document["identity"]),
            mode=CameraModeSnapshot.from_dict(document["mode"]),
            controls=CameraControlSnapshot.from_dict(document["controls"]),
            calibration_sha256=document["calibration_sha256"],  # type: ignore[arg-type]
            minimum_frame_sequence_exclusive=document["minimum_frame_sequence_exclusive"],  # type: ignore[arg-type]
            not_before_monotonic_ns=document["not_before_monotonic_ns"],  # type: ignore[arg-type]
            maximum_frame_age_ns=document["maximum_frame_age_ns"],  # type: ignore[arg-type]
            maximum_feedback_latency_ns=document["maximum_feedback_latency_ns"],  # type: ignore[arg-type]
            maximum_stage_duration_ns=document["maximum_stage_duration_ns"],  # type: ignore[arg-type]
            maximum_session_duration_ns=document["maximum_session_duration_ns"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class RawSensorSessionInput:
    """Detached bytes and records produced by deterministic fake providers."""

    identity: SyntheticCameraIdentity
    mode: CameraModeSnapshot
    controls: CameraControlSnapshot
    timing: SensorTimingBracket
    raw_frame_bytes: bytes
    decoded_frame_bytes: bytes
    undistorted_frame_bytes: bytes
    detector_record: Mapping[str, Any]
    pose_record: Mapping[str, Any]
    t105_request_line: bytes
    t1051_response_line: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SyntheticCameraIdentity):
            raise TypeError("identity must be SyntheticCameraIdentity")
        if not isinstance(self.mode, CameraModeSnapshot):
            raise TypeError("mode must be CameraModeSnapshot")
        if not isinstance(self.controls, CameraControlSnapshot):
            raise TypeError("controls must be CameraControlSnapshot")
        if not isinstance(self.timing, SensorTimingBracket):
            raise TypeError("timing must be SensorTimingBracket")
        for name in ("raw_frame_bytes", "decoded_frame_bytes", "undistorted_frame_bytes"):
            value = getattr(self, name)
            if not isinstance(value, bytes) or not value or len(value) > MAX_FRAME_ARTIFACT_BYTES:
                raise SensorSessionEvidenceError(f"{name} must be nonempty bounded bytes")
        expected_lengths = {
            "raw_frame_bytes": self.mode.pixel_layouts.raw.expected_byte_length,
            "decoded_frame_bytes": self.mode.pixel_layouts.decoded.expected_byte_length,
            "undistorted_frame_bytes": self.mode.pixel_layouts.undistorted.expected_byte_length,
        }
        for name, expected in expected_lengths.items():
            if len(getattr(self, name)) != expected:
                raise SensorSessionEvidenceError(
                    f"{name} byte length does not match its pixel layout: "
                    f"expected {expected}, observed {len(getattr(self, name))}"
                )
        for name in ("t105_request_line", "t1051_response_line"):
            value = getattr(self, name)
            if not isinstance(value, bytes) or not value or len(value) > MAX_WIRE_LINE_BYTES:
                raise SensorSessionEvidenceError(f"{name} must be nonempty bounded bytes")
        for name in ("detector_record", "pose_record"):
            value = getattr(self, name)
            if not isinstance(value, Mapping) or not isinstance(value.get("schema"), str):
                raise SensorSessionEvidenceError(f"{name} must be a schema-labelled JSON object")
            _validate_json_tree(value)
            # Copy and freeze caller-owned records so mutation cannot change the
            # evidence between validation and serialization.
            object.__setattr__(self, name, _deep_freeze(_deep_thaw(value)))


@dataclass(frozen=True, slots=True)
class SensorSessionRecord:
    record_id: str
    directory: Path
    manifest_path: Path
    manifest_sha256: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class VerifiedSensorSessionRecord:
    """Deeply immutable, byte-complete result of strict package verification."""

    record_id: str
    directory: Path
    manifest_sha256: str
    content_sha256: str
    contract: SensorSessionContract
    applied_contract: SensorSessionContract
    stored_contract_sha256: str
    applied_contract_sha256: str
    identity: SyntheticCameraIdentity
    mode: CameraModeSnapshot
    controls: CameraControlSnapshot
    timing: SensorTimingBracket
    calibration_sha256: str
    documents: Mapping[str, Mapping[str, Any]]
    blobs: Mapping[str, bytes]
    feedback_message: Mapping[str, Any]
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _VERIFIED_FACTORY_TOKEN:
            raise SensorSessionEvidenceError(
                "VerifiedSensorSessionRecord can only be created by strict verification"
            )
        if not isinstance(self.record_id, str) or _RECORD_ID.fullmatch(self.record_id) is None:
            raise SensorSessionEvidenceError("verified record_id is invalid")
        if not isinstance(self.directory, Path):
            raise TypeError("verified directory must be Path")
        object.__setattr__(
            self,
            "manifest_sha256",
            _digest(self.manifest_sha256, "verified manifest_sha256"),
        )
        object.__setattr__(
            self,
            "content_sha256",
            _digest(self.content_sha256, "verified content_sha256"),
        )
        if self.record_id != f"sensor-session-{self.content_sha256}":
            raise SensorSessionEvidenceError(
                "verified record_id does not match content_sha256"
            )
        if not isinstance(self.contract, SensorSessionContract):
            raise TypeError("verified stored contract must be SensorSessionContract")
        if not isinstance(self.applied_contract, SensorSessionContract):
            raise TypeError("verified applied contract must be SensorSessionContract")
        object.__setattr__(
            self,
            "stored_contract_sha256",
            _digest(self.stored_contract_sha256, "stored_contract_sha256"),
        )
        object.__setattr__(
            self,
            "applied_contract_sha256",
            _digest(self.applied_contract_sha256, "applied_contract_sha256"),
        )
        if self.stored_contract_sha256 != _stable_hash(self.contract.to_dict()):
            raise SensorSessionEvidenceError("stored contract digest mismatch")
        if self.applied_contract_sha256 != _stable_hash(
            self.applied_contract.to_dict()
        ):
            raise SensorSessionEvidenceError("applied contract digest mismatch")
        _validate_replay_contract_is_not_weaker(self.contract, self.applied_contract)
        if self.identity != self.contract.identity or self.mode != self.contract.mode:
            raise SensorSessionEvidenceError(
                "verified camera identity/mode differs from stored contract"
            )
        if self.controls != self.contract.controls:
            raise SensorSessionEvidenceError(
                "verified camera controls differ from stored contract"
            )
        if self.timing.frame_sequence <= self.contract.minimum_frame_sequence_exclusive:
            raise SensorSessionEvidenceError(
                "verified timing does not satisfy stored sequence policy"
            )
        object.__setattr__(
            self,
            "calibration_sha256",
            _digest(self.calibration_sha256, "verified calibration_sha256"),
        )
        if self.calibration_sha256 != self.contract.calibration_sha256:
            raise SensorSessionEvidenceError(
                "verified calibration differs from stored contract"
            )
        if set(self.documents) != _JSON_ARTIFACTS:
            raise SensorSessionEvidenceError("verified JSON artifact set is not exact")
        expected_blob_names = _EXPECTED_FILES - _JSON_ARTIFACTS - {"manifest.json"}
        if set(self.blobs) != expected_blob_names:
            raise SensorSessionEvidenceError("verified byte artifact set is not exact")
        object.__setattr__(
            self,
            "documents",
            MappingProxyType(
                {name: _deep_freeze(document) for name, document in self.documents.items()}
            ),
        )
        object.__setattr__(self, "blobs", MappingProxyType(dict(self.blobs)))
        object.__setattr__(self, "feedback_message", _deep_freeze(self.feedback_message))

    def document(self, name: str) -> Mapping[str, Any]:
        try:
            return self.documents[name]
        except KeyError as exc:
            raise SensorSessionEvidenceError(f"no verified JSON artifact {name!r}") from exc

    def blob(self, name: str) -> bytes:
        try:
            return self.blobs[name]
        except KeyError as exc:
            raise SensorSessionEvidenceError(f"no verified byte artifact {name!r}") from exc


@dataclass(frozen=True, slots=True)
class ReplayedSensorSession:
    """In-memory replay result; all bytes came from a verified package."""

    record: VerifiedSensorSessionRecord
    replay_sha256: str
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _REPLAY_FACTORY_TOKEN:
            raise SensorSessionEvidenceError(
                "ReplayedSensorSession can only be created by strict replay"
            )
        if not isinstance(self.record, VerifiedSensorSessionRecord):
            raise TypeError("record must be VerifiedSensorSessionRecord")
        object.__setattr__(
            self,
            "replay_sha256",
            _digest(self.replay_sha256, "replay_sha256"),
        )
        if self.replay_sha256 != _stable_hash(_replay_core(self.record)):
            raise SensorSessionEvidenceError("replay digest does not bind its contracts")

    @property
    def status(self) -> str:
        return "REPLAY_VERIFIED_SIMULATION_ONLY"

    @property
    def raw_frame_bytes(self) -> bytes:
        return self.record.blob("raw-frame.bin")

    @property
    def decoded_frame_bytes(self) -> bytes:
        return self.record.blob("decoded-frame.bin")

    @property
    def undistorted_frame_bytes(self) -> bytes:
        return self.record.blob("undistorted-frame.bin")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": REPLAY_SCHEMA,
            "status": self.status,
            "record_id": self.record.record_id,
            "content_sha256": self.record.content_sha256,
            "replay_sha256": self.replay_sha256,
            "stored_contract_sha256": self.record.stored_contract_sha256,
            "applied_contract_sha256": self.record.applied_contract_sha256,
            "contract_override_applied": (
                self.record.stored_contract_sha256
                != self.record.applied_contract_sha256
            ),
            "stored_contract": self.record.contract.to_dict(),
            "applied_contract": self.record.applied_contract.to_dict(),
            "frame_sequence": self.record.timing.frame_sequence,
            "raw_frame_sha256": hashlib.sha256(self.raw_frame_bytes).hexdigest(),
            "decoded_frame_sha256": hashlib.sha256(self.decoded_frame_bytes).hexdigest(),
            "undistorted_frame_sha256": hashlib.sha256(self.undistorted_frame_bytes).hexdigest(),
            "authority": dict(_AUTHORITY),
        }


def _validate_session_against_contract(
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    if session.identity != contract.identity:
        raise SensorSessionEvidenceError("camera identity differs from the session contract")
    if session.mode != contract.mode:
        raise SensorSessionEvidenceError("observed camera mode differs from the session contract")
    if session.controls != contract.controls:
        raise SensorSessionEvidenceError("observed camera controls differ from the session contract")
    _validate_timing_against_contract(session.timing, contract)
    try:
        request = decode_line(session.t105_request_line)
    except ProtocolError as exc:
        raise SensorSessionEvidenceError(f"invalid recorded T=105 request line: {exc}") from exc
    if set(request) != {"T"} or request.get("T") != FEEDBACK_REQUEST_TYPE:
        raise SensorSessionEvidenceError("recorded request must be exactly one T=105 object")
    try:
        validate_feedback_response_line(
            session.t1051_response_line,
            max_line_bytes=MAX_WIRE_LINE_BYTES,
        )
    except FeedbackWireError as exc:
        raise SensorSessionEvidenceError(f"invalid recorded T=1051 response line: {exc}") from exc


def _validate_timing_against_contract(
    timing: SensorTimingBracket,
    contract: SensorSessionContract,
) -> None:
    if timing.frame_sequence <= contract.minimum_frame_sequence_exclusive:
        raise SensorSessionEvidenceError("frame sequence is stale for the session contract")
    captured = timing.timestamp("FRAME_CAPTURED")
    perception_completed = timing.timestamp("PERCEPTION_COMPLETED")
    if captured < contract.not_before_monotonic_ns:
        raise SensorSessionEvidenceError("frame timestamp predates the freshness boundary")
    if perception_completed - captured > contract.maximum_frame_age_ns:
        raise SensorSessionEvidenceError(
            "frame exceeded the maximum capture-to-perception age"
        )
    sent = timing.timestamp("FEEDBACK_REQUEST_SENT")
    response = timing.timestamp("FEEDBACK_RESPONSE_RECEIVED")
    if response - sent > contract.maximum_feedback_latency_ns:
        raise SensorSessionEvidenceError("feedback exceeded the maximum accepted latency")
    stage_durations = tuple(
        later - earlier
        for earlier, later in zip(
            timing.event_monotonic_ns, timing.event_monotonic_ns[1:]
        )
    )
    if any(
        duration > contract.maximum_stage_duration_ns
        for duration in stage_durations
    ):
        raise SensorSessionEvidenceError(
            "timing stage exceeded the maximum accepted duration"
        )
    session_duration = (
        timing.timestamp("SESSION_COMPLETED")
        - timing.timestamp("SESSION_STARTED")
    )
    if session_duration > contract.maximum_session_duration_ns:
        raise SensorSessionEvidenceError(
            "session exceeded the maximum accepted duration"
        )


def _validate_replay_contract_is_not_weaker(
    stored: SensorSessionContract,
    applied: SensorSessionContract,
) -> None:
    """Require an override to preserve identity and tighten every policy bound."""

    if not isinstance(stored, SensorSessionContract) or not isinstance(
        applied, SensorSessionContract
    ):
        raise TypeError("stored and applied contracts must be SensorSessionContract")
    immutable_bindings = (
        (stored.identity, applied.identity, "camera identity"),
        (stored.mode, applied.mode, "camera mode/pixel layouts"),
        (stored.controls, applied.controls, "camera controls"),
        (
            stored.calibration_sha256,
            applied.calibration_sha256,
            "calibration",
        ),
    )
    for recorded, selected, label in immutable_bindings:
        if selected != recorded:
            raise SensorSessionEvidenceError(
                f"replay contract changes the stored {label} binding"
            )

    # Higher lower-bounds and lower upper-bounds are equally or more
    # conservative.  No independent threshold may be relaxed to compensate for
    # tightening a different one.
    if (
        applied.minimum_frame_sequence_exclusive
        < stored.minimum_frame_sequence_exclusive
    ):
        raise SensorSessionEvidenceError(
            "replay contract weakens the minimum frame sequence"
        )
    if applied.not_before_monotonic_ns < stored.not_before_monotonic_ns:
        raise SensorSessionEvidenceError(
            "replay contract weakens the freshness boundary"
        )
    upper_bounds = (
        (
            stored.maximum_frame_age_ns,
            applied.maximum_frame_age_ns,
            "capture-to-perception age",
        ),
        (
            stored.maximum_feedback_latency_ns,
            applied.maximum_feedback_latency_ns,
            "feedback latency",
        ),
        (
            stored.maximum_stage_duration_ns,
            applied.maximum_stage_duration_ns,
            "stage duration",
        ),
        (
            stored.maximum_session_duration_ns,
            applied.maximum_session_duration_ns,
            "session duration",
        ),
    )
    for recorded_limit, selected_limit, limit_label in upper_bounds:
        if selected_limit > recorded_limit:
            raise SensorSessionEvidenceError(
                f"replay contract weakens the maximum {limit_label}"
            )


def _documents_and_blobs(
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    identity = session.identity.to_dict()
    mode = session.mode.to_dict()
    controls = session.controls.to_dict()
    raw_hash = hashlib.sha256(session.raw_frame_bytes).hexdigest()
    decoded_hash = hashlib.sha256(session.decoded_frame_bytes).hexdigest()
    undistorted_hash = hashlib.sha256(session.undistorted_frame_bytes).hexdigest()
    detector = _deep_thaw(session.detector_record)
    pose = _deep_thaw(session.pose_record)
    documents = {
        "contract.json": contract.to_dict(),
        "camera.json": {
            "schema": CAMERA_SCHEMA,
            "source_kind": "FAKE_UVC",
            "identity": identity,
            "selected_mode": contract.mode.to_dict(),
            "observed_mode": mode,
            "requested_controls": contract.controls.to_dict(),
            "observed_controls": controls,
            "frame_sequence": session.timing.frame_sequence,
            "snapshot_sha256": {
                "identity": _stable_hash(identity),
                "selected_mode": _stable_hash(contract.mode.to_dict()),
                "observed_mode": _stable_hash(mode),
                "requested_controls": _stable_hash(contract.controls.to_dict()),
                "observed_controls": _stable_hash(controls),
            },
            "authority": dict(_AUTHORITY),
        },
        "timing.json": session.timing.to_dict(),
        "perception.json": {
            "schema": PERCEPTION_SCHEMA,
            "source_kind": "SYNTHETIC_PERCEPTION_FIXTURE",
            "frame_sequence": session.timing.frame_sequence,
            "calibration_sha256": contract.calibration_sha256,
            "source_sha256": {
                "raw_frame": raw_hash,
                "decoded_frame": decoded_hash,
                "undistorted_frame": undistorted_hash,
                "timing": _stable_hash(session.timing.to_dict()),
            },
            "detector_record": detector,
            "detector_record_sha256": _stable_hash(detector),
            "pose_record": pose,
            "pose_record_sha256": _stable_hash(pose),
            "authority": dict(_AUTHORITY),
        },
    }
    blobs = {
        "raw-frame.bin": session.raw_frame_bytes,
        "decoded-frame.bin": session.decoded_frame_bytes,
        "undistorted-frame.bin": session.undistorted_frame_bytes,
        "t105-request.line": session.t105_request_line,
        "t1051-response.line": session.t1051_response_line,
    }
    return documents, blobs


def _write_new(path: Path, payload: bytes, *, maximum: int) -> None:
    if not payload or len(payload) > maximum:
        raise SensorSessionEvidenceError(f"artifact {path.name} has invalid byte size")
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SensorSessionEvidenceError(f"cannot write sensor artifact {path}") from exc


def _evidence_root(path: Path) -> Path:
    selected = Path(path)
    if selected.is_symlink():
        raise SensorSessionEvidenceError("evidence root must not be a symlink")
    try:
        resolved = selected.resolve(strict=True)
    except OSError as exc:
        raise SensorSessionEvidenceError("evidence root must already exist") from exc
    if not resolved.is_dir():
        raise SensorSessionEvidenceError("evidence root must be a directory")
    return resolved


def record_sensor_session(
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    evidence_root: Path,
) -> SensorSessionRecord:
    """Write one content-addressed package, with ``manifest.json`` last."""

    if not isinstance(session, RawSensorSessionInput):
        raise TypeError("session must be RawSensorSessionInput")
    if not isinstance(contract, SensorSessionContract):
        raise TypeError("contract must be SensorSessionContract")
    _validate_session_against_contract(session, contract)
    documents, blobs = _documents_and_blobs(session, contract)
    root = _evidence_root(evidence_root)

    payloads: dict[str, bytes] = {
        **{name: _canonical_bytes(document) for name, document in documents.items()},
        **blobs,
    }
    rows: list[dict[str, object]] = []
    total = 0
    for name, role, media_type, maximum in _ARTIFACT_ROLES:
        payload = payloads[name]
        if not payload or len(payload) > maximum:
            raise SensorSessionEvidenceError(f"artifact {name} has invalid byte size")
        total += len(payload)
        if total > MAX_PACKAGE_BYTES:
            raise SensorSessionEvidenceError("sensor package exceeds its byte limit")
        rows.append(
            {
                "path": name,
                "role": role,
                "media_type": media_type,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    content_sha256 = _stable_hash(
        {"schema": CONTENT_SCHEMA, "artifacts": rows}
    )
    record_id = f"sensor-session-{content_sha256}"
    destination = root / record_id
    if os.path.lexists(destination):
        raise SensorSessionEvidenceError(
            f"immutable sensor record already exists: {record_id}"
        )
    temporary = root / f".partial-{record_id}-{secrets.token_hex(8)}"
    manifest_payload = b""
    try:
        temporary.mkdir(exist_ok=False)
        for name, _, _, maximum in _ARTIFACT_ROLES:
            _write_new(temporary / name, payloads[name], maximum=maximum)
        core: dict[str, object] = {
            "schema": MANIFEST_SCHEMA,
            "record_id": record_id,
            "content_sha256": content_sha256,
            "artifact_count": len(rows),
            "total_artifact_bytes": total,
            "artifacts": rows,
            "complete": True,
            "manifest_written_last": True,
            "authority": dict(_AUTHORITY),
        }
        manifest = {**core, "package_sha256": _stable_hash(core)}
        manifest_payload = _canonical_bytes(manifest)
        _write_new(
            temporary / "manifest.json",
            manifest_payload,
            maximum=MAX_JSON_ARTIFACT_BYTES,
        )
        if os.path.lexists(destination):
            raise SensorSessionEvidenceError(
                f"immutable sensor record already exists: {record_id}"
            )
        try:
            temporary.rename(destination)
        except OSError as exc:
            raise SensorSessionEvidenceError(
                f"cannot atomically finalize sensor record {record_id}"
            ) from exc
    except Exception:
        if temporary.is_dir() and temporary.parent == root:
            shutil.rmtree(temporary)
        raise
    return SensorSessionRecord(
        record_id=record_id,
        directory=destination,
        manifest_path=destination / "manifest.json",
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        content_sha256=content_sha256,
    )


def _read_bytes(path: Path, *, maximum: int) -> bytes:
    try:
        with path.open("rb") as stream:
            payload = stream.read(maximum + 1)
    except OSError as exc:
        raise SensorSessionEvidenceError(f"cannot read sensor artifact {path.name}") from exc
    if not payload or len(payload) > maximum:
        raise SensorSessionEvidenceError(f"sensor artifact {path.name} has invalid byte size")
    return payload


def _read_json(path: Path, *, maximum: int) -> tuple[dict[str, Any], bytes]:
    payload = _read_bytes(path, maximum=maximum)
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(
                SensorSessionEvidenceError(f"nonfinite JSON constant {value!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SensorSessionEvidenceError(f"invalid strict JSON in {path.name}: {exc}") from exc
    if not isinstance(document, dict):
        raise SensorSessionEvidenceError(f"{path.name} must contain a JSON object")
    _validate_json_tree(document)
    if _canonical_bytes(document) != payload:
        raise SensorSessionEvidenceError(f"sensor artifact is not canonical JSON: {path.name}")
    return document, payload


def _validated_directory(manifest_path: Path) -> tuple[Path, Path]:
    requested = Path(manifest_path)
    if requested.is_symlink() or requested.parent.is_symlink():
        raise SensorSessionEvidenceError("manifest and record directory must not be symlinks")
    try:
        manifest = requested.resolve(strict=True)
    except OSError as exc:
        raise SensorSessionEvidenceError("manifest path does not exist") from exc
    if manifest.name != "manifest.json" or not manifest.is_file():
        raise SensorSessionEvidenceError("manifest path must name manifest.json")
    directory = manifest.parent
    try:
        entries = tuple(directory.iterdir())
    except OSError as exc:
        raise SensorSessionEvidenceError("cannot enumerate sensor record directory") from exc
    actual_files = {entry.name for entry in entries if entry.is_file() and not entry.is_symlink()}
    unsafe = [entry.name for entry in entries if entry.is_symlink() or not entry.is_file()]
    if actual_files != _EXPECTED_FILES or unsafe:
        raise SensorSessionEvidenceError(
            "sensor record directory is not exact; "
            f"files={sorted(actual_files)}, other={sorted(unsafe)}"
        )
    return manifest, directory


def _parse_camera_document(
    value: object,
) -> tuple[SyntheticCameraIdentity, CameraModeSnapshot, CameraControlSnapshot, int]:
    fields = frozenset(
        {"schema", "source_kind", "identity", "selected_mode", "observed_mode", "requested_controls", "observed_controls", "frame_sequence", "snapshot_sha256", "authority"}
    )
    document = _exact_mapping(value, fields, "camera artifact")
    if document["schema"] != CAMERA_SCHEMA or document["source_kind"] != "FAKE_UVC":
        raise SensorSessionEvidenceError("camera artifact is not fake-camera v2")
    _authority(document["authority"], "camera authority")
    identity = SyntheticCameraIdentity.from_dict(document["identity"])
    selected_mode = CameraModeSnapshot.from_dict(document["selected_mode"])
    observed_mode = CameraModeSnapshot.from_dict(document["observed_mode"])
    requested_controls = CameraControlSnapshot.from_dict(document["requested_controls"])
    observed_controls = CameraControlSnapshot.from_dict(document["observed_controls"])
    if selected_mode != observed_mode:
        raise SensorSessionEvidenceError("recorded observed camera mode is wrong")
    if requested_controls != observed_controls:
        raise SensorSessionEvidenceError("recorded camera-control readback is wrong")
    hashes = _exact_mapping(
        document["snapshot_sha256"],
        frozenset({"identity", "selected_mode", "observed_mode", "requested_controls", "observed_controls"}),
        "camera snapshot hashes",
    )
    snapshots = {
        "identity": identity.to_dict(),
        "selected_mode": selected_mode.to_dict(),
        "observed_mode": observed_mode.to_dict(),
        "requested_controls": requested_controls.to_dict(),
        "observed_controls": observed_controls.to_dict(),
    }
    for name, snapshot in snapshots.items():
        if _digest(hashes[name], f"{name} snapshot hash") != _stable_hash(snapshot):
            raise SensorSessionEvidenceError(f"{name} snapshot hash mismatch")
    frame_sequence = _integer(document["frame_sequence"], "camera frame_sequence", minimum=1)
    return identity, observed_mode, observed_controls, frame_sequence


def _validate_perception_document(
    value: object,
    *,
    timing: SensorTimingBracket,
    contract: SensorSessionContract,
    blobs: Mapping[str, bytes],
) -> None:
    fields = frozenset(
        {"schema", "source_kind", "frame_sequence", "calibration_sha256", "source_sha256", "detector_record", "detector_record_sha256", "pose_record", "pose_record_sha256", "authority"}
    )
    document = _exact_mapping(value, fields, "perception artifact")
    if document["schema"] != PERCEPTION_SCHEMA or document["source_kind"] != "SYNTHETIC_PERCEPTION_FIXTURE":
        raise SensorSessionEvidenceError("perception artifact is not synthetic v2")
    _authority(document["authority"], "perception authority")
    if document["frame_sequence"] != timing.frame_sequence:
        raise SensorSessionEvidenceError("perception frame sequence is stale or mismatched")
    if _digest(document["calibration_sha256"], "perception calibration hash") != contract.calibration_sha256:
        raise SensorSessionEvidenceError("perception used the wrong calibration")
    source_hashes = _exact_mapping(
        document["source_sha256"],
        frozenset({"raw_frame", "decoded_frame", "undistorted_frame", "timing"}),
        "perception source hashes",
    )
    expected_sources = {
        "raw_frame": hashlib.sha256(blobs["raw-frame.bin"]).hexdigest(),
        "decoded_frame": hashlib.sha256(blobs["decoded-frame.bin"]).hexdigest(),
        "undistorted_frame": hashlib.sha256(blobs["undistorted-frame.bin"]).hexdigest(),
        "timing": _stable_hash(timing.to_dict()),
    }
    if dict(source_hashes) != expected_sources:
        raise SensorSessionEvidenceError("perception source bindings do not match session bytes")
    detector = document["detector_record"]
    pose = document["pose_record"]
    if not isinstance(detector, Mapping) or not isinstance(detector.get("schema"), str):
        raise SensorSessionEvidenceError("detector record is invalid")
    if not isinstance(pose, Mapping) or not isinstance(pose.get("schema"), str):
        raise SensorSessionEvidenceError("pose record is invalid")
    if _digest(document["detector_record_sha256"], "detector record hash") != _stable_hash(detector):
        raise SensorSessionEvidenceError("detector record hash mismatch")
    if _digest(document["pose_record_sha256"], "pose record hash") != _stable_hash(pose):
        raise SensorSessionEvidenceError("pose record hash mismatch")


def verify_sensor_session_record(
    manifest_path: Path,
    *,
    replay_contract: SensorSessionContract | None = None,
) -> VerifiedSensorSessionRecord:
    """Verify an exact package and optionally apply a newer freshness contract."""

    if replay_contract is not None and not isinstance(replay_contract, SensorSessionContract):
        raise TypeError("replay_contract must be SensorSessionContract or None")
    selected, directory = _validated_directory(manifest_path)
    manifest, manifest_payload = _read_json(selected, maximum=MAX_JSON_ARTIFACT_BYTES)
    if set(manifest) != _MANIFEST_FIELDS:
        raise SensorSessionEvidenceError("sensor manifest fields are not exact")
    if manifest["schema"] != MANIFEST_SCHEMA or manifest["complete"] is not True or manifest["manifest_written_last"] is not True:
        raise SensorSessionEvidenceError("sensor manifest schema or completeness is invalid")
    _authority(manifest["authority"], "manifest authority")
    record_id = manifest["record_id"]
    if not isinstance(record_id, str) or _RECORD_ID.fullmatch(record_id) is None or directory.name != record_id:
        raise SensorSessionEvidenceError("sensor record identity/path is invalid")
    raw_rows = manifest["artifacts"]
    if not isinstance(raw_rows, list) or len(raw_rows) != len(_ARTIFACT_ROLES):
        raise SensorSessionEvidenceError("manifest artifact list is not exact")
    if _integer(manifest["artifact_count"], "artifact_count", maximum=len(_ARTIFACT_ROLES)) != len(_ARTIFACT_ROLES):
        raise SensorSessionEvidenceError("manifest artifact count is invalid")

    documents: dict[str, Mapping[str, Any]] = {}
    blobs: dict[str, bytes] = {}
    total = 0
    normalized_rows: list[dict[str, object]] = []
    for row, (expected_name, expected_role, expected_type, maximum) in zip(raw_rows, _ARTIFACT_ROLES, strict=True):
        item = _exact_mapping(row, _ROW_FIELDS, "manifest artifact row")
        name = item["path"]
        if name != expected_name:
            raise SensorSessionEvidenceError("manifest artifacts are reordered, missing, or duplicated")
        if not isinstance(name, str) or Path(name).name != name or Path(name).is_absolute():
            raise SensorSessionEvidenceError("manifest artifact path is unsafe")
        if item["role"] != expected_role or item["media_type"] != expected_type:
            raise SensorSessionEvidenceError(f"artifact role/type mismatch for {name}")
        expected_size = _integer(item["bytes"], f"{name} bytes", minimum=1, maximum=maximum)
        expected_hash = _digest(item["sha256"], f"{name} hash")
        artifact_path = directory / name
        try:
            resolved = artifact_path.resolve(strict=True)
        except OSError as exc:
            raise SensorSessionEvidenceError(f"missing sensor artifact {name}") from exc
        if artifact_path.is_symlink() or resolved.parent != directory or not resolved.is_file():
            raise SensorSessionEvidenceError(f"sensor artifact escapes its record directory: {name}")
        if name in _JSON_ARTIFACTS:
            document, payload = _read_json(resolved, maximum=maximum)
            documents[name] = document
        else:
            payload = _read_bytes(resolved, maximum=maximum)
            blobs[name] = payload
        if len(payload) != expected_size or hashlib.sha256(payload).hexdigest() != expected_hash:
            raise SensorSessionEvidenceError(f"artifact byte/hash mismatch for {name}")
        total += len(payload)
        if total > MAX_PACKAGE_BYTES:
            raise SensorSessionEvidenceError("sensor package exceeds its byte limit")
        normalized_rows.append(dict(item))

    declared_total = _integer(manifest["total_artifact_bytes"], "total_artifact_bytes", minimum=1, maximum=MAX_PACKAGE_BYTES)
    if total != declared_total:
        raise SensorSessionEvidenceError("manifest total byte count is invalid")
    content_sha256 = _digest(manifest["content_sha256"], "content_sha256")
    expected_content_hash = _stable_hash(
        {"schema": CONTENT_SCHEMA, "artifacts": normalized_rows}
    )
    if content_sha256 != expected_content_hash or record_id != f"sensor-session-{content_sha256}":
        raise SensorSessionEvidenceError("content address does not match ordered artifacts")
    package_sha256 = _digest(manifest["package_sha256"], "package_sha256")
    manifest_core = dict(manifest)
    del manifest_core["package_sha256"]
    if package_sha256 != _stable_hash(manifest_core):
        raise SensorSessionEvidenceError("manifest package hash mismatch")

    contract = SensorSessionContract.from_dict(documents["contract.json"])
    identity, mode, controls, camera_sequence = _parse_camera_document(documents["camera.json"])
    timing = SensorTimingBracket.from_dict(documents["timing.json"])
    if camera_sequence != timing.frame_sequence:
        raise SensorSessionEvidenceError("camera and timing frame sequences differ")
    reconstructed = RawSensorSessionInput(
        identity=identity,
        mode=mode,
        controls=controls,
        timing=timing,
        raw_frame_bytes=blobs["raw-frame.bin"],
        decoded_frame_bytes=blobs["decoded-frame.bin"],
        undistorted_frame_bytes=blobs["undistorted-frame.bin"],
        detector_record=documents["perception.json"]["detector_record"],
        pose_record=documents["perception.json"]["pose_record"],
        t105_request_line=blobs["t105-request.line"],
        t1051_response_line=blobs["t1051-response.line"],
    )
    _validate_session_against_contract(reconstructed, contract)
    _validate_perception_document(
        documents["perception.json"],
        timing=timing,
        contract=contract,
        blobs=blobs,
    )
    active_contract = replay_contract or contract
    _validate_replay_contract_is_not_weaker(contract, active_contract)
    _validate_session_against_contract(reconstructed, active_contract)
    feedback_message = validate_feedback_response_line(
        blobs["t1051-response.line"], max_line_bytes=MAX_WIRE_LINE_BYTES
    )
    return VerifiedSensorSessionRecord(
        record_id=record_id,
        directory=directory,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        content_sha256=content_sha256,
        contract=contract,
        applied_contract=active_contract,
        stored_contract_sha256=_stable_hash(contract.to_dict()),
        applied_contract_sha256=_stable_hash(active_contract.to_dict()),
        identity=identity,
        mode=mode,
        controls=controls,
        timing=timing,
        calibration_sha256=contract.calibration_sha256,
        documents=documents,
        blobs=blobs,
        feedback_message=feedback_message,
        _factory_token=_VERIFIED_FACTORY_TOKEN,
    )


def _replay_core(record: VerifiedSensorSessionRecord) -> dict[str, object]:
    """Build the hash input that binds both stored and applied policies."""

    return {
        "schema": REPLAY_SCHEMA,
        "record_id": record.record_id,
        "content_sha256": record.content_sha256,
        "stored_contract_sha256": record.stored_contract_sha256,
        "applied_contract_sha256": record.applied_contract_sha256,
        "stored_contract": record.contract.to_dict(),
        "applied_contract": record.applied_contract.to_dict(),
        "ordered_artifact_sha256": [
            hashlib.sha256(record.blobs[name]).hexdigest()
            if name in record.blobs
            else hashlib.sha256(
                _canonical_bytes(_deep_thaw(record.documents[name]))
            ).hexdigest()
            for name, _, _, _ in _ARTIFACT_ROLES
        ],
        "authority": dict(_AUTHORITY),
    }


def replay_sensor_session(
    manifest_path: Path,
    *,
    replay_contract: SensorSessionContract | None = None,
) -> ReplayedSensorSession:
    """Replay verified bytes in memory without invoking any hardware adapter."""

    record = verify_sensor_session_record(
        manifest_path,
        replay_contract=replay_contract,
    )
    return ReplayedSensorSession(
        record=record,
        replay_sha256=_stable_hash(_replay_core(record)),
        _factory_token=_REPLAY_FACTORY_TOKEN,
    )


__all__ = [
    "CAMERA_SCHEMA",
    "CONTENT_SCHEMA",
    "CONTRACT_SCHEMA",
    "MANIFEST_SCHEMA",
    "MAX_FRAME_ARTIFACT_BYTES",
    "MAX_JSON_ARTIFACT_BYTES",
    "MAX_PACKAGE_BYTES",
    "MAX_WIRE_LINE_BYTES",
    "PERCEPTION_SCHEMA",
    "PIXEL_LAYOUT_SCHEMA",
    "REPLAY_SCHEMA",
    "TIMING_SCHEMA",
    "CameraControlSnapshot",
    "CameraModeSnapshot",
    "FramePixelLayouts",
    "PixelBufferLayout",
    "RawSensorSessionInput",
    "ReplayedSensorSession",
    "SensorSessionContract",
    "SensorSessionEvidenceError",
    "SensorSessionRecord",
    "SensorTimingBracket",
    "SyntheticCameraIdentity",
    "VerifiedSensorSessionRecord",
    "record_sensor_session",
    "replay_sensor_session",
    "verify_sensor_session_record",
]
