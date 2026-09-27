"""Deterministic fake-only rehearsal for the ARM-063 T=105 intake.

The runner deliberately requires the concrete fake endpoint below.  It cannot
accept pyserial, a port name, a factory, or an arbitrary transport object.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from rocell.arm.feedback_wire import (
    require_quiescent_receive_buffer,
    validate_feedback_response_line,
)
from .native_t105_active_feedback_intake_v1 import (
    REQUEST_BYTES,
    NativeT105ActiveFeedbackIntakeV1,
)


SCHEMA = "rocell.native_t105_active_feedback_rehearsal.v1"
_JOINT_FIELDS = ("b", "s", "e", "t", "r", "g")


class NativeT105ActiveFeedbackRehearsalError(ValueError):
    """The fake exchange failed the frozen one-shot contract."""


class DeterministicFakeT105Endpoint:
    """In-memory endpoint with the minimal closed serial-shaped surface."""

    __slots__ = (
        "endpoint_sha256", "response_line", "prebuffered_bytes",
        "short_write", "open_count", "close_count", "write_count",
        "read_count", "written", "is_open",
    )

    def __init__(
        self, *, endpoint_sha256: str, response_line: bytes,
        prebuffered_bytes: int = 0, short_write: bool = False,
    ) -> None:
        if type(endpoint_sha256) is not str:
            raise TypeError("endpoint_sha256 must be text")
        if type(response_line) is not bytes:
            raise TypeError("response_line must be bytes")
        if type(prebuffered_bytes) is not int or prebuffered_bytes < 0:
            raise ValueError("prebuffered_bytes must be nonnegative")
        self.endpoint_sha256 = endpoint_sha256
        self.response_line = response_line
        self.prebuffered_bytes = prebuffered_bytes
        self.short_write = bool(short_write)
        self.open_count = 0
        self.close_count = 0
        self.write_count = 0
        self.read_count = 0
        self.written = b""
        self.is_open = False

    @property
    def in_waiting(self) -> int:
        return self.prebuffered_bytes

    def open_once(self) -> None:
        if self.open_count or self.is_open:
            raise NativeT105ActiveFeedbackRehearsalError(
                "fake endpoint may open only once")
        self.open_count += 1
        self.is_open = True

    def write_once(self, payload: bytes) -> int:
        if not self.is_open or self.write_count:
            raise NativeT105ActiveFeedbackRehearsalError(
                "fake endpoint may write only once while open")
        self.write_count += 1
        count = len(payload) - 1 if self.short_write else len(payload)
        self.written += payload[:count]
        return count

    def readline_once(self) -> bytes:
        if not self.is_open or self.read_count:
            raise NativeT105ActiveFeedbackRehearsalError(
                "fake endpoint may read only once while open")
        self.read_count += 1
        return self.response_line

    def close_once(self) -> None:
        if self.close_count or not self.is_open:
            raise NativeT105ActiveFeedbackRehearsalError(
                "fake endpoint may close only once after open")
        self.close_count += 1
        self.is_open = False


@dataclass(frozen=True, slots=True)
class NativeT105ActiveFeedbackRehearsalReceiptV1:
    intake_sha256: str
    endpoint_sha256: str
    response_sha256: str
    joint_fields: dict[str, float]
    schema: str = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "FAKE_ONE_SHOT_T105_REHEARSAL_PASS",
            "intake_sha256": self.intake_sha256,
            "endpoint_sha256": self.endpoint_sha256,
            "request_sha256": hashlib.sha256(REQUEST_BYTES).hexdigest(),
            "response_sha256": self.response_sha256,
            "joint_fields": dict(self.joint_fields),
            "open_count": 1,
            "write_count": 1,
            "outbound_byte_count": len(REQUEST_BYTES),
            "active_request_count": 1,
            "response_line_count": 1,
            "close_count": 1,
            "movement_command_count": 0,
            "torque_command_count": 0,
            "t102_command_count": 0,
            "automatic_retry_count": 0,
            "fake_endpoint_only": True,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }


def rehearse_native_t105_active_feedback_v1(
    intake: NativeT105ActiveFeedbackIntakeV1,
    endpoint: DeterministicFakeT105Endpoint,
) -> NativeT105ActiveFeedbackRehearsalReceiptV1:
    """Exercise one exact fake exchange and always close after a successful open."""

    if not isinstance(intake, NativeT105ActiveFeedbackIntakeV1):
        raise TypeError("intake must be NativeT105ActiveFeedbackIntakeV1")
    if type(endpoint) is not DeterministicFakeT105Endpoint:
        raise TypeError("endpoint must be DeterministicFakeT105Endpoint")
    if endpoint.endpoint_sha256 != intake.endpoint.endpoint_sha256:
        raise NativeT105ActiveFeedbackRehearsalError(
            "fake endpoint identity differs from intake")
    endpoint.open_once()
    try:
        require_quiescent_receive_buffer(endpoint)
        written = endpoint.write_once(REQUEST_BYTES)
        if written != len(REQUEST_BYTES) or endpoint.written != REQUEST_BYTES:
            raise NativeT105ActiveFeedbackRehearsalError(
                "exact T=105 request was not written completely")
        response_line = endpoint.readline_once()
        message = validate_feedback_response_line(
            response_line,
            max_line_bytes=intake.maximum_response_line_bytes,
        )
        joints: dict[str, float] = {}
        for field in _JOINT_FIELDS:
            value = message.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise NativeT105ActiveFeedbackRehearsalError(
                    f"T=1051 response lacks numeric joint field {field}")
            parsed = float(value)
            if not math.isfinite(parsed):
                raise NativeT105ActiveFeedbackRehearsalError(
                    f"T=1051 joint field {field} is nonfinite")
            joints[field] = parsed
        canonical_response = json.dumps(
            message, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        return NativeT105ActiveFeedbackRehearsalReceiptV1(
            intake_sha256=intake.intake_sha256,
            endpoint_sha256=intake.endpoint.endpoint_sha256,
            response_sha256=hashlib.sha256(canonical_response).hexdigest(),
            joint_fields=joints,
        )
    finally:
        endpoint.close_once()


__all__ = [
    "SCHEMA", "DeterministicFakeT105Endpoint",
    "NativeT105ActiveFeedbackRehearsalError",
    "NativeT105ActiveFeedbackRehearsalReceiptV1",
    "rehearse_native_t105_active_feedback_v1",
]
