"""Pure receive-buffer and T=1051 wire validation shared by live and fake I/O.

The functions in this module have no device-opening capability.  Keeping the
framing rules here lets the physical ``SerialTransport`` and the deterministic
feedback session exercise the same stale-buffer, line-bound, JSON, response-
type, and typed-field boundary without sharing authorization types.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .feedback import FeedbackError, parse_feedback_1051
from .protocol import FEEDBACK_RESPONSE_TYPE, ProtocolError, decode_line


class FeedbackWireFailure(str, Enum):
    BUFFER_STATE_UNAVAILABLE = "BUFFER_STATE_UNAVAILABLE"
    STALE_BUFFERED_INPUT = "STALE_BUFFERED_INPUT"
    OVERLONG_LINE = "OVERLONG_LINE"
    NON_TEXT_LINE = "NON_TEXT_LINE"
    TRUNCATED_LINE = "TRUNCATED_LINE"
    RESET_BANNER = "RESET_BANNER"
    MALFORMED_JSON = "MALFORMED_JSON"
    WRONG_RESPONSE_TYPE = "WRONG_RESPONSE_TYPE"
    INVALID_TYPED_FEEDBACK = "INVALID_TYPED_FEEDBACK"


class FeedbackWireError(ValueError):
    """One observed receive-buffer or response-line contract failed."""

    def __init__(self, failure: FeedbackWireFailure, message: str) -> None:
        if not isinstance(failure, FeedbackWireFailure):
            raise TypeError("failure must be FeedbackWireFailure")
        super().__init__(message)
        self.failure = failure


def receive_buffered_byte_count(connection: object) -> int:
    """Read a pyserial-shaped ``in_waiting`` value without accepting ambiguity."""

    try:
        raw = getattr(connection, "in_waiting")
    except Exception as exc:
        raise FeedbackWireError(
            FeedbackWireFailure.BUFFER_STATE_UNAVAILABLE,
            f"receive-buffer state is unavailable: {exc}",
        ) from exc
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise FeedbackWireError(
            FeedbackWireFailure.BUFFER_STATE_UNAVAILABLE,
            "receive-buffer state must be a nonnegative integer",
        )
    return raw


def require_quiescent_receive_buffer(connection: object) -> None:
    """Reject any bytes that predate a new feedback request.

    T=1051 does not echo a host transaction identifier.  A pre-buffered valid
    line therefore cannot be correlated safely and must never satisfy a later
    T=105 request.
    """

    buffered = receive_buffered_byte_count(connection)
    if buffered:
        raise FeedbackWireError(
            FeedbackWireFailure.STALE_BUFFERED_INPUT,
            f"receive buffer contains {buffered} byte(s) before the request",
        )


def validate_feedback_response_line(
    line: bytes | str,
    *,
    max_line_bytes: int,
) -> dict[str, Any]:
    """Validate one bounded newline-framed T=1051 response and its typed fields."""

    if (
        isinstance(max_line_bytes, bool)
        or not isinstance(max_line_bytes, int)
        or max_line_bytes < 64
    ):
        raise ValueError("max_line_bytes must be an integer of at least 64")
    if not isinstance(line, (bytes, str)):
        raise FeedbackWireError(
            FeedbackWireFailure.NON_TEXT_LINE,
            "feedback reader returned a non-text value",
        )
    size = len(line if isinstance(line, bytes) else line.encode("utf-8"))
    if size > max_line_bytes:
        raise FeedbackWireError(
            FeedbackWireFailure.OVERLONG_LINE,
            "feedback line exceeds max_line_bytes",
        )
    newline_terminated = (
        line.endswith(b"\n") if isinstance(line, bytes) else line.endswith("\n")
    )
    if not newline_terminated:
        raise FeedbackWireError(
            FeedbackWireFailure.TRUNCATED_LINE,
            "feedback line was truncated before its newline terminator",
        )
    reset_banner = (
        line.startswith(b"ets ")
        if isinstance(line, bytes)
        else line.startswith("ets ")
    )
    if reset_banner:
        raise FeedbackWireError(
            FeedbackWireFailure.RESET_BANNER,
            "controller emitted an ESP reset banner instead of feedback",
        )
    try:
        message = decode_line(line)
    except ProtocolError as exc:
        raise FeedbackWireError(
            FeedbackWireFailure.MALFORMED_JSON,
            f"malformed feedback JSON: {exc}",
        ) from exc
    if message.get("T") != FEEDBACK_RESPONSE_TYPE:
        raise FeedbackWireError(
            FeedbackWireFailure.WRONG_RESPONSE_TYPE,
            f"expected T={FEEDBACK_RESPONSE_TYPE}, received T={message.get('T')!r}",
        )
    try:
        parse_feedback_1051(message)
    except FeedbackError as exc:
        raise FeedbackWireError(
            FeedbackWireFailure.INVALID_TYPED_FEEDBACK,
            f"invalid typed feedback: {exc}",
        ) from exc
    return message


__all__ = [
    "FeedbackWireError",
    "FeedbackWireFailure",
    "receive_buffered_byte_count",
    "require_quiescent_receive_buffer",
    "validate_feedback_response_line",
]
