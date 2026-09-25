"""Deterministic in-memory camera source for simulation and unit tests."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
import time
from typing import Callable, Iterable

from .camera import (
    CameraCaptureError,
    CameraConfigurationError,
    CameraNotOpenError,
    CameraStateError,
    CameraStatus,
    FramePacket,
    TimestampQuality,
    jpeg_dimensions,
    settings_digest,
)


@dataclass(frozen=True, slots=True)
class MockFrame:
    """Source-side evidence attached to one queued mock JPEG."""

    jpeg_bytes: bytes
    source_sequence: int | None = None
    source_timestamp_ns: int | None = None
    source_clock: str | None = None
    freshness_token: str | None = None

    def __post_init__(self) -> None:
        jpeg_dimensions(self.jpeg_bytes)
        if self.source_sequence is not None and (
            isinstance(self.source_sequence, bool)
            or not isinstance(self.source_sequence, int)
            or self.source_sequence < 0
        ):
            raise CameraConfigurationError("MockFrame.source_sequence must be nonnegative")
        if self.source_timestamp_ns is not None and (
            isinstance(self.source_timestamp_ns, bool)
            or not isinstance(self.source_timestamp_ns, int)
            or self.source_timestamp_ns < 0
        ):
            raise CameraConfigurationError(
                "MockFrame.source_timestamp_ns must be nonnegative"
            )
        if self.source_timestamp_ns is not None:
            if not isinstance(self.source_clock, str) or not self.source_clock.strip():
                raise CameraConfigurationError(
                    "MockFrame.source_clock is required with a source timestamp"
                )
        elif self.source_clock is not None:
            raise CameraConfigurationError(
                "MockFrame.source_clock requires a source timestamp"
            )


class MockCamera:
    """Explicit-lifecycle queued camera with no hardware or network access."""

    def __init__(
        self,
        frames: Iterable[MockFrame | bytes] = (),
        *,
        identity: str = "mock-camera",
        clock_ns: Callable[[], int] = time.monotonic_ns,
        repeat_last: bool = False,
    ) -> None:
        if not isinstance(identity, str) or not identity.strip():
            raise CameraConfigurationError("identity must be non-empty text")
        if not callable(clock_ns):
            raise CameraConfigurationError("clock_ns must be callable")
        if not isinstance(repeat_last, bool):
            raise CameraConfigurationError("repeat_last must be boolean")
        self.identity = identity.strip()
        self._clock_ns = clock_ns
        self._repeat_last = repeat_last
        self._frames: deque[MockFrame] = deque()
        self._last_source: MockFrame | None = None
        self._is_open = False
        self._capture_count = 0
        self._lock = RLock()
        self._settings_hash = settings_digest(
            {"backend": "mock", "identity": self.identity, "repeat_last": repeat_last}
        )
        for frame in frames:
            self.queue(frame)

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def pending_frame_count(self) -> int:
        return len(self._frames)

    def queue(self, frame: MockFrame | bytes) -> None:
        if isinstance(frame, bytes):
            frame = MockFrame(frame)
        if not isinstance(frame, MockFrame):
            raise CameraConfigurationError("Mock camera frames must be MockFrame or bytes")
        with self._lock:
            self._frames.append(frame)

    def open(self) -> None:
        with self._lock:
            if self._is_open:
                raise CameraStateError("Mock camera is already open")
            self._is_open = True

    def connect(self) -> None:
        self.open()

    def _require_open(self) -> None:
        if not self._is_open:
            raise CameraNotOpenError("Mock camera is not explicitly open")

    def _next_source(self) -> MockFrame:
        if self._frames:
            source = self._frames.popleft()
            self._last_source = source
            return source
        if self._repeat_last and self._last_source is not None:
            return self._last_source
        raise CameraCaptureError("Mock camera has no queued frame")

    def probe(self) -> CameraStatus:
        with self._lock:
            self._require_open()
            source = self._frames[0] if self._frames else self._last_source
            width: int | None = None
            height: int | None = None
            if source is not None:
                width, height = jpeg_dimensions(source.jpeg_bytes)
            return CameraStatus(
                backend="mock",
                identity=self.identity,
                is_open=True,
                width_px=width,
                height_px=height,
                fps=None,
                settings_hash=self._settings_hash,
                timestamp_quality=TimestampQuality.UNQUALIFIED,
                persistent_identity=True,
                details=(("pending_frames", str(len(self._frames))),),
            )

    def capture(self) -> FramePacket:
        with self._lock:
            self._require_open()
            source = self._next_source()
            request_ns = self._clock_ns()
            first_byte_ns = self._clock_ns()
            complete_ns = self._clock_ns()
            width, height = jpeg_dimensions(source.jpeg_bytes)
            self._capture_count += 1
            if source.source_sequence is not None:
                basis = "mock_device_sequence"
            elif source.source_timestamp_ns is not None:
                basis = "mock_device_timestamp"
            elif source.freshness_token is not None:
                basis = "mock_freshness_token"
            else:
                basis = "mock_host_bracket"
            return FramePacket(
                capture_id=f"{self.identity}:{self._capture_count}",
                jpeg_bytes=source.jpeg_bytes,
                width_px=width,
                height_px=height,
                source_sequence=source.source_sequence,
                source_timestamp_ns=source.source_timestamp_ns,
                source_clock=source.source_clock,
                host_request_ns=request_ns,
                host_first_byte_ns=first_byte_ns,
                host_complete_ns=complete_ns,
                settings_hash=self._settings_hash,
                timestamp_quality=(
                    TimestampQuality.DEVICE_EXPOSURE
                    if source.source_timestamp_ns is not None
                    else TimestampQuality.HOST_RECEIPT
                ),
                freshness_token=source.freshness_token,
                freshness_basis=basis,
            )

    def close(self) -> None:
        with self._lock:
            self._is_open = False

