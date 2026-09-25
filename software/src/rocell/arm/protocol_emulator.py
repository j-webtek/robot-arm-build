"""Deterministic, hardware-free RoArm serial-controller emulator.

The emulator presents the deliberately small subset of the ``pyserial.Serial``
surface consumed by :class:`rocell.arm.serial_transport.SerialTransport`.  It
never enumerates or opens a real port.  Each accepted T=105 request consumes
exactly one immutable scripted exchange, making framing, disconnect, reset, and
protocol failures repeatable without teaching the production transport a test
escape hatch.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from threading import Event, RLock
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .feedback_wire import (
    FeedbackWireError,
    require_quiescent_receive_buffer,
    validate_feedback_response_line,
)
from .protocol import (
    ProtocolError,
    decode_line,
    encode_line,
    feedback_request,
)


class ProtocolEmulatorError(RuntimeError):
    """The deterministic controller script or request sequence is invalid."""


class ProtocolEmulatorSessionFailure(str, Enum):
    """Failure classified from behavior observed at the fake wire boundary."""

    ALREADY_OPEN = "ALREADY_OPEN"
    OPEN_FAILED = "OPEN_FAILED"
    NOT_OPEN = "NOT_OPEN"
    PARTIAL_WRITE = "PARTIAL_WRITE"
    BUFFER_STATE_UNAVAILABLE = "BUFFER_STATE_UNAVAILABLE"
    STALE_BUFFERED_INPUT = "STALE_BUFFERED_INPUT"
    TIMEOUT = "TIMEOUT"
    DISCONNECT = "DISCONNECT"
    RESET_BANNER = "RESET_BANNER"
    OVERLONG_LINE = "OVERLONG_LINE"
    NON_TEXT_LINE = "NON_TEXT_LINE"
    TRUNCATED_LINE = "TRUNCATED_LINE"
    MALFORMED_JSON = "MALFORMED_JSON"
    WRONG_RESPONSE_TYPE = "WRONG_RESPONSE_TYPE"
    INVALID_TYPED_FEEDBACK = "INVALID_TYPED_FEEDBACK"
    IO_FAILURE = "IO_FAILURE"


class ProtocolEmulatorSessionError(ProtocolEmulatorError):
    """A hardware-incapable scripted feedback session failed closed."""

    def __init__(
        self,
        failure: ProtocolEmulatorSessionFailure,
        message: str,
    ) -> None:
        if not isinstance(failure, ProtocolEmulatorSessionFailure):
            raise TypeError("failure must be ProtocolEmulatorSessionFailure")
        super().__init__(message)
        self.failure = failure


class ProtocolEmulatorFault(str, Enum):
    """One fault injected at an exact T=105 exchange boundary."""

    NONE = "NONE"
    OVERLONG_LINE = "OVERLONG_LINE"
    TRUNCATED_LINE = "TRUNCATED_LINE"
    MALFORMED_JSON = "MALFORMED_JSON"
    INVALID_TYPED_FEEDBACK = "INVALID_TYPED_FEEDBACK"
    WRONG_RESPONSE_TYPE = "WRONG_RESPONSE_TYPE"
    TIMEOUT = "TIMEOUT"
    DISCONNECT = "DISCONNECT"
    RESET_BANNER = "RESET_BANNER"
    PARTIAL_WRITE = "PARTIAL_WRITE"


@dataclass(frozen=True, slots=True)
class ProtocolEmulatorStep:
    """One immutable response or injected transport fault."""

    fault: ProtocolEmulatorFault = ProtocolEmulatorFault.NONE
    feedback_fields: Mapping[str, Any] = field(default_factory=dict, repr=False)
    _response_line: bytes = field(init=False, repr=False)
    feedback_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.fault, ProtocolEmulatorFault):
            try:
                object.__setattr__(self, "fault", ProtocolEmulatorFault(self.fault))
            except (TypeError, ValueError) as exc:
                raise ProtocolEmulatorError("unsupported emulator fault") from exc
        if not isinstance(self.feedback_fields, Mapping):
            raise ProtocolEmulatorError("feedback_fields must be a mapping")
        fields = dict(self.feedback_fields)
        if "T" in fields:
            raise ProtocolEmulatorError("feedback_fields must not override T")
        try:
            response = encode_line({"T": 1051, **fields})
        except ProtocolError as exc:
            raise ProtocolEmulatorError(
                f"feedback_fields are not canonical protocol data: {exc}"
            ) from exc
        object.__setattr__(self, "feedback_fields", MappingProxyType(fields))
        object.__setattr__(self, "_response_line", response)
        object.__setattr__(
            self, "feedback_sha256", hashlib.sha256(response).hexdigest()
        )

    @property
    def response_line(self) -> bytes:
        return self._response_line


class DeterministicProtocolController:
    """A single-controller, explicitly opened serial emulator.

    Public configuration attributes mirror the attributes assigned by
    ``SerialTransport.connect``.  ``block_reads=True`` exposes two events for a
    deterministic concurrency test: ``read_started`` and :meth:`allow_read`.
    The default path never waits.
    """

    def __init__(
        self,
        steps: Iterable[ProtocolEmulatorStep] = (),
        *,
        block_reads: bool = False,
    ) -> None:
        self.is_open = False
        self.port: str | None = None
        self.baudrate: int | None = None
        self.timeout: float | None = None
        self.write_timeout: float | None = None
        self.rtscts = True
        self.dsrdtr = True
        self.rts = True
        self.dtr = True
        self._steps = deque(steps)
        if not all(isinstance(step, ProtocolEmulatorStep) for step in self._steps):
            raise TypeError("steps must contain ProtocolEmulatorStep values")
        self._pending: ProtocolEmulatorStep | None = None
        self._preexisting_input: deque[bytes] = deque()
        self._writes: list[bytes] = []
        self._open_count = 0
        self._close_count = 0
        self._flush_count = 0
        self._lock = RLock()
        self._block_reads = bool(block_reads)
        self.read_started = Event()
        self._read_release = Event()
        if not self._block_reads:
            self._read_release.set()

    @property
    def writes(self) -> tuple[bytes, ...]:
        with self._lock:
            return tuple(self._writes)

    @property
    def sent_messages(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(decode_line(payload) for payload in self._writes)

    @property
    def pending_step_count(self) -> int:
        with self._lock:
            return len(self._steps) + (1 if self._pending is not None else 0)

    @property
    def in_waiting(self) -> int:
        """Number of bytes that existed before a new scripted request."""

        with self._lock:
            return sum(len(line) for line in self._preexisting_input)

    @property
    def open_count(self) -> int:
        with self._lock:
            return self._open_count

    @property
    def close_count(self) -> int:
        with self._lock:
            return self._close_count

    @property
    def flush_count(self) -> int:
        with self._lock:
            return self._flush_count

    def allow_read(self) -> None:
        """Release a deliberately blocked read exactly for test orchestration."""

        self._read_release.set()

    def queue_step(self, step: ProtocolEmulatorStep) -> None:
        if not isinstance(step, ProtocolEmulatorStep):
            raise TypeError("step must be ProtocolEmulatorStep")
        with self._lock:
            self._steps.append(step)

    def queue_preexisting_input(self, line: bytes | str) -> None:
        """Stage bytes that predate the next request, only while closed."""

        if isinstance(line, str):
            payload = line.encode("utf-8")
        elif isinstance(line, bytes):
            payload = line
        else:
            raise TypeError("preexisting input must be bytes or text")
        if not payload:
            raise ValueError("preexisting input cannot be empty")
        with self._lock:
            if self.is_open or self._pending is not None:
                raise ProtocolEmulatorError(
                    "preexisting input can be staged only while the controller is closed"
                )
            self._preexisting_input.append(payload)

    def open(self) -> None:
        with self._lock:
            if self.is_open:
                raise ProtocolEmulatorError("controller is already open")
            if self.rts or self.dtr or self.rtscts or self.dsrdtr:
                raise ProtocolEmulatorError(
                    "controller must be opened with reset/flow-control lines inactive"
                )
            self.is_open = True
            self._open_count += 1

    def close(self) -> None:
        with self._lock:
            self.is_open = False
            self._pending = None
            self._close_count += 1

    def write(self, payload: bytes) -> int:
        with self._lock:
            if not self.is_open:
                raise OSError("emulated controller is disconnected")
            if not isinstance(payload, bytes):
                raise TypeError("controller payload must be bytes")
            if self._pending is not None:
                raise ProtocolEmulatorError(
                    "a second request arrived before the first response was read"
                )
            try:
                message = decode_line(payload)
            except ProtocolError as exc:
                raise ProtocolEmulatorError(f"invalid controller request: {exc}") from exc
            if message != feedback_request():
                raise ProtocolEmulatorError(
                    "emulator accepts only the exact T=105 feedback request"
                )
            self._writes.append(payload)
            step = (
                self._steps.popleft()
                if self._steps
                else ProtocolEmulatorStep(ProtocolEmulatorFault.TIMEOUT)
            )
            if step.fault is ProtocolEmulatorFault.PARTIAL_WRITE:
                return max(0, len(payload) - 1)
            self._pending = step
            return len(payload)

    def flush(self) -> None:
        with self._lock:
            if not self.is_open:
                raise OSError("emulated controller disconnected before flush")
            self._flush_count += 1

    def readline(self, maximum: int) -> bytes:
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
            raise ValueError("maximum must be a positive integer")
        with self._lock:
            if not self.is_open:
                raise OSError("emulated controller is disconnected")
            if self._preexisting_input:
                return self._preexisting_input.popleft()[:maximum]
            step = self._pending
            if step is None:
                return b""
            self.read_started.set()

        # Do not hold the emulator lock while a deterministic concurrency test
        # waits.  SerialTransport itself owns the higher-level transaction lock.
        if not self._read_release.wait(timeout=5.0):
            return b""

        with self._lock:
            if self._pending is not step:
                raise ProtocolEmulatorError("pending response changed during read")
            self._pending = None
            fault = step.fault
            if fault is ProtocolEmulatorFault.TIMEOUT:
                return b""
            if fault is ProtocolEmulatorFault.DISCONNECT:
                self.is_open = False
                return b""
            if fault is ProtocolEmulatorFault.RESET_BANNER:
                self.is_open = False
                return b"ets Jun  8 2016 00:22:57\n"
            if fault is ProtocolEmulatorFault.TRUNCATED_LINE:
                return step.response_line.rstrip(b"\n")[:maximum]
            if fault is ProtocolEmulatorFault.MALFORMED_JSON:
                return b'{"T":1051,,}\n'[:maximum]
            if fault is ProtocolEmulatorFault.INVALID_TYPED_FEEDBACK:
                return b'{"T":1051,"x":"not-a-number"}\n'[:maximum]
            if fault is ProtocolEmulatorFault.WRONG_RESPONSE_TYPE:
                return encode_line({"T": 105})[:maximum]
            if fault is ProtocolEmulatorFault.OVERLONG_LINE:
                oversized = (
                    b'{"T":1051,"padding":"'
                    + (b"x" * (maximum + 32))
                    + b'"}\n'
                )
                return oversized[:maximum]
            if fault is ProtocolEmulatorFault.NONE:
                return step.response_line[:maximum]
            if fault is ProtocolEmulatorFault.PARTIAL_WRITE:
                raise ProtocolEmulatorError(
                    "partial-write step unexpectedly reached response handling"
                )
            raise ProtocolEmulatorError(f"unhandled emulator fault {fault.value}")


class DeterministicFeedbackSession:
    """Run exact T=105 framing against an internally owned fake controller.

    This class intentionally is *not* an ``ArmTransport`` and accepts no
    :class:`FeedbackPermit`.  It constructs the only possible I/O endpoint—a
    :class:`DeterministicProtocolController`—from immutable scripted steps.
    Rehearsal code can therefore exercise open/configure/write/read/parse/
    quarantine/close behavior without minting a capability that a live
    ``SerialTransport`` could consume.
    """

    def __init__(
        self,
        steps: Iterable[ProtocolEmulatorStep] = (),
        *,
        max_line_bytes: int = 4096,
    ) -> None:
        if (
            isinstance(max_line_bytes, bool)
            or not isinstance(max_line_bytes, int)
            or max_line_bytes < 64
        ):
            raise ValueError("max_line_bytes must be an integer of at least 64")
        self._controller = DeterministicProtocolController(steps)
        self._max_line_bytes = max_line_bytes
        self._owns_open = False
        self._last_fault: str | None = None
        self._last_failure: ProtocolEmulatorSessionFailure | None = None
        self._received_lines: list[bytes] = []
        self._lock = RLock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._owns_open and self._controller.is_open

    @property
    def last_fault(self) -> str | None:
        with self._lock:
            return self._last_fault

    @property
    def last_failure(self) -> ProtocolEmulatorSessionFailure | None:
        with self._lock:
            return self._last_failure

    @property
    def writes(self) -> tuple[bytes, ...]:
        return self._controller.writes

    @property
    def sent_messages(self) -> tuple[dict[str, Any], ...]:
        return self._controller.sent_messages

    @property
    def received_lines(self) -> tuple[bytes, ...]:
        """Exact lines returned by the fake wire, before parsing."""

        with self._lock:
            return tuple(self._received_lines)

    @property
    def open_count(self) -> int:
        return self._controller.open_count

    @property
    def close_count(self) -> int:
        return self._controller.close_count

    @property
    def pending_step_count(self) -> int:
        return self._controller.pending_step_count

    def inject_preexisting_input(self, line: bytes | str) -> None:
        """Stage a stale line for the next open; available only on this fake."""

        with self._lock:
            if self._owns_open:
                raise ProtocolEmulatorSessionError(
                    ProtocolEmulatorSessionFailure.ALREADY_OPEN,
                    "cannot inject preexisting input while the session is open",
                )
            self._controller.queue_preexisting_input(line)

    @staticmethod
    def _wire_failure(exc: FeedbackWireError) -> ProtocolEmulatorSessionFailure:
        try:
            return ProtocolEmulatorSessionFailure(exc.failure.value)
        except ValueError:
            return ProtocolEmulatorSessionFailure.IO_FAILURE

    def connect(self) -> None:
        """Open only the internally owned fake with reset lines inactive."""

        with self._lock:
            if self._owns_open:
                raise ProtocolEmulatorSessionError(
                    ProtocolEmulatorSessionFailure.ALREADY_OPEN,
                    "emulated feedback session is already open"
                )
            controller = self._controller
            controller.port = "SYNTHETIC://ROARM/REHEARSAL"
            controller.baudrate = 115200
            controller.timeout = 0.25
            controller.write_timeout = 0.25
            controller.rtscts = False
            controller.dsrdtr = False
            controller.rts = False
            controller.dtr = False
            try:
                controller.open()
            except Exception as exc:
                raise ProtocolEmulatorSessionError(
                    ProtocolEmulatorSessionFailure.OPEN_FAILED,
                    f"could not open deterministic controller: {exc}"
                ) from exc
            self._owns_open = True
            self._last_fault = None
            self._last_failure = None
            try:
                require_quiescent_receive_buffer(controller)
            except FeedbackWireError as exc:
                failure = self._wire_failure(exc)
                self._quarantine(failure, str(exc))
                raise ProtocolEmulatorSessionError(failure, str(exc)) from exc

    def close(self) -> None:
        """Close without emitting any request, motion, torque, or park line."""

        with self._lock:
            if self._owns_open:
                self._controller.close()
                self._owns_open = False

    def _quarantine(
        self,
        failure: ProtocolEmulatorSessionFailure,
        reason: str,
    ) -> None:
        self._last_failure = failure
        self._last_fault = reason
        if self._owns_open:
            self._controller.close()
            self._owns_open = False

    def request_feedback(self) -> dict[str, Any]:
        """Perform one scripted exchange; no live-compatible permit exists."""

        payload = encode_line(feedback_request())
        with self._lock:
            if not self.is_open:
                raise ProtocolEmulatorSessionError(
                    ProtocolEmulatorSessionFailure.NOT_OPEN,
                    "emulated feedback session is not explicitly open"
                )
            try:
                try:
                    require_quiescent_receive_buffer(self._controller)
                except FeedbackWireError as exc:
                    raise ProtocolEmulatorSessionError(
                        self._wire_failure(exc),
                        str(exc),
                    ) from exc
                written = self._controller.write(payload)
                if written != len(payload):
                    raise ProtocolEmulatorSessionError(
                        ProtocolEmulatorSessionFailure.PARTIAL_WRITE,
                        f"partial emulated serial write: {written!r}/{len(payload)} bytes"
                    )
                self._controller.flush()
                line = self._controller.readline(self._max_line_bytes + 1)
                if not line:
                    if not self._controller.is_open:
                        raise ProtocolEmulatorSessionError(
                            ProtocolEmulatorSessionFailure.DISCONNECT,
                            "emulated controller disconnected while awaiting feedback"
                        )
                    raise ProtocolEmulatorSessionError(
                        ProtocolEmulatorSessionFailure.TIMEOUT,
                        "emulated controller timed out awaiting feedback"
                    )
                self._received_lines.append(line)
                try:
                    return validate_feedback_response_line(
                        line,
                        max_line_bytes=self._max_line_bytes,
                    )
                except FeedbackWireError as exc:
                    raise ProtocolEmulatorSessionError(
                        self._wire_failure(exc),
                        str(exc),
                    ) from exc
            except ProtocolEmulatorSessionError as exc:
                reason = str(exc) or type(exc).__name__
                self._quarantine(exc.failure, reason)
                raise
            except Exception as exc:
                reason = str(exc) or type(exc).__name__
                self._quarantine(
                    ProtocolEmulatorSessionFailure.IO_FAILURE,
                    reason,
                )
                raise ProtocolEmulatorSessionError(
                    ProtocolEmulatorSessionFailure.IO_FAILURE,
                    f"invalid emulated feedback transaction: {reason}"
                ) from exc


__all__ = [
    "DeterministicFeedbackSession",
    "DeterministicProtocolController",
    "ProtocolEmulatorError",
    "ProtocolEmulatorFault",
    "ProtocolEmulatorSessionError",
    "ProtocolEmulatorSessionFailure",
    "ProtocolEmulatorStep",
]
