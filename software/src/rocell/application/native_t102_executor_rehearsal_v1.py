"""Hardware-incapable qualification of the claimed native T=102 executor.

The executor accepts only ARM-050's exact durable writer claim plus a fresh,
single-use rehearsal authority.  Its transport is a sealed in-memory test
double: it has no serial factory, port, socket, callback, device handle, or
controller process.  The resulting receipt accounts for every attempted byte
without claiming hardware access, controller acknowledgement, or movement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from threading import Lock
from typing import Any

from .native_t102_handoff_journal_v1 import (
    DurableNativeT102HandoffV1,
    NativeT102HandoffJournalError,
)
from .production_controller_runtime_contract_v1 import RuntimeCommandFrameV1
from .reviewed_motion_permit_bridge_v1 import ReviewedMotionPermitAdmissionV1


AUTHORITY_SCHEMA = "rocell.native_t102_execution_authority_rehearsal.v1"
RECEIPT_SCHEMA = "rocell.native_t102_executor_rehearsal_receipt.v1"
AUTHORITY_SCOPE = "HARDWARE_INCAPABLE_NATIVE_T102_REHEARSAL"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class NativeT102ExecutorRehearsalError(ValueError):
    """The claimed handoff, authority, or incapable transport is invalid."""


class IncapableNativeTransportFault(str, Enum):
    NONE = "NONE"
    OPEN_FAILURE = "OPEN_FAILURE"
    ZERO_WRITE = "ZERO_WRITE"
    PARTIAL_WRITE = "PARTIAL_WRITE"
    INVALID_COUNT = "INVALID_COUNT"
    WRITE_EXCEPTION = "WRITE_EXCEPTION"
    CLOSE_FAILURE = "CLOSE_FAILURE"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeT102ExecutorRehearsalError(
            "executor value is not canonical JSON") from exc


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise NativeT102ExecutorRehearsalError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise NativeT102ExecutorRehearsalError(
            f"{label} must be a bounded identifier")
    return value


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NativeT102ExecutorRehearsalError(
            f"{label} must be positive nanoseconds")
    return value


class NativeT102ExecutionAuthorityRehearsalV1:
    """One claim-bound use; explicitly incapable of authorizing hardware."""

    def __init__(
        self, *, authority_id: str, approval_record_sha256: str,
        claim_sha256: str, frame_sha256: str, writer_instance_id: str,
        controller_session_id: str, issued_monotonic_ns: int,
        expires_monotonic_ns: int,
    ) -> None:
        self.authority_id = _identifier(authority_id, "authority_id")
        self.approval_record_sha256 = _digest(
            approval_record_sha256, "approval_record_sha256")
        self.claim_sha256 = _digest(claim_sha256, "claim_sha256")
        self.frame_sha256 = _digest(frame_sha256, "frame_sha256")
        self.writer_instance_id = _identifier(
            writer_instance_id, "writer_instance_id")
        self.controller_session_id = _identifier(
            controller_session_id, "controller_session_id")
        self.issued_monotonic_ns = _positive_ns(
            issued_monotonic_ns, "issued_monotonic_ns")
        self.expires_monotonic_ns = _positive_ns(
            expires_monotonic_ns, "expires_monotonic_ns")
        if self.expires_monotonic_ns <= self.issued_monotonic_ns:
            raise NativeT102ExecutorRehearsalError(
                "authority expiry must follow issuance")
        self._consumed = False
        self._lock = Lock()

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": AUTHORITY_SCHEMA,
            "scope": AUTHORITY_SCOPE,
            "authority_id": self.authority_id,
            "approval_record_sha256": self.approval_record_sha256,
            "claim_sha256": self.claim_sha256,
            "frame_sha256": self.frame_sha256,
            "writer_instance_id": self.writer_instance_id,
            "controller_session_id": self.controller_session_id,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "expires_monotonic_ns": self.expires_monotonic_ns,
            "maximum_uses": 1,
            "hardware_access_authorized": False,
            "physical_authority": False,
            "automatic_retry_allowed": False,
        }

    @property
    def authority_sha256(self) -> str:
        return _hash(self.unsigned_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "authority_sha256": self.authority_sha256}

    def consume(
        self, *, claim_sha256: str, frame: RuntimeCommandFrameV1,
        now_monotonic_ns: int,
    ) -> None:
        if not isinstance(frame, RuntimeCommandFrameV1):
            raise TypeError("frame must be RuntimeCommandFrameV1")
        now = _positive_ns(now_monotonic_ns, "now_monotonic_ns")
        with self._lock:
            if self._consumed:
                raise NativeT102ExecutorRehearsalError(
                    "execution authority was already consumed; no retry")
            if (
                _digest(claim_sha256, "claim_sha256") != self.claim_sha256
                or frame.frame_sha256 != self.frame_sha256
                or frame.writer_instance_id != self.writer_instance_id
                or frame.controller_session_id != self.controller_session_id
                or not self.issued_monotonic_ns <= now
                < self.expires_monotonic_ns
                or now >= frame.expires_monotonic_ns
            ):
                raise NativeT102ExecutorRehearsalError(
                    "authority binding or lifetime differs")
            self._consumed = True


class IncapableNativeT102TransportV1:
    """One-open, one-write byte recorder with no external I/O capability."""

    def __init__(
        self, *, pinned_endpoint_sha256: str,
        fault: IncapableNativeTransportFault = IncapableNativeTransportFault.NONE,
    ) -> None:
        self.pinned_endpoint_sha256 = _digest(
            pinned_endpoint_sha256, "pinned_endpoint_sha256")
        if not isinstance(fault, IncapableNativeTransportFault):
            raise TypeError("fault must be IncapableNativeTransportFault")
        self.fault = fault
        self.open_attempts = 0
        self.write_attempts = 0
        self.close_attempts = 0
        self.recorded_payload_sha256: str | None = None
        self.recorded_payload_bytes = 0
        self._opened = False

    def open_once(self) -> None:
        if self.open_attempts or self._opened:
            raise NativeT102ExecutorRehearsalError("transport open is single use")
        self.open_attempts = 1
        if self.fault is IncapableNativeTransportFault.OPEN_FAILURE:
            raise OSError("incapable transport open fault")
        self._opened = True

    def write_once(self, payload: bytes) -> int:
        if not self._opened or self.write_attempts:
            raise NativeT102ExecutorRehearsalError(
                "transport write requires one open and is single use")
        if not isinstance(payload, bytes) or not payload:
            raise NativeT102ExecutorRehearsalError(
                "transport payload must be nonempty bytes")
        self.write_attempts = 1
        self.recorded_payload_sha256 = hashlib.sha256(payload).hexdigest()
        self.recorded_payload_bytes = len(payload)
        if self.fault is IncapableNativeTransportFault.WRITE_EXCEPTION:
            raise OSError("incapable transport write fault")
        if self.fault is IncapableNativeTransportFault.ZERO_WRITE:
            return 0
        if self.fault is IncapableNativeTransportFault.PARTIAL_WRITE:
            return max(1, len(payload) - 1)
        if self.fault is IncapableNativeTransportFault.INVALID_COUNT:
            return True
        return len(payload)

    def close_once(self) -> None:
        if not self._opened or self.close_attempts:
            return
        self.close_attempts = 1
        self._opened = False
        if self.fault is IncapableNativeTransportFault.CLOSE_FAILURE:
            raise OSError("incapable transport close fault")


@dataclass(frozen=True, slots=True)
class NativeT102ExecutorRehearsalReceiptV1:
    status: str
    authority_sha256: str
    approval_record_sha256: str
    claim_sha256: str
    prepared_sha256: str
    frame_sha256: str
    wire_bytes_sha256: str
    pinned_endpoint_sha256: str
    correlation_id: str
    writer_instance_id: str
    controller_session_id: str
    requested_bytes: int
    confirmed_bytes: int
    open_attempts: int
    write_attempts: int
    close_attempts: int
    error_code: str | None

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": RECEIPT_SCHEMA,
            "status": self.status,
            "authority_sha256": self.authority_sha256,
            "approval_record_sha256": self.approval_record_sha256,
            "claim_sha256": self.claim_sha256,
            "prepared_sha256": self.prepared_sha256,
            "frame_sha256": self.frame_sha256,
            "wire_bytes_sha256": self.wire_bytes_sha256,
            "pinned_endpoint_sha256": self.pinned_endpoint_sha256,
            "correlation_id": self.correlation_id,
            "writer_instance_id": self.writer_instance_id,
            "controller_session_id": self.controller_session_id,
            "requested_bytes": self.requested_bytes,
            "confirmed_bytes": self.confirmed_bytes,
            "open_attempts": self.open_attempts,
            "write_attempts": self.write_attempts,
            "close_attempts": self.close_attempts,
            "error_code": self.error_code,
            "automatic_retry_allowed": False,
            "hardware_access": False,
            "physical_authority": False,
            "authentic_controller_receipt": False,
            "physical_movement_verified": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _hash(self.unsigned_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "receipt_sha256": self.receipt_sha256}


def issue_native_t102_execution_authority_rehearsal_v1(
    journal: DurableNativeT102HandoffV1, frame: RuntimeCommandFrameV1,
    admission: ReviewedMotionPermitAdmissionV1, *,
    adapter_candidate_sha256: str, approval_record_sha256: str,
    authority_id: str, issued_monotonic_ns: int, expires_monotonic_ns: int,
) -> NativeT102ExecutionAuthorityRehearsalV1:
    """Issue only a hardware-incapable claim-bound rehearsal authority."""

    if not isinstance(journal, DurableNativeT102HandoffV1):
        raise TypeError("journal must be DurableNativeT102HandoffV1")
    snapshot = journal.verify_claimed_inputs(
        frame, admission, adapter_candidate_sha256=adapter_candidate_sha256,
        now_monotonic_ns=issued_monotonic_ns,
    )
    assert snapshot.claim_sha256 is not None
    expires = _positive_ns(expires_monotonic_ns, "expires_monotonic_ns")
    if expires > frame.expires_monotonic_ns:
        raise NativeT102ExecutorRehearsalError(
            "authority cannot outlive the claimed frame")
    return NativeT102ExecutionAuthorityRehearsalV1(
        authority_id=authority_id,
        approval_record_sha256=approval_record_sha256,
        claim_sha256=snapshot.claim_sha256,
        frame_sha256=frame.frame_sha256,
        writer_instance_id=frame.writer_instance_id,
        controller_session_id=frame.controller_session_id,
        issued_monotonic_ns=issued_monotonic_ns,
        expires_monotonic_ns=expires,
    )


def execute_native_t102_rehearsal_v1(
    journal: DurableNativeT102HandoffV1, frame: RuntimeCommandFrameV1,
    admission: ReviewedMotionPermitAdmissionV1,
    authority: NativeT102ExecutionAuthorityRehearsalV1,
    transport: IncapableNativeT102TransportV1, *,
    adapter_candidate_sha256: str, now_monotonic_ns: int,
) -> NativeT102ExecutorRehearsalReceiptV1:
    """Consume once, attempt one incapable write, and account for the result."""

    if not isinstance(authority, NativeT102ExecutionAuthorityRehearsalV1):
        raise TypeError("authority must be NativeT102ExecutionAuthorityRehearsalV1")
    if type(transport) is not IncapableNativeT102TransportV1:
        raise TypeError("transport must be the incapable native T102 transport")
    try:
        snapshot = journal.verify_claimed_inputs(
            frame, admission, adapter_candidate_sha256=adapter_candidate_sha256,
            now_monotonic_ns=now_monotonic_ns,
        )
    except NativeT102HandoffJournalError as exc:
        raise NativeT102ExecutorRehearsalError(
            "claimed handoff verification failed") from exc
    assert snapshot.claim_sha256 is not None
    authority.consume(
        claim_sha256=snapshot.claim_sha256, frame=frame,
        now_monotonic_ns=now_monotonic_ns,
    )
    confirmed = 0
    error_code = None
    status = "INCAPABLE_BYTES_CONFIRMED_NOT_CONTROLLER_RECEIVED"
    try:
        transport.open_once()
        try:
            count = transport.write_once(frame.wire_bytes)
            if isinstance(count, bool) or not isinstance(count, int) \
                    or not 0 <= count <= len(frame.wire_bytes):
                error_code = "INVALID_WRITE_COUNT"
                status = "WRITE_UNCERTAIN_NO_RETRY"
            else:
                confirmed = count
                if count != len(frame.wire_bytes):
                    error_code = (
                        "ZERO_WRITE" if count == 0 else "PARTIAL_WRITE")
                    status = "WRITE_UNCERTAIN_NO_RETRY"
        except Exception:
            error_code = "WRITE_EXCEPTION"
            status = "WRITE_UNCERTAIN_NO_RETRY"
    except Exception:
        error_code = "OPEN_FAILURE"
        status = "NOT_OPENED_AUTHORITY_CONSUMED_NO_RETRY"
    finally:
        try:
            transport.close_once()
        except Exception:
            error_code = "CLOSE_FAILURE"
            status = "CLOSE_UNCERTAIN_NO_RETRY"
    return NativeT102ExecutorRehearsalReceiptV1(
        status=status,
        authority_sha256=authority.authority_sha256,
        approval_record_sha256=authority.approval_record_sha256,
        claim_sha256=snapshot.claim_sha256,
        prepared_sha256=snapshot.prepared_sha256,
        frame_sha256=frame.frame_sha256,
        wire_bytes_sha256=frame.wire_bytes_sha256,
        pinned_endpoint_sha256=transport.pinned_endpoint_sha256,
        correlation_id=frame.correlation_id,
        writer_instance_id=frame.writer_instance_id,
        controller_session_id=frame.controller_session_id,
        requested_bytes=len(frame.wire_bytes),
        confirmed_bytes=confirmed,
        open_attempts=transport.open_attempts,
        write_attempts=transport.write_attempts,
        close_attempts=transport.close_attempts,
        error_code=error_code,
    )


__all__ = [
    "AUTHORITY_SCHEMA", "AUTHORITY_SCOPE", "RECEIPT_SCHEMA",
    "IncapableNativeT102TransportV1", "IncapableNativeTransportFault",
    "NativeT102ExecutionAuthorityRehearsalV1",
    "NativeT102ExecutorRehearsalError",
    "NativeT102ExecutorRehearsalReceiptV1",
    "execute_native_t102_rehearsal_v1",
    "issue_native_t102_execution_authority_rehearsal_v1",
]
