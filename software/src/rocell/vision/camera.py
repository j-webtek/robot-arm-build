"""Shared, side-effect-free camera records and validation helpers.

The standalone RoArm-M3 includes a camera holder, but its product page does not
identify or include a camera.  Consequently this module defines an explicit
source boundary without selecting a USB or ESP camera on the arm's behalf.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import string
from typing import Any, Mapping, Protocol, runtime_checkable


class CameraError(RuntimeError):
    """Base error for camera configuration, state, or I/O failures."""


class CameraConfigurationError(CameraError, ValueError):
    """Camera configuration is invalid or internally inconsistent."""


class CameraStateError(CameraError):
    """The requested operation is invalid for the camera lifecycle state."""


class CameraNotOpenError(CameraStateError):
    """An operation requires an explicitly opened camera source."""


class CameraOpenError(CameraError):
    """A camera source could not be opened exactly once as requested."""


class CameraProbeError(CameraError):
    """A camera did not report the configured operating mode."""


class CameraCaptureError(CameraError):
    """A camera did not produce one complete, valid frame."""


class FrameLimitError(CameraCaptureError):
    """A frame or response exceeded a configured resource limit."""


class ResolutionMismatchError(CameraCaptureError):
    """A decoded frame does not have the commissioned resolution."""


class StaleFrameError(CameraCaptureError):
    """Source-provided freshness evidence did not advance."""


class TimestampQuality(str, Enum):
    """What a frame timestamp can honestly establish."""

    DEVICE_EXPOSURE = "device_exposure"
    HOST_RECEIPT = "host_receipt"
    SETTLED_BRACKET = "settled_bracket"
    UNQUALIFIED = "unqualified"


def positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CameraConfigurationError(f"{name} must be a positive integer")
    return value


def nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CameraConfigurationError(f"{name} must be a nonnegative integer")
    return value


def positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CameraConfigurationError(f"{name} must be a positive finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise CameraConfigurationError(f"{name} must be a positive finite number")
    return parsed


def settings_digest(settings: Mapping[str, Any]) -> str:
    """Return a deterministic hash for capture-affecting configuration."""

    try:
        payload = json.dumps(
            dict(settings),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CameraConfigurationError(f"Camera settings are not canonical JSON: {exc}") from exc
    return hashlib.sha256(payload).hexdigest()


_SOF_MARKERS = frozenset(
    {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
)


def jpeg_dimensions(payload: bytes) -> tuple[int, int]:
    """Validate JPEG framing and return ``(width, height)`` without Pillow.

    This deliberately performs a bounded structural parse rather than a full
    pixel decode.  It catches HTML/error bodies, truncation, invalid segment
    lengths, and resolution drift before downstream image libraries see data.
    """

    if not isinstance(payload, bytes):
        raise CameraCaptureError("JPEG payload must be immutable bytes")
    if len(payload) < 8 or not payload.startswith(b"\xff\xd8"):
        raise CameraCaptureError("Frame is not a JPEG: missing SOI marker")
    if not payload.endswith(b"\xff\xd9"):
        raise CameraCaptureError("JPEG frame is truncated: missing EOI marker")

    offset = 2
    found: tuple[int, int] | None = None
    payload_length = len(payload)
    while offset < payload_length - 2:
        if payload[offset] != 0xFF:
            raise CameraCaptureError("JPEG contains data outside a marker segment")
        while offset < payload_length and payload[offset] == 0xFF:
            offset += 1
        if offset >= payload_length:
            break
        marker = payload[offset]
        offset += 1

        if marker == 0xD9:
            break
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > payload_length:
            raise CameraCaptureError("JPEG segment length is truncated")
        segment_length = int.from_bytes(payload[offset : offset + 2], "big")
        if segment_length < 2:
            raise CameraCaptureError("JPEG segment has an invalid length")
        segment_end = offset + segment_length
        if segment_end > payload_length:
            raise CameraCaptureError("JPEG segment extends beyond the frame")

        if marker in _SOF_MARKERS:
            if segment_length < 8:
                raise CameraCaptureError("JPEG SOF segment is too short")
            height = int.from_bytes(payload[offset + 3 : offset + 5], "big")
            width = int.from_bytes(payload[offset + 5 : offset + 7], "big")
            if width <= 0 or height <= 0:
                raise CameraCaptureError("JPEG SOF reports an invalid resolution")
            found = (width, height)

        # Entropy-coded data follows SOS and cannot be scanned as marker
        # segments without handling byte stuffing.  A valid SOF must precede it.
        if marker == 0xDA:
            break
        offset = segment_end

    if found is None:
        raise CameraCaptureError("JPEG does not contain a supported SOF marker")
    return found


@dataclass(frozen=True, slots=True)
class CameraStatus:
    """One read-only snapshot of a camera source and its selected mode."""

    backend: str
    identity: str
    is_open: bool
    width_px: int | None
    height_px: int | None
    fps: float | None
    settings_hash: str
    timestamp_quality: TimestampQuality
    persistent_identity: bool
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.backend, str) or not self.backend.strip():
            raise CameraConfigurationError("CameraStatus.backend must be non-empty")
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise CameraConfigurationError("CameraStatus.identity must be non-empty")
        if (self.width_px is None) != (self.height_px is None):
            raise CameraConfigurationError("CameraStatus resolution must be complete or absent")
        if self.width_px is not None:
            positive_int("CameraStatus.width_px", self.width_px)
            positive_int("CameraStatus.height_px", self.height_px)
        if self.fps is not None:
            positive_finite("CameraStatus.fps", self.fps)
        _validate_sha256("CameraStatus.settings_hash", self.settings_hash)
        if not isinstance(self.timestamp_quality, TimestampQuality):
            raise CameraConfigurationError("CameraStatus.timestamp_quality is invalid")
        if not isinstance(self.persistent_identity, bool):
            raise CameraConfigurationError("CameraStatus.persistent_identity must be boolean")
        for key, value in self.details:
            if not isinstance(key, str) or not isinstance(value, str):
                raise CameraConfigurationError("CameraStatus.details must contain text pairs")


def _validate_sha256(name: str, value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in string.hexdigits for character in value)
    ):
        raise CameraConfigurationError(f"{name} must be a hexadecimal SHA-256 digest")


@dataclass(frozen=True, slots=True)
class FramePacket:
    """One encoded camera frame with honest source and host timing evidence."""

    capture_id: str
    jpeg_bytes: bytes
    width_px: int
    height_px: int
    source_sequence: int | None
    source_timestamp_ns: int | None
    source_clock: str | None
    host_request_ns: int
    host_first_byte_ns: int
    host_complete_ns: int
    settings_hash: str
    timestamp_quality: TimestampQuality
    freshness_token: str | None = None
    freshness_basis: str = "host_request_receipt"

    def __post_init__(self) -> None:
        if not isinstance(self.capture_id, str) or not self.capture_id.strip():
            raise CameraConfigurationError("capture_id must be non-empty text")
        if len(self.capture_id) > 256:
            raise CameraConfigurationError("capture_id is too long")
        positive_int("width_px", self.width_px)
        positive_int("height_px", self.height_px)
        decoded_width, decoded_height = jpeg_dimensions(self.jpeg_bytes)
        if (decoded_width, decoded_height) != (self.width_px, self.height_px):
            raise ResolutionMismatchError(
                "Frame metadata resolution does not match the encoded JPEG"
            )
        if self.source_sequence is not None:
            nonnegative_int("source_sequence", self.source_sequence)
        if self.source_timestamp_ns is not None:
            nonnegative_int("source_timestamp_ns", self.source_timestamp_ns)
            if not isinstance(self.source_clock, str) or not self.source_clock.strip():
                raise CameraConfigurationError(
                    "source_clock is required when source_timestamp_ns is present"
                )
        elif self.source_clock is not None:
            raise CameraConfigurationError(
                "source_clock cannot be set without source_timestamp_ns"
            )
        for name, value in (
            ("host_request_ns", self.host_request_ns),
            ("host_first_byte_ns", self.host_first_byte_ns),
            ("host_complete_ns", self.host_complete_ns),
        ):
            nonnegative_int(name, value)
        if not (
            self.host_request_ns
            <= self.host_first_byte_ns
            <= self.host_complete_ns
        ):
            raise CameraConfigurationError("Host frame timestamps are out of order")
        _validate_sha256("settings_hash", self.settings_hash)
        if not isinstance(self.timestamp_quality, TimestampQuality):
            raise CameraConfigurationError("timestamp_quality is invalid")
        if self.freshness_token is not None:
            if not isinstance(self.freshness_token, str) or not self.freshness_token.strip():
                raise CameraConfigurationError("freshness_token must be non-empty text")
            if len(self.freshness_token) > 1024:
                raise CameraConfigurationError("freshness_token is too long")
        if not isinstance(self.freshness_basis, str) or not self.freshness_basis.strip():
            raise CameraConfigurationError("freshness_basis must be non-empty text")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.jpeg_bytes).hexdigest()


@runtime_checkable
class CameraSource(Protocol):
    """Explicit lifecycle shared by hardware and deterministic camera sources."""

    @property
    def is_open(self) -> bool: ...

    def open(self) -> None: ...

    def probe(self) -> CameraStatus: ...

    def capture(self) -> FramePacket: ...

    def close(self) -> None: ...

