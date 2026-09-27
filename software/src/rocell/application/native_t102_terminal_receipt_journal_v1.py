"""Durable terminal receipt journal for one claimed T=102 rehearsal.

The journal commits ``started.json`` before the incapable executor may open its
in-memory transport.  A restart that sees only that marker is permanently
retry-forbidden.  ``terminal.json`` then binds the exact byte-accounted ARM-051
receipt.  This module owns no serial or device API and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from typing import Any, Mapping

from .native_t102_executor_rehearsal_v1 import (
    AUTHORITY_SCOPE,
    IncapableNativeT102TransportV1,
    NativeT102ExecutionAuthorityRehearsalV1,
    NativeT102ExecutorRehearsalReceiptV1,
    execute_native_t102_rehearsal_v1,
)
from .native_t102_handoff_journal_v1 import DurableNativeT102HandoffV1
from .production_controller_runtime_contract_v1 import RuntimeCommandFrameV1
from .reviewed_motion_permit_bridge_v1 import ReviewedMotionPermitAdmissionV1


STARTED_SCHEMA = "rocell.native_t102_execution_started.v1"
TERMINAL_SCHEMA = "rocell.native_t102_execution_terminal.v1"
SNAPSHOT_SCHEMA = "rocell.native_t102_terminal_receipt_snapshot.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TERMINAL_STATUSES = {
    "INCAPABLE_BYTES_CONFIRMED_NOT_CONTROLLER_RECEIVED",
    "NOT_OPENED_AUTHORITY_CONSUMED_NO_RETRY",
    "WRITE_UNCERTAIN_NO_RETRY",
    "CLOSE_UNCERTAIN_NO_RETRY",
}


class NativeT102TerminalReceiptJournalError(ValueError):
    """The execution marker or terminal receipt is invalid or crossed."""


class NativeT102TerminalReceiptPhase(str, Enum):
    EXECUTION_STARTED = "EXECUTION_STARTED"
    TERMINAL_RECORDED = "TERMINAL_RECORDED"


class NativeT102TerminalRecoveryDisposition(str, Enum):
    RETRY_FORBIDDEN_EXECUTION_UNCERTAIN = (
        "RETRY_FORBIDDEN_EXECUTION_UNCERTAIN")
    TERMINAL_NO_REPLAY = "TERMINAL_NO_REPLAY"


def _canonical(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value, indent=2, sort_keys=True, ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeT102TerminalReceiptJournalError(
            "terminal receipt value is not canonical JSON") from exc


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise NativeT102TerminalReceiptJournalError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise NativeT102TerminalReceiptJournalError(
            f"{label} must be a bounded identifier")
    return value


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NativeT102TerminalReceiptJournalError(
            f"{label} must be positive nanoseconds")
    return value


def _nonnegative_int(value: object, label: str, maximum: int) -> int:
    if (
        isinstance(value, bool) or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise NativeT102TerminalReceiptJournalError(
            f"{label} must be an integer in 0..{maximum}")
    return value


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    payload = _canonical(value)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise NativeT102TerminalReceiptJournalError(
            f"immutable terminal receipt file already exists: {path.name}") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise NativeT102TerminalReceiptJournalError(
            f"terminal receipt file is unavailable: {path.name}")
    payload = path.read_bytes()
    if not payload or len(payload) > 128 * 1024:
        raise NativeT102TerminalReceiptJournalError(
            f"terminal receipt file size is invalid: {path.name}")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeT102TerminalReceiptJournalError(
            f"invalid JSON in {path.name}") from exc
    if not isinstance(value, dict) or _canonical(value) != payload:
        raise NativeT102TerminalReceiptJournalError(
            f"noncanonical terminal receipt file: {path.name}")
    return value


def _validate_started(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema", "status", "prepared_sha256", "claim_sha256",
        "authority_sha256", "approval_record_sha256", "frame_sha256",
        "wire_bytes_sha256", "pinned_endpoint_sha256", "correlation_id",
        "writer_instance_id", "controller_session_id", "started_monotonic_ns",
        "transport_open_count", "physical_command_writes",
        "automatic_retry_allowed", "hardware_access", "physical_authority",
        "recovery_disposition", "started_sha256",
    }
    copy = dict(value)
    if set(copy) != required:
        raise NativeT102TerminalReceiptJournalError(
            "execution-started fields are not exact")
    for field in (
        "prepared_sha256", "claim_sha256", "authority_sha256",
        "approval_record_sha256", "frame_sha256", "wire_bytes_sha256",
        "pinned_endpoint_sha256", "started_sha256",
    ):
        _digest(copy.get(field), field)
    for field in (
        "correlation_id", "writer_instance_id", "controller_session_id",
    ):
        _identifier(copy.get(field), field)
    _positive_ns(copy.get("started_monotonic_ns"), "started_monotonic_ns")
    if (
        copy["schema"] != STARTED_SCHEMA
        or copy["status"] != "EXECUTION_STARTED_BEFORE_TRANSPORT_OPEN"
        or copy["transport_open_count"] != 0
        or copy["physical_command_writes"] != 0
        or copy["automatic_retry_allowed"] is not False
        or copy["hardware_access"] is not False
        or copy["physical_authority"] is not False
        or copy["recovery_disposition"]
        != NativeT102TerminalRecoveryDisposition.RETRY_FORBIDDEN_EXECUTION_UNCERTAIN.value
        or copy["started_sha256"] != _hash({
            key: item for key, item in copy.items() if key != "started_sha256"})
    ):
        raise NativeT102TerminalReceiptJournalError(
            "execution-started content is invalid")
    return copy


def _validate_executor_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema", "status", "authority_sha256", "approval_record_sha256",
        "claim_sha256", "prepared_sha256", "frame_sha256",
        "wire_bytes_sha256", "pinned_endpoint_sha256", "correlation_id",
        "writer_instance_id", "controller_session_id", "requested_bytes",
        "confirmed_bytes", "open_attempts", "write_attempts", "close_attempts",
        "error_code", "automatic_retry_allowed", "hardware_access",
        "physical_authority", "authentic_controller_receipt",
        "physical_movement_verified", "receipt_sha256",
    }
    copy = dict(value)
    if set(copy) != required:
        raise NativeT102TerminalReceiptJournalError(
            "executor receipt fields are not exact")
    for field in (
        "authority_sha256", "approval_record_sha256", "claim_sha256",
        "prepared_sha256", "frame_sha256", "wire_bytes_sha256",
        "pinned_endpoint_sha256", "receipt_sha256",
    ):
        _digest(copy.get(field), field)
    for field in (
        "correlation_id", "writer_instance_id", "controller_session_id",
    ):
        _identifier(copy.get(field), field)
    requested = _nonnegative_int(
        copy.get("requested_bytes"), "requested_bytes", 4096)
    if requested == 0:
        raise NativeT102TerminalReceiptJournalError(
            "requested_bytes must be positive")
    _nonnegative_int(copy.get("confirmed_bytes"), "confirmed_bytes", requested)
    for field in ("open_attempts", "write_attempts", "close_attempts"):
        _nonnegative_int(copy.get(field), field, 1)
    status = copy.get("status")
    error = copy.get("error_code")
    confirmed = copy["confirmed_bytes"]
    lifecycle_valid = (
        status == "INCAPABLE_BYTES_CONFIRMED_NOT_CONTROLLER_RECEIVED"
        and error is None and confirmed == requested
        and (copy["open_attempts"], copy["write_attempts"],
             copy["close_attempts"]) == (1, 1, 1)
    ) or (
        status == "NOT_OPENED_AUTHORITY_CONSUMED_NO_RETRY"
        and error == "OPEN_FAILURE" and confirmed == 0
        and (copy["open_attempts"], copy["write_attempts"],
             copy["close_attempts"]) == (1, 0, 0)
    ) or (
        status == "WRITE_UNCERTAIN_NO_RETRY"
        and error in {
            "ZERO_WRITE", "PARTIAL_WRITE", "WRITE_EXCEPTION",
            "INVALID_WRITE_COUNT",
        }
        and (copy["open_attempts"], copy["write_attempts"],
             copy["close_attempts"]) == (1, 1, 1)
        and (
            (error == "PARTIAL_WRITE" and 0 < confirmed < requested)
            or (error != "PARTIAL_WRITE" and confirmed == 0)
        )
    ) or (
        status == "CLOSE_UNCERTAIN_NO_RETRY"
        and error == "CLOSE_FAILURE" and confirmed == requested
        and (copy["open_attempts"], copy["write_attempts"],
             copy["close_attempts"]) == (1, 1, 1)
    )
    if (
        copy["schema"] != "rocell.native_t102_executor_rehearsal_receipt.v1"
        or status not in _TERMINAL_STATUSES
        or (copy["error_code"] is not None
            and not isinstance(copy["error_code"], str))
        or not lifecycle_valid
        or copy["automatic_retry_allowed"] is not False
        or copy["hardware_access"] is not False
        or copy["physical_authority"] is not False
        or copy["authentic_controller_receipt"] is not False
        or copy["physical_movement_verified"] is not False
        or copy["receipt_sha256"] != _hash({
            key: item for key, item in copy.items() if key != "receipt_sha256"})
    ):
        raise NativeT102TerminalReceiptJournalError(
            "executor receipt content is invalid")
    return copy


def _validate_terminal(
    value: Mapping[str, Any], started: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "schema", "status", "started_sha256", "receipt_sha256",
        "completed_monotonic_ns", "executor_receipt", "recovery_disposition",
        "automatic_retry_allowed", "hardware_access", "physical_authority",
        "terminal_sha256",
    }
    copy = dict(value)
    if set(copy) != required:
        raise NativeT102TerminalReceiptJournalError(
            "terminal fields are not exact")
    _digest(copy.get("started_sha256"), "started_sha256")
    _digest(copy.get("receipt_sha256"), "receipt_sha256")
    _digest(copy.get("terminal_sha256"), "terminal_sha256")
    completed = _positive_ns(
        copy.get("completed_monotonic_ns"), "completed_monotonic_ns")
    receipt_raw = copy.get("executor_receipt")
    if not isinstance(receipt_raw, Mapping):
        raise NativeT102TerminalReceiptJournalError(
            "executor_receipt must be an object")
    receipt = _validate_executor_receipt(receipt_raw)
    bindings = {
        "prepared_sha256", "claim_sha256", "authority_sha256",
        "approval_record_sha256", "frame_sha256", "wire_bytes_sha256",
        "pinned_endpoint_sha256", "correlation_id", "writer_instance_id",
        "controller_session_id",
    }
    if (
        copy["schema"] != TERMINAL_SCHEMA
        or copy["status"] != "TERMINAL_RECEIPT_COMMITTED_NO_REPLAY"
        or copy["started_sha256"] != started["started_sha256"]
        or copy["receipt_sha256"] != receipt["receipt_sha256"]
        or any(receipt[field] != started[field] for field in bindings)
        or completed < started["started_monotonic_ns"]
        or copy["recovery_disposition"]
        != NativeT102TerminalRecoveryDisposition.TERMINAL_NO_REPLAY.value
        or copy["automatic_retry_allowed"] is not False
        or copy["hardware_access"] is not False
        or copy["physical_authority"] is not False
        or copy["terminal_sha256"] != _hash({
            key: item for key, item in copy.items() if key != "terminal_sha256"})
    ):
        raise NativeT102TerminalReceiptJournalError(
            "terminal receipt binding is invalid")
    return copy


@dataclass(frozen=True, slots=True)
class NativeT102TerminalReceiptSnapshotV1:
    phase: NativeT102TerminalReceiptPhase
    started_sha256: str
    claim_sha256: str
    authority_sha256: str
    frame_sha256: str
    terminal_sha256: str | None
    receipt_sha256: str | None

    @property
    def recovery_disposition(self) -> NativeT102TerminalRecoveryDisposition:
        if self.phase is NativeT102TerminalReceiptPhase.TERMINAL_RECORDED:
            return NativeT102TerminalRecoveryDisposition.TERMINAL_NO_REPLAY
        return (
            NativeT102TerminalRecoveryDisposition
            .RETRY_FORBIDDEN_EXECUTION_UNCERTAIN)

    def to_dict(self) -> dict[str, Any]:
        core = {
            "schema": SNAPSHOT_SCHEMA,
            "phase": self.phase.value,
            "started_sha256": self.started_sha256,
            "claim_sha256": self.claim_sha256,
            "authority_sha256": self.authority_sha256,
            "frame_sha256": self.frame_sha256,
            "terminal_sha256": self.terminal_sha256,
            "receipt_sha256": self.receipt_sha256,
            "recovery_disposition": self.recovery_disposition.value,
            "automatic_retry_allowed": False,
            "hardware_access": False,
            "physical_authority": False,
        }
        return {**core, "snapshot_sha256": _hash(core)}


def load_native_t102_terminal_receipt_v1(
    directory: Path,
) -> NativeT102TerminalReceiptSnapshotV1:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise NativeT102TerminalReceiptJournalError(
            "terminal receipt directory is unavailable")
    root = root.resolve()
    entries = {path.name for path in root.iterdir()}
    if entries not in ({"started.json"}, {"started.json", "terminal.json"}):
        raise NativeT102TerminalReceiptJournalError(
            "terminal receipt directory entries are not exact")
    started = _validate_started(_read(root / "started.json"))
    terminal = None
    if "terminal.json" in entries:
        terminal = _validate_terminal(_read(root / "terminal.json"), started)
    return NativeT102TerminalReceiptSnapshotV1(
        phase=(NativeT102TerminalReceiptPhase.TERMINAL_RECORDED
               if terminal else NativeT102TerminalReceiptPhase.EXECUTION_STARTED),
        started_sha256=started["started_sha256"],
        claim_sha256=started["claim_sha256"],
        authority_sha256=started["authority_sha256"],
        frame_sha256=started["frame_sha256"],
        terminal_sha256=(terminal["terminal_sha256"] if terminal else None),
        receipt_sha256=(terminal["receipt_sha256"] if terminal else None),
    )


@dataclass(frozen=True, slots=True)
class DurableNativeT102TerminalReceiptV1:
    directory: Path

    @classmethod
    def begin(
        cls, root: Path, handoff: DurableNativeT102HandoffV1,
        frame: RuntimeCommandFrameV1,
        admission: ReviewedMotionPermitAdmissionV1,
        authority: NativeT102ExecutionAuthorityRehearsalV1, *,
        adapter_candidate_sha256: str, pinned_endpoint_sha256: str,
        started_monotonic_ns: int,
    ) -> "DurableNativeT102TerminalReceiptV1":
        base = Path(root)
        if base.is_symlink() or not base.is_dir():
            raise NativeT102TerminalReceiptJournalError(
                "terminal receipt root is unavailable")
        base = base.resolve()
        if not isinstance(authority, NativeT102ExecutionAuthorityRehearsalV1):
            raise TypeError(
                "authority must be NativeT102ExecutionAuthorityRehearsalV1")
        now = _positive_ns(started_monotonic_ns, "started_monotonic_ns")
        handoff_snapshot = handoff.verify_claimed_inputs(
            frame, admission, adapter_candidate_sha256=adapter_candidate_sha256,
            now_monotonic_ns=now,
        )
        if handoff_snapshot.claim_sha256 is None:
            raise NativeT102TerminalReceiptJournalError(
                "claimed handoff has no claim identity")
        authority_document = authority.to_dict()
        if (
            authority_document["scope"] != AUTHORITY_SCOPE
            or authority.claim_sha256 != handoff_snapshot.claim_sha256
            or authority.frame_sha256 != frame.frame_sha256
            or authority.writer_instance_id != frame.writer_instance_id
            or authority.controller_session_id != frame.controller_session_id
            or not authority.issued_monotonic_ns <= now
            < authority.expires_monotonic_ns
            or now >= frame.expires_monotonic_ns
        ):
            raise NativeT102TerminalReceiptJournalError(
                "execution authority differs from the claimed handoff")
        endpoint = _digest(pinned_endpoint_sha256, "pinned_endpoint_sha256")
        core = {
            "schema": STARTED_SCHEMA,
            "status": "EXECUTION_STARTED_BEFORE_TRANSPORT_OPEN",
            "prepared_sha256": handoff_snapshot.prepared_sha256,
            "claim_sha256": handoff_snapshot.claim_sha256,
            "authority_sha256": authority.authority_sha256,
            "approval_record_sha256": authority.approval_record_sha256,
            "frame_sha256": frame.frame_sha256,
            "wire_bytes_sha256": frame.wire_bytes_sha256,
            "pinned_endpoint_sha256": endpoint,
            "correlation_id": frame.correlation_id,
            "writer_instance_id": frame.writer_instance_id,
            "controller_session_id": frame.controller_session_id,
            "started_monotonic_ns": now,
            "transport_open_count": 0,
            "physical_command_writes": 0,
            "automatic_retry_allowed": False,
            "hardware_access": False,
            "physical_authority": False,
            "recovery_disposition": (
                NativeT102TerminalRecoveryDisposition
                .RETRY_FORBIDDEN_EXECUTION_UNCERTAIN.value),
        }
        started = {**core, "started_sha256": _hash(core)}
        destination = base / f"native-t102-execution-{started['started_sha256'][:24]}"
        temporary = base / f".partial-{destination.name}-{secrets.token_hex(8)}"
        try:
            temporary.mkdir()
            _write_new(temporary / "started.json", started)
            try:
                os.rename(temporary, destination)
            except OSError as exc:
                if os.path.lexists(destination):
                    raise NativeT102TerminalReceiptJournalError(
                        "immutable execution journal already exists") from exc
                raise
            _fsync_directory(base)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        journal = cls(destination)
        load_native_t102_terminal_receipt_v1(journal.directory)
        return journal

    def snapshot(self) -> NativeT102TerminalReceiptSnapshotV1:
        return load_native_t102_terminal_receipt_v1(self.directory)

    def commit_terminal(
        self, receipt: NativeT102ExecutorRehearsalReceiptV1, *,
        completed_monotonic_ns: int,
    ) -> NativeT102TerminalReceiptSnapshotV1:
        before = self.snapshot()
        if before.phase is not NativeT102TerminalReceiptPhase.EXECUTION_STARTED:
            raise NativeT102TerminalReceiptJournalError(
                "execution journal already has a terminal receipt")
        if not isinstance(receipt, NativeT102ExecutorRehearsalReceiptV1):
            raise TypeError(
                "receipt must be NativeT102ExecutorRehearsalReceiptV1")
        started = _validate_started(_read(self.directory / "started.json"))
        receipt_document = _validate_executor_receipt(receipt.to_dict())
        completed = _positive_ns(
            completed_monotonic_ns, "completed_monotonic_ns")
        core = {
            "schema": TERMINAL_SCHEMA,
            "status": "TERMINAL_RECEIPT_COMMITTED_NO_REPLAY",
            "started_sha256": started["started_sha256"],
            "receipt_sha256": receipt_document["receipt_sha256"],
            "completed_monotonic_ns": completed,
            "executor_receipt": receipt_document,
            "recovery_disposition": (
                NativeT102TerminalRecoveryDisposition.TERMINAL_NO_REPLAY.value),
            "automatic_retry_allowed": False,
            "hardware_access": False,
            "physical_authority": False,
        }
        terminal = {**core, "terminal_sha256": _hash(core)}
        _validate_terminal(terminal, started)
        _write_new(self.directory / "terminal.json", terminal)
        _fsync_directory(self.directory)
        return self.snapshot()


def execute_durable_native_t102_rehearsal_v1(
    receipt_root: Path, handoff: DurableNativeT102HandoffV1,
    frame: RuntimeCommandFrameV1,
    admission: ReviewedMotionPermitAdmissionV1,
    authority: NativeT102ExecutionAuthorityRehearsalV1,
    transport: IncapableNativeT102TransportV1, *,
    adapter_candidate_sha256: str, started_monotonic_ns: int,
    completed_monotonic_ns: int,
) -> tuple[
    DurableNativeT102TerminalReceiptV1,
    NativeT102ExecutorRehearsalReceiptV1,
    NativeT102TerminalReceiptSnapshotV1,
]:
    """Persist pre-open ambiguity, execute once, then seal the exact receipt."""

    if type(transport) is not IncapableNativeT102TransportV1:
        raise TypeError("transport must be the incapable native T102 transport")
    journal = DurableNativeT102TerminalReceiptV1.begin(
        receipt_root, handoff, frame, admission, authority,
        adapter_candidate_sha256=adapter_candidate_sha256,
        pinned_endpoint_sha256=transport.pinned_endpoint_sha256,
        started_monotonic_ns=started_monotonic_ns,
    )
    receipt = execute_native_t102_rehearsal_v1(
        handoff, frame, admission, authority, transport,
        adapter_candidate_sha256=adapter_candidate_sha256,
        now_monotonic_ns=started_monotonic_ns,
    )
    snapshot = journal.commit_terminal(
        receipt, completed_monotonic_ns=completed_monotonic_ns)
    return journal, receipt, snapshot


__all__ = [
    "SNAPSHOT_SCHEMA", "STARTED_SCHEMA", "TERMINAL_SCHEMA",
    "DurableNativeT102TerminalReceiptV1",
    "NativeT102TerminalReceiptJournalError",
    "NativeT102TerminalReceiptPhase",
    "NativeT102TerminalReceiptSnapshotV1",
    "NativeT102TerminalRecoveryDisposition",
    "execute_durable_native_t102_rehearsal_v1",
    "load_native_t102_terminal_receipt_v1",
]
