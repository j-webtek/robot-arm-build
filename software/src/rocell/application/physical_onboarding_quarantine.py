"""Permanent cell-global quarantine and conservative startup recovery.

The quarantine is a separate append-only hash chain with its own committed
head.  It can latch a cell but exposes no clearing API.  Startup recovery only
writes evidence state: intent-only attempts are aborted before effect, while
anything already armed is sealed uncertain and permanently latched.  Nothing
in this module can open a device, issue a permit, dispatch work, or retry an
effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rocell.application.physical_onboarding_attempts import (
    ARMED_UNSEALED_STATES,
    MAX_ATTEMPT_EVENTS,
    MAX_JSON_BYTES,
    ZERO_SHA256,
    AttemptEvent,
    AttemptLedgerIntegrityError,
    AttemptLedgerSnapshot,
    AttemptState,
    DurableLedgerPublisher,
    PhysicalOnboardingAttemptError,
    PhysicalOnboardingAttemptLedger,
    _bounded_int,
    _digest,
    _exact_fields,
    _hashed_document,
    _identifier,
    _ledger_root,
    _operation,
    _relative_name,
    _STAGES,
    _timestamp,
    _validate_self_hash,
    canonical_json_bytes,
    parse_canonical_json,
)
from rocell.safety.effects import EffectClass


QUARANTINE_LEDGER_HEADER_SCHEMA = "rocell.physical_onboarding_quarantine_header.v1"
QUARANTINE_LEDGER_EVENT_SCHEMA = "rocell.physical_onboarding_quarantine_event.v1"
QUARANTINE_LEDGER_HEAD_SCHEMA = "rocell.physical_onboarding_quarantine_head.v1"
MAX_QUARANTINE_EVENTS = MAX_ATTEMPT_EVENTS


class PhysicalOnboardingQuarantineError(ValueError):
    """The cell-global quarantine cannot be trusted or changed as requested."""


class QuarantineLedgerIntegrityError(PhysicalOnboardingQuarantineError):
    """The committed quarantine chain cannot be reconstructed exactly."""


class QuarantineLedgerSuffixError(QuarantineLedgerIntegrityError):
    """The immutable event suffix disagrees with the committed head."""


class CellQuarantinedError(PhysicalOnboardingQuarantineError):
    """No new cell effect may begin until separately specified reconciliation."""


class QuarantineReason(str, Enum):
    """Frozen catalog reasons which globally latch the cell."""

    INCIDENT_HOLD = "INCIDENT_HOLD"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"


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
        "clearing_supported",
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
        "quarantine_id",
        "reason",
        "source_attempt_id",
        "source_attempt_event_sha256",
        "session_id",
        "stage",
        "effect_class",
        "operation_id",
        "operation_binding_sha256",
        "source_binding_sha256",
        "stage_plan_sha256",
        "session_journal_head_sha256",
        "evidence_inventory_sha256",
        "attempt_head_sha256",
        "quarantine_head_before_sha256",
        "previous_event_sha256",
        "occurred_at_ns",
        "durability_qualification_sha256",
        "physical_authority",
        "clearing_supported",
        "event_sha256",
    }
)


@dataclass(frozen=True)
class QuarantineEvent:
    ledger_id: str
    cell_id: str
    sequence: int
    quarantine_id: str
    reason: QuarantineReason
    source_attempt_id: str
    source_attempt_event_sha256: str
    session_id: str
    stage: str
    effect_class: EffectClass
    operation_id: str
    operation_binding_sha256: str
    source_binding_sha256: str
    stage_plan_sha256: str
    session_journal_head_sha256: str
    evidence_inventory_sha256: str
    attempt_head_sha256: str
    quarantine_head_before_sha256: str
    previous_event_sha256: str
    occurred_at_ns: int
    durability_qualification_sha256: str
    event_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": QUARANTINE_LEDGER_EVENT_SCHEMA,
            "ledger_id": self.ledger_id,
            "cell_id": self.cell_id,
            "sequence": self.sequence,
            "quarantine_id": self.quarantine_id,
            "reason": self.reason.value,
            "source_attempt_id": self.source_attempt_id,
            "source_attempt_event_sha256": self.source_attempt_event_sha256,
            "session_id": self.session_id,
            "stage": self.stage,
            "effect_class": self.effect_class.value,
            "operation_id": self.operation_id,
            "operation_binding_sha256": self.operation_binding_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "stage_plan_sha256": self.stage_plan_sha256,
            "session_journal_head_sha256": self.session_journal_head_sha256,
            "evidence_inventory_sha256": self.evidence_inventory_sha256,
            "attempt_head_sha256": self.attempt_head_sha256,
            "quarantine_head_before_sha256": self.quarantine_head_before_sha256,
            "previous_event_sha256": self.previous_event_sha256,
            "occurred_at_ns": self.occurred_at_ns,
            "durability_qualification_sha256": self.durability_qualification_sha256,
            "physical_authority": False,
            "clearing_supported": False,
            "event_sha256": self.event_sha256,
        }


@dataclass(frozen=True)
class QuarantineLedgerSnapshot:
    ledger_id: str
    cell_id: str
    header_sha256: str
    head_sha256: str
    events: tuple[QuarantineEvent, ...]

    @property
    def latched(self) -> bool:
        return bool(self.events)

    def event_for_attempt(self, attempt_id: str) -> QuarantineEvent | None:
        _identifier(attempt_id, "attempt_id")
        for event in self.events:
            if event.source_attempt_id == attempt_id:
                return event
        return None


@dataclass(frozen=True)
class StartupRecoveryReport:
    """Evidence-only actions completed by one bounded recovery pass."""

    aborted_pre_effect: tuple[str, ...]
    sealed_uncertain: tuple[str, ...]
    quarantines_latched: tuple[str, ...]
    final_attempt_head_sha256: str
    final_quarantine_head_sha256: str

    @property
    def changed(self) -> bool:
        return bool(
            self.aborted_pre_effect or self.sealed_uncertain or self.quarantines_latched
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
            "schema": QUARANTINE_LEDGER_HEADER_SCHEMA,
            "ledger_kind": "CELL_GLOBAL_PHYSICAL_EFFECT_QUARANTINE",
            "ledger_id": ledger_id,
            "cell_id": cell_id,
            "created_at_ns": created_at_ns,
            "durability_qualification_sha256": qualification_sha256,
            "maximum_events": MAX_QUARANTINE_EVENTS,
            "runtime_activation": False,
            "physical_authority": False,
            "clearing_supported": False,
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
            "schema": QUARANTINE_LEDGER_HEAD_SCHEMA,
            "ledger_id": ledger_id,
            "cell_id": cell_id,
            "header_sha256": header_sha256,
            "event_count": event_count,
            "last_sequence": event_count - 1,
            "last_event_sha256": last_event_sha256,
        },
        "head_sha256",
    )


def _parse_payload(payload: bytes, label: str) -> dict[str, Any]:
    try:
        return parse_canonical_json(payload, label)
    except (PhysicalOnboardingAttemptError, AttemptLedgerIntegrityError) as exc:
        raise QuarantineLedgerIntegrityError(str(exc)) from exc


def _parse_header(document: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        _exact_fields(document, _HEADER_FIELDS, "quarantine header")
        if document["schema"] != QUARANTINE_LEDGER_HEADER_SCHEMA:
            raise QuarantineLedgerIntegrityError("unknown quarantine header schema")
        if document["ledger_kind"] != "CELL_GLOBAL_PHYSICAL_EFFECT_QUARANTINE":
            raise QuarantineLedgerIntegrityError("quarantine ledger kind changed")
        ledger_id = _identifier(document["ledger_id"], "ledger_id")
        cell_id = _identifier(document["cell_id"], "cell_id")
        _timestamp(document["created_at_ns"], "created_at_ns")
        qualification = _digest(
            document["durability_qualification_sha256"],
            "durability_qualification_sha256",
            allow_zero=False,
        )
        if document["maximum_events"] != MAX_QUARANTINE_EVENTS:
            raise QuarantineLedgerIntegrityError("quarantine resource policy changed")
        if (
            document["runtime_activation"] is not False
            or document["physical_authority"] is not False
            or document["clearing_supported"] is not False
        ):
            raise QuarantineLedgerIntegrityError(
                "quarantine header claims authority or clearing support"
            )
        header_hash = _validate_self_hash(
            document, "header_sha256", "quarantine header"
        )
        return ledger_id, cell_id, qualification, header_hash
    except PhysicalOnboardingAttemptError as exc:
        raise QuarantineLedgerIntegrityError(str(exc)) from exc


def _parse_head(
    document: dict[str, Any], *, ledger_id: str, cell_id: str, header_sha256: str
) -> tuple[int, str, str]:
    try:
        _exact_fields(document, _HEAD_FIELDS, "quarantine head")
        if document["schema"] != QUARANTINE_LEDGER_HEAD_SCHEMA:
            raise QuarantineLedgerIntegrityError("unknown quarantine head schema")
        if (
            document["ledger_id"] != ledger_id
            or document["cell_id"] != cell_id
            or document["header_sha256"] != header_sha256
        ):
            raise QuarantineLedgerIntegrityError(
                "quarantine head identity binding mismatch"
            )
        count = _bounded_int(
            document["event_count"], "event_count", 0, MAX_QUARANTINE_EVENTS
        )
        if document["last_sequence"] != count - 1:
            raise QuarantineLedgerIntegrityError(
                "quarantine head sequence/count mismatch"
            )
        last_hash = _digest(document["last_event_sha256"], "last_event_sha256")
        if (count == 0) != (last_hash == ZERO_SHA256):
            raise QuarantineLedgerIntegrityError("quarantine empty head hash mismatch")
        head_hash = _validate_self_hash(document, "head_sha256", "quarantine head")
        return count, last_hash, head_hash
    except PhysicalOnboardingAttemptError as exc:
        raise QuarantineLedgerIntegrityError(str(exc)) from exc


def _parse_event(document: dict[str, Any]) -> QuarantineEvent:
    try:
        _exact_fields(document, _EVENT_FIELDS, "quarantine event")
        if document["schema"] != QUARANTINE_LEDGER_EVENT_SCHEMA:
            raise QuarantineLedgerIntegrityError("unknown quarantine event schema")
        if document["physical_authority"] is not False:
            raise QuarantineLedgerIntegrityError(
                "quarantine event claims physical authority"
            )
        if document["clearing_supported"] is not False:
            raise QuarantineLedgerIntegrityError(
                "quarantine event claims clearing support"
            )
        event_hash = _validate_self_hash(document, "event_sha256", "quarantine event")
        try:
            reason = QuarantineReason(document["reason"])
            effect_class = EffectClass(document["effect_class"])
        except (TypeError, ValueError) as exc:
            raise QuarantineLedgerIntegrityError(
                "quarantine event enum is unknown"
            ) from exc
        stage = document["stage"]
        if not isinstance(stage, str) or stage not in _STAGES:
            raise QuarantineLedgerIntegrityError(
                "quarantine event has an unknown onboarding stage"
            )
        return QuarantineEvent(
            ledger_id=_identifier(document["ledger_id"], "ledger_id"),
            cell_id=_identifier(document["cell_id"], "cell_id"),
            sequence=_bounded_int(
                document["sequence"], "sequence", 0, MAX_QUARANTINE_EVENTS - 1
            ),
            quarantine_id=_identifier(document["quarantine_id"], "quarantine_id"),
            reason=reason,
            source_attempt_id=_identifier(
                document["source_attempt_id"], "source_attempt_id"
            ),
            source_attempt_event_sha256=_digest(
                document["source_attempt_event_sha256"],
                "source_attempt_event_sha256",
                allow_zero=False,
            ),
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
            attempt_head_sha256=_digest(
                document["attempt_head_sha256"],
                "attempt_head_sha256",
                allow_zero=False,
            ),
            quarantine_head_before_sha256=_digest(
                document["quarantine_head_before_sha256"],
                "quarantine_head_before_sha256",
                allow_zero=False,
            ),
            previous_event_sha256=_digest(
                document["previous_event_sha256"], "previous_event_sha256"
            ),
            occurred_at_ns=_timestamp(document["occurred_at_ns"], "occurred_at_ns"),
            durability_qualification_sha256=_digest(
                document["durability_qualification_sha256"],
                "durability_qualification_sha256",
                allow_zero=False,
            ),
            event_sha256=event_hash,
        )
    except PhysicalOnboardingAttemptError as exc:
        raise QuarantineLedgerIntegrityError(str(exc)) from exc


class PhysicalOnboardingQuarantineLedger:
    """One cell's permanent, independently committed quarantine chain."""

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
    ) -> "PhysicalOnboardingQuarantineLedger":
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
    ) -> "PhysicalOnboardingQuarantineLedger":
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
    ) -> QuarantineLedgerSnapshot:
        qualification = _digest(
            self._publisher.qualification_sha256(self._root),
            "durability qualification",
            allow_zero=False,
        )
        header_document = _parse_payload(
            self._publisher.read_bounded(
                self._root, "header.json", maximum_bytes=MAX_JSON_BYTES
            ),
            "quarantine header",
        )
        ledger_id, cell_id, header_qualification, header_hash = _parse_header(
            header_document
        )
        if cell_id != self._expected_cell_id:
            raise QuarantineLedgerIntegrityError(
                "quarantine ledger belongs to another cell"
            )
        if qualification != header_qualification:
            raise QuarantineLedgerIntegrityError(
                "quarantine volume qualification no longer matches its header"
            )
        head_document = _parse_payload(
            self._publisher.read_bounded(
                self._root, "head.json", maximum_bytes=MAX_JSON_BYTES
            ),
            "quarantine head",
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
                raise QuarantineLedgerIntegrityError(
                    "quarantine committed-head anchor mismatch"
                )

        listed = tuple(
            _relative_name(name)
            for name in self._publisher.list_relative_files(
                self._root, maximum_entries=MAX_QUARANTINE_EVENTS + 3
            )
        )
        if len(set(listed)) != len(listed):
            raise QuarantineLedgerIntegrityError(
                "publisher returned duplicate quarantine paths"
            )
        expected_files = {
            "header.json",
            "head.json",
            *(f"events/event-{sequence:08d}.json" for sequence in range(count)),
        }
        present = set(listed)
        if present != expected_files:
            event_prefix = "events/event-"
            has_suffix = any(
                name.startswith(event_prefix) and name.endswith(".json")
                for name in present - expected_files
            )
            missing_event = any(
                f"events/event-{sequence:08d}.json" not in present
                for sequence in range(count)
            )
            if has_suffix or missing_event:
                raise QuarantineLedgerSuffixError(
                    "quarantine suffix differs from its independently committed head"
                )
            raise QuarantineLedgerIntegrityError(
                "quarantine ledger contains an unknown path"
            )

        events: list[QuarantineEvent] = []
        source_attempts: set[str] = set()
        previous_event_hash = ZERO_SHA256
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
                _parse_payload(
                    self._publisher.read_bounded(
                        self._root, relative_path, maximum_bytes=MAX_JSON_BYTES
                    ),
                    f"quarantine event {sequence}",
                )
            )
            if (
                event.ledger_id != ledger_id
                or event.cell_id != cell_id
                or event.sequence != sequence
            ):
                raise QuarantineLedgerIntegrityError(
                    "quarantine event identity/sequence mismatch"
                )
            if event.previous_event_sha256 != previous_event_hash:
                raise QuarantineLedgerIntegrityError(
                    "quarantine event hash chain is broken"
                )
            if event.quarantine_head_before_sha256 != previous_head_hash:
                raise QuarantineLedgerIntegrityError(
                    "quarantine event did not bind its prior head"
                )
            if event.durability_qualification_sha256 != qualification:
                raise QuarantineLedgerIntegrityError(
                    "quarantine event durability qualification mismatch"
                )
            if event.occurred_at_ns < previous_timestamp:
                raise QuarantineLedgerIntegrityError(
                    "quarantine timestamps moved backwards"
                )
            if event.source_attempt_id in source_attempts:
                raise QuarantineLedgerIntegrityError(
                    "one uncertain attempt has duplicate quarantine latches"
                )
            if event.reason is not QuarantineReason.SIDE_EFFECT_UNCERTAIN:
                raise QuarantineLedgerIntegrityError(
                    "this version cannot originate a non-attempt incident latch"
                )
            events.append(event)
            source_attempts.add(event.source_attempt_id)
            previous_event_hash = event.event_sha256
            previous_timestamp = event.occurred_at_ns
            previous_head_hash = _head_document(
                ledger_id=ledger_id,
                cell_id=cell_id,
                header_sha256=header_hash,
                event_count=sequence + 1,
                last_event_sha256=event.event_sha256,
            )["head_sha256"]
        if previous_event_hash != last_event_hash or previous_head_hash != head_hash:
            raise QuarantineLedgerIntegrityError(
                "quarantine committed head does not bind its chain"
            )
        return QuarantineLedgerSnapshot(
            ledger_id=ledger_id,
            cell_id=cell_id,
            header_sha256=header_hash,
            head_sha256=head_hash,
            events=tuple(events),
        )

    def binding_head(self, attempt_ledger: PhysicalOnboardingAttemptLedger) -> str:
        """Return a verified independent head for an attempt event binding."""

        _, quarantine_snapshot = self.verified_snapshots(attempt_ledger)
        return quarantine_snapshot.head_sha256

    def verified_snapshots(
        self, attempt_ledger: PhysicalOnboardingAttemptLedger
    ) -> tuple[AttemptLedgerSnapshot, QuarantineLedgerSnapshot]:
        """Return the exact pair whose cross-ledger bindings were validated.

        Callers that build a wider state challenge must use these returned
        objects instead of validating one pair and then independently reading
        another.  A higher-level bounded double-collect can additionally prove
        that neither append-only head changed across the observation window.
        """

        attempt_snapshot, quarantine_snapshot = self._paired_snapshots(attempt_ledger)
        self._verify_existing_sources(quarantine_snapshot, attempt_snapshot)
        return attempt_snapshot, quarantine_snapshot

    def assert_effects_allowed(
        self, attempt_ledger: PhysicalOnboardingAttemptLedger
    ) -> str:
        """Fail closed for a latch or any attempt requiring startup recovery."""

        attempt_snapshot, quarantine_snapshot = self.verified_snapshots(attempt_ledger)
        if quarantine_snapshot.latched:
            raise CellQuarantinedError(
                f"cell {self.cell_id!r} has a permanent global quarantine latch"
            )
        if attempt_snapshot.unresolved_events or attempt_snapshot.uncertain_events:
            raise CellQuarantinedError(
                "cell has unresolved attempt evidence; startup recovery is required"
            )
        return quarantine_snapshot.head_sha256

    def latch_uncertain_attempt(
        self,
        attempt_ledger: PhysicalOnboardingAttemptLedger,
        attempt_id: str,
        *,
        occurred_at_ns: int,
    ) -> QuarantineEvent:
        """Permanently latch one already-sealed uncertain attempt, idempotently."""

        attempt_id = _identifier(attempt_id, "attempt_id")
        occurred_at_ns = _timestamp(occurred_at_ns, "occurred_at_ns")
        attempt_snapshot, quarantine_snapshot = self.verified_snapshots(attempt_ledger)
        uncertain = attempt_snapshot.latest_event(attempt_id)
        if uncertain is None or uncertain.state is not AttemptState.SEALED_UNCERTAIN:
            raise PhysicalOnboardingQuarantineError(
                "quarantine requires an already SEALED_UNCERTAIN attempt"
            )
        existing = quarantine_snapshot.event_for_attempt(attempt_id)
        if existing is not None:
            if existing.source_attempt_event_sha256 != uncertain.event_sha256:
                raise QuarantineLedgerIntegrityError(
                    "existing quarantine binds a different uncertain event"
                )
            return existing
        if len(quarantine_snapshot.events) >= MAX_QUARANTINE_EVENTS:
            raise PhysicalOnboardingQuarantineError(
                "quarantine ledger event bound is exhausted"
            )
        if (
            quarantine_snapshot.events
            and occurred_at_ns < quarantine_snapshot.events[-1].occurred_at_ns
        ):
            raise PhysicalOnboardingQuarantineError(
                "quarantine timestamp cannot move backwards"
            )
        qualification = _digest(
            self._publisher.qualification_sha256(self._root),
            "durability qualification",
            allow_zero=False,
        )
        sequence = len(quarantine_snapshot.events)
        quarantine_id = f"uncertain-{uncertain.event_sha256[:32]}"
        unsigned: dict[str, Any] = {
            "schema": QUARANTINE_LEDGER_EVENT_SCHEMA,
            "ledger_id": quarantine_snapshot.ledger_id,
            "cell_id": quarantine_snapshot.cell_id,
            "sequence": sequence,
            "quarantine_id": quarantine_id,
            "reason": QuarantineReason.SIDE_EFFECT_UNCERTAIN.value,
            "source_attempt_id": uncertain.attempt_id,
            "source_attempt_event_sha256": uncertain.event_sha256,
            "session_id": uncertain.session_id,
            "stage": uncertain.stage,
            "effect_class": uncertain.effect_class.value,
            "operation_id": uncertain.operation_id,
            "operation_binding_sha256": uncertain.operation_binding_sha256,
            "source_binding_sha256": uncertain.source_binding_sha256,
            "stage_plan_sha256": uncertain.stage_plan_sha256,
            "session_journal_head_sha256": uncertain.session_journal_head_sha256,
            "evidence_inventory_sha256": uncertain.evidence_inventory_sha256,
            "attempt_head_sha256": attempt_snapshot.head_sha256,
            "quarantine_head_before_sha256": quarantine_snapshot.head_sha256,
            "previous_event_sha256": (
                quarantine_snapshot.events[-1].event_sha256
                if quarantine_snapshot.events
                else ZERO_SHA256
            ),
            "occurred_at_ns": occurred_at_ns,
            "durability_qualification_sha256": qualification,
            "physical_authority": False,
            "clearing_supported": False,
        }
        event_document = _hashed_document(unsigned, "event_sha256")
        event = _parse_event(event_document)
        head_document = _head_document(
            ledger_id=quarantine_snapshot.ledger_id,
            cell_id=quarantine_snapshot.cell_id,
            header_sha256=quarantine_snapshot.header_sha256,
            event_count=sequence + 1,
            last_event_sha256=event.event_sha256,
        )
        self._publisher.commit_append(
            self._root,
            event_relative_path=f"events/event-{sequence:08d}.json",
            event_payload=canonical_json_bytes(event_document),
            head_payload=canonical_json_bytes(head_document),
            expected_head_sha256=quarantine_snapshot.head_sha256,
        )
        return event

    def _paired_snapshots(
        self, attempt_ledger: PhysicalOnboardingAttemptLedger
    ) -> tuple[AttemptLedgerSnapshot, QuarantineLedgerSnapshot]:
        if not isinstance(attempt_ledger, PhysicalOnboardingAttemptLedger):
            raise TypeError("attempt_ledger must be PhysicalOnboardingAttemptLedger")
        if attempt_ledger.cell_id != self.cell_id:
            raise PhysicalOnboardingQuarantineError(
                "attempt and quarantine ledgers belong to different cells"
            )
        attempt_snapshot = attempt_ledger.snapshot()
        quarantine_snapshot = self.snapshot()
        return attempt_snapshot, quarantine_snapshot

    @staticmethod
    def _verify_existing_sources(
        quarantine: QuarantineLedgerSnapshot,
        attempts: AttemptLedgerSnapshot,
    ) -> None:
        attempt_by_hash = {event.event_sha256: event for event in attempts.events}
        for event in quarantine.events:
            source = attempt_by_hash.get(event.source_attempt_event_sha256)
            if source is None:
                raise QuarantineLedgerIntegrityError(
                    "quarantine source attempt event is absent"
                )
            if (
                source.state is not AttemptState.SEALED_UNCERTAIN
                or source.attempt_id != event.source_attempt_id
                or source.cell_id != event.cell_id
                or source.session_id != event.session_id
                or source.stage != event.stage
                or source.effect_class is not event.effect_class
                or source.operation_id != event.operation_id
                or source.operation_binding_sha256 != event.operation_binding_sha256
                or source.source_binding_sha256 != event.source_binding_sha256
                or source.stage_plan_sha256 != event.stage_plan_sha256
                or source.session_journal_head_sha256
                != event.session_journal_head_sha256
                or source.evidence_inventory_sha256 != event.evidence_inventory_sha256
                or attempts.head_sha256_after(source) != event.attempt_head_sha256
            ):
                raise QuarantineLedgerIntegrityError(
                    "quarantine source binding differs from its uncertain attempt"
                )


def recover_physical_onboarding_startup(
    attempt_ledger: PhysicalOnboardingAttemptLedger,
    quarantine_ledger: PhysicalOnboardingQuarantineLedger,
    *,
    occurred_at_ns: int,
) -> StartupRecoveryReport:
    """Perform one idempotent, evidence-only recovery pass for a cell.

    The caller must hold the qualified CELL then SESSION locks.  This function
    intentionally does not acquire locks itself and cannot cause a physical
    effect.  A publication failure propagates; callers must remain fail-closed.
    """

    if not isinstance(attempt_ledger, PhysicalOnboardingAttemptLedger):
        raise TypeError("attempt_ledger must be PhysicalOnboardingAttemptLedger")
    if not isinstance(quarantine_ledger, PhysicalOnboardingQuarantineLedger):
        raise TypeError("quarantine_ledger must be PhysicalOnboardingQuarantineLedger")
    occurred_at_ns = _timestamp(occurred_at_ns, "occurred_at_ns")
    if attempt_ledger.cell_id != quarantine_ledger.cell_id:
        raise PhysicalOnboardingQuarantineError(
            "attempt and quarantine ledgers belong to different cells"
        )

    aborted: list[str] = []
    uncertain: list[str] = []
    latched: list[str] = []
    snapshot = attempt_ledger.snapshot()
    for latest in snapshot.latest_events:
        if latest.state is AttemptState.INTENT_DURABLE:
            attempt_ledger.transition(
                latest.attempt_id,
                AttemptState.ABORTED_PRE_EFFECT,
                quarantine_ledger,
                occurred_at_ns=occurred_at_ns,
            )
            aborted.append(latest.attempt_id)
        elif latest.state in ARMED_UNSEALED_STATES:
            attempt_ledger.transition(
                latest.attempt_id,
                AttemptState.SEALED_UNCERTAIN,
                quarantine_ledger,
                occurred_at_ns=occurred_at_ns,
            )
            uncertain.append(latest.attempt_id)

    # A crash between sealing and latching is safe: admission observes the
    # uncertain attempt and blocks, and the next pass completes this loop.
    snapshot = attempt_ledger.snapshot()
    for latest in snapshot.uncertain_events:
        before = quarantine_ledger.snapshot().event_for_attempt(latest.attempt_id)
        quarantine_ledger.latch_uncertain_attempt(
            attempt_ledger,
            latest.attempt_id,
            occurred_at_ns=occurred_at_ns,
        )
        if before is None:
            latched.append(latest.attempt_id)

    final_attempts = attempt_ledger.snapshot()
    final_quarantine = quarantine_ledger.snapshot()
    return StartupRecoveryReport(
        aborted_pre_effect=tuple(aborted),
        sealed_uncertain=tuple(uncertain),
        quarantines_latched=tuple(latched),
        final_attempt_head_sha256=final_attempts.head_sha256,
        final_quarantine_head_sha256=final_quarantine.head_sha256,
    )


GlobalQuarantineLedger = PhysicalOnboardingQuarantineLedger
recover_startup = recover_physical_onboarding_startup


__all__ = [
    "CellQuarantinedError",
    "GlobalQuarantineLedger",
    "MAX_QUARANTINE_EVENTS",
    "PhysicalOnboardingQuarantineError",
    "PhysicalOnboardingQuarantineLedger",
    "QUARANTINE_LEDGER_EVENT_SCHEMA",
    "QUARANTINE_LEDGER_HEAD_SCHEMA",
    "QUARANTINE_LEDGER_HEADER_SCHEMA",
    "QuarantineEvent",
    "QuarantineLedgerIntegrityError",
    "QuarantineLedgerSnapshot",
    "QuarantineLedgerSuffixError",
    "QuarantineReason",
    "StartupRecoveryReport",
    "recover_physical_onboarding_startup",
    "recover_startup",
]
