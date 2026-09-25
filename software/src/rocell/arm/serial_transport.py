"""Permit-consuming serial and replay boundaries for RoArm JSON.

The hardware-backed transport deliberately exposes no arbitrary ``send`` or
``exchange`` operation. Its only outbound operation is the build-gated T=105
feedback request; live motion remains unavailable until a separate executor can
prove calibrated bounds, path linkage, and controller constraints. The replay
transport supports permit-gated motion solely in memory for deterministic tests.
"""

from __future__ import annotations

from collections import deque
import importlib
import math
from threading import RLock
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable

from rocell.safety.permit import FeedbackPermit, MotionPermit

from .feedback_wire import (
    FeedbackWireError,
    require_quiescent_receive_buffer,
    validate_feedback_response_line,
)
from .protocol import (
    CartesianGoal,
    decode_line,
    encode_line,
    feedback_request,
)


class TransportError(RuntimeError):
    """Base error for transport state or I/O failures."""


class NotConnectedError(TransportError):
    """An operation requires an explicitly opened transport."""


class TransportTimeoutError(TransportError):
    """No complete reply arrived within the configured transport timeout."""


class FeedbackNotPermittedError(PermissionError):
    """A valid, unconsumed feedback capability was not supplied."""


class MotionNotPermittedError(PermissionError):
    """The requested operation cannot cross this transport boundary."""


@runtime_checkable
class ArmTransport(Protocol):
    @property
    def is_open(self) -> bool: ...

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def request_feedback(self, permit: FeedbackPermit | None) -> dict[str, Any]: ...

    def send_motion(
        self,
        goal: CartesianGoal,
        permit: MotionPermit | None,
    ) -> None: ...


def _consume_feedback_permit(permit: FeedbackPermit | None) -> None:
    if not isinstance(permit, FeedbackPermit):
        raise FeedbackNotPermittedError(
            "No SafetySupervisor-issued FeedbackPermit was supplied"
        )
    try:
        permitted = permit.consume()
    except Exception as exc:
        raise FeedbackNotPermittedError(
            "Feedback permit evaluation failed; request blocked"
        ) from exc
    if permitted is not True:
        raise FeedbackNotPermittedError(
            "Feedback permit is expired, revoked, or already consumed"
        )


def _authorized_replay_motion(
    goal: CartesianGoal,
    permit: MotionPermit | None,
) -> bytes:
    """Return encoded replay bytes after consuming an exact-goal permit."""

    if not isinstance(goal, CartesianGoal):
        raise TypeError("goal must be a CartesianGoal")
    # Encode first so an invalid typed object could never consume authority.
    payload = encode_line(goal.to_message())
    if not isinstance(permit, MotionPermit):
        raise MotionNotPermittedError(
            "No SafetySupervisor-issued MotionPermit was supplied"
        )
    try:
        permitted = permit.allows(goal)
    except Exception as exc:
        raise MotionNotPermittedError(
            "Motion permit evaluation failed; command blocked"
        ) from exc
    if permitted is not True:
        raise MotionNotPermittedError(
            "Motion permit did not authorize this exact replay goal"
        )
    return payload


def _positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


class SerialTransport:
    """One-owner, feedback-only pyserial transport with no raw write API.

    ``pyserial`` is imported only inside :meth:`connect`.  Construction and
    module import cannot open, reset, initialize, or move attached hardware.
    This class cannot emit live motion: :meth:`send_motion` is an explicit hard
    block until a bounded execution authority exists above the protocol layer.
    """

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        read_timeout_s: float = 1.0,
        write_timeout_s: float = 1.0,
        max_line_bytes: int = 65536,
        serial_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not isinstance(port, str) or not port.strip():
            raise ValueError("port must be a non-empty string")
        if isinstance(baudrate, bool) or not isinstance(baudrate, int) or baudrate <= 0:
            raise ValueError("baudrate must be a positive integer")
        if (
            isinstance(max_line_bytes, bool)
            or not isinstance(max_line_bytes, int)
            or max_line_bytes < 64
        ):
            raise ValueError("max_line_bytes must be an integer of at least 64")
        self.port = port
        self.baudrate = baudrate
        self.read_timeout_s = _positive_finite("read_timeout_s", read_timeout_s)
        self.write_timeout_s = _positive_finite("write_timeout_s", write_timeout_s)
        self.max_line_bytes = max_line_bytes
        self._serial_factory = serial_factory
        self._serial: Any = None
        self._last_fault: str | None = None
        self._lock = RLock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._serial is not None and bool(
                getattr(self._serial, "is_open", False)
            )

    @property
    def last_fault(self) -> str | None:
        """Return the most recent transaction fault without clearing it."""

        with self._lock:
            return self._last_fault

    @staticmethod
    def _load_pyserial_factory() -> Callable[[], Any]:
        try:
            module = importlib.import_module("serial")
        except ImportError as exc:
            raise TransportError(
                "pyserial is required only for live hardware; install it before connecting"
            ) from exc
        factory = getattr(module, "Serial", None)
        if factory is None:
            raise TransportError("Imported serial module does not provide Serial")
        return factory

    def connect(self) -> None:
        """Open once, explicitly; failures propagate and are never retried."""

        with self._lock:
            if self._serial is not None:
                raise TransportError("Transport already has a connection; close it explicitly first")
            factory = self._serial_factory or self._load_pyserial_factory()
            connection = factory()
            try:
                if bool(getattr(connection, "is_open", False)):
                    raise TransportError("Serial factory must return a closed connection")
                connection.port = self.port
                connection.baudrate = self.baudrate
                connection.timeout = self.read_timeout_s
                connection.write_timeout = self.write_timeout_s
                connection.rtscts = False
                connection.dsrdtr = False
                # Set inactive control-line state before opening the port.  This
                # boundary never deliberately toggles the ESP32 reset/boot lines.
                connection.rts = False
                connection.dtr = False
                connection.open()
            except Exception:
                try:
                    connection.close()
                except Exception:
                    pass
                raise
            if not bool(getattr(connection, "is_open", False)):
                try:
                    connection.close()
                finally:
                    raise TransportError("Serial connection did not report open")
            try:
                require_quiescent_receive_buffer(connection)
            except FeedbackWireError as exc:
                reason = f"Serial receive buffer is not quiescent after open: {exc}"
                self._last_fault = reason
                try:
                    connection.close()
                finally:
                    raise TransportError(reason) from exc
            self._serial = connection
            self._last_fault = None

    def close(self) -> None:
        """Close without sending torque, park, stop, or any other command."""

        with self._lock:
            connection = self._serial
            self._serial = None
            if connection is not None:
                connection.close()

    def _connection(self) -> Any:
        connection = self._serial
        if connection is None or not bool(getattr(connection, "is_open", False)):
            raise NotConnectedError("Serial transport is not explicitly connected")
        return connection

    def _write_payload(self, connection: Any, payload: bytes) -> None:
        # One write attempt only. An exception or partial write is returned to
        # the caller; this class never reconnects or retries a controller write.
        written = connection.write(payload)
        if written != len(payload):
            raise TransportError(f"Partial serial write: {written!r}/{len(payload)} bytes")
        flush = getattr(connection, "flush", None)
        if callable(flush):
            flush()

    def _receive_message(self, connection: Any) -> dict[str, Any]:
        # Read one byte beyond the declared limit so a line that fills the
        # entire allowed buffer without a terminator cannot be mistaken for a
        # complete response.  On any framing or protocol failure the caller
        # closes the connection; unread suffix bytes can therefore never be
        # consumed as the response to a later permit.
        line = connection.readline(self.max_line_bytes + 1)
        if not line:
            if not bool(getattr(connection, "is_open", False)):
                raise NotConnectedError(
                    "Serial connection closed while waiting for RoArm feedback"
                )
            raise TransportTimeoutError("Timed out waiting for a RoArm feedback line")
        try:
            return validate_feedback_response_line(
                line,
                max_line_bytes=self.max_line_bytes,
            )
        except FeedbackWireError as exc:
            raise TransportError(f"Invalid RoArm feedback line: {exc}") from exc

    def _fail_closed(self, connection: Any, reason: str) -> None:
        """Quarantine a failed transaction and discard its receive buffer."""

        self._serial = None
        self._last_fault = reason
        try:
            connection.close()
        except Exception:
            # The original failure remains the actionable error.  A failed
            # close cannot make this connection reusable because the transport
            # has already dropped its reference.
            pass

    def request_feedback(self, permit: FeedbackPermit | None) -> dict[str, Any]:
        """Consume one build-authorized permit, then perform one T=105 exchange."""

        payload = encode_line(feedback_request())
        with self._lock:
            # Consume before accessing the connection: even a local I/O failure
            # cannot turn one capability into a blind retry loop.
            _consume_feedback_permit(permit)
            connection = self._connection()
            try:
                # A valid T=1051 line buffered before this request has no
                # correlation token and must not satisfy the new permit.
                require_quiescent_receive_buffer(connection)
                self._write_payload(connection, payload)
                return self._receive_message(connection)
            except FeedbackWireError as exc:
                self._fail_closed(connection, str(exc))
                raise TransportError(
                    f"RoArm receive buffer is not quiescent: {exc}"
                ) from exc
            except TransportError as exc:
                self._fail_closed(connection, str(exc))
                raise
            except Exception as exc:
                reason = f"Serial feedback transaction failed: {exc}"
                self._fail_closed(connection, reason)
                raise TransportError(reason) from exc

    def send_motion(
        self,
        goal: CartesianGoal,
        permit: MotionPermit | None,
    ) -> None:
        """Hard-block live motion until a bounded executor is implemented.

        MotionPermit proves exact message identity and freshness only. It does
        not prove calibrated workspace/orientation/gripper/speed bounds or bind
        the goal to a collision-checked plan, so no serial bytes are written.
        """

        raise MotionNotPermittedError(
            "Live motion executor is unavailable: bounded-goal and checked-path "
            "authorization has not been implemented"
        )


class ReplayTransport:
    """Deterministic in-memory transport using the exact line codec.

    Replay motion still consumes real MotionPermit objects, but it only records
    bytes in memory and therefore cannot become a hardware escape hatch.
    """

    def __init__(
        self,
        incoming: Iterable[Mapping[str, Any] | bytes | str] = (),
        *,
        initially_open: bool = True,
    ) -> None:
        self._incoming: deque[bytes | str] = deque()
        self._sent_lines: list[bytes] = []
        self._is_open = bool(initially_open)
        self._last_fault: str | None = None
        self._lock = RLock()
        for response in incoming:
            self.queue_response(response)

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._is_open

    @property
    def last_fault(self) -> str | None:
        with self._lock:
            return self._last_fault

    @property
    def sent_lines(self) -> tuple[bytes, ...]:
        with self._lock:
            return tuple(self._sent_lines)

    @property
    def sent_messages(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(decode_line(line) for line in self._sent_lines)

    @property
    def pending_response_count(self) -> int:
        with self._lock:
            return len(self._incoming)

    def connect(self) -> None:
        with self._lock:
            if self._is_open:
                raise TransportError("Replay transport is already open")
            self._is_open = True
            self._last_fault = None

    def close(self) -> None:
        with self._lock:
            self._is_open = False

    def _require_open(self) -> None:
        if not self._is_open:
            raise NotConnectedError("Replay transport is closed")

    def queue_response(self, response: Mapping[str, Any] | bytes | str) -> None:
        with self._lock:
            if isinstance(response, Mapping):
                self._incoming.append(encode_line(response))
            elif isinstance(response, (bytes, str)):
                # Validate at queue time so fixtures fail close to their source.
                decode_line(response)
                self._incoming.append(response)
            else:
                raise TypeError("Replay response must be a message, bytes, or text line")

    def _receive_message(self) -> dict[str, Any]:
        self._require_open()
        if not self._incoming:
            raise TransportTimeoutError("Replay has no queued feedback line")
        try:
            return validate_feedback_response_line(
                self._incoming.popleft(),
                max_line_bytes=1_048_576,
            )
        except FeedbackWireError as exc:
            raise TransportError(f"Invalid replay feedback line: {exc}") from exc

    def request_feedback(self, permit: FeedbackPermit | None) -> dict[str, Any]:
        payload = encode_line(feedback_request())
        with self._lock:
            self._require_open()
            _consume_feedback_permit(permit)
            self._sent_lines.append(payload)
            try:
                return self._receive_message()
            except TransportError as exc:
                self._is_open = False
                self._last_fault = str(exc)
                raise

    def send_motion(
        self,
        goal: CartesianGoal,
        permit: MotionPermit | None,
    ) -> None:
        with self._lock:
            self._require_open()
            payload = _authorized_replay_motion(goal, permit)
            self._sent_lines.append(payload)
