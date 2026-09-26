"""Zero-I/O contract rehearsal for a future production controller runtime.

This module models controller-facing admission, ordering, feedback framing and
fail-closed lifecycle rules.  It deliberately owns no transport and cannot
install firmware, restart a controller, generate authority, or move hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
import threading
from typing import Any

from rocell.arm.all_joint_command import JOINT_FIELDS, all_joint_command
from rocell.arm.feedback_wire import validate_feedback_response_line
from rocell.arm.protocol import decode_line, encode_line, feedback_request


MANIFEST_SCHEMA = "rocell.production_controller_runtime_manifest.v1"
REPORT_SCHEMA = "rocell.production_controller_runtime_rehearsal.v1"
STARTUP_POLICY = "SAFE_IDLE_NO_MOTION"
WRITER_POLICY = "ONE_ACTIVE_WRITER_EXACT_SEQUENCE"
RETRY_POLICY = "NEVER_AUTOMATIC"
EXPECTED_T102_FIELDS = ("T", *JOINT_FIELDS, "spd", "acc")
EXPECTED_T1021_FIELDS = ("T", "status", "ordinal")
EXPECTED_T105_FIELDS = ("T",)
EXPECTED_T1051_JOINT_FIELDS = ("b", "s", "e", "t", "r", "g")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ProductionControllerRuntimeContractError(ValueError):
    """The candidate runtime contract or rehearsal failed closed."""


class ProductionRuntimeState(str, Enum):
    SAFE_IDLE = "SAFE_IDLE"
    WRITER_CLAIMED = "WRITER_CLAIMED"
    TERMINAL_LOCKED = "TERMINAL_LOCKED"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProductionControllerRuntimeContractError(
            "runtime value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ProductionControllerRuntimeContractError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ProductionControllerRuntimeContractError(
            f"{label} must be a bounded identifier")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProductionControllerRuntimeContractError(
            f"{label} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class ProductionControllerRuntimeManifestV1:
    runtime_id: str
    candidate_app_sha256: str
    protocol_source_sha256: str
    controller_joint_mapping_sha256: str
    configuration_epoch_sha256: str
    expected_encoding_profile_sha256: str
    controller_session_id: str
    maximum_command_bytes: int = 512
    maximum_feedback_bytes: int = 2048
    schema: str = MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MANIFEST_SCHEMA:
            raise ProductionControllerRuntimeContractError(
                "unsupported production-runtime manifest schema")
        _identifier(self.runtime_id, "runtime_id")
        _identifier(self.controller_session_id, "controller_session_id")
        for name in (
            "candidate_app_sha256", "protocol_source_sha256",
            "controller_joint_mapping_sha256", "configuration_epoch_sha256",
            "expected_encoding_profile_sha256",
        ):
            _digest(getattr(self, name), name)
        command_bytes = _positive_int(
            self.maximum_command_bytes, "maximum_command_bytes")
        feedback_bytes = _positive_int(
            self.maximum_feedback_bytes, "maximum_feedback_bytes")
        if not 64 <= command_bytes <= 4096:
            raise ProductionControllerRuntimeContractError(
                "maximum_command_bytes must be in 64..4096")
        if not 64 <= feedback_bytes <= 16384:
            raise ProductionControllerRuntimeContractError(
                "maximum_feedback_bytes must be in 64..16384")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "runtime_id": self.runtime_id,
            "candidate_app_sha256": self.candidate_app_sha256,
            "protocol_source_sha256": self.protocol_source_sha256,
            "controller_joint_mapping_sha256": (
                self.controller_joint_mapping_sha256),
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "expected_encoding_profile_sha256": (
                self.expected_encoding_profile_sha256),
            "controller_session_id": self.controller_session_id,
            "maximum_command_bytes": self.maximum_command_bytes,
            "maximum_feedback_bytes": self.maximum_feedback_bytes,
            "startup_policy": STARTUP_POLICY,
            "writer_policy": WRITER_POLICY,
            "retry_policy": RETRY_POLICY,
            "supported_command_types": [102, 105],
            "supported_response_types": [1021, 1051],
            "t102_fields": list(EXPECTED_T102_FIELDS),
            "t1021_fields": list(EXPECTED_T1021_FIELDS),
            "t105_fields": list(EXPECTED_T105_FIELDS),
            "t1051_required_joint_fields": list(
                EXPECTED_T1051_JOINT_FIELDS),
            "startup_motion_commands": 0,
            "automatic_retry": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "manifest_sha256": self.manifest_sha256}


@dataclass(frozen=True, slots=True)
class RuntimeCommandFrameV1:
    sequence: int
    correlation_id: str
    writer_instance_id: str
    controller_session_id: str
    configuration_epoch_sha256: str
    encoding_profile_sha256: str
    issued_monotonic_ns: int
    expires_monotonic_ns: int
    wire_bytes: bytes

    def __post_init__(self) -> None:
        _positive_int(self.sequence, "sequence")
        _identifier(self.correlation_id, "correlation_id")
        _identifier(self.writer_instance_id, "writer_instance_id")
        _identifier(self.controller_session_id, "controller_session_id")
        _digest(self.configuration_epoch_sha256, "configuration_epoch_sha256")
        _digest(self.encoding_profile_sha256, "encoding_profile_sha256")
        issued = _positive_int(self.issued_monotonic_ns, "issued_monotonic_ns")
        expires = _positive_int(self.expires_monotonic_ns, "expires_monotonic_ns")
        if expires <= issued:
            raise ProductionControllerRuntimeContractError(
                "frame expiry must follow issuance")
        if not isinstance(self.wire_bytes, bytes) or not self.wire_bytes:
            raise ProductionControllerRuntimeContractError(
                "wire_bytes must be nonempty bytes")

    @property
    def wire_bytes_sha256(self) -> str:
        return hashlib.sha256(self.wire_bytes).hexdigest()

    @property
    def frame_sha256(self) -> str:
        return hashlib.sha256(_canonical({
            "sequence": self.sequence,
            "correlation_id": self.correlation_id,
            "writer_instance_id": self.writer_instance_id,
            "controller_session_id": self.controller_session_id,
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "encoding_profile_sha256": self.encoding_profile_sha256,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "expires_monotonic_ns": self.expires_monotonic_ns,
            "wire_bytes_sha256": self.wire_bytes_sha256,
        })).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeAdmissionRecordV1:
    sequence: int
    correlation_id: str
    frame_sha256: str
    wire_bytes_sha256: str
    message_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "correlation_id": self.correlation_id,
            "frame_sha256": self.frame_sha256,
            "wire_bytes_sha256": self.wire_bytes_sha256,
            "message_sha256": self.message_sha256,
            "status": "ADMITTED_CONTRACT_ONLY",
            "hardware_write_count": 0,
        }


@dataclass(frozen=True, slots=True)
class RuntimeCommandAcknowledgmentRecordV1:
    sequence: int
    response_bytes_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "response_bytes_sha256": self.response_bytes_sha256,
            "status": "ACCEPTED_ONCE",
            "arrival_proven": False,
            "hardware_write_count": 0,
        }


class ProductionControllerRuntimeContractV1:
    """In-memory safe-idle and sole-writer contract with no I/O capability."""

    def __init__(self, manifest: ProductionControllerRuntimeManifestV1) -> None:
        if not isinstance(manifest, ProductionControllerRuntimeManifestV1):
            raise TypeError("manifest must be ProductionControllerRuntimeManifestV1")
        self.manifest = manifest
        self._state = ProductionRuntimeState.SAFE_IDLE
        self._writer_instance_id: str | None = None
        self._last_sequence = 0
        self._admissions: list[RuntimeAdmissionRecordV1] = []
        self._acknowledgments: list[RuntimeCommandAcknowledgmentRecordV1] = []
        self._pending_ack_sequence: int | None = None
        self._feedback_exchange_count = 0
        self._terminal_reason: str | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> ProductionRuntimeState:
        with self._lock:
            return self._state

    def claim_writer(self, writer_instance_id: str) -> None:
        writer = _identifier(writer_instance_id, "writer_instance_id")
        with self._lock:
            if self._state is not ProductionRuntimeState.SAFE_IDLE:
                raise ProductionControllerRuntimeContractError(
                    "runtime is not available for a writer claim")
            self._writer_instance_id = writer
            self._state = ProductionRuntimeState.WRITER_CLAIMED

    def _lock_terminal(self, reason: str) -> None:
        self._state = ProductionRuntimeState.TERMINAL_LOCKED
        self._terminal_reason = reason

    def admit_t102(
        self, frame: RuntimeCommandFrameV1, *, now_monotonic_ns: int,
    ) -> RuntimeAdmissionRecordV1:
        if not isinstance(frame, RuntimeCommandFrameV1):
            raise TypeError("frame must be RuntimeCommandFrameV1")
        now = _positive_int(now_monotonic_ns, "now_monotonic_ns")
        with self._lock:
            try:
                if self._state is not ProductionRuntimeState.WRITER_CLAIMED:
                    raise ProductionControllerRuntimeContractError(
                        "runtime has no active writer")
                if self._pending_ack_sequence is not None:
                    raise ProductionControllerRuntimeContractError(
                        "prior T=102 acknowledgment remains pending")
                if frame.writer_instance_id != self._writer_instance_id:
                    raise ProductionControllerRuntimeContractError(
                        "frame came from a different writer")
                if frame.controller_session_id != self.manifest.controller_session_id:
                    raise ProductionControllerRuntimeContractError(
                        "frame controller session differs")
                if (frame.configuration_epoch_sha256
                        != self.manifest.configuration_epoch_sha256):
                    raise ProductionControllerRuntimeContractError(
                        "frame configuration epoch differs")
                if (frame.encoding_profile_sha256
                        != self.manifest.expected_encoding_profile_sha256):
                    raise ProductionControllerRuntimeContractError(
                        "frame encoding profile differs")
                if frame.sequence != self._last_sequence + 1:
                    raise ProductionControllerRuntimeContractError(
                        "frame sequence is duplicated or out of order")
                if not frame.issued_monotonic_ns <= now < frame.expires_monotonic_ns:
                    raise ProductionControllerRuntimeContractError(
                        "frame is not current")
                if len(frame.wire_bytes) > self.manifest.maximum_command_bytes:
                    raise ProductionControllerRuntimeContractError(
                        "T=102 frame exceeds maximum_command_bytes")
                message = decode_line(frame.wire_bytes)
                if tuple(message) != EXPECTED_T102_FIELDS or message.get("T") != 102:
                    raise ProductionControllerRuntimeContractError(
                        "T=102 frame fields or ordering differ from contract")
                rebuilt = all_joint_command(
                    [message[name] for name in JOINT_FIELDS],
                    speed=message["spd"], acceleration=message["acc"])
                if rebuilt != message or encode_line(rebuilt) != frame.wire_bytes:
                    raise ProductionControllerRuntimeContractError(
                        "T=102 frame is not the exact deterministic encoding")
                record = RuntimeAdmissionRecordV1(
                    sequence=frame.sequence,
                    correlation_id=frame.correlation_id,
                    frame_sha256=frame.frame_sha256,
                    wire_bytes_sha256=frame.wire_bytes_sha256,
                    message_sha256=hashlib.sha256(_canonical(message)).hexdigest(),
                )
                self._last_sequence = frame.sequence
                self._admissions.append(record)
                self._pending_ack_sequence = frame.sequence
                return record
            except Exception as exc:
                self._lock_terminal(type(exc).__name__)
                raise

    def rehearse_command_acknowledgment(self, response_bytes: bytes) -> None:
        """Consume one exact r97 accepted-once response without implying arrival."""

        with self._lock:
            try:
                if self._state is not ProductionRuntimeState.WRITER_CLAIMED:
                    raise ProductionControllerRuntimeContractError(
                        "runtime has no active writer")
                if self._pending_ack_sequence is None:
                    raise ProductionControllerRuntimeContractError(
                        "no T=102 acknowledgment is pending")
                if not isinstance(response_bytes, bytes):
                    raise ProductionControllerRuntimeContractError(
                        "T=1021 acknowledgment must be bytes")
                if len(response_bytes) > self.manifest.maximum_feedback_bytes:
                    raise ProductionControllerRuntimeContractError(
                        "T=1021 acknowledgment exceeds maximum_feedback_bytes")
                message = decode_line(response_bytes)
                expected = {
                    "T": 1021,
                    "status": "ACCEPTED_ONCE",
                    "ordinal": self._pending_ack_sequence,
                }
                if (
                    tuple(message) != EXPECTED_T1021_FIELDS
                    or message != expected
                    or encode_line(expected) != response_bytes
                ):
                    raise ProductionControllerRuntimeContractError(
                        "T=1021 acknowledgment differs from pending command")
                self._acknowledgments.append(
                    RuntimeCommandAcknowledgmentRecordV1(
                        sequence=self._pending_ack_sequence,
                        response_bytes_sha256=hashlib.sha256(
                            response_bytes).hexdigest(),
                    ))
                self._pending_ack_sequence = None
            except Exception as exc:
                self._lock_terminal(type(exc).__name__)
                raise

    def mark_command_acknowledgment_timeout(self) -> None:
        """Latch uncertainty after a missing response; never retry the command."""

        with self._lock:
            if (
                self._state is not ProductionRuntimeState.WRITER_CLAIMED
                or self._pending_ack_sequence is None
            ):
                self._lock_terminal("ACKNOWLEDGMENT_TIMEOUT_WITHOUT_PENDING_COMMAND")
                raise ProductionControllerRuntimeContractError(
                    "no pending command can time out")
            self._lock_terminal("COMMAND_ACKNOWLEDGMENT_TIMEOUT_UNCERTAIN")

    def rehearse_feedback_exchange(
        self, request_bytes: bytes, response_bytes: bytes,
    ) -> None:
        with self._lock:
            try:
                if self._state is not ProductionRuntimeState.WRITER_CLAIMED:
                    raise ProductionControllerRuntimeContractError(
                        "runtime has no active writer")
                if self._pending_ack_sequence is not None:
                    raise ProductionControllerRuntimeContractError(
                        "feedback cannot begin while T=102 acknowledgment is pending")
                if request_bytes != encode_line(feedback_request()):
                    raise ProductionControllerRuntimeContractError(
                        "feedback request must be exact deterministic T=105")
                parsed = validate_feedback_response_line(
                    response_bytes,
                    max_line_bytes=self.manifest.maximum_feedback_bytes,
                )
                if any(field not in parsed for field in EXPECTED_T1051_JOINT_FIELDS):
                    raise ProductionControllerRuntimeContractError(
                        "T=1051 response lacks one or more required joint fields")
                self._feedback_exchange_count += 1
            except Exception as exc:
                self._lock_terminal(type(exc).__name__)
                raise

    def mark_restart_after_claim(self) -> None:
        with self._lock:
            if self._state is ProductionRuntimeState.WRITER_CLAIMED:
                self._lock_terminal("RESTART_RECONCILIATION_REQUIRED")

    def report(self) -> dict[str, Any]:
        with self._lock:
            unsigned = {
                "schema": REPORT_SCHEMA,
                "manifest_sha256": self.manifest.manifest_sha256,
                "state": self._state.value,
                "status": (
                    "AWAITING_COMMAND_ACKNOWLEDGMENT"
                    if (self._state is ProductionRuntimeState.WRITER_CLAIMED
                        and self._pending_ack_sequence is not None)
                    else "CONTRACT_REHEARSAL_READY"
                    if self._state is ProductionRuntimeState.WRITER_CLAIMED
                    else "SAFE_IDLE" if self._state is ProductionRuntimeState.SAFE_IDLE
                    else "TERMINAL_NO_RETRY"),
                "writer_instance_id": self._writer_instance_id,
                "last_sequence": self._last_sequence,
                "admission_count": len(self._admissions),
                "admissions": [item.to_dict() for item in self._admissions],
                "pending_ack_sequence": self._pending_ack_sequence,
                "acknowledgment_count": len(self._acknowledgments),
                "acknowledgments": [
                    item.to_dict() for item in self._acknowledgments],
                "feedback_exchange_count": self._feedback_exchange_count,
                "terminal_reason": self._terminal_reason,
                "startup_motion_commands": 0,
                "transport_open_count": 0,
                "hardware_write_count": 0,
                "automatic_retry": False,
                "replay_allowed": False,
                "hardware_access": False,
                "physical_authority": False,
            }
            return {
                **unsigned,
                "report_sha256": hashlib.sha256(_canonical(unsigned)).hexdigest(),
            }


__all__ = [
    "EXPECTED_T102_FIELDS", "EXPECTED_T1021_FIELDS", "EXPECTED_T105_FIELDS",
    "EXPECTED_T1051_JOINT_FIELDS", "MANIFEST_SCHEMA", "REPORT_SCHEMA",
    "RETRY_POLICY", "STARTUP_POLICY", "WRITER_POLICY",
    "ProductionControllerRuntimeContractError",
    "ProductionControllerRuntimeContractV1",
    "ProductionControllerRuntimeManifestV1", "ProductionRuntimeState",
    "RuntimeAdmissionRecordV1", "RuntimeCommandAcknowledgmentRecordV1",
    "RuntimeCommandFrameV1",
]
