"""Crash-aware, zero-authority orchestration for an ordered action mission.

This module is the hardware-free bridge between the generic runtime ports and
the durable per-action journal.  It deliberately has no imports from serial,
camera, motion-permit, or physical adapter modules.  Every runtime port must
declare a zero physical footprint before the first operation and again after
cleanup.

The critical invariant is write-ahead contact accounting.  An action's
``CONTACT_MAY_HAVE_OCCURRED`` event is made durable *before* either the opaque
contact-producing arm command or the virtual device-contact port is invoked.
Consequently a restart can never justify automatically repeating a key press
or screen tap.  It may only obtain an independent outcome, retract after a
confirmed outcome, or stop for manual review.

Opaque commands and contacts have one immutable representation: the canonical
bytes that are both hashed into the plan and sent to zero-authority ports.
Those bytes are seal-checked immediately before each send.  Route/collision
and preflight inputs are likewise hash-bound receipts produced by upstream
zero-authority simulation.  A required authorization-v2 cursor consumes the
exact journal-derived command suffix; none of these artifacts is a live motion
permit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Generic, NoReturn, Protocol, TypeVar, cast, runtime_checkable

from rocell.safety.authorization_v2 import (
    AuthorizationContinuityEvidence,
    AuthorizationEvidence,
    AuthorizationV2Error,
    OrderedSimulationPermit,
    SimulationPrimitive,
    SimulationTrajectoryCommand,
    canonical_record_sha256,
    issue_ordered_simulation_permit,
)

from .mission_journal import (
    ActionJournalState,
    ActionOccurrence,
    MissionJournalError,
    MissionJournalSnapshot,
    ZeroAuthorityMissionJournal,
)
from .runtime_ports import (
    ArmExecutionRequest,
    ArmExecutionResult,
    ArmFeedbackRequest,
    ArmFeedbackSample,
    CancellationCheck,
    CancellationStatus,
    DeviceContactRequest,
    DeviceContactResult,
    LifecycleRequest,
    LifecycleResult,
    MissionRuntimePorts,
    ObservationRequest,
    ObservationResult,
    OutcomeObservation,
    OutcomeRequest,
    RuntimeContractReport,
    RuntimeDeadline,
    RuntimeInstant,
    RuntimePortOperationError,
    validate_arm_feedback_sample,
    validate_runtime_ports,
)


ZERO_AUTHORITY_MULTI_ACTION_MISSION_SCHEMA = (
    "rocell.zero_authority_multi_action_mission.v1"
)
ZERO_AUTHORITY_MULTI_ACTION_REPORT_SCHEMA = (
    "rocell.zero_authority_multi_action_report.v1"
)
ZERO_AUTHORITY_MULTI_ACTION_RECORD_SCHEMA = (
    "rocell.zero_authority_multi_action_record.v1"
)
MAX_MISSION_ACTIONS = 512
MAX_OPAQUE_BINDING_BYTES = 1024 * 1024

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class MultiActionMissionError(ValueError):
    """A mission definition, journal bundle, or result is invalid."""


class MissionBoundary(str, Enum):
    """Ordered observable boundaries used for accounting and fault injection."""

    VALIDATE_PORTS_INITIAL = "VALIDATE_PORTS_INITIAL"
    CONNECT = "CONNECT"
    REFERENCE = "REFERENCE"
    ACTION_GATE = "ACTION_GATE"
    PRE_MOTION_FEEDBACK = "PRE_MOTION_FEEDBACK"
    FRESH_OBSERVATION = "FRESH_OBSERVATION"
    ROUTE_AUTHORIZATION = "ROUTE_AUTHORIZATION"
    HOVER_EXECUTE = "HOVER_EXECUTE"
    APPROACH_EXECUTE = "APPROACH_EXECUTE"
    JOURNAL_PRE_CONTACT = "JOURNAL_PRE_CONTACT"
    JOURNAL_CONTACT_BOUNDARY = "JOURNAL_CONTACT_BOUNDARY"
    CONTACT_EXECUTE = "CONTACT_EXECUTE"
    CONTACT_FEEDBACK = "CONTACT_FEEDBACK"
    DEVICE_CONTACT = "DEVICE_CONTACT"
    OUTCOME_OBSERVATION = "OUTCOME_OBSERVATION"
    JOURNAL_OUTCOME_CONFIRMED = "JOURNAL_OUTCOME_CONFIRMED"
    RETRACT_EXECUTE = "RETRACT_EXECUTE"
    RETRACT_FEEDBACK = "RETRACT_FEEDBACK"
    JOURNAL_RETRACTED = "JOURNAL_RETRACTED"
    JOURNAL_FAILURE_STATE = "JOURNAL_FAILURE_STATE"
    PARK_EXECUTE = "PARK_EXECUTE"
    PARK_FEEDBACK = "PARK_FEEDBACK"
    JOURNAL_PARKED = "JOURNAL_PARKED"
    STOP = "STOP"
    CLOSE = "CLOSE"
    VALIDATE_PORTS_FINAL = "VALIDATE_PORTS_FINAL"
    VALIDATE_JOURNALS_FINAL = "VALIDATE_JOURNALS_FINAL"


class BoundaryStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    RESUMED = "RESUMED"


CommandT = TypeVar("CommandT")
FeedbackT = TypeVar("FeedbackT")
ObservationT = TypeVar("ObservationT")
ContactT = TypeVar("ContactT")
OutcomeT = TypeVar("OutcomeT")
ValueT = TypeVar("ValueT")


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise MultiActionMissionError(f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise MultiActionMissionError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MultiActionMissionError("value is not canonical JSON data") from exc


def _stable_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _materialize_mission_spec(
    spec: "MultiActionMissionSpec[object, object]",
) -> "MultiActionMissionSpec[object, object]":
    """Detach execution from caller-owned objects using sealed canonical bytes.

    Frozen dataclasses protect ordinary callers, but ``object.__setattr__`` can
    still be abused after an authorization plan is issued.  The kernel takes a
    private, byte-for-byte materialization at entry.  Every value later sent to
    a runtime port is one of these immutable bytes and is re-seal-checked at
    the send boundary.
    """

    spec.__post_init__()

    def clone_payload(value: BoundOpaqueValue[object]) -> BoundOpaqueValue[object]:
        return BoundOpaqueValue(bytes(value.verified_payload()))

    actions: list[MultiActionSpec[object, object]] = []
    for action in spec.actions:
        action.__post_init__()
        actions.append(
            MultiActionSpec(
                action_id=action.action_id,
                hover_command=clone_payload(
                    cast(BoundOpaqueValue[object], action.hover_command)
                ),
                approach_command=clone_payload(
                    cast(BoundOpaqueValue[object], action.approach_command)
                ),
                contact_command=clone_payload(
                    cast(BoundOpaqueValue[object], action.contact_command)
                ),
                retract_command=clone_payload(
                    cast(BoundOpaqueValue[object], action.retract_command)
                ),
                device_contact=clone_payload(
                    cast(BoundOpaqueValue[object], action.device_contact)
                ),
                expected_outcome=cast(
                    BoundOpaqueValue[bytes],
                    clone_payload(cast(BoundOpaqueValue[object], action.expected_outcome)),
                ),
                route_authorization_sha256=action.route_authorization_sha256,
                observation_phase=action.observation_phase,
                required_activation_count=action.required_activation_count,
            )
        )
    return MultiActionMissionSpec(
        mission_id=spec.mission_id,
        actions=tuple(actions),
        park_command=clone_payload(cast(BoundOpaqueValue[object], spec.park_command)),
        preflight_binding_sha256=spec.preflight_binding_sha256,
        deadline_budget_ticks=spec.deadline_budget_ticks,
        deadline_expiry_boundary=spec.deadline_expiry_boundary,
        deadline_expiry_action_index=spec.deadline_expiry_action_index,
        schema=spec.schema,
    )


def _instant_dict(value: RuntimeInstant) -> dict[str, object]:
    return {
        "clock_id": value.clock_id,
        "tick": value.tick,
        "tick_period_ns": value.tick_period_ns,
    }


def _contract_dict(value: RuntimeContractReport) -> dict[str, object]:
    return {
        "runtime_id": value.runtime_id,
        "contract": value.contract,
        "validated_roles": [item.value for item in value.validated_roles],
        "unique_port_ids": list(value.unique_port_ids),
        "execution_modes": [item.value for item in value.execution_modes],
        "zero_authority": value.zero_authority,
        "hardware_accessed": value.hardware_accessed,
        "hardware_commands_generated": value.hardware_commands_generated,
    }


def _runtime_identity_document(
    ports: MissionRuntimePorts[object, object, object, object, object],
) -> dict[str, object]:
    """Capture identities omitted from the compact RuntimeContractReport."""

    document: dict[str, object] = {}
    for attribute in (
        "clock",
        "arm_lifecycle",
        "arm_execution",
        "arm_feedback",
        "observation",
        "device_contact",
        "outcome_observer",
        "cancellation",
        "evidence",
    ):
        metadata = getattr(ports, attribute).runtime_metadata
        authority = metadata.authority
        document[attribute] = {
            "runtime_id": metadata.runtime_id,
            "port_id": metadata.port_id,
            "implementation_id": metadata.implementation_id,
            "roles": [role.value for role in metadata.roles],
            "contract": metadata.contract,
            "authority": {
                "execution_mode": authority.execution_mode.value,
                "hardware_accessed": authority.hardware_accessed,
                "hardware_commands_generated": authority.hardware_commands_generated,
                "live_motion_authorized": authority.live_motion_authorized,
                "physical_contact_authorized": authority.physical_contact_authorized,
                "physical_release_effect": authority.physical_release_effect,
            },
        }
    return document


@dataclass(frozen=True, slots=True)
class BoundOpaqueValue(Generic[ValueT]):
    """One immutable canonical payload whose bytes are its only materialization.

    Earlier versions accepted a Python value and unrelated binding bytes.  A
    caller could therefore authorize one digest and send another value, or
    mutate the value after the plan hash was computed.  This type has one
    source of truth: the exact bytes sent through the zero-authority port.
    ``verified_payload`` recomputes the construction-time seal immediately
    before every send, catching even deliberate frozen-dataclass bypasses.
    """

    canonical_bytes: bytes = field(repr=False)
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.canonical_bytes) is not bytes:
            raise MultiActionMissionError("canonical_bytes must be exactly bytes")
        if not self.canonical_bytes:
            raise MultiActionMissionError("canonical_bytes must not be empty")
        if len(self.canonical_bytes) > MAX_OPAQUE_BINDING_BYTES:
            raise MultiActionMissionError(
                f"canonical_bytes exceeds {MAX_OPAQUE_BINDING_BYTES} bytes"
            )
        object.__setattr__(
            self,
            "_sealed_sha256",
            hashlib.sha256(self.canonical_bytes).hexdigest(),
        )

    @classmethod
    def from_json(cls, document: object) -> "BoundOpaqueValue[bytes]":
        return BoundOpaqueValue(_canonical_bytes(document))

    def verified_payload(self) -> bytes:
        if type(self.canonical_bytes) is not bytes:
            raise MultiActionMissionError("canonical payload type changed after sealing")
        actual = hashlib.sha256(self.canonical_bytes).hexdigest()
        if actual != self._sealed_sha256:
            raise MultiActionMissionError("canonical payload changed after plan sealing")
        return self.canonical_bytes

    @property
    def value(self) -> bytes:
        """Compatibility alias that still verifies the exact payload."""

        return self.verified_payload()

    @property
    def binding_bytes(self) -> bytes:
        return self.verified_payload()

    @property
    def binding_sha256(self) -> str:
        self.verified_payload()
        return self._sealed_sha256


@dataclass(frozen=True, slots=True)
class ObservedSemanticOutcome:
    """Independent device-state meaning plus the contact events that caused it."""

    action_occurrence_id: str
    semantic_payload: BoundOpaqueValue[bytes]
    contact_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.action_occurrence_id, "outcome action_occurrence_id")
        if not isinstance(self.semantic_payload, BoundOpaqueValue):
            raise MultiActionMissionError(
                "outcome semantic_payload must be BoundOpaqueValue"
            )
        self.semantic_payload.verified_payload()
        if type(self.contact_event_ids) is not tuple or not self.contact_event_ids:
            raise MultiActionMissionError(
                "outcome contact_event_ids must be a non-empty immutable tuple"
            )
        for event_id in self.contact_event_ids:
            _identifier(event_id, "outcome contact event ID")
        if len(self.contact_event_ids) != len(set(self.contact_event_ids)):
            raise MultiActionMissionError("outcome contact event IDs are duplicated")

    @property
    def semantic_sha256(self) -> str:
        return self.semantic_payload.binding_sha256

    def binding_document(self) -> dict[str, object]:
        self.__post_init__()
        return {
            "action_occurrence_id": self.action_occurrence_id,
            "semantic_sha256": self.semantic_sha256,
            "contact_event_ids": list(self.contact_event_ids),
        }

    @property
    def evidence_sha256(self) -> str:
        return _stable_hash(self.binding_document())


@dataclass(frozen=True, slots=True)
class MultiActionSpec(Generic[CommandT, ContactT]):
    """Opaque commands and evidence bindings for one key press or phone tap."""

    action_id: str
    hover_command: BoundOpaqueValue[CommandT]
    approach_command: BoundOpaqueValue[CommandT]
    contact_command: BoundOpaqueValue[CommandT]
    retract_command: BoundOpaqueValue[CommandT]
    device_contact: BoundOpaqueValue[ContactT]
    expected_outcome: BoundOpaqueValue[bytes]
    route_authorization_sha256: str
    observation_phase: str = "PRE_CONTACT_LOCALIZATION"
    required_activation_count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", _identifier(self.action_id, "action_id"))
        for name in (
            "hover_command",
            "approach_command",
            "contact_command",
            "retract_command",
            "device_contact",
            "expected_outcome",
        ):
            if not isinstance(getattr(self, name), BoundOpaqueValue):
                raise MultiActionMissionError(f"{name} must be BoundOpaqueValue")
        object.__setattr__(
            self,
            "route_authorization_sha256",
            _digest(self.route_authorization_sha256, "route_authorization_sha256"),
        )
        object.__setattr__(
            self,
            "observation_phase",
            _identifier(self.observation_phase, "observation_phase"),
        )
        if (
            isinstance(self.required_activation_count, bool)
            or not isinstance(self.required_activation_count, int)
            or self.required_activation_count != 1
        ):
            raise MultiActionMissionError(
                "each action occurrence must require exactly one device activation"
            )

    def binding_document(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "hover_command_sha256": self.hover_command.binding_sha256,
            "approach_command_sha256": self.approach_command.binding_sha256,
            "contact_command_sha256": self.contact_command.binding_sha256,
            "retract_command_sha256": self.retract_command.binding_sha256,
            "device_contact_sha256": self.device_contact.binding_sha256,
            "expected_outcome_sha256": self.expected_outcome.binding_sha256,
            "route_authorization_sha256": self.route_authorization_sha256,
            "observation_phase": self.observation_phase,
            "required_activation_count": self.required_activation_count,
        }


_DEADLINE_BOUNDARIES = frozenset(
    {
        MissionBoundary.CONNECT,
        MissionBoundary.REFERENCE,
        MissionBoundary.PRE_MOTION_FEEDBACK,
        MissionBoundary.FRESH_OBSERVATION,
        MissionBoundary.HOVER_EXECUTE,
        MissionBoundary.APPROACH_EXECUTE,
        MissionBoundary.CONTACT_EXECUTE,
        MissionBoundary.CONTACT_FEEDBACK,
        MissionBoundary.DEVICE_CONTACT,
        MissionBoundary.OUTCOME_OBSERVATION,
        MissionBoundary.RETRACT_EXECUTE,
        MissionBoundary.RETRACT_FEEDBACK,
        MissionBoundary.PARK_EXECUTE,
        MissionBoundary.PARK_FEEDBACK,
        MissionBoundary.STOP,
        MissionBoundary.CLOSE,
    }
)


@dataclass(frozen=True, slots=True)
class MultiActionMissionSpec(Generic[CommandT, ContactT]):
    """Immutable ordered plan; every occurrence is derived from this plan hash."""

    mission_id: str
    actions: tuple[MultiActionSpec[CommandT, ContactT], ...]
    park_command: BoundOpaqueValue[CommandT]
    preflight_binding_sha256: str
    deadline_budget_ticks: int = 2
    deadline_expiry_boundary: MissionBoundary | None = None
    deadline_expiry_action_index: int | None = None
    schema: str = ZERO_AUTHORITY_MULTI_ACTION_MISSION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != ZERO_AUTHORITY_MULTI_ACTION_MISSION_SCHEMA:
            raise MultiActionMissionError("unsupported multi-action mission schema")
        object.__setattr__(
            self, "mission_id", _identifier(self.mission_id, "mission_id")
        )
        if len(self.mission_id) > 72:
            raise MultiActionMissionError(
                "mission_id exceeds the operation-correlation length budget"
            )
        if not isinstance(self.actions, tuple) or not self.actions:
            raise MultiActionMissionError("actions must be a non-empty immutable tuple")
        if len(self.actions) > MAX_MISSION_ACTIONS:
            raise MultiActionMissionError(
                f"actions exceeds the {MAX_MISSION_ACTIONS}-action limit"
            )
        if not all(isinstance(item, MultiActionSpec) for item in self.actions):
            raise MultiActionMissionError("actions contains an invalid action spec")
        if not isinstance(self.park_command, BoundOpaqueValue):
            raise MultiActionMissionError("park_command must be BoundOpaqueValue")
        object.__setattr__(
            self,
            "preflight_binding_sha256",
            _digest(self.preflight_binding_sha256, "preflight_binding_sha256"),
        )
        if (
            isinstance(self.deadline_budget_ticks, bool)
            or not isinstance(self.deadline_budget_ticks, int)
            or not 1 <= self.deadline_budget_ticks <= 1_000_000
        ):
            raise MultiActionMissionError(
                "deadline_budget_ticks must be within [1, 1000000]"
            )
        boundary = self.deadline_expiry_boundary
        if boundary is not None:
            try:
                boundary = MissionBoundary(boundary)
            except (TypeError, ValueError) as exc:
                raise MultiActionMissionError(
                    "deadline_expiry_boundary is unsupported"
                ) from exc
            if boundary not in _DEADLINE_BOUNDARIES:
                raise MultiActionMissionError(
                    "deadline_expiry_boundary must be deadline-capable"
                )
            object.__setattr__(self, "deadline_expiry_boundary", boundary)
        index = self.deadline_expiry_action_index
        if index is not None and (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(self.actions)
        ):
            raise MultiActionMissionError(
                "deadline_expiry_action_index is outside the action plan"
            )
        action_boundaries = _DEADLINE_BOUNDARIES - {
            MissionBoundary.CONNECT,
            MissionBoundary.REFERENCE,
            MissionBoundary.PARK_EXECUTE,
            MissionBoundary.PARK_FEEDBACK,
            MissionBoundary.STOP,
            MissionBoundary.CLOSE,
        }
        if boundary in action_boundaries and index is None:
            raise MultiActionMissionError(
                "an action deadline fault needs deadline_expiry_action_index"
            )
        if boundary is not None and boundary not in action_boundaries and index is not None:
            raise MultiActionMissionError(
                "a mission-level deadline fault cannot name an action index"
            )
        if boundary is None and index is not None:
            raise MultiActionMissionError(
                "deadline_expiry_action_index requires a deadline boundary"
            )

    def definition_document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "mission_id": self.mission_id,
            "actions": [item.binding_document() for item in self.actions],
            "park_command_sha256": self.park_command.binding_sha256,
            "preflight_binding_sha256": self.preflight_binding_sha256,
            "deadline_budget_ticks": self.deadline_budget_ticks,
            "deadline_expiry_boundary": (
                self.deadline_expiry_boundary.value
                if self.deadline_expiry_boundary is not None
                else None
            ),
            "deadline_expiry_action_index": self.deadline_expiry_action_index,
            "simulation_only": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
        }

    @property
    def plan_sha256(self) -> str:
        return _stable_hash(self.definition_document())

    @property
    def occurrences(self) -> tuple[ActionOccurrence, ...]:
        return tuple(
            ActionOccurrence.from_action_document(
                mission_id=self.mission_id,
                plan_sha256=self.plan_sha256,
                action_ordinal=index,
                action=action.binding_document(),
            )
            for index, action in enumerate(self.actions)
        )

    def operation_id(
        self, boundary: MissionBoundary, action_index: int | None = None
    ) -> str:
        try:
            parsed = MissionBoundary(boundary)
        except (TypeError, ValueError) as exc:
            raise MultiActionMissionError("boundary is unsupported") from exc
        prefix = f"{self.mission_id}.mission"
        if action_index is not None:
            if (
                isinstance(action_index, bool)
                or not isinstance(action_index, int)
                or not 0 <= action_index < len(self.actions)
            ):
                raise MultiActionMissionError("action_index is outside the plan")
            prefix = f"{self.mission_id}.a{action_index:06d}"
        return f"{prefix}.{parsed.value.lower().replace('_', '-')}"


_PHASE_PRIMITIVES = {
    MissionBoundary.HOVER_EXECUTE: SimulationPrimitive.MOVE_ABOVE,
    MissionBoundary.APPROACH_EXECUTE: SimulationPrimitive.DESCEND_PRECONTACT,
    MissionBoundary.CONTACT_EXECUTE: SimulationPrimitive.CONTACT_INTENT,
    MissionBoundary.RETRACT_EXECUTE: SimulationPrimitive.RETRACT,
    MissionBoundary.PARK_EXECUTE: SimulationPrimitive.PARK,
}


@dataclass(frozen=True, slots=True)
class MissionCommandAuthorizationBinding:
    """Exact authorization-v2 command expected at one absolute plan ordinal."""

    absolute_ordinal: int
    action_occurrence_sha256: str
    phase: MissionBoundary
    canonical_payload_sha256: str
    constraint_set_sha256: str
    simulation_command: SimulationTrajectoryCommand

    def __post_init__(self) -> None:
        if (
            isinstance(self.absolute_ordinal, bool)
            or not isinstance(self.absolute_ordinal, int)
            or self.absolute_ordinal < 0
        ):
            raise MultiActionMissionError("authorization ordinal must be nonnegative")
        _digest(self.action_occurrence_sha256, "authorization occurrence sha256")
        if self.phase not in _PHASE_PRIMITIVES:
            raise MultiActionMissionError("authorization phase is not an arm command")
        _digest(self.canonical_payload_sha256, "authorization payload sha256")
        _digest(self.constraint_set_sha256, "authorization constraint sha256")
        if type(self.simulation_command) is not SimulationTrajectoryCommand:
            raise MultiActionMissionError(
                "authorization command must be SimulationTrajectoryCommand"
            )
        expected_occurrence = _stable_hash(
            {
                "schema": "rocell.zero_authority.command_occurrence.v1",
                "absolute_ordinal": self.absolute_ordinal,
                "action_occurrence_sha256": self.action_occurrence_sha256,
                "phase": self.phase.value,
                "canonical_payload_sha256": self.canonical_payload_sha256,
                "constraint_set_sha256": self.constraint_set_sha256,
            }
        )
        command = self.simulation_command
        if (
            command.command_occurrence_id != expected_occurrence
            or command.action_occurrence_id != self.action_occurrence_sha256
            or command.primitive is not _PHASE_PRIMITIVES[self.phase]
            or command.target_state_sha256 != self.canonical_payload_sha256
            or command.constraint_set_sha256 != self.constraint_set_sha256
        ):
            raise MultiActionMissionError(
                "authorization-v2 command does not match its kernel binding"
            )

    @property
    def command_sha256(self) -> str:
        self.__post_init__()
        return self.simulation_command.command_sha256

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        return {
            "absolute_ordinal": self.absolute_ordinal,
            "action_occurrence_sha256": self.action_occurrence_sha256,
            "phase": self.phase.value,
            "canonical_payload_sha256": self.canonical_payload_sha256,
            "constraint_set_sha256": self.constraint_set_sha256,
            "simulation_command_sha256": self.command_sha256,
        }


def _make_command_binding(
    *,
    absolute_ordinal: int,
    occurrence: ActionOccurrence,
    phase: MissionBoundary,
    payload: BoundOpaqueValue[object],
    constraint_set_sha256: str,
) -> MissionCommandAuthorizationBinding:
    payload_sha256 = payload.binding_sha256
    occurrence_sha256 = occurrence.occurrence_hash
    command_occurrence_id = _stable_hash(
        {
            "schema": "rocell.zero_authority.command_occurrence.v1",
            "absolute_ordinal": absolute_ordinal,
            "action_occurrence_sha256": occurrence_sha256,
            "phase": phase.value,
            "canonical_payload_sha256": payload_sha256,
            "constraint_set_sha256": constraint_set_sha256,
        }
    )
    command = SimulationTrajectoryCommand(
        command_occurrence_id=command_occurrence_id,
        action_occurrence_id=occurrence_sha256,
        primitive=_PHASE_PRIMITIVES[phase],
        target_state_sha256=payload_sha256,
        constraint_set_sha256=constraint_set_sha256,
    )
    return MissionCommandAuthorizationBinding(
        absolute_ordinal=absolute_ordinal,
        action_occurrence_sha256=occurrence_sha256,
        phase=phase,
        canonical_payload_sha256=payload_sha256,
        constraint_set_sha256=constraint_set_sha256,
        simulation_command=command,
    )


def _validate_state_prefix(states: tuple[ActionJournalState, ...]) -> None:
    if type(states) is not tuple or not states:
        raise MultiActionMissionError("journal states must be a non-empty tuple")
    if not all(type(state) is ActionJournalState for state in states):
        raise MultiActionMissionError("journal state tuple contains an invalid state")
    if any(state is ActionJournalState.PARKED for state in states):
        first_not_parked = next(
            (index for index, state in enumerate(states) if state is not ActionJournalState.PARKED),
            len(states),
        )
        if any(state is ActionJournalState.PARKED for state in states[first_not_parked:]):
            raise MultiActionMissionError("PARKED journals must form an ordered prefix")
        if any(
            state is not ActionJournalState.RETRACTED
            for state in states[first_not_parked:]
        ):
            raise MultiActionMissionError(
                "after mission parking starts, every remaining action must be RETRACTED"
            )
        return

    frontier_seen = False
    for state in states:
        if not frontier_seen and state is ActionJournalState.RETRACTED:
            continue
        if not frontier_seen:
            frontier_seen = True
            continue
        if state is not ActionJournalState.INTENT_COMMITTED:
            raise MultiActionMissionError(
                "a later action advanced while an earlier action was incomplete"
            )


def _validate_global_journal_prefix(
    snapshots: tuple[MissionJournalSnapshot, ...],
) -> None:
    """Require a single ordered action frontier across independent journals."""

    _validate_state_prefix(tuple(snapshot.current_state for snapshot in snapshots))


def build_mission_authorization_schedule(
    spec: MultiActionMissionSpec[object, object],
    snapshots: tuple[MissionJournalSnapshot, ...],
) -> tuple[MissionCommandAuthorizationBinding, ...]:
    """Build the exact safe remaining suffix implied by durable journal state."""

    if len(snapshots) != len(spec.actions):
        raise MultiActionMissionError("authorization snapshots do not match the plan")
    _validate_global_journal_prefix(snapshots)
    full: list[MissionCommandAuthorizationBinding] = []
    occurrences = spec.occurrences
    for index, (action, occurrence) in enumerate(zip(spec.actions, occurrences)):
        for offset, (phase, payload) in enumerate(
            (
                (MissionBoundary.HOVER_EXECUTE, action.hover_command),
                (MissionBoundary.APPROACH_EXECUTE, action.approach_command),
                (MissionBoundary.CONTACT_EXECUTE, action.contact_command),
                (MissionBoundary.RETRACT_EXECUTE, action.retract_command),
            )
        ):
            full.append(
                _make_command_binding(
                    absolute_ordinal=index * 4 + offset,
                    occurrence=occurrence,
                    phase=phase,
                    payload=cast(BoundOpaqueValue[object], payload),
                    constraint_set_sha256=action.route_authorization_sha256,
                )
            )
    full.append(
        _make_command_binding(
            absolute_ordinal=len(spec.actions) * 4,
            occurrence=occurrences[-1],
            phase=MissionBoundary.PARK_EXECUTE,
            payload=cast(BoundOpaqueValue[object], spec.park_command),
            constraint_set_sha256=spec.preflight_binding_sha256,
        )
    )

    if all(state is ActionJournalState.PARKED for state in (s.current_state for s in snapshots)):
        return ()
    start: int | None = None
    for index, snapshot in enumerate(snapshots):
        state = snapshot.current_state
        if state in {ActionJournalState.INTENT_COMMITTED, ActionJournalState.PRE_CONTACT}:
            start = index * 4
            break
        if state in {
            ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            ActionJournalState.OUTCOME_CONFIRMED,
        }:
            start = index * 4 + 3
            break
        if state in {ActionJournalState.FAULTED, ActionJournalState.OUTCOME_UNCERTAIN}:
            return ()
    if start is None:
        start = len(spec.actions) * 4
    return tuple(item for item in full if item.absolute_ordinal >= start)


_AUTHORIZATION_RECEIPT_ISSUER = object()


@dataclass(frozen=True, slots=True)
class MissionCommandAuthorizationReceipt:
    _issuer: object = field(default=None, init=False, repr=False, compare=False)
    absolute_ordinal: int
    action_occurrence_sha256: str
    phase: MissionBoundary
    canonical_payload_sha256: str
    simulation_command_sha256: str
    plan_sha256: str
    starting_ordinal: int
    authorization_v2_receipt_sha256: str
    cursor_context_sha256: str
    zero_authority: bool = True

    def __post_init__(self) -> None:
        if self._issuer is not _AUTHORIZATION_RECEIPT_ISSUER:
            raise MultiActionMissionError(
                "command authorization receipts may only be issued by the adapter"
            )
        if (
            isinstance(self.absolute_ordinal, bool)
            or not isinstance(self.absolute_ordinal, int)
            or self.absolute_ordinal < 0
        ):
            raise MultiActionMissionError("receipt ordinal must be nonnegative")
        _digest(self.action_occurrence_sha256, "receipt occurrence sha256")
        if self.phase not in _PHASE_PRIMITIVES:
            raise MultiActionMissionError("receipt phase is not an arm command")
        _digest(self.canonical_payload_sha256, "receipt payload sha256")
        _digest(self.simulation_command_sha256, "receipt command sha256")
        _digest(self.plan_sha256, "receipt plan sha256")
        if (
            isinstance(self.starting_ordinal, bool)
            or not isinstance(self.starting_ordinal, int)
            or not 0 <= self.starting_ordinal <= self.absolute_ordinal
        ):
            raise MultiActionMissionError("receipt starting ordinal is invalid")
        _digest(
            self.authorization_v2_receipt_sha256,
            "authorization-v2 receipt sha256",
        )
        _digest(self.cursor_context_sha256, "cursor context sha256")
        if self.zero_authority is not True:
            raise MultiActionMissionError("authorization receipt is not zero-authority")

    @classmethod
    def _issued(
        cls,
        binding: MissionCommandAuthorizationBinding,
        *,
        plan_sha256: str,
        starting_ordinal: int,
        authorization_v2_receipt_sha256: str,
        cursor_context_sha256: str,
    ) -> "MissionCommandAuthorizationReceipt":
        receipt = object.__new__(cls)
        values = {
            "_issuer": _AUTHORIZATION_RECEIPT_ISSUER,
            "absolute_ordinal": binding.absolute_ordinal,
            "action_occurrence_sha256": binding.action_occurrence_sha256,
            "phase": binding.phase,
            "canonical_payload_sha256": binding.canonical_payload_sha256,
            "simulation_command_sha256": binding.command_sha256,
            "plan_sha256": plan_sha256,
            "starting_ordinal": starting_ordinal,
            "authorization_v2_receipt_sha256": authorization_v2_receipt_sha256,
            "cursor_context_sha256": cursor_context_sha256,
            "zero_authority": True,
        }
        for name, value in values.items():
            object.__setattr__(receipt, name, value)
        receipt.__post_init__()
        return receipt

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        return {
            "absolute_ordinal": self.absolute_ordinal,
            "action_occurrence_sha256": self.action_occurrence_sha256,
            "phase": self.phase.value,
            "canonical_payload_sha256": self.canonical_payload_sha256,
            "simulation_command_sha256": self.simulation_command_sha256,
            "plan_sha256": self.plan_sha256,
            "starting_ordinal": self.starting_ordinal,
            "authorization_v2_receipt_sha256": self.authorization_v2_receipt_sha256,
            "cursor_context_sha256": self.cursor_context_sha256,
            "zero_authority": True,
            "live_transport_authorized": False,
            "hardware_commands_generated": 0,
        }

    @property
    def receipt_sha256(self) -> str:
        return _stable_hash(self.to_dict())


@runtime_checkable
class SimulationCommandAuthorizationCursor(Protocol):
    @property
    def plan_sha256(self) -> str: ...

    @property
    def expected_bindings(self) -> tuple[MissionCommandAuthorizationBinding, ...]: ...

    @property
    def starting_ordinal(self) -> int | None: ...

    @property
    def next_ordinal(self) -> int | None: ...

    @property
    def zero_authority(self) -> bool: ...

    @property
    def can_authorize_live_transport(self) -> bool: ...

    @property
    def complete(self) -> bool: ...

    def consume(
        self, binding: MissionCommandAuthorizationBinding
    ) -> MissionCommandAuthorizationReceipt: ...


ContinuitySupplier = Callable[
    [MissionCommandAuthorizationBinding, int],
    tuple[AuthorizationContinuityEvidence, float],
]


class AuthorizationV2MissionCursor:
    """Required adapter from a remaining mission suffix to authorization-v2."""

    __slots__ = (
        "_bindings",
        "_continuity_supplier",
        "_cursor_context_sha256",
        "_permit",
        "_plan_sha256",
        "_sealed",
        "_starting_ordinal",
    )

    _bindings: tuple[MissionCommandAuthorizationBinding, ...]
    _continuity_supplier: ContinuitySupplier
    _cursor_context_sha256: str
    _permit: OrderedSimulationPermit
    _plan_sha256: str
    _sealed: bool
    _starting_ordinal: int

    def __init__(self) -> None:
        raise MultiActionMissionError(
            "authorization cursors must be issued from authorization-v2 evidence"
        )

    def __setattr__(self, name: str, value: object) -> NoReturn:
        del name, value
        raise MultiActionMissionError("authorization cursors are immutable")

    def __copy__(self) -> NoReturn:
        raise MultiActionMissionError("authorization cursors cannot be copied")

    def __deepcopy__(self, memo: object) -> NoReturn:
        del memo
        raise MultiActionMissionError("authorization cursors cannot be copied")

    def __reduce_ex__(self, protocol: object) -> NoReturn:
        del protocol
        raise MultiActionMissionError("authorization cursors cannot be serialized")

    @classmethod
    def issue(
        cls,
        *,
        evidence: AuthorizationEvidence,
        bindings: tuple[MissionCommandAuthorizationBinding, ...],
        starting_ordinal: int,
        continuity_supplier: ContinuitySupplier,
        ttl_s: float,
        now_monotonic: float,
        interlock_max_age_s: float = 0.5,
    ) -> "AuthorizationV2MissionCursor":
        if type(bindings) is not tuple or not bindings:
            raise MultiActionMissionError(
                "authorization-v2 issuance requires a non-empty remaining suffix"
            )
        if bindings[0].absolute_ordinal != starting_ordinal:
            raise MultiActionMissionError(
                "authorization starting ordinal does not match the suffix"
            )
        if tuple(item.absolute_ordinal for item in bindings) != tuple(
            range(starting_ordinal, starting_ordinal + len(bindings))
        ):
            raise MultiActionMissionError(
                "authorization bindings must be a contiguous absolute suffix"
            )
        _digest(evidence.plan_sha256, "evidence plan sha256")
        for binding in bindings:
            binding.__post_init__()
        expected_commands = tuple(item.simulation_command for item in bindings)
        if evidence.ordered_commands != expected_commands:
            raise MultiActionMissionError(
                "authorization-v2 evidence commands do not match the mission suffix"
            )
        grouped: list[str] = []
        for binding in bindings:
            if not grouped or grouped[-1] != binding.action_occurrence_sha256:
                grouped.append(binding.action_occurrence_sha256)
        if evidence.ordered_action_occurrence_ids != tuple(grouped):
            raise MultiActionMissionError(
                "authorization-v2 action grouping does not match the mission suffix"
            )
        if not callable(continuity_supplier):
            raise MultiActionMissionError("continuity_supplier must be callable")
        permit = issue_ordered_simulation_permit(
            evidence,
            ttl_s=ttl_s,
            now_monotonic=now_monotonic,
            interlock_max_age_s=interlock_max_age_s,
        )
        cursor = object.__new__(cls)
        object.__setattr__(cursor, "_bindings", bindings)
        object.__setattr__(cursor, "_continuity_supplier", continuity_supplier)
        object.__setattr__(cursor, "_permit", permit)
        object.__setattr__(cursor, "_plan_sha256", evidence.plan_sha256)
        object.__setattr__(cursor, "_starting_ordinal", starting_ordinal)
        object.__setattr__(
            cursor,
            "_cursor_context_sha256",
            _stable_hash(
                {
                    "schema": "rocell.zero_authority.mission_authorization_cursor.v1",
                    "authorization_v2_context_sha256": permit.context_sha256,
                    "plan_sha256": evidence.plan_sha256,
                    "starting_ordinal": starting_ordinal,
                    "bindings": [item.to_dict() for item in bindings],
                }
            ),
        )
        object.__setattr__(cursor, "_sealed", True)
        return cursor

    @property
    def plan_sha256(self) -> str:
        return self._plan_sha256

    @property
    def expected_bindings(self) -> tuple[MissionCommandAuthorizationBinding, ...]:
        return self._bindings

    @property
    def starting_ordinal(self) -> int:
        return self._starting_ordinal

    @property
    def next_ordinal(self) -> int | None:
        relative = self._permit.next_ordinal
        return None if relative is None else self._starting_ordinal + relative

    @property
    def zero_authority(self) -> bool:
        return self._permit.authority == "SIMULATION_ONLY_NO_PHYSICAL_RELEASE"

    @property
    def can_authorize_live_transport(self) -> bool:
        return False

    @property
    def complete(self) -> bool:
        return self._permit.complete

    def consume(
        self, binding: MissionCommandAuthorizationBinding
    ) -> MissionCommandAuthorizationReceipt:
        if self._sealed is not True:
            raise MultiActionMissionError("authorization cursor seal is invalid")
        binding.__post_init__()
        next_ordinal = self.next_ordinal
        if next_ordinal is None:
            raise MultiActionMissionError("mission authorization cursor is exhausted")
        relative = next_ordinal - self._starting_ordinal
        expected = self._bindings[relative]
        if binding != expected or binding.absolute_ordinal != next_ordinal:
            raise MultiActionMissionError(
                "mission command was skipped, duplicated, mutated, or reordered"
            )
        continuity, now_monotonic = self._continuity_supplier(binding, relative)
        underlying = self._permit.consume_next(
            ordinal=relative,
            action_occurrence_id=binding.action_occurrence_sha256,
            command=binding.simulation_command,
            continuity=continuity,
            now_monotonic=now_monotonic,
        )
        return MissionCommandAuthorizationReceipt._issued(
            binding,
            plan_sha256=self._plan_sha256,
            starting_ordinal=self._starting_ordinal,
            authorization_v2_receipt_sha256=canonical_record_sha256(
                underlying.to_dict()
            ),
            cursor_context_sha256=self._cursor_context_sha256,
        )


@dataclass(frozen=True, slots=True)
class CompletedMissionAuthorizationCursor:
    """Zero-command cursor used only when every journal is already PARKED."""

    plan_sha256: str

    def __post_init__(self) -> None:
        _digest(self.plan_sha256, "completed cursor plan sha256")

    @property
    def expected_bindings(self) -> tuple[MissionCommandAuthorizationBinding, ...]:
        return ()

    @property
    def starting_ordinal(self) -> None:
        return None

    @property
    def next_ordinal(self) -> None:
        return None

    @property
    def zero_authority(self) -> bool:
        return True

    @property
    def can_authorize_live_transport(self) -> bool:
        return False

    @property
    def complete(self) -> bool:
        return True

    def consume(
        self, binding: MissionCommandAuthorizationBinding
    ) -> MissionCommandAuthorizationReceipt:
        del binding
        raise MultiActionMissionError("completed authorization cursor has no commands")


@dataclass(frozen=True, slots=True)
class ActionOutcomeReceipt:
    action_index: int
    action_occurrence_id: str
    semantic_sha256: str
    contact_event_ids: tuple[str, ...]
    checkpoint_id: str
    observation_sequence: int
    observed_at: RuntimeInstant
    evidence_sha256: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.action_index, bool)
            or not isinstance(self.action_index, int)
            or self.action_index < 0
        ):
            raise MultiActionMissionError("outcome action_index must be nonnegative")
        _identifier(self.action_occurrence_id, "outcome action occurrence ID")
        _digest(self.semantic_sha256, "outcome semantic sha256")
        if type(self.contact_event_ids) is not tuple or not self.contact_event_ids:
            raise MultiActionMissionError(
                "outcome contact_event_ids must be a non-empty tuple"
            )
        for event_id in self.contact_event_ids:
            _identifier(event_id, "outcome contact event ID")
        if len(self.contact_event_ids) != len(set(self.contact_event_ids)):
            raise MultiActionMissionError("outcome contact event IDs are duplicated")
        _identifier(self.checkpoint_id, "outcome checkpoint ID")
        if (
            isinstance(self.observation_sequence, bool)
            or not isinstance(self.observation_sequence, int)
            or self.observation_sequence < 0
        ):
            raise MultiActionMissionError("outcome observation sequence is invalid")
        if not isinstance(self.observed_at, RuntimeInstant):
            raise MultiActionMissionError("outcome observed_at is invalid")
        _digest(self.evidence_sha256, "outcome evidence sha256")
        if self.evidence_sha256 != _stable_hash(self.core_document()):
            raise MultiActionMissionError("outcome receipt evidence hash is inconsistent")

    def core_document(self) -> dict[str, object]:
        return {
            "action_index": self.action_index,
            "action_occurrence_id": self.action_occurrence_id,
            "semantic_sha256": self.semantic_sha256,
            "contact_event_ids": list(self.contact_event_ids),
            "checkpoint_id": self.checkpoint_id,
            "observation_sequence": self.observation_sequence,
            "observed_at": _instant_dict(self.observed_at),
        }

    @classmethod
    def from_observation(
        cls,
        action_index: int,
        observation: OutcomeObservation[object],
    ) -> "ActionOutcomeReceipt":
        if type(observation.outcome) is not ObservedSemanticOutcome:
            raise MultiActionMissionError(
                "outcome observation lacks a semantic outcome"
            )
        outcome = observation.outcome
        core = {
            "action_index": action_index,
            "action_occurrence_id": outcome.action_occurrence_id,
            "semantic_sha256": outcome.semantic_sha256,
            "contact_event_ids": list(outcome.contact_event_ids),
            "checkpoint_id": observation.checkpoint_id,
            "observation_sequence": observation.sequence,
            "observed_at": _instant_dict(observation.observed_at),
        }
        return cls(
            action_index=action_index,
            action_occurrence_id=outcome.action_occurrence_id,
            semantic_sha256=outcome.semantic_sha256,
            contact_event_ids=outcome.contact_event_ids,
            checkpoint_id=observation.checkpoint_id,
            observation_sequence=observation.sequence,
            observed_at=observation.observed_at,
            evidence_sha256=_stable_hash(core),
        )

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        return {**self.core_document(), "evidence_sha256": self.evidence_sha256}


@dataclass(frozen=True, slots=True)
class MissionBoundaryRecord:
    boundary: MissionBoundary
    operation_id: str
    action_index: int | None
    status: BoundaryStatus
    started_at: RuntimeInstant
    completed_at: RuntimeInstant
    fault_code: str | None = None
    evidence_sha256: str | None = None
    schema: str = ZERO_AUTHORITY_MULTI_ACTION_RECORD_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != ZERO_AUTHORITY_MULTI_ACTION_RECORD_SCHEMA:
            raise MultiActionMissionError("unsupported mission record schema")
        if not isinstance(self.boundary, MissionBoundary):
            raise MultiActionMissionError("boundary must be MissionBoundary")
        _identifier(self.operation_id, "operation_id")
        if self.action_index is not None and (
            isinstance(self.action_index, bool)
            or not isinstance(self.action_index, int)
            or self.action_index < 0
        ):
            raise MultiActionMissionError("action_index must be nonnegative or None")
        if not isinstance(self.status, BoundaryStatus):
            raise MultiActionMissionError("status must be BoundaryStatus")
        if not isinstance(self.started_at, RuntimeInstant) or not isinstance(
            self.completed_at, RuntimeInstant
        ):
            raise MultiActionMissionError("record times must be RuntimeInstant values")
        if (
            self.started_at.clock_id != self.completed_at.clock_id
            or self.started_at.tick_period_ns != self.completed_at.tick_period_ns
            or self.completed_at.tick < self.started_at.tick
        ):
            raise MultiActionMissionError("record times are not monotonic")
        if self.fault_code is not None:
            _identifier(self.fault_code, "fault_code")
        if self.status is BoundaryStatus.FAILED and self.fault_code is None:
            raise MultiActionMissionError("a failed boundary needs a fault_code")
        if self.status is not BoundaryStatus.FAILED and self.fault_code is not None:
            raise MultiActionMissionError("a successful boundary cannot have a fault")
        if self.evidence_sha256 is not None:
            _digest(self.evidence_sha256, "evidence_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "boundary": self.boundary.value,
            "operation_id": self.operation_id,
            "action_index": self.action_index,
            "status": self.status.value,
            "started_at": _instant_dict(self.started_at),
            "completed_at": _instant_dict(self.completed_at),
            "fault_code": self.fault_code,
            "evidence_sha256": self.evidence_sha256,
        }


@dataclass(frozen=True, slots=True)
class MissionFailure:
    boundary: MissionBoundary
    operation_id: str
    action_index: int | None
    fault_code: str
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, MissionBoundary):
            raise MultiActionMissionError("failure boundary must be MissionBoundary")
        _identifier(self.operation_id, "operation_id")
        _identifier(self.fault_code, "fault_code")
        if not isinstance(self.detail, str):
            raise MultiActionMissionError("failure detail must be text")
        if len(self.detail) > 1024:
            raise MultiActionMissionError("failure detail exceeds 1024 characters")
        if any(ord(character) < 32 and character not in "\t" for character in self.detail):
            raise MultiActionMissionError("failure detail contains a control character")

    def to_dict(self) -> dict[str, object]:
        return {
            "boundary": self.boundary.value,
            "operation_id": self.operation_id,
            "action_index": self.action_index,
            "fault_code": self.fault_code,
            "detail": self.detail,
        }


_REPORT_ISSUER = object()
_ARM_COMMAND_BOUNDARIES = frozenset(_PHASE_PRIMITIVES)


@dataclass(frozen=True, slots=True)
class MultiActionMissionReport:
    """Factory-sealed, internally cross-validated mission result."""

    _issuer: object = field(default=None, init=False, repr=False, compare=False)
    mission_id: str
    plan_sha256: str
    runtime_id: str
    occurrence_ids: tuple[str, ...]
    initial_states: tuple[ActionJournalState, ...]
    final_states: tuple[ActionJournalState, ...]
    records: tuple[MissionBoundaryRecord, ...]
    outcome_receipts: tuple[ActionOutcomeReceipt, ...]
    authorization_receipt_sha256s: tuple[str, ...]
    authorization_complete: bool
    journals_verified: bool
    primary_failure: MissionFailure | None
    cleanup_failures: tuple[MissionFailure, ...]
    zero_authority: bool
    hardware_accessed: bool
    hardware_commands_generated: int
    schema: str = ZERO_AUTHORITY_MULTI_ACTION_REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self._issuer is not _REPORT_ISSUER:
            raise MultiActionMissionError(
                "multi-action reports may only be issued by the mission kernel"
            )
        if self.schema != ZERO_AUTHORITY_MULTI_ACTION_REPORT_SCHEMA:
            raise MultiActionMissionError("unsupported multi-action report schema")
        _identifier(self.mission_id, "report mission_id")
        _identifier(self.runtime_id, "report runtime_id")
        _digest(self.plan_sha256, "report plan_sha256")
        if type(self.occurrence_ids) is not tuple or not self.occurrence_ids:
            raise MultiActionMissionError("report occurrence_ids must be non-empty tuple")
        if not all(
            isinstance(value, str) and re.fullmatch(r"occ-[0-9a-f]{32}", value)
            for value in self.occurrence_ids
        ):
            raise MultiActionMissionError("report occurrence ID is malformed")
        if len(self.occurrence_ids) != len(set(self.occurrence_ids)):
            raise MultiActionMissionError("report occurrence IDs are duplicated")
        if (
            type(self.initial_states) is not tuple
            or type(self.final_states) is not tuple
            or len(self.initial_states) != len(self.occurrence_ids)
            or len(self.final_states) != len(self.occurrence_ids)
        ):
            raise MultiActionMissionError(
                "report state cardinality does not match occurrences"
            )
        _validate_state_prefix(self.initial_states)
        _validate_state_prefix(self.final_states)
        if type(self.records) is not tuple or not self.records:
            raise MultiActionMissionError("report records must be non-empty tuple")
        if not all(type(item) is MissionBoundaryRecord for item in self.records):
            raise MultiActionMissionError("report contains an invalid boundary record")
        if self.records[0].boundary is not MissionBoundary.VALIDATE_PORTS_INITIAL:
            raise MultiActionMissionError("report does not begin with port validation")
        if self.records[-1].boundary not in {
            MissionBoundary.VALIDATE_PORTS_FINAL,
            MissionBoundary.VALIDATE_JOURNALS_FINAL,
        }:
            raise MultiActionMissionError("report does not end with final validation")
        record_ids = tuple(item.operation_id for item in self.records)
        if len(record_ids) != len(set(record_ids)):
            raise MultiActionMissionError("report operation accounting is duplicated")
        first_time = self.records[0].started_at
        previous = self.records[0].completed_at
        for record in self.records:
            record.__post_init__()
            if record.action_index is not None and record.action_index >= len(
                self.occurrence_ids
            ):
                raise MultiActionMissionError(
                    "report record action_index exceeds occurrence cardinality"
                )
            expected_prefix = (
                f"{self.mission_id}.mission"
                if record.action_index is None
                else f"{self.mission_id}.a{record.action_index:06d}"
            )
            expected_operation_id = (
                f"{expected_prefix}."
                f"{record.boundary.value.lower().replace('_', '-')}"
            )
            if record.operation_id != expected_operation_id:
                raise MultiActionMissionError(
                    "report record operation ID is not derived from its boundary"
                )
            if (
                record.started_at.clock_id != first_time.clock_id
                or record.started_at.tick_period_ns != first_time.tick_period_ns
                or record.started_at.tick < previous.tick
            ):
                raise MultiActionMissionError(
                    "report records are reordered or use inconsistent clocks"
                )
            previous = record.completed_at
        if self.primary_failure is not None and type(self.primary_failure) is not MissionFailure:
            raise MultiActionMissionError("report primary failure has invalid type")
        if type(self.cleanup_failures) is not tuple or not all(
            type(item) is MissionFailure for item in self.cleanup_failures
        ):
            raise MultiActionMissionError("report cleanup failures are invalid")
        failures = (
            *((self.primary_failure,) if self.primary_failure is not None else ()),
            *self.cleanup_failures,
        )
        for failure in failures:
            failure.__post_init__()
        failure_keys = tuple(
            (item.boundary, item.operation_id, item.action_index, item.fault_code)
            for item in failures
        )
        if len(failure_keys) != len(set(failure_keys)):
            raise MultiActionMissionError("report failure accounting is duplicated")
        failed_record_keys = tuple(
            (item.boundary, item.operation_id, item.action_index, item.fault_code)
            for item in self.records
            if item.status is BoundaryStatus.FAILED
        )
        if failed_record_keys != failure_keys:
            raise MultiActionMissionError(
                "failed boundary accounting order does not match reported failures"
            )
        if type(self.outcome_receipts) is not tuple or not all(
            type(item) is ActionOutcomeReceipt for item in self.outcome_receipts
        ):
            raise MultiActionMissionError("report outcome receipts are invalid")
        outcome_indexes = tuple(item.action_index for item in self.outcome_receipts)
        if outcome_indexes != tuple(sorted(set(outcome_indexes))):
            raise MultiActionMissionError("outcome receipts are duplicated or reordered")
        for outcome in self.outcome_receipts:
            outcome.__post_init__()
            if (
                outcome.action_index >= len(self.occurrence_ids)
                or outcome.action_occurrence_id
                != self.occurrence_ids[outcome.action_index]
            ):
                raise MultiActionMissionError(
                    "outcome receipt is bound to the wrong occurrence"
                )
            observed = tuple(
                record
                for record in self.records
                if record.boundary is MissionBoundary.OUTCOME_OBSERVATION
                and record.action_index == outcome.action_index
            )
            journaled = tuple(
                record
                for record in self.records
                if record.boundary is MissionBoundary.JOURNAL_OUTCOME_CONFIRMED
                and record.action_index == outcome.action_index
            )
            if (
                len(observed) != 1
                or observed[0].status is not BoundaryStatus.PASSED
                or observed[0].evidence_sha256 != outcome.evidence_sha256
                or len(journaled) != 1
                or journaled[0].evidence_sha256 != outcome.evidence_sha256
            ):
                raise MultiActionMissionError(
                    "outcome receipt is not bound to observation and journal records"
                )
        if type(self.authorization_receipt_sha256s) is not tuple:
            raise MultiActionMissionError(
                "authorization receipt hashes must be immutable tuple"
            )
        for receipt_sha256 in self.authorization_receipt_sha256s:
            _digest(receipt_sha256, "authorization receipt sha256")
        if len(self.authorization_receipt_sha256s) != len(
            set(self.authorization_receipt_sha256s)
        ):
            raise MultiActionMissionError("authorization receipts are duplicated")
        recorded_authorizations = tuple(
            cast(str, record.evidence_sha256)
            for record in self.records
            if record.boundary in _ARM_COMMAND_BOUNDARIES
            and record.evidence_sha256 is not None
        )
        if self.authorization_receipt_sha256s != recorded_authorizations:
            raise MultiActionMissionError(
                "authorization receipts do not match command operation accounting"
            )
        if type(self.authorization_complete) is not bool:
            raise MultiActionMissionError("authorization_complete must be boolean")
        if type(self.journals_verified) is not bool:
            raise MultiActionMissionError("journals_verified must be boolean")
        if (
            self.zero_authority is not True
            or self.hardware_accessed is not False
            or isinstance(self.hardware_commands_generated, bool)
            or self.hardware_commands_generated != 0
        ):
            raise MultiActionMissionError("report violates zero physical authority")
        if self.primary_failure is None and not self.cleanup_failures:
            if not self.authorization_complete:
                raise MultiActionMissionError(
                    "successful report has an incomplete authorization cursor"
                )
            if not self.journals_verified:
                raise MultiActionMissionError(
                    "successful report has unverified final journals"
                )
            if any(state is not ActionJournalState.PARKED for state in self.final_states):
                raise MultiActionMissionError(
                    "successful report requires every action journal PARKED"
                )

    @classmethod
    def _issued(cls, **values: object) -> "MultiActionMissionReport":
        report = object.__new__(cls)
        object.__setattr__(report, "_issuer", _REPORT_ISSUER)
        for name in (
            "mission_id",
            "plan_sha256",
            "runtime_id",
            "occurrence_ids",
            "initial_states",
            "final_states",
            "records",
            "outcome_receipts",
            "authorization_receipt_sha256s",
            "authorization_complete",
            "journals_verified",
            "primary_failure",
            "cleanup_failures",
            "zero_authority",
            "hardware_accessed",
            "hardware_commands_generated",
            "schema",
        ):
            object.__setattr__(
                report,
                name,
                values.get(name, ZERO_AUTHORITY_MULTI_ACTION_REPORT_SCHEMA)
                if name == "schema"
                else values[name],
            )
        report.__post_init__()
        return report

    @property
    def passed(self) -> bool:
        self.__post_init__()
        return (
            self.primary_failure is None
            and not self.cleanup_failures
            and all(state is ActionJournalState.PARKED for state in self.final_states)
            and self.zero_authority
            and not self.hardware_accessed
            and self.hardware_commands_generated == 0
            and self.authorization_complete
            and self.journals_verified
        )

    @property
    def contact_operation_ids(self) -> tuple[str, ...]:
        self.__post_init__()
        return tuple(
            item.operation_id
            for item in self.records
            if item.boundary
            in {MissionBoundary.CONTACT_EXECUTE, MissionBoundary.DEVICE_CONTACT}
            and item.status is not BoundaryStatus.RESUMED
        )

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        self.__post_init__()
        value: dict[str, object] = {
            "schema": self.schema,
            "mission_id": self.mission_id,
            "plan_sha256": self.plan_sha256,
            "runtime_id": self.runtime_id,
            "occurrence_ids": list(self.occurrence_ids),
            "initial_states": [item.value for item in self.initial_states],
            "final_states": [item.value for item in self.final_states],
            "records": [item.to_dict() for item in self.records],
            "outcome_receipts": [item.to_dict() for item in self.outcome_receipts],
            "authorization_receipt_sha256s": list(
                self.authorization_receipt_sha256s
            ),
            "authorization_complete": self.authorization_complete,
            "journals_verified": self.journals_verified,
            "primary_failure": (
                self.primary_failure.to_dict()
                if self.primary_failure is not None
                else None
            ),
            "cleanup_failures": [item.to_dict() for item in self.cleanup_failures],
            "passed": self.passed,
            "zero_authority": self.zero_authority,
            "hardware_accessed": self.hardware_accessed,
            "hardware_commands_generated": self.hardware_commands_generated,
            "physical_release_effect": "NONE",
        }
        if include_hash:
            value["report_sha256"] = _stable_hash(value)
        return value

    @property
    def report_sha256(self) -> str:
        return _stable_hash(self.to_dict(include_hash=False))


@dataclass(frozen=True, slots=True)
class _BoundaryAbort(Exception):
    failure: MissionFailure


def prepare_zero_authority_mission_journals(
    root: Path,
    spec: MultiActionMissionSpec[CommandT, ContactT],
    *,
    created_at_ns: int,
) -> tuple[ZeroAuthorityMissionJournal, ...]:
    """Create every durable action intent before a runtime is allowed to run.

    The function intentionally creates new journals only.  A caller resuming a
    process must explicitly reopen the previously returned directories, which
    prevents an accidental "resume" from silently substituting a new intent.
    """

    if not isinstance(spec, MultiActionMissionSpec):
        raise TypeError("spec must be MultiActionMissionSpec")
    if isinstance(created_at_ns, bool) or not isinstance(created_at_ns, int):
        raise MultiActionMissionError("created_at_ns must be an integer")
    if not 0 < created_at_ns <= 2**63 - 1:
        raise MultiActionMissionError("created_at_ns is outside the journal range")
    if created_at_ns + len(spec.actions) - 1 > 2**63 - 1:
        raise MultiActionMissionError("per-action journal timestamps would overflow")
    return tuple(
        ZeroAuthorityMissionJournal.create(
            root,
            occurrence,
            created_at_ns=created_at_ns + ordinal,
        )
        for ordinal, occurrence in enumerate(spec.occurrences)
    )


def reopen_zero_authority_mission_journals(
    directories: tuple[Path, ...],
) -> tuple[ZeroAuthorityMissionJournal, ...]:
    """Strictly reopen a caller-retained journal set after process restart."""

    if not isinstance(directories, tuple) or not directories:
        raise MultiActionMissionError(
            "journal directories must be a non-empty immutable tuple"
        )
    return tuple(ZeroAuthorityMissionJournal.open(path) for path in directories)


def _validate_journals(
    spec: MultiActionMissionSpec[object, object],
    journals: tuple[ZeroAuthorityMissionJournal, ...],
) -> tuple[MissionJournalSnapshot, ...]:
    if not isinstance(journals, tuple) or len(journals) != len(spec.actions):
        raise MultiActionMissionError("journals must match the action count exactly")
    if not all(isinstance(item, ZeroAuthorityMissionJournal) for item in journals):
        raise MultiActionMissionError("journals contains an invalid journal handle")
    if len({item.directory.resolve() for item in journals}) != len(journals):
        raise MultiActionMissionError("journals contains a duplicate directory")
    snapshots = tuple(item.snapshot() for item in journals)
    for expected, snapshot in zip(spec.occurrences, snapshots):
        if snapshot.occurrence != expected:
            raise MultiActionMissionError(
                "journal occurrence does not match the immutable mission plan"
            )
    _validate_global_journal_prefix(snapshots)
    return snapshots


def _fault(exc: Exception) -> tuple[str, str]:
    try:
        raw_detail = str(exc)[:1024]
    except Exception:
        raw_detail = f"{type(exc).__name__} raised without a printable detail"
    detail = "".join(
        character
        if ord(character) >= 32 and ord(character) != 127
        else " "
        for character in raw_detail
    )
    if isinstance(exc, RuntimePortOperationError):
        return exc.fault_code, detail
    if isinstance(exc, MissionJournalError):
        return "MISSION_JOURNAL_ERROR", detail
    if isinstance(exc, AuthorizationV2Error):
        return "SIMULATION_AUTHORIZATION_DENIED", detail
    if isinstance(exc, MultiActionMissionError):
        return "MISSION_KERNEL_ERROR", detail
    name = re.sub(r"[^A-Z0-9]+", "_", type(exc).__name__.upper()).strip("_")
    return (name or "UNEXPECTED_ERROR")[:128], detail


def _journal_detail(fault_code: str) -> str:
    parsed = re.sub(r"[^A-Z0-9]+", "_", fault_code.upper()).strip("_")
    return f"KERNEL_{parsed or 'FAILURE'}"[:128]


def _journal_time(
    journal: ZeroAuthorityMissionJournal, instant: RuntimeInstant
) -> int:
    snapshot = journal.snapshot()
    scale = instant.tick_period_ns if instant.tick_period_ns is not None else 1
    derived = instant.tick * scale + 1
    return max(snapshot.events[-1].event_time_ns + 1, derived)


def _same_clock(
    value: RuntimeInstant,
    started_at: RuntimeInstant,
    deadline: RuntimeDeadline | None,
) -> None:
    if (
        value.clock_id != started_at.clock_id
        or value.tick_period_ns != started_at.tick_period_ns
        or value.tick < started_at.tick
    ):
        raise MultiActionMissionError("operation result time is not monotonic")
    if deadline is not None and (
        value.clock_id != deadline.at.clock_id
        or value.tick_period_ns != deadline.at.tick_period_ns
        or value.tick > deadline.at.tick
    ):
        raise MultiActionMissionError("operation result exceeded its deadline")


def run_zero_authority_multi_action_mission(
    ports: MissionRuntimePorts[
        CommandT, FeedbackT, ObservationT, ContactT, OutcomeT
    ],
    spec: MultiActionMissionSpec[CommandT, ContactT],
    journals: tuple[ZeroAuthorityMissionJournal, ...],
    authorization: SimulationCommandAuthorizationCursor,
) -> MultiActionMissionReport:
    """Run or conservatively resume an ordered, journaled zero-authority mission.

    Contract/specification errors raise before orchestration.  Runtime and
    journal failures are returned in the report.  Later action contacts are
    never attempted after the first failure, while bounded cleanup failures are
    retained separately from the primary error.
    """

    if not isinstance(spec, MultiActionMissionSpec):
        raise TypeError("spec must be MultiActionMissionSpec")
    generic_ports = cast(
        MissionRuntimePorts[object, object, object, object, object], ports
    )
    # Execute from a private canonical snapshot.  The caller's dataclass graph
    # is never consulted again after this point.
    generic_spec = _materialize_mission_spec(
        cast(MultiActionMissionSpec[object, object], spec)
    )
    initial_contract = validate_runtime_ports(generic_ports)
    initial_contract_document = _contract_dict(initial_contract)
    initial_runtime_identity = _runtime_identity_document(generic_ports)
    initial_runtime_binding = _stable_hash(
        {
            "contract": initial_contract_document,
            "ports": initial_runtime_identity,
        }
    )
    if generic_ports.device_contact is generic_ports.outcome_observer or (
        generic_ports.device_contact.runtime_metadata.port_id
        == generic_ports.outcome_observer.runtime_metadata.port_id
    ):
        raise MultiActionMissionError(
            "outcome observation must be independent from device contact"
        )
    initial_snapshots = _validate_journals(generic_spec, journals)
    initial_states = tuple(item.current_state for item in initial_snapshots)
    authorization_schedule = build_mission_authorization_schedule(
        generic_spec, initial_snapshots
    )
    expected_authorization_type = (
        AuthorizationV2MissionCursor
        if authorization_schedule
        else CompletedMissionAuthorizationCursor
    )
    if isinstance(authorization, OrderedSimulationPermit) or type(
        authorization
    ) is not expected_authorization_type:
        raise MultiActionMissionError(
            "the concrete mission authorization-v2 cursor for the exact suffix is required"
        )
    if (
        authorization.plan_sha256 != generic_spec.plan_sha256
        or authorization.expected_bindings != authorization_schedule
        or authorization.starting_ordinal
        != (
            authorization_schedule[0].absolute_ordinal
            if authorization_schedule
            else None
        )
        or authorization.next_ordinal != authorization.starting_ordinal
        or authorization.zero_authority is not True
        or authorization.can_authorize_live_transport is not False
        or (not authorization_schedule and not authorization.complete)
    ):
        raise MultiActionMissionError(
            "authorization cursor does not match the exact safe mission suffix"
        )
    authorization_by_ordinal = {
        item.absolute_ordinal: item for item in authorization_schedule
    }
    records: list[MissionBoundaryRecord] = []
    outcome_receipts: list[ActionOutcomeReceipt] = []
    authorization_receipt_sha256s: list[str] = []
    cleanup_failures: list[MissionFailure] = []
    primary_failure: MissionFailure | None = None
    previous_feedback_sequence: int | None = None
    previous_observation_sequence: int | None = None
    previous_outcome_sequence: int | None = None
    retraction_proven: set[str] = set()
    connected = False
    referenced = False
    last_known_snapshots = list(initial_snapshots)

    initial_clock_failure: Exception | None = None
    try:
        initial_now = generic_ports.clock.now()
        if not isinstance(initial_now, RuntimeInstant):
            raise MultiActionMissionError("runtime clock returned an invalid instant")
    except Exception as exc:
        initial_clock_failure = exc
        initial_now = RuntimeInstant("kernel-fallback-clock", 0, 1)
    last_runtime_instant = initial_now
    initial_status = (
        BoundaryStatus.FAILED
        if initial_clock_failure is not None
        else BoundaryStatus.PASSED
    )
    initial_fault = (
        _fault(initial_clock_failure)[0]
        if initial_clock_failure is not None
        else None
    )
    records.append(
        MissionBoundaryRecord(
            MissionBoundary.VALIDATE_PORTS_INITIAL,
            generic_spec.operation_id(MissionBoundary.VALIDATE_PORTS_INITIAL),
            None,
            initial_status,
            initial_now,
            initial_now,
            fault_code=initial_fault,
            evidence_sha256=(
                None if initial_clock_failure is not None else initial_runtime_binding
            ),
        )
    )
    if initial_clock_failure is not None:
        initial_code, initial_detail = _fault(initial_clock_failure)
        primary_failure = MissionFailure(
            MissionBoundary.VALIDATE_PORTS_INITIAL,
            generic_spec.operation_id(MissionBoundary.VALIDATE_PORTS_INITIAL),
            None,
            initial_code,
            initial_detail,
        )

    def deadline_for(
        boundary: MissionBoundary,
        action_index: int | None,
        started_at: RuntimeInstant,
    ) -> RuntimeDeadline:
        expire = (
            generic_spec.deadline_expiry_boundary is boundary
            and generic_spec.deadline_expiry_action_index == action_index
        )
        budget = 0 if expire else generic_spec.deadline_budget_ticks
        return RuntimeDeadline(
            RuntimeInstant(
                started_at.clock_id,
                started_at.tick + budget,
                started_at.tick_period_ns,
            )
        )

    def attempt(
        boundary: MissionBoundary,
        action_index: int | None,
        invoke: Callable[[RuntimeDeadline], object],
        validate: Callable[[object, RuntimeInstant, RuntimeDeadline], str | None],
        failure_evidence: Callable[[], str | None] | None = None,
    ) -> object:
        nonlocal last_runtime_instant
        operation_id = generic_spec.operation_id(boundary, action_index)
        started = last_runtime_instant
        try:
            started = generic_ports.clock.now()
            last_runtime_instant = started
            deadline = deadline_for(boundary, action_index, started)
            result = invoke(deadline)
            evidence = validate(result, started, deadline)
            completed = generic_ports.clock.now()
            _same_clock(completed, started, deadline)
            last_runtime_instant = completed
            records.append(
                MissionBoundaryRecord(
                    boundary,
                    operation_id,
                    action_index,
                    BoundaryStatus.PASSED,
                    started,
                    completed,
                    evidence_sha256=evidence,
                )
            )
            return result
        except Exception as exc:
            try:
                completed = generic_ports.clock.now()
                _same_clock(completed, started, None)
                last_runtime_instant = completed
            except Exception:
                completed = last_runtime_instant
            code, detail = _fault(exc)
            try:
                evidence = (
                    failure_evidence() if failure_evidence is not None else None
                )
            except Exception:
                evidence = None
            records.append(
                MissionBoundaryRecord(
                    boundary,
                    operation_id,
                    action_index,
                    BoundaryStatus.FAILED,
                    started,
                    completed,
                    fault_code=code,
                    evidence_sha256=evidence,
                )
            )
            raise _BoundaryAbort(
                MissionFailure(boundary, operation_id, action_index, code, detail)
            ) from exc

    def local_attempt(
        boundary: MissionBoundary,
        action_index: int | None,
        invoke: Callable[[], str | None],
        *,
        resumed: bool = False,
        failure_evidence: Callable[[], str | None] | None = None,
    ) -> str | None:
        nonlocal last_runtime_instant
        operation_id = generic_spec.operation_id(boundary, action_index)
        started = last_runtime_instant
        try:
            started = generic_ports.clock.now()
            last_runtime_instant = started
            evidence = invoke()
            completed = generic_ports.clock.now()
            _same_clock(completed, started, None)
            last_runtime_instant = completed
            records.append(
                MissionBoundaryRecord(
                    boundary,
                    operation_id,
                    action_index,
                    BoundaryStatus.RESUMED if resumed else BoundaryStatus.PASSED,
                    started,
                    completed,
                    evidence_sha256=evidence,
                )
            )
            return evidence
        except Exception as exc:
            try:
                completed = generic_ports.clock.now()
                _same_clock(completed, started, None)
                last_runtime_instant = completed
            except Exception:
                completed = last_runtime_instant
            code, detail = _fault(exc)
            try:
                evidence = (
                    failure_evidence() if failure_evidence is not None else None
                )
            except Exception:
                evidence = None
            records.append(
                MissionBoundaryRecord(
                    boundary,
                    operation_id,
                    action_index,
                    BoundaryStatus.FAILED,
                    started,
                    completed,
                    fault_code=code,
                    evidence_sha256=evidence,
                )
            )
            raise _BoundaryAbort(
                MissionFailure(boundary, operation_id, action_index, code, detail)
            ) from exc

    def external_failure(
        boundary: MissionBoundary,
        action_index: int | None,
        exc: Exception,
    ) -> _BoundaryAbort:
        """Account for an exception raised outside an ``attempt`` wrapper."""

        nonlocal last_runtime_instant
        operation_id = generic_spec.operation_id(boundary, action_index)
        code, detail = _fault(exc)
        started = last_runtime_instant
        try:
            candidate = generic_ports.clock.now()
            _same_clock(candidate, started, None)
            last_runtime_instant = candidate
        except Exception:
            candidate = last_runtime_instant
        if any(record.operation_id == operation_id for record in records):
            # A wrapped boundary already accounted for this operation.  Never
            # manufacture a second record with the same stable operation ID.
            return _BoundaryAbort(
                MissionFailure(boundary, operation_id, action_index, code, detail)
            )
        records.append(
            MissionBoundaryRecord(
                boundary,
                operation_id,
                action_index,
                BoundaryStatus.FAILED,
                started,
                candidate,
                fault_code=code,
            )
        )
        return _BoundaryAbort(
            MissionFailure(boundary, operation_id, action_index, code, detail)
        )

    def validate_lifecycle(
        value: object,
        started: RuntimeInstant,
        deadline: RuntimeDeadline,
        *,
        operation_id: str,
        expected_state: str,
    ) -> str | None:
        if not isinstance(value, LifecycleResult):
            raise MultiActionMissionError("lifecycle result has invalid type")
        if value.operation_id != operation_id:
            raise MultiActionMissionError("lifecycle result is not correlated")
        _same_clock(value.observed_at, started, deadline)
        if not value.succeeded:
            raise RuntimePortOperationError(
                value.fault_code or "LIFECYCLE_FAILED", operation_id
            )
        if value.state != expected_state:
            raise MultiActionMissionError("lifecycle state is unexpected")
        return None

    def execute_command(
        boundary: MissionBoundary,
        action_index: int,
        waypoint_sequence: int,
        command: BoundOpaqueValue[object],
    ) -> ArmExecutionResult[object]:
        record_action_index = (
            None if boundary is MissionBoundary.PARK_EXECUTE else action_index
        )
        operation_id = generic_spec.operation_id(boundary, record_action_index)
        binding = authorization_by_ordinal.get(waypoint_sequence)
        receipt_holder: list[MissionCommandAuthorizationReceipt] = []

        def invoke(deadline: RuntimeDeadline) -> object:
            current = _validate_journals(generic_spec, journals)
            last_known_snapshots[:] = current
            if (
                binding is None
                or binding.phase is not boundary
                or binding.canonical_payload_sha256 != command.binding_sha256
                or authorization.next_ordinal != waypoint_sequence
            ):
                raise MultiActionMissionError(
                    "arm command is absent from the safe authorization suffix"
                )
            # Verify the sole canonical materialization, consume a sealed
            # authorization-v2 receipt, then verify once more immediately
            # before handing those exact bytes to the runtime port.
            command.verified_payload()
            receipt = authorization.consume(binding)
            if type(receipt) is not MissionCommandAuthorizationReceipt:
                raise MultiActionMissionError(
                    "authorization cursor returned an unsealed receipt"
                )
            receipt.__post_init__()
            if (
                receipt.absolute_ordinal != binding.absolute_ordinal
                or receipt.action_occurrence_sha256
                != binding.action_occurrence_sha256
                or receipt.phase is not boundary
                or receipt.canonical_payload_sha256 != command.binding_sha256
                or receipt.simulation_command_sha256 != binding.command_sha256
                or receipt.plan_sha256 != generic_spec.plan_sha256
                or receipt.starting_ordinal
                != authorization_schedule[0].absolute_ordinal
                or not receipt.zero_authority
            ):
                raise MultiActionMissionError(
                    "authorization receipt does not bind the exact command"
                )
            receipt_holder.append(receipt)
            authorization_receipt_sha256s.append(receipt.receipt_sha256)
            payload = command.verified_payload()
            return generic_ports.arm_execution.execute(
                ArmExecutionRequest(
                    generic_spec.mission_id,
                    operation_id,
                    action_index,
                    waypoint_sequence,
                    payload,
                    deadline,
                ),
                generic_ports.cancellation,
            )

        def validate(
            value: object, started: RuntimeInstant, deadline: RuntimeDeadline
        ) -> str:
            if not isinstance(value, ArmExecutionResult):
                raise MultiActionMissionError("arm result has invalid type")
            if value.operation_id != operation_id:
                raise MultiActionMissionError("arm result is not correlated")
            _same_clock(value.observed_at, started, deadline)
            if not value.accepted or not value.completed:
                raise RuntimePortOperationError(
                    value.fault_code or "ARM_EXECUTION_INCOMPLETE", operation_id
                )
            if len(receipt_holder) != 1:
                raise MultiActionMissionError(
                    "arm execution lacks one sealed authorization receipt"
                )
            return receipt_holder[0].receipt_sha256

        result = attempt(
            boundary,
            record_action_index,
            invoke,
            validate,
            failure_evidence=lambda: (
                receipt_holder[0].receipt_sha256 if receipt_holder else None
            ),
        )
        assert isinstance(result, ArmExecutionResult)
        return result

    def read_feedback(
        boundary: MissionBoundary, action_index: int
    ) -> ArmFeedbackSample[object]:
        nonlocal previous_feedback_sequence
        operation_id = generic_spec.operation_id(boundary, action_index)

        def validate(
            value: object, started: RuntimeInstant, deadline: RuntimeDeadline
        ) -> str:
            if not isinstance(value, ArmFeedbackSample):
                raise MultiActionMissionError("feedback result has invalid type")
            request = ArmFeedbackRequest(
                generic_spec.mission_id, operation_id, action_index, deadline
            )
            validate_arm_feedback_sample(
                request,
                value,
                previous_sequence=previous_feedback_sequence,
                require_fresh=True,
            )
            _same_clock(value.observed_at, started, deadline)
            if value.feedback_binding_sha256 is None:
                raise MultiActionMissionError("feedback binding is missing")
            return value.feedback_binding_sha256

        value = attempt(
            boundary,
            action_index,
            lambda deadline: generic_ports.arm_feedback.read_feedback(
                ArmFeedbackRequest(
                    generic_spec.mission_id, operation_id, action_index, deadline
                ),
                generic_ports.cancellation,
            ),
            validate,
        )
        assert isinstance(value, ArmFeedbackSample)
        previous_feedback_sequence = value.sequence
        return value

    def poll_gate(boundary: MissionBoundary, action_index: int) -> str:
        operation_id = generic_spec.operation_id(boundary, action_index)
        status = generic_ports.cancellation.poll(
            CancellationCheck(generic_spec.mission_id, operation_id)
        )
        if not isinstance(status, CancellationStatus):
            raise MultiActionMissionError("cancellation result has invalid type")
        if status.checkpoint_id != operation_id:
            raise RuntimePortOperationError(
                "CANCELLATION_CORRELATION_MISMATCH", operation_id
            )
        if status.cancelled:
            raise RuntimePortOperationError(
                "OPERATION_CANCELLED", operation_id, status.reason
            )
        return generic_spec.preflight_binding_sha256

    def journal_transition(
        boundary: MissionBoundary,
        action_index: int,
        transition: Callable[[int], MissionJournalSnapshot],
        evidence_sha256: str,
        *,
        resumed: bool = False,
    ) -> None:
        journal = journals[action_index]
        committed: list[MissionJournalSnapshot] = []

        def commit() -> str:
            if resumed:
                current = _validate_journals(generic_spec, journals)
                committed.append(current[action_index])
                last_known_snapshots[:] = current
                return evidence_sha256
            committed.append(
                transition(_journal_time(journal, generic_ports.clock.now()))
            )
            current = _validate_journals(generic_spec, journals)
            committed[0] = current[action_index]
            last_known_snapshots[:] = current
            return evidence_sha256

        local_attempt(
            boundary,
            action_index,
            commit,
            resumed=resumed,
            failure_evidence=lambda: evidence_sha256,
        )
        if len(committed) != 1:
            raise MultiActionMissionError("journal transition did not return a snapshot")
        last_known_snapshots[action_index] = committed[0]

    def mark_primary_journal_failure(failure: MissionFailure) -> None:
        if failure.action_index is None or failure.boundary in {
            MissionBoundary.PARK_EXECUTE,
            MissionBoundary.PARK_FEEDBACK,
            MissionBoundary.JOURNAL_PARKED,
            MissionBoundary.JOURNAL_FAILURE_STATE,
        }:
            return
        journal = journals[failure.action_index]
        failure_evidence = _stable_hash(failure.to_dict())

        def persist_terminal_state() -> str:
            snapshot = journal.snapshot()
            timestamp = _journal_time(journal, generic_ports.clock.now())
            detail = _journal_detail(failure.fault_code)
            if snapshot.current_state in {
                ActionJournalState.INTENT_COMMITTED,
                ActionJournalState.PRE_CONTACT,
                ActionJournalState.OUTCOME_CONFIRMED,
                ActionJournalState.RETRACTED,
            }:
                journal.mark_faulted(
                    event_time_ns=timestamp,
                    detail_code=detail,
                    evidence_sha256=failure_evidence,
                )
            elif snapshot.current_state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED:
                journal.mark_outcome_uncertain(
                    event_time_ns=timestamp,
                    detail_code=detail,
                    evidence_sha256=failure_evidence,
                )
            current = _validate_journals(generic_spec, journals)
            last_known_snapshots[:] = current
            return failure_evidence

        try:
            local_attempt(
                MissionBoundary.JOURNAL_FAILURE_STATE,
                failure.action_index,
                persist_terminal_state,
            )
        except _BoundaryAbort as abort:
            cleanup_failures.append(abort.failure)

    def all_safe_to_park() -> bool:
        for journal in journals:
            try:
                snapshot = journal.snapshot()
            except Exception as exc:
                cleanup_failures.append(
                    external_failure(MissionBoundary.PARK_EXECUTE, None, exc).failure
                )
                return False
            if not snapshot.contact_may_have_occurred:
                continue
            if snapshot.current_state in {
                ActionJournalState.RETRACTED,
                ActionJournalState.PARKED,
            }:
                continue
            if snapshot.occurrence.occurrence_id in retraction_proven:
                continue
            return False
        return True

    def run_park(*, cleanup: bool) -> None:
        operation_index = len(generic_spec.actions)
        try:
            execute_command(
                MissionBoundary.PARK_EXECUTE,
                operation_index,
                operation_index * 4,
                cast(BoundOpaqueValue[object], generic_spec.park_command),
            )
            feedback_id = generic_spec.operation_id(MissionBoundary.PARK_FEEDBACK)

            def validate_park_feedback(
                value: object,
                started: RuntimeInstant,
                deadline: RuntimeDeadline,
            ) -> str:
                nonlocal previous_feedback_sequence
                if not isinstance(value, ArmFeedbackSample):
                    raise MultiActionMissionError(
                        "park feedback result has invalid type"
                    )
                request = ArmFeedbackRequest(
                    generic_spec.mission_id, feedback_id, None, deadline
                )
                validate_arm_feedback_sample(
                    request,
                    value,
                    previous_sequence=previous_feedback_sequence,
                    require_fresh=True,
                )
                _same_clock(value.observed_at, started, deadline)
                if value.feedback_binding_sha256 is None:
                    raise MultiActionMissionError("park feedback binding is missing")
                previous_feedback_sequence = value.sequence
                return value.feedback_binding_sha256

            raw_park_feedback = attempt(
                MissionBoundary.PARK_FEEDBACK,
                None,
                lambda deadline: generic_ports.arm_feedback.read_feedback(
                    ArmFeedbackRequest(
                        generic_spec.mission_id, feedback_id, None, deadline
                    ),
                    generic_ports.cancellation,
                ),
                validate_park_feedback,
            )
            assert isinstance(raw_park_feedback, ArmFeedbackSample)
            park_feedback = raw_park_feedback
            assert park_feedback.feedback_binding_sha256 is not None
            try:
                park_snapshots = _validate_journals(generic_spec, journals)
                last_known_snapshots[:] = park_snapshots
            except Exception as exc:
                abort = external_failure(
                    MissionBoundary.JOURNAL_PARKED, None, exc
                )
                if cleanup:
                    cleanup_failures.append(abort.failure)
                    return
                raise abort
            # A cleanup park may be physically/virtually proven after a
            # retraction journal write failed.  Do not then advance only a
            # subset of journals to PARKED: that would persist an invalid
            # cross-action parking prefix.  The park operation/feedback remain
            # accounted, while journals conservatively retain their states.
            if any(
                snapshot.current_state
                not in {ActionJournalState.RETRACTED, ActionJournalState.PARKED}
                for snapshot in park_snapshots
            ):
                return
            for index, (journal, snapshot) in enumerate(
                zip(journals, park_snapshots)
            ):
                if snapshot.current_state is not ActionJournalState.RETRACTED:
                    continue

                def commit_parked(
                    event_time_ns: int,
                    selected: ZeroAuthorityMissionJournal = journal,
                ) -> MissionJournalSnapshot:
                    return selected.confirm_parked(
                        event_time_ns=event_time_ns,
                        feedback_sha256=park_feedback.feedback_binding_sha256 or "",
                    )

                journal_transition(
                    MissionBoundary.JOURNAL_PARKED,
                    index,
                    commit_parked,
                    park_feedback.feedback_binding_sha256,
                )
        except _BoundaryAbort as abort:
            if cleanup:
                cleanup_failures.append(abort.failure)
                return
            raise

    def cleanup_lifecycle() -> None:
        nonlocal primary_failure
        for boundary, method, expected_state in (
            (MissionBoundary.STOP, generic_ports.arm_lifecycle.stop, "STOPPED"),
            (MissionBoundary.CLOSE, generic_ports.arm_lifecycle.close, "CLOSED"),
        ):
            operation_id = generic_spec.operation_id(boundary)
            try:

                def invoke_cleanup(deadline: RuntimeDeadline) -> LifecycleResult:
                    return method(
                        LifecycleRequest(
                            generic_spec.mission_id, operation_id, deadline
                        ),
                        generic_ports.cancellation,
                    )

                def validate_cleanup(
                    value: object,
                    started: RuntimeInstant,
                    deadline: RuntimeDeadline,
                ) -> str | None:
                    return validate_lifecycle(
                        value,
                        started,
                        deadline,
                        operation_id=operation_id,
                        expected_state=expected_state,
                    )

                attempt(
                    boundary,
                    None,
                    invoke_cleanup,
                    validate_cleanup,
                )
            except _BoundaryAbort as abort:
                if primary_failure is None:
                    primary_failure = abort.failure
                else:
                    cleanup_failures.append(abort.failure)
            except Exception as exc:
                failure = external_failure(boundary, None, exc).failure
                if primary_failure is None:
                    primary_failure = failure
                else:
                    cleanup_failures.append(failure)

    terminal_at_entry = all(
        state is ActionJournalState.PARKED for state in initial_states
    )
    manual_state = next(
        (
            index
            for index, state in enumerate(initial_states)
            if state
            in {ActionJournalState.FAULTED, ActionJournalState.OUTCOME_UNCERTAIN}
        ),
        None,
    )

    if primary_failure is not None:
        # Initial clock/recording failure occurred before any connection or
        # command.  Preserve it and proceed directly to guarded validation.
        pass
    elif manual_state is not None:
        now = last_runtime_instant
        operation_id = generic_spec.operation_id(
            MissionBoundary.ACTION_GATE, manual_state
        )
        primary_failure = MissionFailure(
            MissionBoundary.ACTION_GATE,
            operation_id,
            manual_state,
            "JOURNAL_MANUAL_REVIEW_REQUIRED",
            "a terminal journal state forbids automatic mission recovery",
        )
        records.append(
            MissionBoundaryRecord(
                MissionBoundary.ACTION_GATE,
                operation_id,
                manual_state,
                BoundaryStatus.FAILED,
                now,
                now,
                fault_code=primary_failure.fault_code,
            )
        )
    elif not terminal_at_entry:
        try:
            connect_id = generic_spec.operation_id(MissionBoundary.CONNECT)
            attempt(
                MissionBoundary.CONNECT,
                None,
                lambda deadline: generic_ports.arm_lifecycle.connect(
                    LifecycleRequest(generic_spec.mission_id, connect_id, deadline),
                    generic_ports.cancellation,
                ),
                lambda value, started, deadline: validate_lifecycle(
                    value,
                    started,
                    deadline,
                    operation_id=connect_id,
                    expected_state="CONNECTED",
                ),
            )
            connected = True
            reference_id = generic_spec.operation_id(MissionBoundary.REFERENCE)
            attempt(
                MissionBoundary.REFERENCE,
                None,
                lambda deadline: generic_ports.arm_lifecycle.reference(
                    LifecycleRequest(
                        generic_spec.mission_id, reference_id, deadline
                    ),
                    generic_ports.cancellation,
                ),
                lambda value, started, deadline: validate_lifecycle(
                    value,
                    started,
                    deadline,
                    operation_id=reference_id,
                    expected_state="REFERENCED",
                ),
            )
            referenced = True

            for index, (action, journal) in enumerate(
                zip(generic_spec.actions, journals)
            ):
                try:
                    current_snapshots = _validate_journals(generic_spec, journals)
                    last_known_snapshots[:] = current_snapshots
                    snapshot = current_snapshots[index]
                except Exception as exc:
                    raise external_failure(
                        MissionBoundary.ACTION_GATE, index, exc
                    ) from exc
                state = snapshot.current_state
                if state in {ActionJournalState.PARKED, ActionJournalState.RETRACTED}:
                    continue
                if state in {
                    ActionJournalState.FAULTED,
                    ActionJournalState.OUTCOME_UNCERTAIN,
                }:
                    raise _BoundaryAbort(
                        MissionFailure(
                            MissionBoundary.ACTION_GATE,
                            generic_spec.operation_id(MissionBoundary.ACTION_GATE, index),
                            index,
                            "JOURNAL_MANUAL_REVIEW_REQUIRED",
                            "action journal is terminal and cannot resume",
                        )
                    )

                # Recovery work is gated afresh too.  A journal state proves
                # what was durably recorded; it does not make yesterday's
                # cancellation/preflight decision current after a restart.
                def action_gate(selected: int = index) -> str:
                    return poll_gate(MissionBoundary.ACTION_GATE, selected)

                local_attempt(
                    MissionBoundary.ACTION_GATE,
                    index,
                    action_gate,
                )

                if state in {
                    ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
                    ActionJournalState.OUTCOME_CONFIRMED,
                }:
                    # A process restart invalidates any in-memory achieved pose.
                    # Sample the current controller state before outcome/retract
                    # recovery, without repeating localization or contact.
                    read_feedback(MissionBoundary.PRE_MOTION_FEEDBACK, index)

                contact_result: DeviceContactResult | None = None
                if state in {
                    ActionJournalState.INTENT_COMMITTED,
                    ActionJournalState.PRE_CONTACT,
                }:
                    pre_feedback = read_feedback(
                        MissionBoundary.PRE_MOTION_FEEDBACK, index
                    )
                    observation_id = generic_spec.operation_id(
                        MissionBoundary.FRESH_OBSERVATION, index
                    )

                    def validate_observation(
                        value: object,
                        started: RuntimeInstant,
                        deadline: RuntimeDeadline,
                    ) -> str:
                        nonlocal previous_observation_sequence
                        if not isinstance(value, ObservationResult):
                            raise MultiActionMissionError(
                                "observation result has invalid type"
                            )
                        if value.observation_id != observation_id:
                            raise MultiActionMissionError(
                                "observation result is not correlated"
                            )
                        _same_clock(value.observed_at, started, deadline)
                        if not value.valid:
                            raise RuntimePortOperationError(
                                value.fault_code or "OBSERVATION_INVALID",
                                observation_id,
                            )
                        if (
                            previous_observation_sequence is not None
                            and value.sequence <= previous_observation_sequence
                        ):
                            raise RuntimePortOperationError(
                                "OBSERVATION_NOT_FRESH", observation_id
                            )
                        previous_observation_sequence = value.sequence
                        return _stable_hash(
                            {
                                "observation_id": value.observation_id,
                                "sequence": value.sequence,
                                "observed_at": _instant_dict(value.observed_at),
                            }
                        )

                    observation = attempt(
                        MissionBoundary.FRESH_OBSERVATION,
                        index,
                        lambda deadline: generic_ports.observation.observe(
                            ObservationRequest(
                                generic_spec.mission_id,
                                observation_id,
                                index,
                                action.observation_phase,
                                deadline,
                            ),
                            generic_ports.cancellation,
                        ),
                        validate_observation,
                    )
                    assert isinstance(observation, ObservationResult)
                    assert pre_feedback.feedback_binding_sha256 is not None
                    route_receipt = _stable_hash(
                        {
                            "schema": "rocell.zero_authority_route_receipt.v1",
                            "occurrence_id": snapshot.occurrence.occurrence_id,
                            "preflight_binding_sha256": (
                                generic_spec.preflight_binding_sha256
                            ),
                            "route_authorization_sha256": (
                                action.route_authorization_sha256
                            ),
                            "pre_motion_feedback_sha256": (
                                pre_feedback.feedback_binding_sha256
                            ),
                            "observation_id": observation.observation_id,
                            "observation_sequence": observation.sequence,
                        }
                    )

                    def authorize_route(
                        selected: int = index,
                        receipt: str = route_receipt,
                    ) -> str:
                        poll_gate(MissionBoundary.ROUTE_AUTHORIZATION, selected)
                        return receipt

                    local_attempt(
                        MissionBoundary.ROUTE_AUTHORIZATION,
                        index,
                        authorize_route,
                    )
                    execute_command(
                        MissionBoundary.HOVER_EXECUTE,
                        index,
                        index * 4,
                        action.hover_command,
                    )
                    execute_command(
                        MissionBoundary.APPROACH_EXECUTE,
                        index,
                        index * 4 + 1,
                        action.approach_command,
                    )
                    try:
                        current_snapshots = _validate_journals(
                            generic_spec, journals
                        )
                        last_known_snapshots[:] = current_snapshots
                        snapshot = current_snapshots[index]
                    except Exception as exc:
                        raise external_failure(
                            MissionBoundary.JOURNAL_PRE_CONTACT, index, exc
                        ) from exc
                    if snapshot.current_state is ActionJournalState.INTENT_COMMITTED:

                        def commit_pre_contact(
                            event_time_ns: int,
                            selected: ZeroAuthorityMissionJournal = journal,
                        ) -> MissionJournalSnapshot:
                            return selected.commit_pre_contact(
                                event_time_ns=event_time_ns,
                                route_sha256=route_receipt,
                            )

                        journal_transition(
                            MissionBoundary.JOURNAL_PRE_CONTACT,
                            index,
                            commit_pre_contact,
                            route_receipt,
                        )
                    elif snapshot.current_state is ActionJournalState.PRE_CONTACT:
                        journal_transition(
                            MissionBoundary.JOURNAL_PRE_CONTACT,
                            index,
                            lambda _event_time_ns: snapshot,
                            route_receipt,
                            resumed=True,
                        )
                    else:
                        raise MultiActionMissionError(
                            "journal changed during pre-contact execution"
                        )
                    contact_receipt = _stable_hash(
                        {
                            "schema": "rocell.zero_authority_contact_receipt.v1",
                            "occurrence_id": snapshot.occurrence.occurrence_id,
                            "route_receipt_sha256": route_receipt,
                            "contact_command_sha256": (
                                action.contact_command.binding_sha256
                            ),
                            "device_contact_sha256": (
                                action.device_contact.binding_sha256
                            ),
                        }
                    )

                    def commit_contact_boundary(
                        event_time_ns: int,
                        selected: ZeroAuthorityMissionJournal = journal,
                    ) -> MissionJournalSnapshot:
                        return selected.commit_contact_boundary(
                            event_time_ns=event_time_ns,
                            command_sha256=contact_receipt,
                        )

                    journal_transition(
                        MissionBoundary.JOURNAL_CONTACT_BOUNDARY,
                        index,
                        commit_contact_boundary,
                        contact_receipt,
                    )
                    execute_command(
                        MissionBoundary.CONTACT_EXECUTE,
                        index,
                        index * 4 + 2,
                        action.contact_command,
                    )
                    read_feedback(MissionBoundary.CONTACT_FEEDBACK, index)
                    contact_id = generic_spec.operation_id(
                        MissionBoundary.DEVICE_CONTACT, index
                    )

                    def validate_contact(
                        value: object,
                        started: RuntimeInstant,
                        deadline: RuntimeDeadline,
                    ) -> str:
                        if not isinstance(value, DeviceContactResult):
                            raise MultiActionMissionError(
                                "device contact result has invalid type"
                            )
                        if value.operation_id != contact_id:
                            raise MultiActionMissionError(
                                "device contact result is not correlated"
                            )
                        _same_clock(value.observed_at, started, deadline)
                        if not value.accepted:
                            raise RuntimePortOperationError(
                                value.fault_code or "DEVICE_CONTACT_REJECTED",
                                contact_id,
                            )
                        if value.activation_count != action.required_activation_count:
                            raise RuntimePortOperationError(
                                "DEVICE_ACTIVATION_COUNT_MISMATCH", contact_id
                            )
                        if (
                            type(value.device_event_ids) is not tuple
                            or len(value.device_event_ids) != value.activation_count
                            or len(value.device_event_ids)
                            != len(set(value.device_event_ids))
                        ):
                            raise RuntimePortOperationError(
                                "DEVICE_EVENT_ACCOUNTING_MISMATCH", contact_id
                            )
                        for event_id in value.device_event_ids:
                            _identifier(event_id, "device contact event ID")
                        return _stable_hash(
                            {
                                "operation_id": value.operation_id,
                                "activation_count": value.activation_count,
                                "device_event_ids": list(value.device_event_ids),
                            }
                        )

                    raw_contact = attempt(
                        MissionBoundary.DEVICE_CONTACT,
                        index,
                        lambda deadline: generic_ports.device_contact.apply_contact(
                            DeviceContactRequest(
                                generic_spec.mission_id,
                                contact_id,
                                index,
                                action.device_contact.verified_payload(),
                                deadline,
                            ),
                            generic_ports.cancellation,
                        ),
                        validate_contact,
                    )
                    assert isinstance(raw_contact, DeviceContactResult)
                    contact_result = raw_contact
                    state = ActionJournalState.CONTACT_MAY_HAVE_OCCURRED

                if state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED:
                    outcome_id = generic_spec.operation_id(
                        MissionBoundary.OUTCOME_OBSERVATION, index
                    )
                    outcome_holder: list[ActionOutcomeReceipt] = []

                    def validate_outcome(
                        value: object,
                        started: RuntimeInstant,
                        deadline: RuntimeDeadline,
                    ) -> str:
                        nonlocal previous_outcome_sequence
                        if not isinstance(value, OutcomeObservation):
                            raise MultiActionMissionError(
                                "outcome result has invalid type"
                            )
                        if value.checkpoint_id != outcome_id:
                            raise MultiActionMissionError(
                                "outcome result is not correlated"
                            )
                        _same_clock(value.observed_at, started, deadline)
                        if not value.valid:
                            raise RuntimePortOperationError(
                                value.fault_code or "OUTCOME_INVALID", outcome_id
                            )
                        if (
                            previous_outcome_sequence is not None
                            and value.sequence <= previous_outcome_sequence
                        ):
                            raise RuntimePortOperationError(
                                "OUTCOME_NOT_FRESH", outcome_id
                            )
                        if type(value.outcome) is not ObservedSemanticOutcome:
                            raise MultiActionMissionError(
                                "outcome observer did not return semantic evidence"
                            )
                        semantic = value.outcome
                        semantic.__post_init__()
                        expected_occurrence = generic_spec.occurrences[index]
                        if (
                            semantic.action_occurrence_id
                            != expected_occurrence.occurrence_id
                        ):
                            raise MultiActionMissionError(
                                "outcome is bound to the wrong action occurrence"
                            )
                        if (
                            semantic.semantic_sha256
                            != action.expected_outcome.binding_sha256
                        ):
                            raise MultiActionMissionError(
                                "observed device meaning does not match the expected outcome"
                            )
                        if (
                            contact_result is not None
                            and semantic.contact_event_ids
                            != contact_result.device_event_ids
                        ):
                            raise MultiActionMissionError(
                                "outcome contact events do not match device contact"
                            )
                        receipt = ActionOutcomeReceipt.from_observation(index, value)
                        outcome_holder.append(receipt)
                        previous_outcome_sequence = value.sequence
                        return receipt.evidence_sha256

                    outcome = attempt(
                        MissionBoundary.OUTCOME_OBSERVATION,
                        index,
                        lambda deadline: generic_ports.outcome_observer.observe_outcome(
                            OutcomeRequest(
                                generic_spec.mission_id, outcome_id, index, deadline
                            ),
                            generic_ports.cancellation,
                        ),
                        validate_outcome,
                    )
                    assert isinstance(outcome, OutcomeObservation)
                    if len(outcome_holder) != 1:
                        raise MultiActionMissionError(
                            "outcome observation did not yield one semantic receipt"
                        )
                    outcome_receipt = outcome_holder[0]
                    outcome_receipts.append(outcome_receipt)

                    def confirm_outcome(
                        event_time_ns: int,
                        selected: ZeroAuthorityMissionJournal = journal,
                    ) -> MissionJournalSnapshot:
                        return selected.confirm_outcome(
                            event_time_ns=event_time_ns,
                            outcome_sha256=outcome_receipt.evidence_sha256,
                        )

                    journal_transition(
                        MissionBoundary.JOURNAL_OUTCOME_CONFIRMED,
                        index,
                        confirm_outcome,
                        outcome_receipt.evidence_sha256,
                    )
                    state = ActionJournalState.OUTCOME_CONFIRMED

                if state is ActionJournalState.OUTCOME_CONFIRMED:
                    execute_command(
                        MissionBoundary.RETRACT_EXECUTE,
                        index,
                        index * 4 + 3,
                        action.retract_command,
                    )
                    retract_feedback = read_feedback(
                        MissionBoundary.RETRACT_FEEDBACK, index
                    )
                    assert retract_feedback.feedback_binding_sha256 is not None
                    retraction_proven.add(snapshot.occurrence.occurrence_id)

                    def confirm_retracted(
                        event_time_ns: int,
                        selected: ZeroAuthorityMissionJournal = journal,
                    ) -> MissionJournalSnapshot:
                        return selected.confirm_retracted(
                            event_time_ns=event_time_ns,
                            feedback_sha256=(
                                retract_feedback.feedback_binding_sha256 or ""
                            ),
                        )

                    journal_transition(
                        MissionBoundary.JOURNAL_RETRACTED,
                        index,
                        confirm_retracted,
                        retract_feedback.feedback_binding_sha256,
                    )

            try:
                current_snapshots = _validate_journals(generic_spec, journals)
                last_known_snapshots[:] = current_snapshots
            except Exception as exc:
                raise external_failure(
                    MissionBoundary.PARK_EXECUTE, None, exc
                ) from exc
            if any(
                snapshot.current_state is ActionJournalState.RETRACTED
                for snapshot in current_snapshots
            ):
                run_park(cleanup=False)
        except _BoundaryAbort as abort:
            primary_failure = abort.failure
            mark_primary_journal_failure(abort.failure)
        except Exception as exc:
            primary_failure = external_failure(
                MissionBoundary.ACTION_GATE, None, exc
            ).failure

        park_already_attempted = (
            primary_failure is not None
            and primary_failure.boundary
            in {
                MissionBoundary.PARK_EXECUTE,
                MissionBoundary.PARK_FEEDBACK,
                MissionBoundary.JOURNAL_PARKED,
            }
        )
        if (
            primary_failure is not None
            and referenced
            and not park_already_attempted
            and all_safe_to_park()
            and authorization.next_ordinal == len(generic_spec.actions) * 4
        ):
            run_park(cleanup=True)
        if connected or records[-1].boundary in {
            MissionBoundary.CONNECT,
            MissionBoundary.REFERENCE,
        }:
            cleanup_lifecycle()

    def retain_final_failure(failure: MissionFailure) -> None:
        nonlocal primary_failure
        if primary_failure is None:
            primary_failure = failure
        else:
            cleanup_failures.append(failure)

    try:
        final_contract = validate_runtime_ports(generic_ports)
        if (
            _contract_dict(final_contract) != initial_contract_document
            or _runtime_identity_document(generic_ports) != initial_runtime_identity
        ):
            raise MultiActionMissionError(
                "runtime authority or identity changed during the mission"
            )
        candidate = generic_ports.clock.now()
        _same_clock(candidate, last_runtime_instant, None)
        last_runtime_instant = candidate
        records.append(
            MissionBoundaryRecord(
                MissionBoundary.VALIDATE_PORTS_FINAL,
                generic_spec.operation_id(MissionBoundary.VALIDATE_PORTS_FINAL),
                None,
                BoundaryStatus.PASSED,
                candidate,
                candidate,
                evidence_sha256=initial_runtime_binding,
            )
        )
    except Exception as exc:
        retain_final_failure(
            external_failure(MissionBoundary.VALIDATE_PORTS_FINAL, None, exc).failure
        )

    journals_verified = False
    final_snapshots = tuple(last_known_snapshots)
    try:
        verified_snapshots = _validate_journals(generic_spec, journals)
        last_known_snapshots[:] = verified_snapshots
        final_snapshots = verified_snapshots
        candidate = generic_ports.clock.now()
        _same_clock(candidate, last_runtime_instant, None)
        last_runtime_instant = candidate
        records.append(
            MissionBoundaryRecord(
                MissionBoundary.VALIDATE_JOURNALS_FINAL,
                generic_spec.operation_id(MissionBoundary.VALIDATE_JOURNALS_FINAL),
                None,
                BoundaryStatus.PASSED,
                candidate,
                candidate,
                evidence_sha256=_stable_hash(
                    {
                        "plan_sha256": generic_spec.plan_sha256,
                        "snapshot_sha256s": [
                            snapshot.snapshot_hash
                            for snapshot in verified_snapshots
                        ],
                    }
                ),
            )
        )
        journals_verified = True
    except Exception as exc:
        retain_final_failure(
            external_failure(
                MissionBoundary.VALIDATE_JOURNALS_FINAL, None, exc
            ).failure
        )

    return MultiActionMissionReport._issued(
        mission_id=generic_spec.mission_id,
        plan_sha256=generic_spec.plan_sha256,
        runtime_id=initial_contract.runtime_id,
        occurrence_ids=tuple(
            occurrence.occurrence_id for occurrence in generic_spec.occurrences
        ),
        initial_states=initial_states,
        final_states=tuple(item.current_state for item in final_snapshots),
        records=tuple(records),
        outcome_receipts=tuple(outcome_receipts),
        authorization_receipt_sha256s=tuple(authorization_receipt_sha256s),
        authorization_complete=authorization.complete,
        journals_verified=journals_verified,
        primary_failure=primary_failure,
        cleanup_failures=tuple(cleanup_failures),
        zero_authority=initial_contract.zero_authority,
        hardware_accessed=initial_contract.hardware_accessed,
        hardware_commands_generated=initial_contract.hardware_commands_generated,
    )


__all__ = [
    "MAX_MISSION_ACTIONS",
    "MAX_OPAQUE_BINDING_BYTES",
    "ZERO_AUTHORITY_MULTI_ACTION_MISSION_SCHEMA",
    "ZERO_AUTHORITY_MULTI_ACTION_RECORD_SCHEMA",
    "ZERO_AUTHORITY_MULTI_ACTION_REPORT_SCHEMA",
    "BoundOpaqueValue",
    "BoundaryStatus",
    "ActionOutcomeReceipt",
    "AuthorizationV2MissionCursor",
    "CompletedMissionAuthorizationCursor",
    "MissionBoundary",
    "MissionBoundaryRecord",
    "MissionCommandAuthorizationBinding",
    "MissionCommandAuthorizationReceipt",
    "MissionFailure",
    "MultiActionMissionError",
    "MultiActionMissionReport",
    "MultiActionMissionSpec",
    "MultiActionSpec",
    "ObservedSemanticOutcome",
    "SimulationCommandAuthorizationCursor",
    "build_mission_authorization_schedule",
    "prepare_zero_authority_mission_journals",
    "reopen_zero_authority_mission_journals",
    "run_zero_authority_multi_action_mission",
]
