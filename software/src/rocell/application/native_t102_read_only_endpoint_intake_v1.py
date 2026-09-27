"""Hardware-incapable intake for a later read-only ARM-054 endpoint probe.

The intake binds owner-accepted review evidence to one exact endpoint and a
closed zero-write observation policy.  It neither enumerates nor opens ports
and cannot authorize the later physical probe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

from .native_t102_owner_ai_review_acceptance_v1 import (
    NativeT102OwnerAIReviewAcceptanceV1,
)
from .native_t102_production_transport_v1 import PinnedNativeT102EndpointV1


SCHEMA = "rocell.native_t102_read_only_endpoint_intake.v1"
OPERATIONS = (
    "VERIFY_PINNED_IDENTITY_BEFORE_OPEN",
    "OPEN_EXACT_ENDPOINT_ONCE",
    "VERIFY_PINNED_IDENTITY_AFTER_OPEN",
    "PASSIVE_READ_BOUNDED_LINES",
    "CLOSE_EXACT_ENDPOINT_ONCE",
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class NativeT102ReadOnlyEndpointIntakeError(ValueError):
    """The read-only qualification intake is invalid or crossed."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "intake value is not canonical JSON") from exc


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise NativeT102ReadOnlyEndpointIntakeError(
            f"{label} must be a bounded identifier")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise NativeT102ReadOnlyEndpointIntakeError(
            f"{label} must be whole-second UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise NativeT102ReadOnlyEndpointIntakeError(
            f"{label} must be valid UTC") from exc


def _timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NativeT102ReadOnlyEndpointIntakeError(
            "passive_read_timeout_s must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= 10:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "passive_read_timeout_s must be finite and in (0, 10]")
    return result


@dataclass(frozen=True, slots=True)
class NativeT102ReadOnlyEndpointIntakeV1:
    intake_id: str
    owner_acceptance_sha256: str
    owner_acceptance_id: str
    host_id: str
    created_utc: str
    endpoint: PinnedNativeT102EndpointV1
    passive_read_timeout_s: float = 1.0
    maximum_passive_lines: int = 4
    maximum_line_bytes: int = 2048
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise NativeT102ReadOnlyEndpointIntakeError(
                "unsupported read-only endpoint intake schema")
        _identifier(self.intake_id, "intake_id")
        _identifier(self.owner_acceptance_id, "owner_acceptance_id")
        _identifier(self.host_id, "host_id")
        _utc(self.created_utc, "created_utc")
        if not isinstance(self.owner_acceptance_sha256, str) or not re.fullmatch(
                r"[0-9a-f]{64}", self.owner_acceptance_sha256):
            raise NativeT102ReadOnlyEndpointIntakeError(
                "owner_acceptance_sha256 must be a SHA-256 digest")
        if not isinstance(self.endpoint, PinnedNativeT102EndpointV1):
            raise TypeError("endpoint must be PinnedNativeT102EndpointV1")
        object.__setattr__(
            self, "passive_read_timeout_s", _timeout(self.passive_read_timeout_s))
        if type(self.maximum_passive_lines) is not int \
                or not 1 <= self.maximum_passive_lines <= 16:
            raise NativeT102ReadOnlyEndpointIntakeError(
                "maximum_passive_lines must be in 1..16")
        if type(self.maximum_line_bytes) is not int \
                or not 64 <= self.maximum_line_bytes <= 4096:
            raise NativeT102ReadOnlyEndpointIntakeError(
                "maximum_line_bytes must be in 64..4096")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION",
            "intake_id": self.intake_id,
            "owner_acceptance_sha256": self.owner_acceptance_sha256,
            "owner_acceptance_id": self.owner_acceptance_id,
            "host_id": self.host_id,
            "created_utc": self.created_utc,
            "endpoint": self.endpoint.to_dict(),
            "endpoint_sha256": self.endpoint.endpoint_sha256,
            "operations": list(OPERATIONS),
            "passive_read_timeout_s": self.passive_read_timeout_s,
            "maximum_passive_lines": self.maximum_passive_lines,
            "maximum_line_bytes": self.maximum_line_bytes,
            "open_count_limit": 1,
            "close_count_limit": 1,
            "transport_write_count_limit": 0,
            "active_request_count_limit": 0,
            "movement_command_count_limit": 0,
            "torque_command_count_limit": 0,
            "buffer_purge_allowed": False,
            "fallback_endpoint_allowed": False,
            "automatic_retry_allowed": False,
            "dtr_assertion_allowed": False,
            "rts_assertion_allowed": False,
            "ready_for_separate_read_only_authorization": True,
            "read_only_endpoint_authorized": False,
            "endpoint_open_authorized": False,
            "controller_start_authorized": False,
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


def build_native_t102_read_only_endpoint_intake_v1(
    owner_acceptance: NativeT102OwnerAIReviewAcceptanceV1,
    endpoint: PinnedNativeT102EndpointV1, *, intake_id: str, host_id: str,
    created_utc: str, passive_read_timeout_s: float = 1.0,
    maximum_passive_lines: int = 4, maximum_line_bytes: int = 2048,
) -> NativeT102ReadOnlyEndpointIntakeV1:
    """Create a zero-I/O intake after exact owner review acceptance."""

    if not isinstance(
        owner_acceptance, NativeT102OwnerAIReviewAcceptanceV1
    ):
        raise TypeError(
            "owner_acceptance must be NativeT102OwnerAIReviewAcceptanceV1")
    if not isinstance(endpoint, PinnedNativeT102EndpointV1):
        raise TypeError("endpoint must be PinnedNativeT102EndpointV1")
    accepted = _utc(owner_acceptance.accepted_utc, "accepted_utc")
    created = _utc(created_utc, "created_utc")
    if created < accepted:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "intake creation must not predate owner acceptance")
    return NativeT102ReadOnlyEndpointIntakeV1(
        intake_id=intake_id,
        owner_acceptance_sha256=owner_acceptance.acceptance_sha256,
        owner_acceptance_id=owner_acceptance.acceptance_id,
        host_id=host_id,
        created_utc=created_utc,
        endpoint=endpoint,
        passive_read_timeout_s=passive_read_timeout_s,
        maximum_passive_lines=maximum_passive_lines,
        maximum_line_bytes=maximum_line_bytes,
    )


def parse_native_t102_read_only_endpoint_intake_v1(
    document: dict[str, Any],
) -> NativeT102ReadOnlyEndpointIntakeV1:
    """Strictly parse a retained intake without performing hardware I/O."""

    required = {
        "schema", "status", "intake_id", "owner_acceptance_sha256",
        "owner_acceptance_id", "host_id", "created_utc", "endpoint",
        "endpoint_sha256", "operations", "passive_read_timeout_s",
        "maximum_passive_lines", "maximum_line_bytes", "open_count_limit",
        "close_count_limit", "transport_write_count_limit",
        "active_request_count_limit", "movement_command_count_limit",
        "torque_command_count_limit", "buffer_purge_allowed",
        "fallback_endpoint_allowed", "automatic_retry_allowed",
        "dtr_assertion_allowed", "rts_assertion_allowed",
        "ready_for_separate_read_only_authorization",
        "read_only_endpoint_authorized", "endpoint_open_authorized",
        "controller_start_authorized", "transport_write_authorized",
        "execution_authorized", "hardware_access", "physical_authority",
        "intake_sha256",
    }
    if type(document) is not dict or set(document) != required:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "read-only intake must contain exactly the closed fields")
    constants = {
        "status": "READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION",
        "operations": list(OPERATIONS),
        "open_count_limit": 1,
        "close_count_limit": 1,
        "transport_write_count_limit": 0,
        "active_request_count_limit": 0,
        "movement_command_count_limit": 0,
        "torque_command_count_limit": 0,
        "buffer_purge_allowed": False,
        "fallback_endpoint_allowed": False,
        "automatic_retry_allowed": False,
        "dtr_assertion_allowed": False,
        "rts_assertion_allowed": False,
        "ready_for_separate_read_only_authorization": True,
        "read_only_endpoint_authorized": False,
        "endpoint_open_authorized": False,
        "controller_start_authorized": False,
        "transport_write_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
    }
    if any(document[key] != value for key, value in constants.items()):
        raise NativeT102ReadOnlyEndpointIntakeError(
            "read-only intake policy or authority differs")
    raw_endpoint = document["endpoint"]
    if type(raw_endpoint) is not dict:
        raise NativeT102ReadOnlyEndpointIntakeError(
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
        parsed = NativeT102ReadOnlyEndpointIntakeV1(
            intake_id=document["intake_id"],
            owner_acceptance_sha256=document["owner_acceptance_sha256"],
            owner_acceptance_id=document["owner_acceptance_id"],
            host_id=document["host_id"],
            created_utc=document["created_utc"],
            endpoint=endpoint,
            passive_read_timeout_s=document["passive_read_timeout_s"],
            maximum_passive_lines=document["maximum_passive_lines"],
            maximum_line_bytes=document["maximum_line_bytes"],
            schema=document["schema"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "read-only intake contains invalid typed values") from exc
    if raw_endpoint != endpoint.to_dict() \
            or document["endpoint_sha256"] != endpoint.endpoint_sha256:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "embedded endpoint identity differs")
    if document["intake_sha256"] != parsed.intake_sha256:
        raise NativeT102ReadOnlyEndpointIntakeError(
            "read-only intake content hash differs")
    return parsed


__all__ = [
    "OPERATIONS", "SCHEMA", "NativeT102ReadOnlyEndpointIntakeError",
    "NativeT102ReadOnlyEndpointIntakeV1",
    "build_native_t102_read_only_endpoint_intake_v1",
    "parse_native_t102_read_only_endpoint_intake_v1",
]
