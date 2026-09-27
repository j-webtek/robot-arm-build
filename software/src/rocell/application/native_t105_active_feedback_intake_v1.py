"""Hardware-incapable intake for one later active T=105 feedback exchange.

This record freezes the exact request bytes and one-shot lifecycle after the
ARM-062 passive endpoint qualification.  It performs no I/O and grants no
authority to open or write the endpoint.  A distinct operator authorization
must bind the retained intake before a hardware-capable runner may exist.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

from rocell.arm.protocol import encode_line, feedback_request
from .native_t102_production_transport_v1 import PinnedNativeT102EndpointV1
from .native_t102_read_only_endpoint_intake_v1 import (
    NativeT102ReadOnlyEndpointIntakeV1,
)


SCHEMA = "rocell.native_t105_active_feedback_intake.v1"
STATUS = "READY_FOR_SEPARATE_ACTIVE_FEEDBACK_AUTHORIZATION"
OPERATIONS = (
    "VERIFY_PINNED_IDENTITY_BEFORE_OPEN",
    "OPEN_EXACT_ENDPOINT_ONCE",
    "VERIFY_QUIESCENT_RECEIVE_BUFFER",
    "WRITE_EXACT_T105_REQUEST_ONCE",
    "READ_ONE_BOUNDED_T1051_RESPONSE",
    "CLOSE_EXACT_ENDPOINT_ONCE",
    "VERIFY_PINNED_IDENTITY_AFTER_CLOSE",
)
REQUEST_BYTES = encode_line(feedback_request())
REQUEST_SHA256 = hashlib.sha256(REQUEST_BYTES).hexdigest()
REQUEST_BASE64 = base64.b64encode(REQUEST_BYTES).decode("ascii")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class NativeT105ActiveFeedbackIntakeError(ValueError):
    """The active-feedback intake is invalid or its boundary was crossed."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeT105ActiveFeedbackIntakeError(
            "intake value is not canonical JSON") from exc


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise NativeT105ActiveFeedbackIntakeError(
            f"{label} must be a bounded identifier")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise NativeT105ActiveFeedbackIntakeError(
            f"{label} must be a SHA-256 digest")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise NativeT105ActiveFeedbackIntakeError(
            f"{label} must be whole-second UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise NativeT105ActiveFeedbackIntakeError(
            f"{label} must be valid UTC") from exc


def _timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NativeT105ActiveFeedbackIntakeError(
            "response_timeout_s must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= 5:
        raise NativeT105ActiveFeedbackIntakeError(
            "response_timeout_s must be finite and in (0, 5]")
    return result


@dataclass(frozen=True, slots=True)
class NativeT105ActiveFeedbackIntakeV1:
    intake_id: str
    created_utc: str
    host_id: str
    endpoint: PinnedNativeT102EndpointV1
    read_only_intake_sha256: str
    passive_qualification_sha256: str
    response_timeout_s: float = 1.0
    maximum_response_line_bytes: int = 2048
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise NativeT105ActiveFeedbackIntakeError(
                "unsupported active-feedback intake schema")
        _identifier(self.intake_id, "intake_id")
        _identifier(self.host_id, "host_id")
        _utc(self.created_utc, "created_utc")
        _sha256(self.read_only_intake_sha256, "read_only_intake_sha256")
        _sha256(
            self.passive_qualification_sha256,
            "passive_qualification_sha256",
        )
        if not isinstance(self.endpoint, PinnedNativeT102EndpointV1):
            raise TypeError("endpoint must be PinnedNativeT102EndpointV1")
        object.__setattr__(self, "response_timeout_s", _timeout(
            self.response_timeout_s))
        if type(self.maximum_response_line_bytes) is not int or not (
            64 <= self.maximum_response_line_bytes <= 4096
        ):
            raise NativeT105ActiveFeedbackIntakeError(
                "maximum_response_line_bytes must be in 64..4096")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": STATUS,
            "intake_id": self.intake_id,
            "created_utc": self.created_utc,
            "host_id": self.host_id,
            "read_only_intake_sha256": self.read_only_intake_sha256,
            "passive_qualification_sha256": self.passive_qualification_sha256,
            "endpoint": self.endpoint.to_dict(),
            "endpoint_sha256": self.endpoint.endpoint_sha256,
            "operations": list(OPERATIONS),
            "request_command_type": 105,
            "expected_response_type": 1051,
            "request_bytes_base64": REQUEST_BASE64,
            "request_byte_count": len(REQUEST_BYTES),
            "request_sha256": REQUEST_SHA256,
            "response_timeout_s": self.response_timeout_s,
            "maximum_response_lines": 1,
            "maximum_response_line_bytes": self.maximum_response_line_bytes,
            "open_count_limit": 1,
            "close_count_limit": 1,
            "transport_write_count_limit": 1,
            "active_request_count_limit": 1,
            "movement_command_count_limit": 0,
            "torque_command_count_limit": 0,
            "t102_command_count_limit": 0,
            "buffer_purge_allowed": False,
            "fallback_endpoint_allowed": False,
            "automatic_retry_allowed": False,
            "dtr_assertion_allowed": False,
            "rts_assertion_allowed": False,
            "controller_start_allowed": False,
            "ready_for_separate_active_feedback_authorization": True,
            "active_feedback_authorized": False,
            "endpoint_open_authorized": False,
            "transport_write_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def intake_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "intake_sha256": self.intake_sha256}


def build_native_t105_active_feedback_intake_v1(
    read_only_intake: NativeT102ReadOnlyEndpointIntakeV1,
    *, passive_qualification_sha256: str, intake_id: str, created_utc: str,
    response_timeout_s: float = 1.0, maximum_response_line_bytes: int = 2048,
) -> NativeT105ActiveFeedbackIntakeV1:
    """Build a zero-I/O proposal bound to the qualified endpoint."""

    if not isinstance(
        read_only_intake, NativeT102ReadOnlyEndpointIntakeV1
    ):
        raise TypeError(
            "read_only_intake must be NativeT102ReadOnlyEndpointIntakeV1")
    if _utc(created_utc, "created_utc") < _utc(
        read_only_intake.created_utc, "read_only_intake.created_utc"
    ):
        raise NativeT105ActiveFeedbackIntakeError(
            "active-feedback intake must not predate read-only intake")
    return NativeT105ActiveFeedbackIntakeV1(
        intake_id=intake_id,
        created_utc=created_utc,
        host_id=read_only_intake.host_id,
        endpoint=read_only_intake.endpoint,
        read_only_intake_sha256=read_only_intake.intake_sha256,
        passive_qualification_sha256=passive_qualification_sha256,
        response_timeout_s=response_timeout_s,
        maximum_response_line_bytes=maximum_response_line_bytes,
    )


def parse_native_t105_active_feedback_intake_v1(
    document: dict[str, Any],
) -> NativeT105ActiveFeedbackIntakeV1:
    """Strictly parse an intake without opening or writing any endpoint."""

    template = NativeT105ActiveFeedbackIntakeV1(
        intake_id="template", created_utc="2000-01-01T00:00:00Z",
        host_id="template", endpoint=PinnedNativeT102EndpointV1(
            port_name="COM1", usb_vid="0000", usb_pid="0000",
            usb_serial_number="template"),
        read_only_intake_sha256="0" * 64,
        passive_qualification_sha256="0" * 64,
    ).to_dict()
    if type(document) is not dict or set(document) != set(template):
        raise NativeT105ActiveFeedbackIntakeError(
            "active-feedback intake must contain exactly the closed fields")
    constants = {
        key: value for key, value in template.items() if key not in {
            "intake_id", "created_utc", "host_id", "endpoint",
            "endpoint_sha256", "read_only_intake_sha256",
            "passive_qualification_sha256", "response_timeout_s",
            "maximum_response_line_bytes", "intake_sha256",
        }
    }
    if any(document[key] != value for key, value in constants.items()):
        raise NativeT105ActiveFeedbackIntakeError(
            "active-feedback request, policy, or authority differs")
    raw_endpoint = document["endpoint"]
    if type(raw_endpoint) is not dict:
        raise NativeT105ActiveFeedbackIntakeError(
            "endpoint must be a closed object")
    try:
        endpoint = PinnedNativeT102EndpointV1(
            port_name=raw_endpoint["port_name"],
            usb_vid=raw_endpoint["usb_vid"],
            usb_pid=raw_endpoint["usb_pid"],
            usb_serial_number=raw_endpoint["usb_serial_number"],
            baud_rate=raw_endpoint["baud_rate"],
            data_bits=raw_endpoint["data_bits"],
            parity=raw_endpoint["parity"],
            stop_bits=raw_endpoint["stop_bits"],
            flow_control=raw_endpoint["flow_control"],
        )
        parsed = NativeT105ActiveFeedbackIntakeV1(
            intake_id=document["intake_id"],
            created_utc=document["created_utc"],
            host_id=document["host_id"],
            endpoint=endpoint,
            read_only_intake_sha256=document["read_only_intake_sha256"],
            passive_qualification_sha256=(
                document["passive_qualification_sha256"]),
            response_timeout_s=document["response_timeout_s"],
            maximum_response_line_bytes=document[
                "maximum_response_line_bytes"],
            schema=document["schema"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NativeT105ActiveFeedbackIntakeError(
            "active-feedback intake contains invalid typed values") from exc
    if raw_endpoint != endpoint.to_dict() or (
        document["endpoint_sha256"] != endpoint.endpoint_sha256
    ):
        raise NativeT105ActiveFeedbackIntakeError(
            "embedded endpoint identity differs")
    if document["intake_sha256"] != parsed.intake_sha256:
        raise NativeT105ActiveFeedbackIntakeError(
            "active-feedback intake content hash differs")
    return parsed


__all__ = [
    "OPERATIONS", "REQUEST_BASE64", "REQUEST_BYTES", "REQUEST_SHA256",
    "SCHEMA", "STATUS", "NativeT105ActiveFeedbackIntakeError",
    "NativeT105ActiveFeedbackIntakeV1",
    "build_native_t105_active_feedback_intake_v1",
    "parse_native_t105_active_feedback_intake_v1",
]
