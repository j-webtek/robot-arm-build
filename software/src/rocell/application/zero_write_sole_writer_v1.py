"""Durable-shape, zero-I/O rehearsal of the future sole controller writer.

This module never imports or accepts a transport.  It exercises ownership,
reservation, fault closure, restart reconciliation, and no-retry rules around a
hash-bound :class:`ZeroWriteWavesharePreviewReceiptV1`.  Injected partial-write
and timeout labels are counterfactual lifecycle events, not physical writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
import threading
from typing import Any, Mapping

from .zero_write_waveshare_adapter_v1 import ZeroWriteWavesharePreviewReceiptV1


JOURNAL_SCHEMA = "rocell.zero_write_sole_writer_journal.v1"
REPORT_SCHEMA = "rocell.zero_write_sole_writer_report.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ZeroWriteSoleWriterError(ValueError):
    """Writer ownership, journal integrity, or replay protection failed."""


class ZeroWriteWriterFault(str, Enum):
    NONE = "NONE"
    PARTIAL_WRITE = "PARTIAL_WRITE"
    ACK_TIMEOUT = "ACK_TIMEOUT"
    FEEDBACK_TIMEOUT = "FEEDBACK_TIMEOUT"
    TRANSPORT_CLOSE_UNCERTAIN = "TRANSPORT_CLOSE_UNCERTAIN"
    PROCESS_RESTART_AFTER_RESERVATION = "PROCESS_RESTART_AFTER_RESERVATION"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ZeroWriteSoleWriterError("value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ZeroWriteSoleWriterError(f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ZeroWriteSoleWriterError(f"{label} must be a bounded identifier")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ZeroWriteSoleWriterError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _receipt_identity(receipt: ZeroWriteWavesharePreviewReceiptV1) -> tuple[str, str]:
    if not isinstance(receipt, ZeroWriteWavesharePreviewReceiptV1):
        raise TypeError("receipt must be a ZeroWriteWavesharePreviewReceiptV1")
    return receipt.receipt_sha256, receipt.correlation_id


@dataclass(frozen=True, slots=True)
class ZeroWriteWriterEventV1:
    ordinal: int
    kind: str
    preview_receipt_sha256: str
    correlation_id: str
    writer_instance_id: str
    previous_event_sha256: str | None
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) \
                or self.ordinal < 0:
            raise ZeroWriteSoleWriterError("event ordinal must be nonnegative")
        if self.kind not in {"RESERVED", "CLOSED"}:
            raise ZeroWriteSoleWriterError("unsupported writer event kind")
        _digest(self.preview_receipt_sha256, "preview_receipt_sha256")
        _identifier(self.correlation_id, "correlation_id")
        _identifier(self.writer_instance_id, "writer_instance_id")
        if self.previous_event_sha256 is not None:
            _digest(self.previous_event_sha256, "previous_event_sha256")
        if not isinstance(self.details, Mapping):
            raise ZeroWriteSoleWriterError("event details must be an object")
        object.__setattr__(self, "details", dict(self.details))
        _canonical(self.details)

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "preview_receipt_sha256": self.preview_receipt_sha256,
            "correlation_id": self.correlation_id,
            "writer_instance_id": self.writer_instance_id,
            "previous_event_sha256": self.previous_event_sha256,
            "details": dict(self.details),
        }

    @property
    def event_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "event_sha256": self.event_sha256}

    @classmethod
    def from_mapping(cls, value: object) -> "ZeroWriteWriterEventV1":
        fields = {
            "ordinal", "kind", "preview_receipt_sha256", "correlation_id",
            "writer_instance_id", "previous_event_sha256", "details",
            "event_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ZeroWriteSoleWriterError("writer event fields are invalid")
        event = cls(**{key: value[key] for key in fields if key != "event_sha256"})
        if _digest(value["event_sha256"], "event_sha256") != event.event_sha256:
            raise ZeroWriteSoleWriterError("writer event hash is invalid")
        return event


class ZeroWriteSoleWriterJournalV1:
    """One correlation reservation with hash-chained terminal closure."""

    def __init__(
        self, *, preview_receipt_sha256: str, correlation_id: str,
        writer_instance_id: str,
    ) -> None:
        self.preview_receipt_sha256 = _digest(
            preview_receipt_sha256, "preview_receipt_sha256")
        self.correlation_id = _identifier(correlation_id, "correlation_id")
        self.writer_instance_id = _identifier(
            writer_instance_id, "writer_instance_id")
        self._events: list[ZeroWriteWriterEventV1] = []
        self._lock = threading.RLock()

    @property
    def events(self) -> tuple[ZeroWriteWriterEventV1, ...]:
        with self._lock:
            return tuple(self._events)

    @property
    def recovery_disposition(self) -> str:
        with self._lock:
            if not self._events:
                return "UNUSED"
            if self._events[-1].kind == "RESERVED":
                return "RECONCILIATION_REQUIRED_NO_RETRY"
            return "TERMINAL_NO_REPLAY"

    def _append(self, kind: str, details: Mapping[str, Any]) -> ZeroWriteWriterEventV1:
        previous = None if not self._events else self._events[-1].event_sha256
        event = ZeroWriteWriterEventV1(
            ordinal=len(self._events), kind=kind,
            preview_receipt_sha256=self.preview_receipt_sha256,
            correlation_id=self.correlation_id,
            writer_instance_id=self.writer_instance_id,
            previous_event_sha256=previous, details=details)
        self._events.append(event)
        return event

    def reserve(self, receipt: ZeroWriteWavesharePreviewReceiptV1) -> None:
        receipt_sha256, correlation_id = _receipt_identity(receipt)
        with self._lock:
            if self._events:
                raise ZeroWriteSoleWriterError(
                    "writer correlation was already reserved; no replay")
            if (
                receipt_sha256 != self.preview_receipt_sha256
                or correlation_id != self.correlation_id
            ):
                raise ZeroWriteSoleWriterError(
                    "journal binds a different preview receipt")
            self._append("RESERVED", {
                "command_count": len(receipt.commands),
                "transport_opened": False,
                "physical_write_count": 0,
            })

    def close(self, *, status: str, fault: ZeroWriteWriterFault) -> None:
        with self._lock:
            if len(self._events) != 1 or self._events[0].kind != "RESERVED":
                raise ZeroWriteSoleWriterError(
                    "writer journal is not an open reservation")
            self._append("CLOSED", {
                "status": _identifier(status, "status"),
                "fault": fault.value,
                "automatic_retry": False,
                "transport_opened": False,
                "physical_write_count": 0,
            })

    def unsigned_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": JOURNAL_SCHEMA,
                "preview_receipt_sha256": self.preview_receipt_sha256,
                "correlation_id": self.correlation_id,
                "writer_instance_id": self.writer_instance_id,
                "events": [event.to_dict() for event in self._events],
                "recovery_disposition": self.recovery_disposition,
                "transport_open_count": 0,
                "physical_write_count": 0,
                "hardware_access": False,
                "physical_authority": False,
            }

    @property
    def journal_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def export_bytes(self) -> bytes:
        return _canonical({
            **self.unsigned_dict(), "journal_sha256": self.journal_sha256})

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ZeroWriteSoleWriterJournalV1":
        if not isinstance(payload, bytes) or not payload:
            raise ZeroWriteSoleWriterError("journal payload must be nonempty bytes")
        try:
            document = json.loads(
                payload.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ZeroWriteSoleWriterError("journal payload is invalid JSON") from exc
        fields = {
            "schema", "preview_receipt_sha256", "correlation_id",
            "writer_instance_id", "events", "recovery_disposition",
            "transport_open_count", "physical_write_count", "hardware_access",
            "physical_authority", "journal_sha256",
        }
        if not isinstance(document, Mapping) or set(document) != fields:
            raise ZeroWriteSoleWriterError("journal fields are invalid")
        if (
            document["schema"] != JOURNAL_SCHEMA
            or document["transport_open_count"] != 0
            or document["physical_write_count"] != 0
            or document["hardware_access"] is not False
            or document["physical_authority"] is not False
        ):
            raise ZeroWriteSoleWriterError("journal violates zero authority")
        events_raw = document["events"]
        if not isinstance(events_raw, list) or len(events_raw) > 2:
            raise ZeroWriteSoleWriterError("journal event count is invalid")
        journal = cls(
            preview_receipt_sha256=document["preview_receipt_sha256"],
            correlation_id=document["correlation_id"],
            writer_instance_id=document["writer_instance_id"])
        events = [ZeroWriteWriterEventV1.from_mapping(item) for item in events_raw]
        for index, event in enumerate(events):
            expected_previous = None if index == 0 else events[index - 1].event_sha256
            if (
                event.ordinal != index
                or event.preview_receipt_sha256 != journal.preview_receipt_sha256
                or event.correlation_id != journal.correlation_id
                or event.writer_instance_id != journal.writer_instance_id
                or event.previous_event_sha256 != expected_previous
                or (index == 0 and event.kind != "RESERVED")
                or (index == 1 and event.kind != "CLOSED")
            ):
                raise ZeroWriteSoleWriterError("journal event chain is invalid")
        journal._events.extend(events)
        if document["recovery_disposition"] != journal.recovery_disposition:
            raise ZeroWriteSoleWriterError("journal recovery disposition is invalid")
        claimed = _digest(document["journal_sha256"], "journal_sha256")
        if claimed != journal.journal_sha256:
            raise ZeroWriteSoleWriterError("journal content hash is invalid")
        return journal


@dataclass(frozen=True, slots=True)
class ZeroWriteSoleWriterReportV1:
    preview_receipt_sha256: str
    correlation_id: str
    writer_instance_id: str
    fault: ZeroWriteWriterFault
    status: str
    recovery_disposition: str
    journal_sha256: str
    command_count: int
    schema: str = REPORT_SCHEMA

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "preview_receipt_sha256": self.preview_receipt_sha256,
            "correlation_id": self.correlation_id,
            "writer_instance_id": self.writer_instance_id,
            "fault": self.fault.value,
            "status": self.status,
            "recovery_disposition": self.recovery_disposition,
            "journal_sha256": self.journal_sha256,
            "command_count": self.command_count,
            "would_submit_command_count": self.command_count,
            "transport_open_count": 0,
            "physical_write_count": 0,
            "submitted_bytes": [],
            "acknowledgements": [],
            "feedback_samples": [],
            "timeout_events": ([] if self.fault not in {
                ZeroWriteWriterFault.ACK_TIMEOUT,
                ZeroWriteWriterFault.FEEDBACK_TIMEOUT,
            } else [self.fault.value]),
            "automatic_retry": False,
            "writer_closed": self.status != "RECONCILIATION_REQUIRED",
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "report_sha256": self.report_sha256}


def run_zero_write_sole_writer_rehearsal_v1(
    receipt: ZeroWriteWavesharePreviewReceiptV1,
    journal: ZeroWriteSoleWriterJournalV1, *,
    fault: ZeroWriteWriterFault = ZeroWriteWriterFault.NONE,
) -> ZeroWriteSoleWriterReportV1:
    """Reserve once and reach one terminal or restart-reconciliation state."""
    if not isinstance(journal, ZeroWriteSoleWriterJournalV1):
        raise TypeError("journal must be a ZeroWriteSoleWriterJournalV1")
    try:
        selected_fault = ZeroWriteWriterFault(fault)
    except ValueError as exc:
        raise ZeroWriteSoleWriterError("unsupported fault injection") from exc
    journal.reserve(receipt)
    if selected_fault is ZeroWriteWriterFault.PROCESS_RESTART_AFTER_RESERVATION:
        status = "RECONCILIATION_REQUIRED"
    elif selected_fault is ZeroWriteWriterFault.NONE:
        status = "ZERO_WRITE_REHEARSAL_COMPLETE"
        journal.close(status=status, fault=selected_fault)
    else:
        status = "AMBIGUOUS_NO_RETRY"
        journal.close(status=status, fault=selected_fault)
    return ZeroWriteSoleWriterReportV1(
        preview_receipt_sha256=receipt.receipt_sha256,
        correlation_id=receipt.correlation_id,
        writer_instance_id=journal.writer_instance_id,
        fault=selected_fault, status=status,
        recovery_disposition=journal.recovery_disposition,
        journal_sha256=journal.journal_sha256,
        command_count=len(receipt.commands),
    )


__all__ = [
    "JOURNAL_SCHEMA", "REPORT_SCHEMA", "ZeroWriteSoleWriterError",
    "ZeroWriteSoleWriterJournalV1", "ZeroWriteSoleWriterReportV1",
    "ZeroWriteWriterEventV1", "ZeroWriteWriterFault",
    "run_zero_write_sole_writer_rehearsal_v1",
]
