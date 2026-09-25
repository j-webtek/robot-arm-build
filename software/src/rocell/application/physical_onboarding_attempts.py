"""Cell-global, append-only records for physical onboarding effects.

This module records *descriptions* of effect attempts.  It deliberately has no
camera, controller, serial, permit, worker, or hardware adapter.  Filesystem
publication is also not implemented here: callers must inject a publisher
whose implementation has independently qualified its locking and durability
semantics on the ledger volume.

An attempt is never replayed.  Its only valid state paths are::

    INTENT_DURABLE -> EFFECT_ARMED -> EFFECT_OBSERVED
        -> CLEANUP_CONFIRMED -> SEALED_KNOWN
    INTENT_DURABLE -> ABORTED_PRE_EFFECT
    EFFECT_ARMED|EFFECT_OBSERVED|CLEANUP_CONFIRMED -> SEALED_UNCERTAIN

Every mutation is one compare-and-commit call.  A concurrent-head failure is
surfaced to the caller; this module contains no retry loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable, Protocol, runtime_checkable

from rocell.safety.effects import EffectClass


ATTEMPT_LEDGER_HEADER_SCHEMA = "rocell.physical_onboarding_attempt_header.v1"
ATTEMPT_LEDGER_EVENT_SCHEMA = "rocell.physical_onboarding_attempt_event.v1"
ATTEMPT_LEDGER_HEAD_SCHEMA = "rocell.physical_onboarding_attempt_head.v1"

MAX_JSON_BYTES = 256 * 1024
MAX_LEDGER_PATH_CHARS = 2048
MAX_LEDGER_PATH_PARTS = 128
MAX_ATTEMPT_EVENTS = 4096

ZERO_SHA256 = "0" * 64
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")
_OPERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_EVENT_NAME_RE = re.compile(r"events/event-([0-9]{8})\.json\Z")

_STAGES = frozenset(
    {
        "workspace_sources",
        "static_camera_contract",
        "camera_receipt",
        "camera_identity",
        "camera_mode_controls",
        "camera_frame_freshness",
        "optics_intrinsics",
        "static_registration",
        "arm_identity",
        "power_safety",
        "power_on_observation",
        "feedback_only_connection",
        "reference_frame_calibration",
        "noncontact_acceptance",
        "physical_handoff",
    }
)


class PhysicalOnboardingAttemptError(ValueError):
    """An attempt ledger is malformed, unqualified, or transition-invalid."""


class AttemptLedgerIntegrityError(PhysicalOnboardingAttemptError):
    """The committed ledger cannot be reconstructed exactly."""


class AttemptLedgerSuffixError(AttemptLedgerIntegrityError):
    """Files after, or missing from, the committed head were detected."""


class AttemptTransitionError(PhysicalOnboardingAttemptError):
    """The requested state change is not one of the frozen transitions."""


class AttemptState(str, Enum):
    """Frozen physical-effect attempt states from the v2 stage catalog."""

    INTENT_DURABLE = "INTENT_DURABLE"
    ABORTED_PRE_EFFECT = "ABORTED_PRE_EFFECT"
    EFFECT_ARMED = "EFFECT_ARMED"
    EFFECT_OBSERVED = "EFFECT_OBSERVED"
    CLEANUP_CONFIRMED = "CLEANUP_CONFIRMED"
    SEALED_KNOWN = "SEALED_KNOWN"
    SEALED_UNCERTAIN = "SEALED_UNCERTAIN"


TERMINAL_ATTEMPT_STATES = frozenset(
    {
        AttemptState.ABORTED_PRE_EFFECT,
        AttemptState.SEALED_KNOWN,
        AttemptState.SEALED_UNCERTAIN,
    }
)
ARMED_UNSEALED_STATES = frozenset(
    {
        AttemptState.EFFECT_ARMED,
        AttemptState.EFFECT_OBSERVED,
        AttemptState.CLEANUP_CONFIRMED,
    }
)

_TRANSITIONS: dict[AttemptState, frozenset[AttemptState]] = {
    AttemptState.INTENT_DURABLE: frozenset(
        {AttemptState.EFFECT_ARMED, AttemptState.ABORTED_PRE_EFFECT}
    ),
    AttemptState.EFFECT_ARMED: frozenset(
        {AttemptState.EFFECT_OBSERVED, AttemptState.SEALED_UNCERTAIN}
    ),
    AttemptState.EFFECT_OBSERVED: frozenset(
        {AttemptState.CLEANUP_CONFIRMED, AttemptState.SEALED_UNCERTAIN}
    ),
    AttemptState.CLEANUP_CONFIRMED: frozenset(
        {AttemptState.SEALED_KNOWN, AttemptState.SEALED_UNCERTAIN}
    ),
    AttemptState.ABORTED_PRE_EFFECT: frozenset(),
    AttemptState.SEALED_KNOWN: frozenset(),
    AttemptState.SEALED_UNCERTAIN: frozenset(),
}


@runtime_checkable
class DurableLedgerPublisher(Protocol):
    """Narrow persistence boundary required by both cell-global ledgers.

    Implementations must reject unqualified volumes, reparse/symlink/hardlink
    surprises, traversal, short writes, and stale expected heads.  They must
    publish the immutable event before atomically advancing ``head.json`` and
    make both durable before returning.  None of those OS-specific claims are
    emulated by this application-layer module.
    """

    def qualification_sha256(self, root: Path) -> str:
        """Return the current on-volume qualification receipt hash or raise."""

    def initialize_ledger(
        self, root: Path, *, header_payload: bytes, head_payload: bytes
    ) -> None:
        """Create a new ledger with exactly its immutable header and head."""

    def read_bounded(
        self, root: Path, relative_path: str, *, maximum_bytes: int
    ) -> bytes:
        """Read one regular owned file without following links."""

    def list_relative_files(
        self, root: Path, *, maximum_entries: int
    ) -> tuple[str, ...]:
        """Return normalized POSIX relative file names without following links."""

    def commit_append(
        self,
        root: Path,
        *,
        event_relative_path: str,
        event_payload: bytes,
        head_payload: bytes,
        expected_head_sha256: str,
    ) -> None:
        """Durably append once and CAS-advance the independently owned head."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the one accepted JSON encoding for a ledger-owned document."""

    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingAttemptError(
            "attempt ledger value is not strict canonical JSON"
        ) from exc


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise AttemptLedgerIntegrityError(f"duplicate JSON field {key!r}")
        document[key] = value
    return document


def _reject_float(value: str) -> None:
    raise AttemptLedgerIntegrityError(f"JSON floating point is forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise AttemptLedgerIntegrityError(f"non-finite JSON value is forbidden: {value}")


def parse_canonical_json(payload: bytes, label: str) -> dict[str, Any]:
    if not isinstance(payload, bytes):
        raise AttemptLedgerIntegrityError(f"{label} payload is not bytes")
    if not payload or len(payload) > MAX_JSON_BYTES:
        raise AttemptLedgerIntegrityError(f"{label} exceeds the JSON resource bound")
    try:
        decoded = payload.decode("ascii")
        value = json.loads(
            decoded,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttemptLedgerIntegrityError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise AttemptLedgerIntegrityError(f"{label} must be a JSON object")
    if canonical_json_bytes(value) != payload:
        raise AttemptLedgerIntegrityError(f"{label} is not canonical JSON")
    return value


def _exact_fields(document: dict[str, Any], fields: frozenset[str], label: str) -> None:
    present = frozenset(document)
    if present != fields:
        missing = sorted(fields - present)
        extra = sorted(present - fields)
        raise AttemptLedgerIntegrityError(
            f"{label} fields differ (missing={missing}, extra={extra})"
        )


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise PhysicalOnboardingAttemptError(f"{label} is not a bounded identifier")
    return value


def _operation(value: object) -> str:
    if not isinstance(value, str) or _OPERATION_RE.fullmatch(value) is None:
        raise PhysicalOnboardingAttemptError(
            "operation_id is not bounded and canonical"
        )
    return value


def _digest(value: object, label: str, *, allow_zero: bool = True) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PhysicalOnboardingAttemptError(f"{label} is not a lowercase SHA-256")
    if not allow_zero and value == ZERO_SHA256:
        raise PhysicalOnboardingAttemptError(f"{label} cannot be the zero digest")
    return value


def _bounded_int(value: object, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PhysicalOnboardingAttemptError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise PhysicalOnboardingAttemptError(f"{label} is outside its resource bound")
    return value


def _timestamp(value: object, label: str) -> int:
    return _bounded_int(value, label, 1, (1 << 63) - 1)


def _ledger_root(root: Path) -> Path:
    if not isinstance(root, Path):
        raise TypeError("ledger root must be pathlib.Path")
    rendered = str(root)
    if not root.is_absolute() or len(rendered) > MAX_LEDGER_PATH_CHARS:
        raise PhysicalOnboardingAttemptError(
            "ledger root must be a bounded absolute path"
        )
    if root.parent == root or len(root.parts) > MAX_LEDGER_PATH_PARTS:
        raise PhysicalOnboardingAttemptError(
            "ledger root is too broad or deeply nested"
        )
    if any(part in {"", ".", ".."} for part in root.parts[1:]):
        raise PhysicalOnboardingAttemptError("ledger root contains traversal")
    return root


def _relative_name(value: str) -> str:
    if not isinstance(value, str) or "\\" in value or len(value) > 64:
        raise AttemptLedgerIntegrityError(
            "publisher returned a malformed relative path"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise AttemptLedgerIntegrityError("publisher returned path traversal")
    return value


def _enum_value(enum_type: type[Enum], value: object, label: str) -> Enum:
    if not isinstance(value, str):
        raise PhysicalOnboardingAttemptError(f"{label} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise PhysicalOnboardingAttemptError(f"unknown {label} {value!r}") from exc


_HEADER_FIELDS = frozenset(
    {
        "schema",
        "ledger_kind",
        "ledger_id",
        "cell_id",
        "created_at_ns",
        "durability_qualification_sha256",
        "maximum_events",
        "runtime_activation",
        "physical_authority",
        "automatic_retry_allowed",
        "header_sha256",
    }
)
_HEAD_FIELDS = frozenset(
    {
        "schema",
        "ledger_id",
        "cell_id",
        "header_sha256",
        "event_count",
        "last_sequence",
        "last_event_sha256",
        "head_sha256",
    }
)
_EVENT_FIELDS = frozenset(
    {
        "schema",
        "ledger_id",
        "cell_id",
        "sequence",
        "attempt_id",
        "session_id",
        "stage",
        "effect_class",
        "operation_id",
        "operation_binding_sha256",
        "source_binding_sha256",
        "stage_plan_sha256",
        "session_journal_head_sha256",
        "evidence_inventory_sha256",
        "state",
        "intent_at_ns",
        "occurred_at_ns",
        "attempt_head_before_sha256",
        "quarantine_head_sha256",
        "previous_event_sha256",
        "previous_attempt_event_sha256",
        "durability_qualification_sha256",
        "physical_authority",
        "automatic_retry_allowed",
        "event_sha256",
    }
)


def _hashed_document(document: dict[str, Any], hash_field: str) -> dict[str, Any]:
    if hash_field in document:
        raise ValueError(f"hash field {hash_field} already present")
    sealed = dict(document)
    sealed[hash_field] = sha256_bytes(canonical_json_bytes(document))
    return sealed


def _validate_self_hash(document: dict[str, Any], hash_field: str, label: str) -> str:
    recorded = _digest(document[hash_field], f"{label} {hash_field}", allow_zero=False)
    unsigned = dict(document)
    del unsigned[hash_field]
    actual = sha256_bytes(canonical_json_bytes(unsigned))
    if recorded != actual:
        raise AttemptLedgerIntegrityError(f"{label} self hash mismatch")
    return recorded


@dataclass(frozen=True)
class AttemptBinding:
    """Immutable identity and provenance bound by an attempt intent."""

    attempt_id: str
    session_id: str
    stage: str
    effect_class: EffectClass
    operation_id: str
    operation_binding_sha256: str
    source_binding_sha256: str
    stage_plan_sha256: str
    session_journal_head_sha256: str
    evidence_inventory_sha256: str
    intent_at_ns: int

    def __post_init__(self) -> None:
        _identifier(self.attempt_id, "attempt_id")
        _identifier(self.session_id, "session_id")
        if not isinstance(self.stage, str) or self.stage not in _STAGES:
            raise PhysicalOnboardingAttemptError(
                "stage is not in the canonical stage order"
            )
        if not isinstance(self.effect_class, EffectClass):
            raise TypeError("effect_class must be EffectClass")
        _operation(self.operation_id)
        _digest(
            self.operation_binding_sha256, "operation_binding_sha256", allow_zero=False
        )
        _digest(self.source_binding_sha256, "source_binding_sha256", allow_zero=False)
        _digest(self.stage_plan_sha256, "stage_plan_sha256", allow_zero=False)
        _digest(self.session_journal_head_sha256, "session_journal_head_sha256")
        _digest(self.evidence_inventory_sha256, "evidence_inventory_sha256")
        _timestamp(self.intent_at_ns, "intent_at_ns")


@dataclass(frozen=True)
class AttemptEvent:
    ledger_id: str
    cell_id: str
    sequence: int
    attempt_id: str
    session_id: str
    stage: str
    effect_class: EffectClass
    operation_id: str
    operation_binding_sha256: str
    source_binding_sha256: str
    stage_plan_sha256: str
    session_journal_head_sha256: str
    evidence_inventory_sha256: str
    state: AttemptState
    intent_at_ns: int
    occurred_at_ns: int
    attempt_head_before_sha256: str
    quarantine_head_sha256: str
    previous_event_sha256: str
    previous_attempt_event_sha256: str
    durability_qualification_sha256: str
    event_sha256: str

    @property
    def context_key(self) -> tuple[object, ...]:
        return (
            self.cell_id,
            self.attempt_id,
            self.session_id,
            self.stage,
            self.effect_class,
            self.operation_id,
            self.operation_binding_sha256,
            self.source_binding_sha256,
            self.stage_plan_sha256,
            self.intent_at_ns,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ATTEMPT_LEDGER_EVENT_SCHEMA,
            "ledger_id": self.ledger_id,
            "cell_id": self.cell_id,
            "sequence": self.sequence,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "stage": self.stage,
            "effect_class": self.effect_class.value,
            "operation_id": self.operation_id,
            "operation_binding_sha256": self.operation_binding_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "stage_plan_sha256": self.stage_plan_sha256,
            "session_journal_head_sha256": self.session_journal_head_sha256,
            "evidence_inventory_sha256": self.evidence_inventory_sha256,
            "state": self.state.value,
            "intent_at_ns": self.intent_at_ns,
            "occurred_at_ns": self.occurred_at_ns,
            "attempt_head_before_sha256": self.attempt_head_before_sha256,
            "quarantine_head_sha256": self.quarantine_head_sha256,
            "previous_event_sha256": self.previous_event_sha256,
            "previous_attempt_event_sha256": self.previous_attempt_event_sha256,
            "durability_qualification_sha256": self.durability_qualification_sha256,
            "physical_authority": False,
            "automatic_retry_allowed": False,
            "event_sha256": self.event_sha256,
        }


@dataclass(frozen=True)
class AttemptLedgerSnapshot:
    ledger_id: str
    cell_id: str
    header_sha256: str
    durability_qualification_sha256: str
    head_sha256: str
    events: tuple[AttemptEvent, ...]

    def latest_event(self, attempt_id: str) -> AttemptEvent | None:
        _identifier(attempt_id, "attempt_id")
        for event in reversed(self.events):
            if event.attempt_id == attempt_id:
                return event
        return None

    def head_sha256_after(self, event: AttemptEvent) -> str:
        """Reconstruct the committed-head hash immediately after ``event``."""

        if not isinstance(event, AttemptEvent):
            raise TypeError("event must be AttemptEvent")
        if (
            event.ledger_id != self.ledger_id
            or event.cell_id != self.cell_id
            or event.sequence < 0
            or event.sequence >= len(self.events)
            or self.events[event.sequence] != event
        ):
            raise AttemptLedgerIntegrityError(
                "attempt event is not part of this exact ledger snapshot"
            )
        return _head_document(
            ledger_id=self.ledger_id,
            cell_id=self.cell_id,
            header_sha256=self.header_sha256,
            event_count=event.sequence + 1,
            last_event_sha256=event.event_sha256,
        )["head_sha256"]

    @property
    def latest_events(self) -> tuple[AttemptEvent, ...]:
        latest: dict[str, AttemptEvent] = {}
        order: list[str] = []
        for event in self.events:
            if event.attempt_id not in latest:
                order.append(event.attempt_id)
            latest[event.attempt_id] = event
        return tuple(latest[attempt_id] for attempt_id in order)

    @property
    def unresolved_events(self) -> tuple[AttemptEvent, ...]:
        return tuple(
            event
            for event in self.latest_events
            if event.state not in TERMINAL_ATTEMPT_STATES
        )

    @property
    def uncertain_events(self) -> tuple[AttemptEvent, ...]:
        return tuple(
            event
            for event in self.latest_events
            if event.state is AttemptState.SEALED_UNCERTAIN
        )


def _header_document(
    *,
    ledger_id: str,
    cell_id: str,
    created_at_ns: int,
    qualification_sha256: str,
) -> dict[str, Any]:
    return _hashed_document(
        {
            "schema": ATTEMPT_LEDGER_HEADER_SCHEMA,
            "ledger_kind": "CELL_GLOBAL_PHYSICAL_EFFECT_ATTEMPTS",
            "ledger_id": ledger_id,
            "cell_id": cell_id,
            "created_at_ns": created_at_ns,
            "durability_qualification_sha256": qualification_sha256,
            "maximum_events": MAX_ATTEMPT_EVENTS,
            "runtime_activation": False,
            "physical_authority": False,
            "automatic_retry_allowed": False,
        },
        "header_sha256",
    )


def _head_document(
    *,
    ledger_id: str,
    cell_id: str,
    header_sha256: str,
    event_count: int,
    last_event_sha256: str,
) -> dict[str, Any]:
    return _hashed_document(
        {
            "schema": ATTEMPT_LEDGER_HEAD_SCHEMA,
            "ledger_id": ledger_id,
            "cell_id": cell_id,
            "header_sha256": header_sha256,
            "event_count": event_count,
            "last_sequence": event_count - 1,
            "last_event_sha256": last_event_sha256,
        },
        "head_sha256",
    )


def _parse_header(document: dict[str, Any]) -> tuple[str, str, str, str]:
    _exact_fields(document, _HEADER_FIELDS, "attempt header")
    if document["schema"] != ATTEMPT_LEDGER_HEADER_SCHEMA:
        raise AttemptLedgerIntegrityError("unknown attempt header schema")
    if document["ledger_kind"] != "CELL_GLOBAL_PHYSICAL_EFFECT_ATTEMPTS":
        raise AttemptLedgerIntegrityError("attempt ledger kind changed")
    ledger_id = _identifier(document["ledger_id"], "ledger_id")
    cell_id = _identifier(document["cell_id"], "cell_id")
    _timestamp(document["created_at_ns"], "created_at_ns")
    qualification = _digest(
        document["durability_qualification_sha256"],
        "durability_qualification_sha256",
        allow_zero=False,
    )
    if document["maximum_events"] != MAX_ATTEMPT_EVENTS:
        raise AttemptLedgerIntegrityError("attempt event resource policy changed")
    if (
        document["runtime_activation"] is not False
        or document["physical_authority"] is not False
        or document["automatic_retry_allowed"] is not False
    ):
        raise AttemptLedgerIntegrityError("attempt header claims authority or retry")
    header_hash = _validate_self_hash(document, "header_sha256", "attempt header")
    return ledger_id, cell_id, qualification, header_hash


def _parse_head(
    document: dict[str, Any], *, ledger_id: str, cell_id: str, header_sha256: str
) -> tuple[int, str, str]:
    _exact_fields(document, _HEAD_FIELDS, "attempt head")
    if document["schema"] != ATTEMPT_LEDGER_HEAD_SCHEMA:
        raise AttemptLedgerIntegrityError("unknown attempt head schema")
    if (
        document["ledger_id"] != ledger_id
        or document["cell_id"] != cell_id
        or document["header_sha256"] != header_sha256
    ):
        raise AttemptLedgerIntegrityError("attempt head identity binding mismatch")
    count = _bounded_int(document["event_count"], "event_count", 0, MAX_ATTEMPT_EVENTS)
    if document["last_sequence"] != count - 1:
        raise AttemptLedgerIntegrityError("attempt head sequence/count mismatch")
    last_hash = _digest(document["last_event_sha256"], "last_event_sha256")
    if (count == 0) != (last_hash == ZERO_SHA256):
        raise AttemptLedgerIntegrityError("attempt empty head hash mismatch")
    head_hash = _validate_self_hash(document, "head_sha256", "attempt head")
    return count, last_hash, head_hash


def _parse_event(document: dict[str, Any]) -> AttemptEvent:
    _exact_fields(document, _EVENT_FIELDS, "attempt event")
    if document["schema"] != ATTEMPT_LEDGER_EVENT_SCHEMA:
        raise AttemptLedgerIntegrityError("unknown attempt event schema")
    if document["physical_authority"] is not False:
        raise AttemptLedgerIntegrityError("attempt event claims physical authority")
    if document["automatic_retry_allowed"] is not False:
        raise AttemptLedgerIntegrityError("attempt event claims retry authority")
    event_hash = _validate_self_hash(document, "event_sha256", "attempt event")
    stage = document["stage"]
    if not isinstance(stage, str) or stage not in _STAGES:
        raise AttemptLedgerIntegrityError("attempt event has an unknown stage")
    try:
        effect_class = EffectClass(document["effect_class"])
        state = AttemptState(document["state"])
    except (TypeError, ValueError) as exc:
        raise AttemptLedgerIntegrityError("attempt event enum is unknown") from exc
    try:
        return AttemptEvent(
            ledger_id=_identifier(document["ledger_id"], "ledger_id"),
            cell_id=_identifier(document["cell_id"], "cell_id"),
            sequence=_bounded_int(
                document["sequence"], "sequence", 0, MAX_ATTEMPT_EVENTS - 1
            ),
            attempt_id=_identifier(document["attempt_id"], "attempt_id"),
            session_id=_identifier(document["session_id"], "session_id"),
            stage=stage,
            effect_class=effect_class,
            operation_id=_operation(document["operation_id"]),
            operation_binding_sha256=_digest(
                document["operation_binding_sha256"],
                "operation_binding_sha256",
                allow_zero=False,
            ),
            source_binding_sha256=_digest(
                document["source_binding_sha256"],
                "source_binding_sha256",
                allow_zero=False,
            ),
            stage_plan_sha256=_digest(
                document["stage_plan_sha256"], "stage_plan_sha256", allow_zero=False
            ),
            session_journal_head_sha256=_digest(
                document["session_journal_head_sha256"],
                "session_journal_head_sha256",
            ),
            evidence_inventory_sha256=_digest(
                document["evidence_inventory_sha256"],
                "evidence_inventory_sha256",
            ),
            state=state,
            intent_at_ns=_timestamp(document["intent_at_ns"], "intent_at_ns"),
            occurred_at_ns=_timestamp(document["occurred_at_ns"], "occurred_at_ns"),
            attempt_head_before_sha256=_digest(
                document["attempt_head_before_sha256"],
                "attempt_head_before_sha256",
                allow_zero=False,
            ),
            quarantine_head_sha256=_digest(
                document["quarantine_head_sha256"],
                "quarantine_head_sha256",
                allow_zero=False,
            ),
            previous_event_sha256=_digest(
                document["previous_event_sha256"], "previous_event_sha256"
            ),
            previous_attempt_event_sha256=_digest(
                document["previous_attempt_event_sha256"],
                "previous_attempt_event_sha256",
            ),
            durability_qualification_sha256=_digest(
                document["durability_qualification_sha256"],
                "durability_qualification_sha256",
                allow_zero=False,
            ),
            event_sha256=event_hash,
        )
    except PhysicalOnboardingAttemptError as exc:
        raise AttemptLedgerIntegrityError(str(exc)) from exc


class PhysicalOnboardingAttemptLedger:
    """One cell's globally serialized physical-effect attempt chain."""

    def __init__(
        self,
        root: Path,
        publisher: DurableLedgerPublisher,
        *,
        expected_cell_id: str,
    ) -> None:
        self._root = _ledger_root(root)
        if not isinstance(publisher, DurableLedgerPublisher):
            raise TypeError("publisher does not implement DurableLedgerPublisher")
        self._publisher = publisher
        self._expected_cell_id = _identifier(expected_cell_id, "expected_cell_id")

    @classmethod
    def create(
        cls,
        root: Path,
        publisher: DurableLedgerPublisher,
        *,
        ledger_id: str,
        cell_id: str,
        created_at_ns: int,
    ) -> "PhysicalOnboardingAttemptLedger":
        root = _ledger_root(root)
        ledger_id = _identifier(ledger_id, "ledger_id")
        cell_id = _identifier(cell_id, "cell_id")
        created_at_ns = _timestamp(created_at_ns, "created_at_ns")
        qualification = _digest(
            publisher.qualification_sha256(root),
            "durability qualification",
            allow_zero=False,
        )
        header = _header_document(
            ledger_id=ledger_id,
            cell_id=cell_id,
            created_at_ns=created_at_ns,
            qualification_sha256=qualification,
        )
        head = _head_document(
            ledger_id=ledger_id,
            cell_id=cell_id,
            header_sha256=header["header_sha256"],
            event_count=0,
            last_event_sha256=ZERO_SHA256,
        )
        publisher.initialize_ledger(
            root,
            header_payload=canonical_json_bytes(header),
            head_payload=canonical_json_bytes(head),
        )
        ledger = cls(root, publisher, expected_cell_id=cell_id)
        ledger.snapshot(expected_head_sha256=head["head_sha256"])
        return ledger

    @classmethod
    def open(
        cls,
        root: Path,
        publisher: DurableLedgerPublisher,
        *,
        expected_cell_id: str,
        expected_head_sha256: str | None = None,
    ) -> "PhysicalOnboardingAttemptLedger":
        ledger = cls(root, publisher, expected_cell_id=expected_cell_id)
        ledger.snapshot(expected_head_sha256=expected_head_sha256)
        return ledger

    @property
    def root(self) -> Path:
        return self._root

    @property
    def cell_id(self) -> str:
        return self._expected_cell_id

    def snapshot(
        self, *, expected_head_sha256: str | None = None
    ) -> AttemptLedgerSnapshot:
        qualification = _digest(
            self._publisher.qualification_sha256(self._root),
            "durability qualification",
            allow_zero=False,
        )
        header_document = parse_canonical_json(
            self._publisher.read_bounded(
                self._root, "header.json", maximum_bytes=MAX_JSON_BYTES
            ),
            "attempt header",
        )
        ledger_id, cell_id, header_qualification, header_hash = _parse_header(
            header_document
        )
        if cell_id != self._expected_cell_id:
            raise AttemptLedgerIntegrityError("attempt ledger belongs to another cell")
        if qualification != header_qualification:
            raise AttemptLedgerIntegrityError(
                "attempt ledger volume qualification no longer matches its header"
            )
        head_document = parse_canonical_json(
            self._publisher.read_bounded(
                self._root, "head.json", maximum_bytes=MAX_JSON_BYTES
            ),
            "attempt head",
        )
        count, last_event_hash, head_hash = _parse_head(
            head_document,
            ledger_id=ledger_id,
            cell_id=cell_id,
            header_sha256=header_hash,
        )
        if expected_head_sha256 is not None:
            expected = _digest(
                expected_head_sha256, "expected_head_sha256", allow_zero=False
            )
            if head_hash != expected:
                raise AttemptLedgerIntegrityError(
                    "attempt committed-head anchor mismatch"
                )

        listed = tuple(
            _relative_name(name)
            for name in self._publisher.list_relative_files(
                self._root, maximum_entries=MAX_ATTEMPT_EVENTS + 3
            )
        )
        if len(set(listed)) != len(listed):
            raise AttemptLedgerIntegrityError(
                "publisher returned duplicate ledger paths"
            )
        expected_files = {
            "header.json",
            "head.json",
            *(f"events/event-{sequence:08d}.json" for sequence in range(count)),
        }
        present = set(listed)
        if present != expected_files:
            event_indexes = []
            for name in present:
                match = _EVENT_NAME_RE.fullmatch(name)
                if match is not None:
                    event_indexes.append(int(match.group(1)))
            if any(index >= count for index in event_indexes) or any(
                f"events/event-{sequence:08d}.json" not in present
                for sequence in range(count)
            ):
                raise AttemptLedgerSuffixError(
                    "attempt event suffix differs from the independently committed head"
                )
            raise AttemptLedgerIntegrityError("attempt ledger contains an unknown path")

        events: list[AttemptEvent] = []
        latest: dict[str, AttemptEvent] = {}
        previous_global_hash = ZERO_SHA256
        previous_head_hash = _head_document(
            ledger_id=ledger_id,
            cell_id=cell_id,
            header_sha256=header_hash,
            event_count=0,
            last_event_sha256=ZERO_SHA256,
        )["head_sha256"]
        previous_timestamp = 0
        for sequence in range(count):
            relative_path = f"events/event-{sequence:08d}.json"
            event = _parse_event(
                parse_canonical_json(
                    self._publisher.read_bounded(
                        self._root, relative_path, maximum_bytes=MAX_JSON_BYTES
                    ),
                    f"attempt event {sequence}",
                )
            )
            if (
                event.ledger_id != ledger_id
                or event.cell_id != cell_id
                or event.sequence != sequence
            ):
                raise AttemptLedgerIntegrityError(
                    "attempt event identity/sequence mismatch"
                )
            if event.durability_qualification_sha256 != qualification:
                raise AttemptLedgerIntegrityError(
                    "attempt event durability qualification mismatch"
                )
            if event.previous_event_sha256 != previous_global_hash:
                raise AttemptLedgerIntegrityError("attempt global hash chain is broken")
            if event.attempt_head_before_sha256 != previous_head_hash:
                raise AttemptLedgerIntegrityError(
                    "attempt event did not bind its prior head"
                )
            if event.occurred_at_ns < event.intent_at_ns:
                raise AttemptLedgerIntegrityError("attempt event predates its intent")
            if event.occurred_at_ns < previous_timestamp:
                raise AttemptLedgerIntegrityError(
                    "attempt event timestamps moved backwards"
                )

            prior = latest.get(event.attempt_id)
            if prior is None:
                if event.state is not AttemptState.INTENT_DURABLE:
                    raise AttemptLedgerIntegrityError(
                        "attempt does not begin with durable intent"
                    )
                if event.previous_attempt_event_sha256 != ZERO_SHA256:
                    raise AttemptLedgerIntegrityError(
                        "new attempt has an attempt predecessor"
                    )
                if any(
                    item.state not in TERMINAL_ATTEMPT_STATES
                    for item in latest.values()
                ):
                    raise AttemptLedgerIntegrityError(
                        "a new intent overlaps an unresolved cell-global attempt"
                    )
            else:
                if event.context_key != prior.context_key:
                    raise AttemptLedgerIntegrityError(
                        "attempt identity/provenance drifted"
                    )
                if event.previous_attempt_event_sha256 != prior.event_sha256:
                    raise AttemptLedgerIntegrityError(
                        "attempt-local hash chain is broken"
                    )
                if event.state not in _TRANSITIONS[prior.state]:
                    raise AttemptLedgerIntegrityError(
                        "attempt state transition is invalid"
                    )
                if event.occurred_at_ns < prior.occurred_at_ns:
                    raise AttemptLedgerIntegrityError(
                        "attempt timestamp moved backwards"
                    )

            latest[event.attempt_id] = event
            events.append(event)
            previous_global_hash = event.event_sha256
            previous_timestamp = event.occurred_at_ns
            previous_head_hash = _head_document(
                ledger_id=ledger_id,
                cell_id=cell_id,
                header_sha256=header_hash,
                event_count=sequence + 1,
                last_event_sha256=event.event_sha256,
            )["head_sha256"]

        if previous_global_hash != last_event_hash or previous_head_hash != head_hash:
            raise AttemptLedgerIntegrityError(
                "attempt committed head does not bind its chain"
            )
        return AttemptLedgerSnapshot(
            ledger_id=ledger_id,
            cell_id=cell_id,
            header_sha256=header_hash,
            durability_qualification_sha256=qualification,
            head_sha256=head_hash,
            events=tuple(events),
        )

    def begin_attempt(
        self,
        binding: AttemptBinding,
        quarantine_ledger: object,
    ) -> AttemptEvent:
        """Append durable intent after consulting the real cell quarantine ledger."""

        from rocell.application.physical_onboarding_quarantine import (
            PhysicalOnboardingQuarantineLedger,
        )

        if not isinstance(quarantine_ledger, PhysicalOnboardingQuarantineLedger):
            raise TypeError(
                "quarantine_ledger must be PhysicalOnboardingQuarantineLedger"
            )
        if not isinstance(binding, AttemptBinding):
            raise TypeError("binding must be AttemptBinding")
        quarantine_head = quarantine_ledger.assert_effects_allowed(self)
        snapshot = self.snapshot()
        if snapshot.unresolved_events:
            raise AttemptTransitionError("another cell-global attempt is unresolved")
        if snapshot.latest_event(binding.attempt_id) is not None:
            raise AttemptTransitionError("an attempt identifier can never be reused")
        return self._append(
            snapshot=snapshot,
            binding=binding,
            prior=None,
            state=AttemptState.INTENT_DURABLE,
            occurred_at_ns=binding.intent_at_ns,
            session_journal_head_sha256=binding.session_journal_head_sha256,
            evidence_inventory_sha256=binding.evidence_inventory_sha256,
            quarantine_head_sha256=quarantine_head,
        )

    def transition(
        self,
        attempt_id: str,
        state: AttemptState,
        quarantine_ledger: object,
        *,
        occurred_at_ns: int,
        session_journal_head_sha256: str | None = None,
        evidence_inventory_sha256: str | None = None,
    ) -> AttemptEvent:
        """Append exactly one legal state transition, without any automatic retry."""

        from rocell.application.physical_onboarding_quarantine import (
            PhysicalOnboardingQuarantineLedger,
        )

        if not isinstance(quarantine_ledger, PhysicalOnboardingQuarantineLedger):
            raise TypeError(
                "quarantine_ledger must be PhysicalOnboardingQuarantineLedger"
            )
        attempt_id = _identifier(attempt_id, "attempt_id")
        if not isinstance(state, AttemptState):
            raise TypeError("state must be AttemptState")
        occurred_at_ns = _timestamp(occurred_at_ns, "occurred_at_ns")
        snapshot = self.snapshot()
        prior = snapshot.latest_event(attempt_id)
        if prior is None:
            raise AttemptTransitionError("unknown attempt identifier")
        if state not in _TRANSITIONS[prior.state]:
            raise AttemptTransitionError(
                f"invalid attempt transition {prior.state.value} -> {state.value}"
            )
        if occurred_at_ns < prior.occurred_at_ns:
            raise AttemptTransitionError("attempt timestamp cannot move backwards")
        journal_hash = (
            prior.session_journal_head_sha256
            if session_journal_head_sha256 is None
            else _digest(session_journal_head_sha256, "session_journal_head_sha256")
        )
        evidence_hash = (
            prior.evidence_inventory_sha256
            if evidence_inventory_sha256 is None
            else _digest(evidence_inventory_sha256, "evidence_inventory_sha256")
        )
        quarantine_head = quarantine_ledger.binding_head(self)
        binding = AttemptBinding(
            attempt_id=prior.attempt_id,
            session_id=prior.session_id,
            stage=prior.stage,
            effect_class=prior.effect_class,
            operation_id=prior.operation_id,
            operation_binding_sha256=prior.operation_binding_sha256,
            source_binding_sha256=prior.source_binding_sha256,
            stage_plan_sha256=prior.stage_plan_sha256,
            session_journal_head_sha256=journal_hash,
            evidence_inventory_sha256=evidence_hash,
            intent_at_ns=prior.intent_at_ns,
        )
        return self._append(
            snapshot=snapshot,
            binding=binding,
            prior=prior,
            state=state,
            occurred_at_ns=occurred_at_ns,
            session_journal_head_sha256=journal_hash,
            evidence_inventory_sha256=evidence_hash,
            quarantine_head_sha256=quarantine_head,
        )

    def _append(
        self,
        *,
        snapshot: AttemptLedgerSnapshot,
        binding: AttemptBinding,
        prior: AttemptEvent | None,
        state: AttemptState,
        occurred_at_ns: int,
        session_journal_head_sha256: str,
        evidence_inventory_sha256: str,
        quarantine_head_sha256: str,
    ) -> AttemptEvent:
        sequence = len(snapshot.events)
        if sequence >= MAX_ATTEMPT_EVENTS:
            raise AttemptTransitionError("attempt ledger event bound is exhausted")
        if snapshot.events and occurred_at_ns < snapshot.events[-1].occurred_at_ns:
            raise AttemptTransitionError(
                "global attempt timestamp cannot move backwards"
            )
        qualification = _digest(
            self._publisher.qualification_sha256(self._root),
            "durability qualification",
            allow_zero=False,
        )
        if qualification != snapshot.durability_qualification_sha256:
            raise AttemptLedgerIntegrityError(
                "attempt volume qualification changed during append"
            )
        previous_global_hash = (
            snapshot.events[-1].event_sha256 if snapshot.events else ZERO_SHA256
        )
        unsigned: dict[str, Any] = {
            "schema": ATTEMPT_LEDGER_EVENT_SCHEMA,
            "ledger_id": snapshot.ledger_id,
            "cell_id": snapshot.cell_id,
            "sequence": sequence,
            "attempt_id": binding.attempt_id,
            "session_id": binding.session_id,
            "stage": binding.stage,
            "effect_class": binding.effect_class.value,
            "operation_id": binding.operation_id,
            "operation_binding_sha256": binding.operation_binding_sha256,
            "source_binding_sha256": binding.source_binding_sha256,
            "stage_plan_sha256": binding.stage_plan_sha256,
            "session_journal_head_sha256": session_journal_head_sha256,
            "evidence_inventory_sha256": evidence_inventory_sha256,
            "state": state.value,
            "intent_at_ns": binding.intent_at_ns,
            "occurred_at_ns": occurred_at_ns,
            "attempt_head_before_sha256": snapshot.head_sha256,
            "quarantine_head_sha256": quarantine_head_sha256,
            "previous_event_sha256": previous_global_hash,
            "previous_attempt_event_sha256": (
                prior.event_sha256 if prior is not None else ZERO_SHA256
            ),
            "durability_qualification_sha256": qualification,
            "physical_authority": False,
            "automatic_retry_allowed": False,
        }
        event_document = _hashed_document(unsigned, "event_sha256")
        event = _parse_event(event_document)
        head_document = _head_document(
            ledger_id=snapshot.ledger_id,
            cell_id=snapshot.cell_id,
            header_sha256=snapshot.header_sha256,
            event_count=sequence + 1,
            last_event_sha256=event.event_sha256,
        )
        self._publisher.commit_append(
            self._root,
            event_relative_path=f"events/event-{sequence:08d}.json",
            event_payload=canonical_json_bytes(event_document),
            head_payload=canonical_json_bytes(head_document),
            expected_head_sha256=snapshot.head_sha256,
        )
        return event


# Concise aliases for integrations while retaining domain-specific names.
GlobalAttemptLedger = PhysicalOnboardingAttemptLedger


__all__ = [
    "ARMED_UNSEALED_STATES",
    "ATTEMPT_LEDGER_EVENT_SCHEMA",
    "ATTEMPT_LEDGER_HEAD_SCHEMA",
    "ATTEMPT_LEDGER_HEADER_SCHEMA",
    "AttemptBinding",
    "AttemptEvent",
    "AttemptLedgerIntegrityError",
    "AttemptLedgerSnapshot",
    "AttemptLedgerSuffixError",
    "AttemptState",
    "AttemptTransitionError",
    "DurableLedgerPublisher",
    "GlobalAttemptLedger",
    "MAX_ATTEMPT_EVENTS",
    "PhysicalOnboardingAttemptError",
    "PhysicalOnboardingAttemptLedger",
    "TERMINAL_ATTEMPT_STATES",
    "ZERO_SHA256",
    "canonical_json_bytes",
    "parse_canonical_json",
    "sha256_bytes",
]
