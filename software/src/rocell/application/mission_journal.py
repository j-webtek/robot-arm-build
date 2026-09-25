"""Crash-safe, zero-authority journaling for one planned contact occurrence.

The physical runtime does not exist yet, but its most important restart rule can
be designed and tested now: once a contact command *may* have been submitted,
software must never infer that it is safe to repeat it.  This module therefore
persists a conservative state transition before the virtual contact boundary.

The journal is deliberately a simulation/replay schema.  It cannot be changed
into physical evidence by toggling a flag.  A future physical executor will use
a separately reviewed schema while preserving these transition semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
from typing import Any, Iterable, Mapping


ACTION_OCCURRENCE_SCHEMA = "rocell.action_occurrence.v1"
MISSION_JOURNAL_HEADER_SCHEMA = "rocell.zero_authority_mission_journal_header.v1"
MISSION_JOURNAL_EVENT_SCHEMA = "rocell.zero_authority_mission_journal_event.v1"
MISSION_JOURNAL_HIGH_WATER_SCHEMA = (
    "rocell.zero_authority_mission_journal_high_water.v1"
)
MISSION_JOURNAL_SNAPSHOT_SCHEMA = "rocell.zero_authority_mission_journal_snapshot.v1"

MAX_ACTION_DOCUMENT_BYTES = 256 * 1024
MAX_JOURNAL_FILE_BYTES = 64 * 1024
MAX_JOURNAL_EVENTS = 32

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DETAIL_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_OCCURRENCE_ID = re.compile(r"^occ-[0-9a-f]{32}$")
_JOURNAL_ID = re.compile(r"^journal-[0-9a-f]{24}$")
_EVENT_FILENAME = re.compile(r"^event-([0-9]{6})\.json$")
_HIGH_WATER_FILENAME = "high-water.json"
_ZERO_DIGEST = "0" * 64


class MissionJournalError(ValueError):
    """A journal is unsafe, malformed, incomplete, or transition-invalid."""


class ActionJournalState(str, Enum):
    """Conservative state of one action occurrence.

    ``NOT_STARTED`` is a planning state only and is never persisted.  Creating
    a journal atomically commits ``INTENT_COMMITTED``.
    """

    NOT_STARTED = "NOT_STARTED"
    INTENT_COMMITTED = "INTENT_COMMITTED"
    PRE_CONTACT = "PRE_CONTACT"
    CONTACT_MAY_HAVE_OCCURRED = "CONTACT_MAY_HAVE_OCCURRED"
    OUTCOME_CONFIRMED = "OUTCOME_CONFIRMED"
    RETRACTED = "RETRACTED"
    PARKED = "PARKED"
    FAULTED = "FAULTED"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"


class JournalRecoveryDisposition(str, Enum):
    """Only the bounded recovery class; never an instruction to move hardware."""

    PRE_CONTACT_WORK_MAY_RESUME = "PRE_CONTACT_WORK_MAY_RESUME"
    CONTACT_RETRY_FORBIDDEN_OUTCOME_UNCERTAIN = (
        "CONTACT_RETRY_FORBIDDEN_OUTCOME_UNCERTAIN"
    )
    RETRACT_ONLY_AFTER_INDEPENDENT_REVIEW = "RETRACT_ONLY_AFTER_INDEPENDENT_REVIEW"
    PARK_ONLY_AFTER_INDEPENDENT_REVIEW = "PARK_ONLY_AFTER_INDEPENDENT_REVIEW"
    COMPLETE_NO_ACTION = "COMPLETE_NO_ACTION"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


_ALLOWED_TRANSITIONS: Mapping[ActionJournalState, frozenset[ActionJournalState]] = {
    ActionJournalState.INTENT_COMMITTED: frozenset(
        {ActionJournalState.PRE_CONTACT, ActionJournalState.FAULTED}
    ),
    ActionJournalState.PRE_CONTACT: frozenset(
        {
            ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            ActionJournalState.FAULTED,
        }
    ),
    # A generic fault is intentionally not allowed after this boundary.  If an
    # outcome is not independently proven, the only truthful state is uncertain.
    ActionJournalState.CONTACT_MAY_HAVE_OCCURRED: frozenset(
        {
            ActionJournalState.OUTCOME_CONFIRMED,
            ActionJournalState.OUTCOME_UNCERTAIN,
        }
    ),
    ActionJournalState.OUTCOME_CONFIRMED: frozenset(
        {ActionJournalState.RETRACTED, ActionJournalState.FAULTED}
    ),
    ActionJournalState.RETRACTED: frozenset(
        {ActionJournalState.PARKED, ActionJournalState.FAULTED}
    ),
    ActionJournalState.PARKED: frozenset(),
    ActionJournalState.FAULTED: frozenset(),
    ActionJournalState.OUTCOME_UNCERTAIN: frozenset(),
    ActionJournalState.NOT_STARTED: frozenset(),
}

_EVIDENCE_REQUIRED_STATES = frozenset(
    {
        ActionJournalState.INTENT_COMMITTED,
        ActionJournalState.PRE_CONTACT,
        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
        ActionJournalState.OUTCOME_CONFIRMED,
        ActionJournalState.RETRACTED,
        ActionJournalState.PARKED,
    }
)

_FIXED_DETAIL_CODES: Mapping[ActionJournalState, str] = {
    ActionJournalState.INTENT_COMMITTED: "ACTION_INTENT_COMMITTED",
    ActionJournalState.PRE_CONTACT: "PRE_CONTACT_EVIDENCE_COMMITTED",
    ActionJournalState.CONTACT_MAY_HAVE_OCCURRED: (
        "CONTACT_BOUNDARY_COMMITTED_BEFORE_SUBMISSION"
    ),
    ActionJournalState.OUTCOME_CONFIRMED: "INDEPENDENT_OUTCOME_CONFIRMED",
    ActionJournalState.RETRACTED: "RETRACTION_CONFIRMED",
    ActionJournalState.PARKED: "PARK_CONFIRMED",
}


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MissionJournalError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise MissionJournalError(f"nonfinite JSON number {value!r}")
    raise MissionJournalError("journal JSON must not contain floating-point numbers")


def _reject_constant(value: str) -> None:
    raise MissionJournalError(f"nonfinite JSON constant {value!r}")


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionJournalError(f"value is not canonical JSON: {exc}") from exc


def _compact_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionJournalError(f"action is not canonical JSON: {exc}") from exc
    if len(payload) > MAX_ACTION_DOCUMENT_BYTES:
        raise MissionJournalError("canonical action document exceeds the size limit")
    return payload


def _stable_hash(value: object) -> str:
    return hashlib.sha256(_compact_bytes(value)).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise MissionJournalError(f"{label} must be lowercase SHA-256")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise MissionJournalError(f"{label} must be a bounded identifier")
    return value


def _detail_code(value: object) -> str:
    if not isinstance(value, str) or _DETAIL_CODE.fullmatch(value) is None:
        raise MissionJournalError("detail_code must be a bounded uppercase code")
    return value


def _state_detail_code(state: ActionJournalState, value: object) -> str:
    """Validate the semantic code for a state with a fixed journal meaning."""

    detail = _detail_code(value)
    expected = _FIXED_DETAIL_CODES.get(state)
    if expected is not None and detail != expected:
        raise MissionJournalError(
            f"{state.value} requires detail_code {expected!r}"
        )
    if expected is None and detail in _FIXED_DETAIL_CODES.values():
        raise MissionJournalError(
            f"detail_code {detail!r} is reserved for its fixed transition state"
        )
    return detail


def _bounded_integer(value: object, label: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise MissionJournalError(f"{label} must be a bounded nonnegative integer")
    return value


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise MissionJournalError(
            f"{label} fields differ: missing={missing}, extra={extra}"
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MissionJournalError(f"{label} must be a JSON object")
    return value


def _read_canonical_json(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise MissionJournalError(f"journal entry is not a regular file: {path.name}")
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_JOURNAL_FILE_BYTES + 1)
    except OSError as exc:
        raise MissionJournalError(f"cannot read journal entry {path.name}") from exc
    if len(payload) > MAX_JOURNAL_FILE_BYTES:
        raise MissionJournalError(f"journal entry is oversized: {path.name}")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MissionJournalError(f"invalid strict JSON in {path.name}") from exc
    if not isinstance(document, dict):
        raise MissionJournalError(f"{path.name} must contain a JSON object")
    if _canonical_bytes(document) != payload:
        raise MissionJournalError(f"journal entry is not canonical JSON: {path.name}")
    return document, payload


def _write_new(path: Path, payload: bytes) -> None:
    if len(payload) > MAX_JOURNAL_FILE_BYTES:
        raise MissionJournalError(f"journal entry is oversized: {path.name}")
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise MissionJournalError(f"cannot write journal entry {path.name}") from exc


def _fsync_directory(path: Path) -> None:
    """Make published directory entries durable on platforms that support it.

    POSIX filesystems require an fsync of the containing directory in addition
    to fsyncing the file contents.  CPython cannot portably open a directory for
    fsync on Windows, so Windows retains the atomic replace/link ordering and
    fails closed through the high-water record, but skips this unsupported call.
    """

    flags = os.O_RDONLY
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    flags |= directory_flag
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if os.name == "nt":
            return
        raise MissionJournalError(
            f"cannot open journal directory for durability sync: {path.name}"
        ) from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if os.name != "nt":
            raise MissionJournalError(
                f"cannot durability-sync journal directory: {path.name}"
            ) from exc
    finally:
        os.close(descriptor)


def _safe_existing_directory(path: Path, label: str) -> Path:
    selected = Path(path)
    if selected.is_symlink():
        raise MissionJournalError(f"{label} must not be a symlink")
    resolved = selected.resolve()
    if not resolved.is_dir():
        raise MissionJournalError(f"{label} is not an existing directory")
    return resolved


@dataclass(frozen=True, slots=True)
class ActionOccurrence:
    """Stable identity for one ordinal action in one immutable plan."""

    mission_id: str
    plan_sha256: str
    action_ordinal: int
    action_sha256: str
    occurrence_id: str
    schema: str = ACTION_OCCURRENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != ACTION_OCCURRENCE_SCHEMA:
            raise MissionJournalError("unsupported action-occurrence schema")
        _identifier(self.mission_id, "mission_id")
        _digest(self.plan_sha256, "plan_sha256")
        _bounded_integer(self.action_ordinal, "action_ordinal", maximum=999_999)
        _digest(self.action_sha256, "action_sha256")
        if not isinstance(self.occurrence_id, str) or _OCCURRENCE_ID.fullmatch(
            self.occurrence_id
        ) is None:
            raise MissionJournalError("occurrence_id has invalid syntax")
        if self.occurrence_id != self.expected_occurrence_id:
            raise MissionJournalError("occurrence_id does not bind the plan and action")

    @property
    def expected_occurrence_id(self) -> str:
        core = {
            "schema": ACTION_OCCURRENCE_SCHEMA,
            "mission_id": self.mission_id,
            "plan_sha256": self.plan_sha256,
            "action_ordinal": self.action_ordinal,
            "action_sha256": self.action_sha256,
        }
        return f"occ-{_stable_hash(core)[:32]}"

    @property
    def occurrence_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "mission_id": self.mission_id,
            "plan_sha256": self.plan_sha256,
            "action_ordinal": self.action_ordinal,
            "action_sha256": self.action_sha256,
            "occurrence_id": self.occurrence_id,
        }

    @classmethod
    def from_action_document(
        cls,
        *,
        mission_id: str,
        plan_sha256: str,
        action_ordinal: int,
        action: object,
    ) -> "ActionOccurrence":
        action_sha256 = hashlib.sha256(_compact_bytes(action)).hexdigest()
        core = {
            "schema": ACTION_OCCURRENCE_SCHEMA,
            "mission_id": _identifier(mission_id, "mission_id"),
            "plan_sha256": _digest(plan_sha256, "plan_sha256"),
            "action_ordinal": _bounded_integer(
                action_ordinal,
                "action_ordinal",
                maximum=999_999,
            ),
            "action_sha256": action_sha256,
        }
        return cls(
            mission_id=mission_id,
            plan_sha256=plan_sha256,
            action_ordinal=action_ordinal,
            action_sha256=action_sha256,
            occurrence_id=f"occ-{_stable_hash(core)[:32]}",
        )

    @classmethod
    def from_dict(cls, value: object) -> "ActionOccurrence":
        document = _mapping(value, "occurrence")
        _exact_fields(
            document,
            frozenset(
                {
                    "schema",
                    "mission_id",
                    "plan_sha256",
                    "action_ordinal",
                    "action_sha256",
                    "occurrence_id",
                }
            ),
            "occurrence",
        )
        try:
            return cls(
                schema=document["schema"],
                mission_id=document["mission_id"],
                plan_sha256=document["plan_sha256"],
                action_ordinal=document["action_ordinal"],
                action_sha256=document["action_sha256"],
                occurrence_id=document["occurrence_id"],
            )
        except TypeError as exc:
            raise MissionJournalError("occurrence fields have invalid types") from exc


@dataclass(frozen=True, slots=True)
class MissionJournalEvent:
    """One immutable, hash-chained journal transition."""

    journal_id: str
    occurrence_id: str
    sequence: int
    state: ActionJournalState
    previous_event_sha256: str
    event_time_ns: int
    evidence_sha256: str | None
    detail_code: str
    event_sha256: str
    schema: str = MISSION_JOURNAL_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MISSION_JOURNAL_EVENT_SCHEMA:
            raise MissionJournalError("unsupported journal-event schema")
        if not isinstance(self.journal_id, str) or _JOURNAL_ID.fullmatch(
            self.journal_id
        ) is None:
            raise MissionJournalError("journal_id has invalid syntax")
        if not isinstance(self.occurrence_id, str) or _OCCURRENCE_ID.fullmatch(
            self.occurrence_id
        ) is None:
            raise MissionJournalError("occurrence_id has invalid syntax")
        _bounded_integer(self.sequence, "sequence", maximum=MAX_JOURNAL_EVENTS - 1)
        if not isinstance(self.state, ActionJournalState):
            raise MissionJournalError("state must be ActionJournalState")
        if self.state is ActionJournalState.NOT_STARTED:
            raise MissionJournalError("NOT_STARTED is not a persistent event state")
        _digest(self.previous_event_sha256, "previous_event_sha256")
        _bounded_integer(self.event_time_ns, "event_time_ns", maximum=2**63 - 1)
        if self.event_time_ns == 0:
            raise MissionJournalError("event_time_ns must be positive")
        if self.evidence_sha256 is not None:
            _digest(self.evidence_sha256, "evidence_sha256")
        if self.state in _EVIDENCE_REQUIRED_STATES and self.evidence_sha256 is None:
            raise MissionJournalError(f"{self.state.value} requires evidence_sha256")
        _detail_code(self.detail_code)
        _digest(self.event_sha256, "event_sha256")
        if self.event_sha256 != _stable_hash(self.core_dict()):
            raise MissionJournalError("event_sha256 does not bind the event")
        _state_detail_code(self.state, self.detail_code)

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "journal_id": self.journal_id,
            "occurrence_id": self.occurrence_id,
            "sequence": self.sequence,
            "state": self.state.value,
            "previous_event_sha256": self.previous_event_sha256,
            "event_time_ns": self.event_time_ns,
            "evidence_sha256": self.evidence_sha256,
            "detail_code": self.detail_code,
            "simulation_only": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "event_sha256": self.event_sha256}

    @classmethod
    def build(
        cls,
        *,
        journal_id: str,
        occurrence_id: str,
        sequence: int,
        state: ActionJournalState,
        previous_event_sha256: str,
        event_time_ns: int,
        evidence_sha256: str | None,
        detail_code: str,
    ) -> "MissionJournalEvent":
        core = {
            "schema": MISSION_JOURNAL_EVENT_SCHEMA,
            "journal_id": journal_id,
            "occurrence_id": occurrence_id,
            "sequence": sequence,
            "state": state.value,
            "previous_event_sha256": previous_event_sha256,
            "event_time_ns": event_time_ns,
            "evidence_sha256": evidence_sha256,
            "detail_code": detail_code,
            "simulation_only": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }
        return cls(
            journal_id=journal_id,
            occurrence_id=occurrence_id,
            sequence=sequence,
            state=state,
            previous_event_sha256=previous_event_sha256,
            event_time_ns=event_time_ns,
            evidence_sha256=evidence_sha256,
            detail_code=detail_code,
            event_sha256=_stable_hash(core),
        )

    @classmethod
    def from_dict(cls, value: object) -> "MissionJournalEvent":
        document = _mapping(value, "journal event")
        _exact_fields(
            document,
            frozenset(
                {
                    "schema",
                    "journal_id",
                    "occurrence_id",
                    "sequence",
                    "state",
                    "previous_event_sha256",
                    "event_time_ns",
                    "evidence_sha256",
                    "detail_code",
                    "simulation_only",
                    "hardware_accessed",
                    "hardware_commands_generated",
                    "physical_release_effect",
                    "event_sha256",
                }
            ),
            "journal event",
        )
        if (
            document["simulation_only"] is not True
            or document["hardware_accessed"] is not False
            or document["hardware_commands_generated"] != 0
            or isinstance(document["hardware_commands_generated"], bool)
            or document["physical_release_effect"] != "NONE"
        ):
            raise MissionJournalError("journal event violates zero authority")
        try:
            state = ActionJournalState(document["state"])
        except (TypeError, ValueError) as exc:
            raise MissionJournalError("journal event has invalid state") from exc
        try:
            return cls(
                schema=document["schema"],
                journal_id=document["journal_id"],
                occurrence_id=document["occurrence_id"],
                sequence=document["sequence"],
                state=state,
                previous_event_sha256=document["previous_event_sha256"],
                event_time_ns=document["event_time_ns"],
                evidence_sha256=document["evidence_sha256"],
                detail_code=document["detail_code"],
                event_sha256=document["event_sha256"],
            )
        except TypeError as exc:
            raise MissionJournalError("journal event fields have invalid types") from exc


@dataclass(frozen=True, slots=True)
class MissionJournalSnapshot:
    """Strictly reconstructed state and conservative restart decision."""

    journal_id: str
    occurrence: ActionOccurrence
    created_at_ns: int
    header_sha256: str
    high_water_sha256: str
    events: tuple[MissionJournalEvent, ...]

    @property
    def current_state(self) -> ActionJournalState:
        return self.events[-1].state

    @property
    def contact_may_have_occurred(self) -> bool:
        return any(
            event.state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
            for event in self.events
        )

    @property
    def contact_submission_permitted(self) -> bool:
        """Whether the original contact boundary may be committed once.

        This is never a retry authorization.  The caller must first append the
        contact boundary, then submit at most one operation associated with the
        exact evidence hash stored in that event.
        """

        return (
            self.current_state is ActionJournalState.PRE_CONTACT
            and not self.contact_may_have_occurred
        )

    @property
    def automatic_contact_retry_permitted(self) -> bool:
        return False

    @property
    def recovery_disposition(self) -> JournalRecoveryDisposition:
        state = self.current_state
        if state in {
            ActionJournalState.INTENT_COMMITTED,
            ActionJournalState.PRE_CONTACT,
        }:
            return JournalRecoveryDisposition.PRE_CONTACT_WORK_MAY_RESUME
        if state in {
            ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            ActionJournalState.OUTCOME_UNCERTAIN,
        }:
            return (
                JournalRecoveryDisposition.CONTACT_RETRY_FORBIDDEN_OUTCOME_UNCERTAIN
            )
        if state is ActionJournalState.OUTCOME_CONFIRMED:
            return JournalRecoveryDisposition.RETRACT_ONLY_AFTER_INDEPENDENT_REVIEW
        if state is ActionJournalState.RETRACTED:
            return JournalRecoveryDisposition.PARK_ONLY_AFTER_INDEPENDENT_REVIEW
        if state is ActionJournalState.PARKED:
            return JournalRecoveryDisposition.COMPLETE_NO_ACTION
        return JournalRecoveryDisposition.MANUAL_REVIEW_REQUIRED

    @property
    def snapshot_hash(self) -> str:
        return _stable_hash(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": MISSION_JOURNAL_SNAPSHOT_SCHEMA,
            "journal_id": self.journal_id,
            "occurrence": self.occurrence.to_dict(),
            "created_at_ns": self.created_at_ns,
            "header_sha256": self.header_sha256,
            "high_water_sha256": self.high_water_sha256,
            "current_state": self.current_state.value,
            "event_count": len(self.events),
            "event_hashes": [event.event_sha256 for event in self.events],
            "contact_may_have_occurred": self.contact_may_have_occurred,
            "contact_submission_permitted": self.contact_submission_permitted,
            "automatic_contact_retry_permitted": False,
            "recovery_disposition": self.recovery_disposition.value,
            "simulation_only": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }
        if include_hash:
            value["snapshot_sha256"] = _stable_hash(value)
        return value


def _journal_id(occurrence: ActionOccurrence) -> str:
    return f"journal-{occurrence.occurrence_hash[:24]}"


def _header_document(
    occurrence: ActionOccurrence,
    *,
    journal_id: str,
    created_at_ns: int,
) -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": MISSION_JOURNAL_HEADER_SCHEMA,
        "journal_id": journal_id,
        "occurrence": occurrence.to_dict(),
        "occurrence_sha256": occurrence.occurrence_hash,
        "created_at_ns": created_at_ns,
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
    }
    return {**core, "header_sha256": _stable_hash(core)}


_HEADER_FIELDS = frozenset(
    {
        "schema",
        "journal_id",
        "occurrence",
        "occurrence_sha256",
        "created_at_ns",
        "simulation_only",
        "hardware_accessed",
        "hardware_commands_generated",
        "physical_release_effect",
        "header_sha256",
    }
)


def _parse_header(value: object) -> tuple[str, ActionOccurrence, int, str]:
    document = _mapping(value, "journal header")
    _exact_fields(document, _HEADER_FIELDS, "journal header")
    if document["schema"] != MISSION_JOURNAL_HEADER_SCHEMA:
        raise MissionJournalError("unsupported journal-header schema")
    journal_id = document["journal_id"]
    if not isinstance(journal_id, str) or _JOURNAL_ID.fullmatch(journal_id) is None:
        raise MissionJournalError("journal header has invalid journal_id")
    occurrence = ActionOccurrence.from_dict(document["occurrence"])
    if document["occurrence_sha256"] != occurrence.occurrence_hash:
        raise MissionJournalError("journal header occurrence digest mismatch")
    created_at_ns = _bounded_integer(
        document["created_at_ns"], "created_at_ns", maximum=2**63 - 1
    )
    if created_at_ns == 0:
        raise MissionJournalError("created_at_ns must be positive")
    if (
        document["simulation_only"] is not True
        or document["hardware_accessed"] is not False
        or document["hardware_commands_generated"] != 0
        or isinstance(document["hardware_commands_generated"], bool)
        or document["physical_release_effect"] != "NONE"
    ):
        raise MissionJournalError("journal header violates zero authority")
    header_sha256 = _digest(document["header_sha256"], "header_sha256")
    core = dict(document)
    del core["header_sha256"]
    if header_sha256 != _stable_hash(core):
        raise MissionJournalError("header_sha256 does not bind the journal header")
    if journal_id != _journal_id(occurrence):
        raise MissionJournalError("journal_id does not bind the occurrence")
    return journal_id, occurrence, created_at_ns, header_sha256


_HIGH_WATER_FIELDS = frozenset(
    {
        "schema",
        "journal_id",
        "occurrence_id",
        "header_sha256",
        "committed_sequence",
        "committed_event_sha256",
        "committed_state",
        "committed_event_time_ns",
        "event_count",
        "contact_boundary_ever_committed",
        "contact_boundary_sequence",
        "contact_boundary_event_sha256",
        "simulation_only",
        "hardware_accessed",
        "hardware_commands_generated",
        "physical_release_effect",
        "high_water_sha256",
    }
)


def _high_water_document(
    *,
    journal_id: str,
    occurrence_id: str,
    header_sha256: str,
    events: tuple[MissionJournalEvent, ...],
) -> dict[str, Any]:
    """Build the separately persisted monotonic tail commitment."""

    if not events:
        raise MissionJournalError("cannot anchor an empty journal")
    tail = events[-1]
    contact = next(
        (
            event
            for event in events
            if event.state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
        ),
        None,
    )
    core: dict[str, Any] = {
        "schema": MISSION_JOURNAL_HIGH_WATER_SCHEMA,
        "journal_id": journal_id,
        "occurrence_id": occurrence_id,
        "header_sha256": header_sha256,
        "committed_sequence": tail.sequence,
        "committed_event_sha256": tail.event_sha256,
        "committed_state": tail.state.value,
        "committed_event_time_ns": tail.event_time_ns,
        "event_count": len(events),
        "contact_boundary_ever_committed": contact is not None,
        "contact_boundary_sequence": None if contact is None else contact.sequence,
        "contact_boundary_event_sha256": (
            None if contact is None else contact.event_sha256
        ),
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
    }
    return {**core, "high_water_sha256": _stable_hash(core)}


def _parse_high_water(value: object) -> dict[str, Any]:
    document = _mapping(value, "journal high-water record")
    _exact_fields(document, _HIGH_WATER_FIELDS, "journal high-water record")
    if document["schema"] != MISSION_JOURNAL_HIGH_WATER_SCHEMA:
        raise MissionJournalError("unsupported journal high-water schema")
    journal_id = document["journal_id"]
    occurrence_id = document["occurrence_id"]
    if not isinstance(journal_id, str) or _JOURNAL_ID.fullmatch(journal_id) is None:
        raise MissionJournalError("journal high-water record has invalid journal_id")
    if (
        not isinstance(occurrence_id, str)
        or _OCCURRENCE_ID.fullmatch(occurrence_id) is None
    ):
        raise MissionJournalError("journal high-water record has invalid occurrence_id")
    _digest(document["header_sha256"], "high-water header_sha256")
    committed_sequence = _bounded_integer(
        document["committed_sequence"],
        "high-water committed_sequence",
        maximum=MAX_JOURNAL_EVENTS - 1,
    )
    event_count = _bounded_integer(
        document["event_count"],
        "high-water event_count",
        maximum=MAX_JOURNAL_EVENTS,
    )
    if event_count == 0 or committed_sequence != event_count - 1:
        raise MissionJournalError("journal high-water event count is inconsistent")
    _digest(document["committed_event_sha256"], "committed_event_sha256")
    try:
        committed_state = ActionJournalState(document["committed_state"])
    except (TypeError, ValueError) as exc:
        raise MissionJournalError("journal high-water state is invalid") from exc
    if committed_state is ActionJournalState.NOT_STARTED:
        raise MissionJournalError("journal high-water state cannot be NOT_STARTED")
    committed_time = _bounded_integer(
        document["committed_event_time_ns"],
        "high-water committed_event_time_ns",
        maximum=2**63 - 1,
    )
    if committed_time == 0:
        raise MissionJournalError("high-water committed_event_time_ns must be positive")
    contact_ever = document["contact_boundary_ever_committed"]
    if not isinstance(contact_ever, bool):
        raise MissionJournalError(
            "contact_boundary_ever_committed must be boolean"
        )
    contact_sequence = document["contact_boundary_sequence"]
    contact_hash = document["contact_boundary_event_sha256"]
    if contact_ever:
        _bounded_integer(
            contact_sequence,
            "contact_boundary_sequence",
            maximum=MAX_JOURNAL_EVENTS - 1,
        )
        _digest(contact_hash, "contact_boundary_event_sha256")
    elif contact_sequence is not None or contact_hash is not None:
        raise MissionJournalError(
            "journal high-water record has inconsistent contact boundary fields"
        )
    if (
        document["simulation_only"] is not True
        or document["hardware_accessed"] is not False
        or document["hardware_commands_generated"] != 0
        or isinstance(document["hardware_commands_generated"], bool)
        or document["physical_release_effect"] != "NONE"
    ):
        raise MissionJournalError("journal high-water record violates zero authority")
    high_water_sha256 = _digest(
        document["high_water_sha256"], "high_water_sha256"
    )
    core = dict(document)
    del core["high_water_sha256"]
    if high_water_sha256 != _stable_hash(core):
        raise MissionJournalError(
            "high_water_sha256 does not bind the journal high-water record"
        )
    return dict(document)


def _validate_high_water_against_events(
    high_water: Mapping[str, Any],
    *,
    journal_id: str,
    occurrence: ActionOccurrence,
    header_sha256: str,
    events: tuple[MissionJournalEvent, ...],
) -> None:
    """Reject truncation, unanchored append, rollback, or contact-bit drift."""

    if (
        high_water["journal_id"] != journal_id
        or high_water["occurrence_id"] != occurrence.occurrence_id
        or high_water["header_sha256"] != header_sha256
    ):
        raise MissionJournalError("journal high-water correlation mismatch")
    if high_water["event_count"] != len(events):
        raise MissionJournalError(
            "journal event suffix differs from the durable high-water record"
        )
    tail = events[-1]
    if (
        high_water["committed_sequence"] != tail.sequence
        or high_water["committed_event_sha256"] != tail.event_sha256
        or high_water["committed_state"] != tail.state.value
        or high_water["committed_event_time_ns"] != tail.event_time_ns
    ):
        raise MissionJournalError("journal tail does not match its high-water record")
    contacts = tuple(
        event
        for event in events
        if event.state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
    )
    if len(contacts) > 1:
        raise MissionJournalError("journal contains more than one contact boundary")
    contact = contacts[0] if contacts else None
    if high_water["contact_boundary_ever_committed"] is not (contact is not None):
        raise MissionJournalError("journal contact high-water state is inconsistent")
    if contact is None:
        if (
            high_water["contact_boundary_sequence"] is not None
            or high_water["contact_boundary_event_sha256"] is not None
        ):
            raise MissionJournalError("journal contact high-water fields are inconsistent")
    elif (
        high_water["contact_boundary_sequence"] != contact.sequence
        or high_water["contact_boundary_event_sha256"] != contact.event_sha256
    ):
        raise MissionJournalError("journal contact boundary differs from high-water")


def load_mission_journal(directory: Path) -> MissionJournalSnapshot:
    """Strictly reconstruct an immutable event chain from disk."""

    root = _safe_existing_directory(directory, "journal directory")
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise MissionJournalError("cannot enumerate journal directory") from exc
    if len(entries) > MAX_JOURNAL_EVENTS + 2:
        raise MissionJournalError("journal contains too many entries")

    event_paths: list[tuple[int, Path]] = []
    header_seen = False
    high_water_seen = False
    for entry in entries:
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            raise MissionJournalError(f"unexpected non-file journal entry {entry.name!r}")
        if entry.name == "header.json":
            if header_seen:
                raise MissionJournalError("journal contains duplicate header")
            header_seen = True
            continue
        if entry.name == _HIGH_WATER_FILENAME:
            if high_water_seen:
                raise MissionJournalError("journal contains duplicate high-water record")
            high_water_seen = True
            continue
        match = _EVENT_FILENAME.fullmatch(entry.name)
        if match is None:
            raise MissionJournalError(f"unexpected journal entry {entry.name!r}")
        event_paths.append((int(match.group(1)), Path(entry.path)))
    if not header_seen:
        raise MissionJournalError("journal header is missing")
    if not high_water_seen:
        raise MissionJournalError("journal high-water record is missing")
    if not event_paths:
        raise MissionJournalError("journal has no committed intent event")
    event_paths.sort(key=lambda item: item[0])
    expected_sequences = list(range(len(event_paths)))
    if [sequence for sequence, _ in event_paths] != expected_sequences:
        raise MissionJournalError("journal event sequence is not contiguous")

    header, _ = _read_canonical_json(root / "header.json")
    journal_id, occurrence, created_at_ns, header_sha256 = _parse_header(header)

    events: list[MissionJournalEvent] = []
    previous_hash = _ZERO_DIGEST
    previous_time = created_at_ns - 1
    previous_state: ActionJournalState | None = None
    for sequence, path in event_paths:
        document, _ = _read_canonical_json(path)
        event = MissionJournalEvent.from_dict(document)
        if event.sequence != sequence:
            raise MissionJournalError("event filename and sequence disagree")
        if event.journal_id != journal_id or event.occurrence_id != occurrence.occurrence_id:
            raise MissionJournalError("journal event correlation mismatch")
        if event.previous_event_sha256 != previous_hash:
            raise MissionJournalError("journal event hash chain is broken")
        if event.event_time_ns <= previous_time:
            raise MissionJournalError("journal event time is not strictly increasing")
        if sequence == 0:
            if event.state is not ActionJournalState.INTENT_COMMITTED:
                raise MissionJournalError("first journal event must commit intent")
            if event.evidence_sha256 != occurrence.action_sha256:
                raise MissionJournalError("intent event does not bind the action")
        else:
            assert previous_state is not None
            if event.state not in _ALLOWED_TRANSITIONS[previous_state]:
                raise MissionJournalError(
                    f"invalid journal transition {previous_state.value}->{event.state.value}"
                )
        events.append(event)
        previous_hash = event.event_sha256
        previous_time = event.event_time_ns
        previous_state = event.state

    high_water_document, _ = _read_canonical_json(root / _HIGH_WATER_FILENAME)
    high_water = _parse_high_water(high_water_document)
    immutable_events = tuple(events)
    _validate_high_water_against_events(
        high_water,
        journal_id=journal_id,
        occurrence=occurrence,
        header_sha256=header_sha256,
        events=immutable_events,
    )

    return MissionJournalSnapshot(
        journal_id=journal_id,
        occurrence=occurrence,
        created_at_ns=created_at_ns,
        header_sha256=header_sha256,
        high_water_sha256=high_water["high_water_sha256"],
        events=immutable_events,
    )


@dataclass(frozen=True, slots=True)
class ZeroAuthorityMissionJournal:
    """Handle for atomic append and strict restart reconstruction."""

    directory: Path

    @classmethod
    def create(
        cls,
        root: Path,
        occurrence: ActionOccurrence,
        *,
        created_at_ns: int,
    ) -> "ZeroAuthorityMissionJournal":
        if not isinstance(occurrence, ActionOccurrence):
            raise TypeError("occurrence must be ActionOccurrence")
        evidence_root = _safe_existing_directory(root, "journal root")
        created = _bounded_integer(
            created_at_ns, "created_at_ns", maximum=2**63 - 1
        )
        if created == 0:
            raise MissionJournalError("created_at_ns must be positive")
        journal_id = _journal_id(occurrence)
        destination = evidence_root / journal_id
        if os.path.lexists(destination):
            raise MissionJournalError(f"immutable journal already exists: {journal_id}")
        temporary = evidence_root / f".partial-{journal_id}-{secrets.token_hex(8)}"
        header = _header_document(
            occurrence,
            journal_id=journal_id,
            created_at_ns=created,
        )
        intent = MissionJournalEvent.build(
            journal_id=journal_id,
            occurrence_id=occurrence.occurrence_id,
            sequence=0,
            state=ActionJournalState.INTENT_COMMITTED,
            previous_event_sha256=_ZERO_DIGEST,
            event_time_ns=created,
            evidence_sha256=occurrence.action_sha256,
            detail_code="ACTION_INTENT_COMMITTED",
        )
        high_water = _high_water_document(
            journal_id=journal_id,
            occurrence_id=occurrence.occurrence_id,
            header_sha256=header["header_sha256"],
            events=(intent,),
        )
        try:
            temporary.mkdir(exist_ok=False)
            _write_new(temporary / "header.json", _canonical_bytes(header))
            _write_new(temporary / "event-000000.json", _canonical_bytes(intent.to_dict()))
            _write_new(
                temporary / _HIGH_WATER_FILENAME,
                _canonical_bytes(high_water),
            )
            _fsync_directory(temporary)
            try:
                temporary.rename(destination)
            except OSError as exc:
                raise MissionJournalError(
                    f"cannot atomically publish journal {journal_id}"
                ) from exc
            _fsync_directory(evidence_root)
        except Exception:
            if temporary.is_dir() and not temporary.is_symlink():
                shutil.rmtree(temporary)
            raise
        journal = cls(destination)
        journal.snapshot()
        return journal

    @classmethod
    def open(cls, directory: Path) -> "ZeroAuthorityMissionJournal":
        journal = cls(_safe_existing_directory(directory, "journal directory"))
        journal.snapshot()
        return journal

    def snapshot(self) -> MissionJournalSnapshot:
        return load_mission_journal(self.directory)

    def commit_transition(
        self,
        state: ActionJournalState,
        *,
        event_time_ns: int,
        evidence_sha256: str | None,
        detail_code: str,
    ) -> MissionJournalSnapshot:
        """Atomically append one allowed transition and return fresh state.

        The implementation writes and fsyncs a temporary file outside the
        journal, then hard-links it to the unique sequence filename.  Competing
        writers therefore cannot overwrite or partially publish an event.
        """

        if not isinstance(state, ActionJournalState):
            raise TypeError("state must be ActionJournalState")
        current = self.snapshot()
        if state not in _ALLOWED_TRANSITIONS[current.current_state]:
            raise MissionJournalError(
                f"invalid journal transition {current.current_state.value}->{state.value}"
            )
        sequence = len(current.events)
        if sequence >= MAX_JOURNAL_EVENTS:
            raise MissionJournalError("journal event limit reached")
        observed = _bounded_integer(
            event_time_ns, "event_time_ns", maximum=2**63 - 1
        )
        if observed <= current.events[-1].event_time_ns:
            raise MissionJournalError("event_time_ns must strictly increase")
        evidence = None if evidence_sha256 is None else _digest(
            evidence_sha256, "evidence_sha256"
        )
        detail = _detail_code(detail_code)
        event = MissionJournalEvent.build(
            journal_id=current.journal_id,
            occurrence_id=current.occurrence.occurrence_id,
            sequence=sequence,
            state=state,
            previous_event_sha256=current.events[-1].event_sha256,
            event_time_ns=observed,
            evidence_sha256=evidence,
            detail_code=detail,
        )
        final_path = self.directory / f"event-{sequence:06d}.json"
        root = self.directory.parent
        event_temporary = root / (
            f".partial-{current.journal_id}-event-{sequence:06d}-{secrets.token_hex(8)}"
        )
        high_water_temporary = root / (
            f".partial-{current.journal_id}-high-water-{sequence:06d}-"
            f"{secrets.token_hex(8)}"
        )
        high_water = _high_water_document(
            journal_id=current.journal_id,
            occurrence_id=current.occurrence.occurrence_id,
            header_sha256=current.header_sha256,
            events=(*current.events, event),
        )
        _write_new(event_temporary, _canonical_bytes(event.to_dict()))
        try:
            _write_new(high_water_temporary, _canonical_bytes(high_water))
            try:
                os.link(event_temporary, final_path)
            except FileExistsError as exc:
                raise MissionJournalError(
                    "concurrent journal transition already won this sequence"
                ) from exc
            except OSError as exc:
                raise MissionJournalError(
                    "cannot atomically publish journal transition"
                ) from exc
            # First make the immutable event durable.  Only then advance the
            # fixed high-water record.  Any interruption between these steps
            # leaves an extra unanchored event and therefore fails closed.
            _fsync_directory(self.directory)
            try:
                os.replace(
                    high_water_temporary,
                    self.directory / _HIGH_WATER_FILENAME,
                )
            except OSError as exc:
                raise MissionJournalError(
                    "cannot atomically advance journal high-water record"
                ) from exc
            _fsync_directory(self.directory)
        finally:
            for temporary in (event_temporary, high_water_temporary):
                try:
                    if temporary.is_file() and not temporary.is_symlink():
                        temporary.unlink()
                except OSError:
                    pass
        return self.snapshot()

    def commit_pre_contact(
        self, *, event_time_ns: int, route_sha256: str
    ) -> MissionJournalSnapshot:
        return self.commit_transition(
            ActionJournalState.PRE_CONTACT,
            event_time_ns=event_time_ns,
            evidence_sha256=route_sha256,
            detail_code="PRE_CONTACT_EVIDENCE_COMMITTED",
        )

    def commit_contact_boundary(
        self, *, event_time_ns: int, command_sha256: str
    ) -> MissionJournalSnapshot:
        """Persist possible contact *before* submitting the associated command."""

        current = self.snapshot()
        if not current.contact_submission_permitted:
            raise MissionJournalError("contact submission is not permitted by the journal")
        return self.commit_transition(
            ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            event_time_ns=event_time_ns,
            evidence_sha256=command_sha256,
            detail_code="CONTACT_BOUNDARY_COMMITTED_BEFORE_SUBMISSION",
        )

    def confirm_outcome(
        self, *, event_time_ns: int, outcome_sha256: str
    ) -> MissionJournalSnapshot:
        return self.commit_transition(
            ActionJournalState.OUTCOME_CONFIRMED,
            event_time_ns=event_time_ns,
            evidence_sha256=outcome_sha256,
            detail_code="INDEPENDENT_OUTCOME_CONFIRMED",
        )

    def confirm_retracted(
        self, *, event_time_ns: int, feedback_sha256: str
    ) -> MissionJournalSnapshot:
        return self.commit_transition(
            ActionJournalState.RETRACTED,
            event_time_ns=event_time_ns,
            evidence_sha256=feedback_sha256,
            detail_code="RETRACTION_CONFIRMED",
        )

    def confirm_parked(
        self, *, event_time_ns: int, feedback_sha256: str
    ) -> MissionJournalSnapshot:
        return self.commit_transition(
            ActionJournalState.PARKED,
            event_time_ns=event_time_ns,
            evidence_sha256=feedback_sha256,
            detail_code="PARK_CONFIRMED",
        )

    def mark_outcome_uncertain(
        self,
        *,
        event_time_ns: int,
        detail_code: str,
        evidence_sha256: str | None = None,
    ) -> MissionJournalSnapshot:
        return self.commit_transition(
            ActionJournalState.OUTCOME_UNCERTAIN,
            event_time_ns=event_time_ns,
            evidence_sha256=evidence_sha256,
            detail_code=detail_code,
        )

    def mark_faulted(
        self,
        *,
        event_time_ns: int,
        detail_code: str,
        evidence_sha256: str | None = None,
    ) -> MissionJournalSnapshot:
        return self.commit_transition(
            ActionJournalState.FAULTED,
            event_time_ns=event_time_ns,
            evidence_sha256=evidence_sha256,
            detail_code=detail_code,
        )


__all__ = [
    "ACTION_OCCURRENCE_SCHEMA",
    "MISSION_JOURNAL_EVENT_SCHEMA",
    "MISSION_JOURNAL_HEADER_SCHEMA",
    "MISSION_JOURNAL_HIGH_WATER_SCHEMA",
    "MISSION_JOURNAL_SNAPSHOT_SCHEMA",
    "ActionJournalState",
    "ActionOccurrence",
    "JournalRecoveryDisposition",
    "MissionJournalError",
    "MissionJournalEvent",
    "MissionJournalSnapshot",
    "ZeroAuthorityMissionJournal",
    "load_mission_journal",
]
