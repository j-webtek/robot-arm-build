"""Durable, append-only lifecycle journal for one admitted model batch.

The journal is deliberately hardware-neutral.  Its dispatch-boundary event must
be committed before a future executor performs I/O.  Reopening a journal whose
tail is that boundary yields a retry-forbidden uncertain disposition.
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

from rocell.models import ModelMotionBatch

from .model_motion_sequence_coordinator import VerifiedActionResult


HEADER_SCHEMA = "rocell.model_motion_sequence_journal_header.v1"
EVENT_SCHEMA = "rocell.model_motion_sequence_journal_event.v1"
HEAD_SCHEMA = "rocell.model_motion_sequence_journal_head.v1"
SNAPSHOT_SCHEMA = "rocell.model_motion_sequence_journal_snapshot.v1"
MAX_EVENTS = 256
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENT_NAME = re.compile(r"^event-([0-9]{6})\.json$")


class ModelMotionSequenceJournalError(ValueError):
    """The persistent sequence history is malformed, unsafe, or inconsistent."""


class SequenceJournalPhase(str, Enum):
    SEQUENCE_CREATED = "SEQUENCE_CREATED"
    ACTION_READY = "ACTION_READY"
    DISPATCH_BOUNDARY_COMMITTED = "DISPATCH_BOUNDARY_COMMITTED"
    ACTION_VERIFIED = "ACTION_VERIFIED"
    BLOCKED = "BLOCKED"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"
    COMPLETED = "COMPLETED"


class SequenceRecoveryDisposition(str, Enum):
    RESUME_WITH_FRESH_STATE = "RESUME_WITH_FRESH_STATE"
    REEVALUATE_READY_ACTION_FROM_FRESH_STATE = (
        "REEVALUATE_READY_ACTION_FROM_FRESH_STATE"
    )
    RETRY_FORBIDDEN_OUTCOME_UNCERTAIN = "RETRY_FORBIDDEN_OUTCOME_UNCERTAIN"
    COMPLETE_NO_ACTION = "COMPLETE_NO_ACTION"
    TERMINAL_NO_ACTION = "TERMINAL_NO_ACTION"


def _canonical(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ModelMotionSequenceJournalError("journal value is not canonical JSON") from exc


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ModelMotionSequenceJournalError(f"{label} must be a SHA-256 digest")
    return value


def _positive(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ModelMotionSequenceJournalError(f"{label} must be a positive integer")
    return value


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ModelMotionSequenceJournalError(f"journal file is unavailable: {path.name}")
    payload = path.read_bytes()
    if len(payload) > 256 * 1024:
        raise ModelMotionSequenceJournalError(f"journal file is oversized: {path.name}")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelMotionSequenceJournalError(f"invalid JSON in {path.name}") from exc
    if not isinstance(value, dict) or _canonical(value) != payload:
        raise ModelMotionSequenceJournalError(f"noncanonical journal file: {path.name}")
    return value


def _write_new(path: Path, value: object) -> None:
    payload = _canonical(value)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _replace(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        _write_new(temporary, value)
        os.replace(temporary, path)
        # Windows does not permit opening a directory with ``os.open``. The
        # replaced file itself was flushed before publication; POSIX also gets
        # the directory-entry durability barrier.
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


@dataclass(frozen=True, slots=True)
class SequenceJournalEvent:
    sequence: int
    phase: SequenceJournalPhase
    action_index: int
    previous_event_sha256: str
    event_time_ns: int
    evidence_sha256: str
    event_sha256: str

    def core(self) -> dict[str, object]:
        return {
            "schema": EVENT_SCHEMA,
            "sequence": self.sequence,
            "phase": self.phase.value,
            "action_index": self.action_index,
            "previous_event_sha256": self.previous_event_sha256,
            "event_time_ns": self.event_time_ns,
            "evidence_sha256": self.evidence_sha256,
            "hardware_access": False,
            "hardware_commands_generated": 0,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.core(), "event_sha256": self.event_sha256}

    @classmethod
    def build(
        cls, *, sequence: int, phase: SequenceJournalPhase, action_index: int,
        previous_event_sha256: str, event_time_ns: int, evidence_sha256: str
    ) -> "SequenceJournalEvent":
        event = cls(
            sequence=sequence,
            phase=phase,
            action_index=action_index,
            previous_event_sha256=_digest(previous_event_sha256, "previous event"),
            event_time_ns=_positive(event_time_ns, "event_time_ns"),
            evidence_sha256=_digest(evidence_sha256, "evidence_sha256"),
            event_sha256="0" * 64,
        )
        return cls(
            sequence=event.sequence,
            phase=event.phase,
            action_index=event.action_index,
            previous_event_sha256=event.previous_event_sha256,
            event_time_ns=event.event_time_ns,
            evidence_sha256=event.evidence_sha256,
            event_sha256=_hash(event.core()),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SequenceJournalEvent":
        required = {
            "schema", "sequence", "phase", "action_index",
            "previous_event_sha256", "event_time_ns", "evidence_sha256",
            "hardware_access", "hardware_commands_generated", "event_sha256",
        }
        if set(value) != required or value.get("schema") != EVENT_SCHEMA:
            raise ModelMotionSequenceJournalError("journal event fields are invalid")
        if value["hardware_access"] is not False or value["hardware_commands_generated"] != 0:
            raise ModelMotionSequenceJournalError("journal event violates zero authority")
        try:
            phase = SequenceJournalPhase(value["phase"])
        except (TypeError, ValueError) as exc:
            raise ModelMotionSequenceJournalError("journal event phase is invalid") from exc
        sequence = value["sequence"]
        action_index = value["action_index"]
        if (
            isinstance(sequence, bool) or not isinstance(sequence, int)
            or not 0 <= sequence < MAX_EVENTS
            or isinstance(action_index, bool) or not isinstance(action_index, int)
            or action_index < 0
        ):
            raise ModelMotionSequenceJournalError("journal event ordinal is invalid")
        event = cls(
            sequence=sequence,
            phase=phase,
            action_index=action_index,
            previous_event_sha256=_digest(value["previous_event_sha256"], "previous event"),
            event_time_ns=_positive(value["event_time_ns"], "event_time_ns"),
            evidence_sha256=_digest(value["evidence_sha256"], "evidence_sha256"),
            event_sha256=_digest(value["event_sha256"], "event_sha256"),
        )
        if event.event_sha256 != _hash(event.core()):
            raise ModelMotionSequenceJournalError("event content hash is invalid")
        return event


def _allowed(previous: SequenceJournalEvent, current: SequenceJournalEvent, count: int) -> bool:
    if current.event_time_ns <= previous.event_time_ns:
        return False
    if previous.phase is SequenceJournalPhase.SEQUENCE_CREATED:
        return current.action_index == 0 and current.phase in {
            SequenceJournalPhase.ACTION_READY, SequenceJournalPhase.BLOCKED
        }
    if previous.phase is SequenceJournalPhase.ACTION_READY:
        return current.action_index == previous.action_index and current.phase in {
            SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED,
            SequenceJournalPhase.BLOCKED,
        }
    if previous.phase is SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED:
        return current.action_index == previous.action_index and current.phase in {
            SequenceJournalPhase.ACTION_VERIFIED,
            SequenceJournalPhase.OUTCOME_UNCERTAIN,
        }
    if previous.phase is SequenceJournalPhase.ACTION_VERIFIED:
        if previous.action_index == count - 1:
            return (
                current.action_index == previous.action_index
                and current.phase is SequenceJournalPhase.COMPLETED
            )
        return current.action_index == previous.action_index + 1 and current.phase in {
            SequenceJournalPhase.ACTION_READY, SequenceJournalPhase.BLOCKED
        }
    return False


@dataclass(frozen=True, slots=True)
class SequenceJournalSnapshot:
    directory: Path
    batch_sha256: str
    ingress_sha256: str
    action_count: int
    events: tuple[SequenceJournalEvent, ...]
    head_sha256: str

    @property
    def phase(self) -> SequenceJournalPhase:
        return self.events[-1].phase

    @property
    def recovery_disposition(self) -> SequenceRecoveryDisposition:
        if self.phase is SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED:
            return SequenceRecoveryDisposition.RETRY_FORBIDDEN_OUTCOME_UNCERTAIN
        if self.phase is SequenceJournalPhase.ACTION_READY:
            return SequenceRecoveryDisposition.REEVALUATE_READY_ACTION_FROM_FRESH_STATE
        if self.phase in {
            SequenceJournalPhase.SEQUENCE_CREATED,
            SequenceJournalPhase.ACTION_VERIFIED,
        }:
            return SequenceRecoveryDisposition.RESUME_WITH_FRESH_STATE
        if self.phase is SequenceJournalPhase.COMPLETED:
            return SequenceRecoveryDisposition.COMPLETE_NO_ACTION
        return SequenceRecoveryDisposition.TERMINAL_NO_ACTION

    def to_dict(self) -> dict[str, object]:
        core = {
            "schema": SNAPSHOT_SCHEMA,
            "batch_sha256": self.batch_sha256,
            "ingress_sha256": self.ingress_sha256,
            "action_count": self.action_count,
            "phase": self.phase.value,
            "current_action_index": self.events[-1].action_index,
            "event_count": len(self.events),
            "event_sha256": [item.event_sha256 for item in self.events],
            "head_sha256": self.head_sha256,
            "recovery_disposition": self.recovery_disposition.value,
            "automatic_retry_allowed": False,
            "hardware_access": False,
            "hardware_commands_generated": 0,
        }
        return {**core, "snapshot_sha256": _hash(core)}


def load_model_motion_sequence_journal(directory: Path) -> SequenceJournalSnapshot:
    root = Path(directory).resolve()
    if root.is_symlink() or not root.is_dir():
        raise ModelMotionSequenceJournalError("sequence journal directory is unavailable")
    entries = list(root.iterdir())
    event_paths = []
    for path in entries:
        match = _EVENT_NAME.fullmatch(path.name)
        if match:
            event_paths.append((int(match.group(1)), path))
        elif path.name not in {"header.json", "head.json"}:
            raise ModelMotionSequenceJournalError(f"unexpected journal entry {path.name!r}")
    header = _read(root / "header.json")
    required_header = {
        "schema", "batch_sha256", "ingress_sha256", "action_count",
        "created_at_ns", "header_sha256", "hardware_access",
        "hardware_commands_generated",
    }
    if set(header) != required_header or header.get("schema") != HEADER_SCHEMA:
        raise ModelMotionSequenceJournalError("sequence journal header is invalid")
    if header["hardware_access"] is not False or header["hardware_commands_generated"] != 0:
        raise ModelMotionSequenceJournalError("sequence journal violates zero authority")
    header_hash = _digest(header["header_sha256"], "header_sha256")
    if header_hash != _hash({k: v for k, v in header.items() if k != "header_sha256"}):
        raise ModelMotionSequenceJournalError("header content hash is invalid")
    batch_sha256 = _digest(header["batch_sha256"], "batch_sha256")
    ingress_sha256 = _digest(header["ingress_sha256"], "ingress_sha256")
    _positive(header["created_at_ns"], "created_at_ns")
    count = _positive(header["action_count"], "action_count")
    if count > 64:
        raise ModelMotionSequenceJournalError("action_count exceeds the batch limit")
    event_paths.sort()
    if [item[0] for item in event_paths] != list(range(len(event_paths))):
        raise ModelMotionSequenceJournalError("event sequence is not contiguous")
    events = tuple(SequenceJournalEvent.from_dict(_read(path)) for _, path in event_paths)
    if not events or len(events) > MAX_EVENTS:
        raise ModelMotionSequenceJournalError("event chain size is invalid")
    if (
        events[0].phase is not SequenceJournalPhase.SEQUENCE_CREATED
        or events[0].action_index != 0
        or events[0].evidence_sha256 != ingress_sha256
        or events[0].previous_event_sha256 != "0" * 64
    ):
        raise ModelMotionSequenceJournalError("initial event is invalid")
    for index, event in enumerate(events):
        if event.sequence != index:
            raise ModelMotionSequenceJournalError("event ordinal differs from filename")
        if index and (
            event.previous_event_sha256 != events[index - 1].event_sha256
            or not _allowed(events[index - 1], event, count)
        ):
            raise ModelMotionSequenceJournalError("event transition is invalid")
    head = _read(root / "head.json")
    head_core = {
        "schema": HEAD_SCHEMA,
        "header_sha256": header_hash,
        "event_count": len(events),
        "tail_event_sha256": events[-1].event_sha256,
        "tail_phase": events[-1].phase.value,
        "tail_action_index": events[-1].action_index,
    }
    if set(head) != {*head_core, "head_sha256"} or any(
        head.get(key) != value for key, value in head_core.items()
    ):
        raise ModelMotionSequenceJournalError("journal head differs from event chain")
    head_sha256 = _digest(head["head_sha256"], "head_sha256")
    if head_sha256 != _hash(head_core):
        raise ModelMotionSequenceJournalError("journal head hash is invalid")
    return SequenceJournalSnapshot(
        root, batch_sha256, ingress_sha256, count, events, head_sha256
    )


@dataclass(frozen=True, slots=True)
class DurableModelMotionSequenceJournal:
    directory: Path

    @classmethod
    def create(
        cls, root: Path, batch: ModelMotionBatch, ingress_report: Mapping[str, Any],
        *, created_at_ns: int
    ) -> "DurableModelMotionSequenceJournal":
        base = Path(root).resolve()
        if base.is_symlink() or not base.is_dir():
            raise ModelMotionSequenceJournalError("journal root is unavailable")
        if ingress_report.get("batch_sha256") != batch.batch_sha256:
            raise ModelMotionSequenceJournalError("ingress binds a different batch")
        ingress_sha256 = _digest(ingress_report.get("ingress_sha256"), "ingress_sha256")
        ingress_core = {
            key: value for key, value in ingress_report.items() if key != "ingress_sha256"
        }
        if ingress_sha256 != _hash(ingress_core):
            raise ModelMotionSequenceJournalError("ingress content hash is invalid")
        created = _positive(created_at_ns, "created_at_ns")
        destination = base / f"model-sequence-{batch.batch_sha256[:24]}"
        if os.path.lexists(destination):
            raise ModelMotionSequenceJournalError("immutable sequence journal already exists")
        temporary = base / f".partial-{destination.name}-{secrets.token_hex(8)}"
        header_core = {
            "schema": HEADER_SCHEMA,
            "batch_sha256": batch.batch_sha256,
            "ingress_sha256": ingress_sha256,
            "action_count": len(batch.proposals),
            "created_at_ns": created,
            "hardware_access": False,
            "hardware_commands_generated": 0,
        }
        header = {**header_core, "header_sha256": _hash(header_core)}
        event = SequenceJournalEvent.build(
            sequence=0, phase=SequenceJournalPhase.SEQUENCE_CREATED,
            action_index=0, previous_event_sha256="0" * 64,
            event_time_ns=created, evidence_sha256=ingress_sha256,
        )
        head_core = {
            "schema": HEAD_SCHEMA, "header_sha256": header["header_sha256"],
            "event_count": 1, "tail_event_sha256": event.event_sha256,
            "tail_phase": event.phase.value, "tail_action_index": 0,
        }
        try:
            temporary.mkdir()
            _write_new(temporary / "header.json", header)
            _write_new(temporary / "event-000000.json", event.to_dict())
            _write_new(temporary / "head.json", {**head_core, "head_sha256": _hash(head_core)})
            temporary.rename(destination)
        except Exception:
            if temporary.exists() and temporary.is_dir():
                shutil.rmtree(temporary)
            raise
        journal = cls(destination)
        journal.snapshot()
        return journal

    @classmethod
    def open(cls, directory: Path) -> "DurableModelMotionSequenceJournal":
        journal = cls(Path(directory).resolve())
        journal.snapshot()
        return journal

    def snapshot(self) -> SequenceJournalSnapshot:
        return load_model_motion_sequence_journal(self.directory)

    def append(
        self, phase: SequenceJournalPhase, *, action_index: int,
        event_time_ns: int, evidence_sha256: str
    ) -> SequenceJournalSnapshot:
        current = self.snapshot()
        event = SequenceJournalEvent.build(
            sequence=len(current.events), phase=phase, action_index=action_index,
            previous_event_sha256=current.events[-1].event_sha256,
            event_time_ns=event_time_ns, evidence_sha256=evidence_sha256,
        )
        if not _allowed(current.events[-1], event, current.action_count):
            raise ModelMotionSequenceJournalError("requested journal transition is invalid")
        if phase is SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED and any(
            prior.phase is SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED
            and prior.evidence_sha256 == event.evidence_sha256
            for prior in current.events
        ):
            raise ModelMotionSequenceJournalError(
                "execution request evidence cannot be reused"
            )
        if len(current.events) >= MAX_EVENTS:
            raise ModelMotionSequenceJournalError("journal event limit reached")
        _write_new(self.directory / f"event-{event.sequence:06d}.json", event.to_dict())
        header = _read(self.directory / "header.json")
        head_core = {
            "schema": HEAD_SCHEMA, "header_sha256": header["header_sha256"],
            "event_count": event.sequence + 1,
            "tail_event_sha256": event.event_sha256,
            "tail_phase": event.phase.value,
            "tail_action_index": event.action_index,
        }
        _replace(self.directory / "head.json", {**head_core, "head_sha256": _hash(head_core)})
        return self.snapshot()

    def commit_action_ready(
        self, *, action_index: int, event_time_ns: int,
        planner_gate_sha256: str, coordinator_snapshot_sha256: str
    ) -> SequenceJournalSnapshot:
        evidence = _hash({
            "planner_gate_sha256": _digest(planner_gate_sha256, "planner_gate_sha256"),
            "coordinator_snapshot_sha256": _digest(
                coordinator_snapshot_sha256, "coordinator_snapshot_sha256"
            ),
        })
        return self.append(
            SequenceJournalPhase.ACTION_READY, action_index=action_index,
            event_time_ns=event_time_ns, evidence_sha256=evidence,
        )

    def commit_dispatch_boundary(
        self, *, action_index: int, event_time_ns: int,
        execution_request_sha256: str
    ) -> SequenceJournalSnapshot:
        return self.append(
            SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED,
            action_index=action_index, event_time_ns=event_time_ns,
            evidence_sha256=_digest(execution_request_sha256, "execution request"),
        )

    def record_verified_result(
        self, result: VerifiedActionResult, *, event_time_ns: int
    ) -> SequenceJournalSnapshot:
        current = self.snapshot()
        if result.batch_sha256 != current.batch_sha256:
            raise ModelMotionSequenceJournalError("result binds a different batch")
        return self.append(
            SequenceJournalPhase.ACTION_VERIFIED,
            action_index=result.action_index, event_time_ns=event_time_ns,
            evidence_sha256=_hash(result.to_dict()),
        )

    def mark_outcome_uncertain(
        self, *, action_index: int, event_time_ns: int,
        uncertainty_evidence_sha256: str
    ) -> SequenceJournalSnapshot:
        return self.append(
            SequenceJournalPhase.OUTCOME_UNCERTAIN,
            action_index=action_index, event_time_ns=event_time_ns,
            evidence_sha256=_digest(
                uncertainty_evidence_sha256, "uncertainty evidence"
            ),
        )

    def block(
        self, *, action_index: int, event_time_ns: int,
        blocker_evidence_sha256: str
    ) -> SequenceJournalSnapshot:
        return self.append(
            SequenceJournalPhase.BLOCKED,
            action_index=action_index, event_time_ns=event_time_ns,
            evidence_sha256=_digest(blocker_evidence_sha256, "blocker evidence"),
        )

    def complete(
        self, *, action_index: int, event_time_ns: int,
        completion_evidence_sha256: str
    ) -> SequenceJournalSnapshot:
        return self.append(
            SequenceJournalPhase.COMPLETED,
            action_index=action_index, event_time_ns=event_time_ns,
            evidence_sha256=_digest(
                completion_evidence_sha256, "completion evidence"
            ),
        )


__all__ = [
    "DurableModelMotionSequenceJournal", "ModelMotionSequenceJournalError",
    "SequenceJournalEvent", "SequenceJournalPhase", "SequenceJournalSnapshot",
    "SequenceRecoveryDisposition", "load_model_motion_sequence_journal",
]
