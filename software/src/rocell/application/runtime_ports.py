"""Hardware-neutral runtime contracts for one typing-mission orchestrator.

The application layer should describe *what* a mission needs without knowing
whether an adapter is virtual, replaying recorded evidence, or (after physical
commissioning) connected to a device.  This module is that boundary.  It only
contains immutable request/result envelopes, structural protocols, and a
fail-closed bundle validator; it deliberately imports no arm, camera, serial,
vision, simulation, or device implementation.

Two rules are important:

* ``RuntimeAuthority`` is descriptive evidence, never a motion permit.  A
  physical adapter still needs the separate safety/capability boundary before
  it can act.  The pre-hardware orchestrator calls :func:`validate_runtime_ports`
  with its default ``require_zero_authority=True``.
* Contact geometry remains a domain concern.  ``DeviceContactPort`` is generic
  in an opaque, immutable contact value so this layer does not duplicate the
  contact-truth model or leak the planner's expected character to the device.

The protocols are synchronous on purpose.  A physical adapter may perform
asynchronous work internally, but it must present the same bounded operation,
cancellation, deadline, and result semantics as virtual and replay adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Generic, Protocol, TypeVar, runtime_checkable


RUNTIME_PORT_CONTRACT = "rocell.runtime_ports.v1"
MAX_RUNTIME_PAYLOAD_BYTES = 16 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RuntimeContractError(ValueError):
    """A runtime adapter bundle violates the application-level contract."""


def _identifier(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeContractError(f"{label} must be non-empty text")
    parsed = value.strip()
    if parsed != value:
        raise RuntimeContractError(f"{label} must not have surrounding whitespace")
    if len(parsed) > maximum:
        raise RuntimeContractError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in parsed):
        raise RuntimeContractError(f"{label} contains a control character")
    return parsed


class RuntimePortOperationError(RuntimeError):
    """A bounded port operation failed closed with a stable fault code."""

    def __init__(
        self,
        fault_code: str,
        operation_id: str,
        detail: str | None = None,
    ) -> None:
        self.fault_code = _identifier(fault_code, "fault_code", maximum=128)
        self.operation_id = _identifier(operation_id, "operation_id")
        self.detail = _optional_text(detail, "detail", maximum=1024)
        message = f"{self.fault_code} at {self.operation_id}"
        if self.detail is not None:
            message = f"{message}: {self.detail}"
        super().__init__(message)


def _optional_text(value: object, label: str, *, maximum: int = 1024) -> str | None:
    if value is None:
        return None
    return _identifier(value, label, maximum=maximum)


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = (1 << 63) - 1,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeContractError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise RuntimeContractError(f"{label} must be within [{minimum}, {maximum}]")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RuntimeContractError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _tuple_of_ids(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise RuntimeContractError(f"{label} must be an immutable tuple")
    parsed = tuple(_identifier(value, f"{label} item") for value in values)
    if len(parsed) != len(set(parsed)):
        raise RuntimeContractError(f"{label} contains a duplicate value")
    return parsed


class RuntimeExecutionMode(str, Enum):
    """How an implementation obtains its results, not what it is authorized to do."""

    VIRTUAL = "VIRTUAL"
    REPLAY = "REPLAY"
    PHYSICAL = "PHYSICAL"


class RuntimePortRole(str, Enum):
    """Capabilities consumed independently by the mission orchestrator."""

    CLOCK = "CLOCK"
    ARM_LIFECYCLE = "ARM_LIFECYCLE"
    ARM_EXECUTION = "ARM_EXECUTION"
    ARM_FEEDBACK = "ARM_FEEDBACK"
    OBSERVATION = "OBSERVATION"
    DEVICE_CONTACT = "DEVICE_CONTACT"
    OUTCOME_OBSERVER = "OUTCOME_OBSERVER"
    CANCELLATION = "CANCELLATION"
    EVIDENCE = "EVIDENCE"


@dataclass(frozen=True, slots=True)
class RuntimeAuthority:
    """Observed authority footprint for a runtime adapter.

    This record cannot authorize an operation.  In particular,
    ``live_motion_authorized=True`` is only a claim to be checked against the
    independent permit boundary; the runtime contracts never issue that
    permit.
    """

    execution_mode: RuntimeExecutionMode
    hardware_accessed: bool
    hardware_commands_generated: int
    live_motion_authorized: bool
    physical_contact_authorized: bool
    physical_release_effect: str

    def __post_init__(self) -> None:
        if not isinstance(self.execution_mode, RuntimeExecutionMode):
            try:
                object.__setattr__(
                    self,
                    "execution_mode",
                    RuntimeExecutionMode(self.execution_mode),
                )
            except (TypeError, ValueError) as exc:
                raise RuntimeContractError("execution_mode is unsupported") from exc
        for field_name in (
            "hardware_accessed",
            "live_motion_authorized",
            "physical_contact_authorized",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise RuntimeContractError(f"{field_name} must be boolean")
        object.__setattr__(
            self,
            "hardware_commands_generated",
            _integer(
                self.hardware_commands_generated,
                "hardware_commands_generated",
                maximum=1_000_000_000,
            ),
        )
        object.__setattr__(
            self,
            "physical_release_effect",
            _identifier(
                self.physical_release_effect,
                "physical_release_effect",
                maximum=128,
            ),
        )
        if self.hardware_commands_generated and not self.hardware_accessed:
            raise RuntimeContractError(
                "hardware commands cannot be reported without hardware access"
            )
        if self.execution_mode is not RuntimeExecutionMode.PHYSICAL and (
            self.hardware_accessed
            or self.hardware_commands_generated
            or self.live_motion_authorized
            or self.physical_contact_authorized
            or self.physical_release_effect != "NONE"
        ):
            raise RuntimeContractError(
                "virtual/replay adapters must declare a zero physical footprint"
            )

    @classmethod
    def zero(
        cls,
        execution_mode: RuntimeExecutionMode = RuntimeExecutionMode.VIRTUAL,
    ) -> "RuntimeAuthority":
        """Create the required authority declaration for virtual or replay runs."""

        if execution_mode is RuntimeExecutionMode.PHYSICAL:
            raise RuntimeContractError(
                "a physical adapter must declare its measured authority footprint"
            )
        return cls(
            execution_mode=execution_mode,
            hardware_accessed=False,
            hardware_commands_generated=0,
            live_motion_authorized=False,
            physical_contact_authorized=False,
            physical_release_effect="NONE",
        )

    @property
    def is_zero_authority(self) -> bool:
        return (
            not self.hardware_accessed
            and self.hardware_commands_generated == 0
            and not self.live_motion_authorized
            and not self.physical_contact_authorized
            and self.physical_release_effect == "NONE"
        )


@dataclass(frozen=True, slots=True)
class RuntimePortMetadata:
    """Stable identity and footprint exposed by every structural port."""

    runtime_id: str
    port_id: str
    implementation_id: str
    roles: tuple[RuntimePortRole, ...]
    authority: RuntimeAuthority
    contract: str = RUNTIME_PORT_CONTRACT

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_id", _identifier(self.runtime_id, "runtime_id"))
        object.__setattr__(self, "port_id", _identifier(self.port_id, "port_id"))
        object.__setattr__(
            self,
            "implementation_id",
            _identifier(self.implementation_id, "implementation_id", maximum=512),
        )
        if not isinstance(self.roles, tuple) or not self.roles:
            raise RuntimeContractError("roles must be a non-empty immutable tuple")
        parsed_roles: list[RuntimePortRole] = []
        for value in self.roles:
            try:
                parsed_roles.append(
                    value if isinstance(value, RuntimePortRole) else RuntimePortRole(value)
                )
            except (TypeError, ValueError) as exc:
                raise RuntimeContractError("roles contains an unsupported role") from exc
        if len(parsed_roles) != len(set(parsed_roles)):
            raise RuntimeContractError("roles contains a duplicate role")
        object.__setattr__(self, "roles", tuple(parsed_roles))
        if not isinstance(self.authority, RuntimeAuthority):
            raise RuntimeContractError("authority must be RuntimeAuthority")
        if self.contract != RUNTIME_PORT_CONTRACT:
            raise RuntimeContractError(
                f"contract must equal {RUNTIME_PORT_CONTRACT!r}"
            )


@dataclass(frozen=True, slots=True)
class RuntimeInstant:
    """A monotonic timestamp whose unit is declared by its clock adapter."""

    clock_id: str
    tick: int
    tick_period_ns: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "clock_id", _identifier(self.clock_id, "clock_id"))
        object.__setattr__(self, "tick", _integer(self.tick, "tick"))
        if self.tick_period_ns is not None:
            object.__setattr__(
                self,
                "tick_period_ns",
                _integer(
                    self.tick_period_ns,
                    "tick_period_ns",
                    minimum=1,
                    maximum=1_000_000_000_000,
                ),
            )


@dataclass(frozen=True, slots=True)
class RuntimeDeadline:
    """A same-clock, inclusive deadline for one bounded adapter operation."""

    at: RuntimeInstant

    def __post_init__(self) -> None:
        if not isinstance(self.at, RuntimeInstant):
            raise RuntimeContractError("deadline at must be RuntimeInstant")


@dataclass(frozen=True, slots=True)
class LifecycleRequest:
    mission_id: str
    operation_id: str
    deadline: RuntimeDeadline | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        if self.deadline is not None and not isinstance(self.deadline, RuntimeDeadline):
            raise RuntimeContractError("deadline must be RuntimeDeadline or None")


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    operation_id: str
    state: str
    observed_at: RuntimeInstant
    succeeded: bool
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(self, "state", _identifier(self.state, "state"))
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        if not isinstance(self.succeeded, bool):
            raise RuntimeContractError("succeeded must be boolean")
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.succeeded != (self.fault_code is None):
            raise RuntimeContractError(
                "a successful lifecycle result has no fault; a failed result needs one"
            )


CommandT_co = TypeVar("CommandT_co", covariant=True)
CommandT_contra = TypeVar("CommandT_contra", contravariant=True)
FeedbackT_co = TypeVar("FeedbackT_co", covariant=True)


@dataclass(frozen=True, slots=True)
class ArmExecutionRequest(Generic[CommandT_co]):
    """One accepted arm command; ``command`` is adapter/domain specific."""

    mission_id: str
    operation_id: str
    action_index: int
    waypoint_sequence: int
    command: CommandT_co
    deadline: RuntimeDeadline | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(
            self, "action_index", _integer(self.action_index, "action_index")
        )
        object.__setattr__(
            self,
            "waypoint_sequence",
            _integer(self.waypoint_sequence, "waypoint_sequence"),
        )
        if self.deadline is not None and not isinstance(self.deadline, RuntimeDeadline):
            raise RuntimeContractError("deadline must be RuntimeDeadline or None")


@dataclass(frozen=True, slots=True)
class ArmExecutionResult(Generic[FeedbackT_co]):
    operation_id: str
    observed_at: RuntimeInstant
    accepted: bool
    completed: bool
    feedback: FeedbackT_co | None = None
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        if not isinstance(self.accepted, bool) or not isinstance(self.completed, bool):
            raise RuntimeContractError("accepted/completed must be boolean")
        if self.completed and not self.accepted:
            raise RuntimeContractError("an unaccepted arm command cannot be completed")
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.completed and self.fault_code is not None:
            raise RuntimeContractError("a completed arm command cannot have a fault")
        if self.completed and self.feedback is None:
            raise RuntimeContractError("a completed arm command needs achieved feedback")
        if not self.completed and self.fault_code is None:
            raise RuntimeContractError("an incomplete arm command needs a fault")
        if not self.accepted and self.feedback is not None:
            raise RuntimeContractError(
                "an unaccepted arm command cannot return achieved feedback"
            )


@dataclass(frozen=True, slots=True)
class ArmFeedbackRequest:
    mission_id: str
    operation_id: str
    action_index: int | None = None
    deadline: RuntimeDeadline | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        if self.action_index is not None:
            object.__setattr__(
                self, "action_index", _integer(self.action_index, "action_index")
            )
        if self.deadline is not None and not isinstance(self.deadline, RuntimeDeadline):
            raise RuntimeContractError("deadline must be RuntimeDeadline or None")


@dataclass(frozen=True, slots=True)
class ArmFeedbackSample(Generic[FeedbackT_co]):
    """One correlated feedback sample from an adapter.

    ``feedback_binding_sha256`` is optional at the general port boundary for
    backward compatibility.  Evidence-producing orchestrators may require an
    adapter-owned canonical digest before opaque feedback can affect a report.
    """

    sample_id: str
    observed_at: RuntimeInstant
    sequence: int
    feedback: FeedbackT_co
    stale: bool = False
    request_operation_id: str | None = None
    action_index: int | None = None
    feedback_binding_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sample_id", _identifier(self.sample_id, "sample_id"))
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        object.__setattr__(self, "sequence", _integer(self.sequence, "sequence"))
        if self.feedback is None:
            raise RuntimeContractError("feedback sample needs a feedback value")
        if not isinstance(self.stale, bool):
            raise RuntimeContractError("stale must be boolean")
        if self.request_operation_id is not None:
            object.__setattr__(
                self,
                "request_operation_id",
                _identifier(self.request_operation_id, "request_operation_id"),
            )
        if self.action_index is not None:
            object.__setattr__(
                self, "action_index", _integer(self.action_index, "action_index")
            )
        if self.feedback_binding_sha256 is not None:
            object.__setattr__(
                self,
                "feedback_binding_sha256",
                _digest(
                    self.feedback_binding_sha256,
                    "feedback_binding_sha256",
                ),
            )


def validate_arm_feedback_sample(
    request: ArmFeedbackRequest,
    sample: ArmFeedbackSample[FeedbackT_co],
    *,
    previous_sequence: int | None = None,
    require_fresh: bool = True,
) -> None:
    """Validate correlation, ordering, freshness, and deadline of one sample.

    The structural ``ArmFeedbackPort`` protocol cannot force arbitrary adapter
    implementations to correlate their results.  Orchestrators and the
    reusable zero-authority adapters call this function at the trust boundary
    before a sample can influence camera pose, correction, or contact.
    """

    if not isinstance(request, ArmFeedbackRequest):
        raise TypeError("request must be ArmFeedbackRequest")
    if not isinstance(sample, ArmFeedbackSample):
        raise TypeError("sample must be ArmFeedbackSample")
    if not isinstance(require_fresh, bool):
        raise RuntimeContractError("require_fresh must be boolean")
    if sample.request_operation_id != request.operation_id:
        raise RuntimePortOperationError(
            "ARM_FEEDBACK_CORRELATION_MISMATCH",
            request.operation_id,
            "sample request_operation_id does not match the request",
        )
    if sample.action_index != request.action_index:
        raise RuntimePortOperationError(
            "ARM_FEEDBACK_ACTION_MISMATCH",
            request.operation_id,
            "sample action_index does not match the request",
        )
    if require_fresh and sample.stale:
        raise RuntimePortOperationError(
            "ARM_FEEDBACK_STALE",
            request.operation_id,
        )
    if previous_sequence is not None:
        parsed_previous = _integer(
            previous_sequence,
            "previous_sequence",
            maximum=(1 << 63) - 1,
        )
        if sample.sequence <= parsed_previous:
            raise RuntimePortOperationError(
                "ARM_FEEDBACK_REORDERED",
                request.operation_id,
                "sample sequence did not increase strictly",
            )
    if request.deadline is not None:
        deadline = request.deadline.at
        if (
            sample.observed_at.clock_id != deadline.clock_id
            or sample.observed_at.tick_period_ns != deadline.tick_period_ns
        ):
            raise RuntimePortOperationError(
                "ARM_FEEDBACK_DEADLINE_CLOCK_MISMATCH",
                request.operation_id,
            )
        # RuntimeDeadline is inclusive: a sample exactly at the deadline is
        # valid, while any later sample is rejected.
        if sample.observed_at.tick > deadline.tick:
            raise RuntimePortOperationError(
                "ARM_FEEDBACK_DEADLINE_EXPIRED",
                request.operation_id,
            )


@dataclass(frozen=True, slots=True)
class CancellationCheck:
    mission_id: str
    checkpoint_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self, "checkpoint_id", _identifier(self.checkpoint_id, "checkpoint_id")
        )


@dataclass(frozen=True, slots=True)
class CancellationStatus:
    checkpoint_id: str
    observed_at: RuntimeInstant
    cancelled: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "checkpoint_id", _identifier(self.checkpoint_id, "checkpoint_id")
        )
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        if not isinstance(self.cancelled, bool):
            raise RuntimeContractError("cancelled must be boolean")
        object.__setattr__(self, "reason", _optional_text(self.reason, "reason"))
        if self.cancelled != (self.reason is not None):
            raise RuntimeContractError(
                "a cancellation reason must exist exactly when cancellation is active"
            )


@dataclass(frozen=True, slots=True)
class ObservationRequest:
    """Request a sensor observation without exposing expected detector output."""

    mission_id: str
    observation_id: str
    action_index: int | None
    phase: str
    deadline: RuntimeDeadline | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self,
            "observation_id",
            _identifier(self.observation_id, "observation_id"),
        )
        if self.action_index is not None:
            object.__setattr__(
                self, "action_index", _integer(self.action_index, "action_index")
            )
        object.__setattr__(self, "phase", _identifier(self.phase, "phase"))
        if self.deadline is not None and not isinstance(self.deadline, RuntimeDeadline):
            raise RuntimeContractError("deadline must be RuntimeDeadline or None")


ObservationT_co = TypeVar("ObservationT_co", covariant=True)


@dataclass(frozen=True, slots=True)
class ObservationResult(Generic[ObservationT_co]):
    observation_id: str
    observed_at: RuntimeInstant
    sequence: int
    observation: ObservationT_co | None
    valid: bool
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_id",
            _identifier(self.observation_id, "observation_id"),
        )
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        object.__setattr__(self, "sequence", _integer(self.sequence, "sequence"))
        if not isinstance(self.valid, bool):
            raise RuntimeContractError("valid must be boolean")
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.valid and (self.observation is None or self.fault_code is not None):
            raise RuntimeContractError(
                "a valid observation needs a value and cannot have a fault"
            )
        if not self.valid and self.fault_code is None:
            raise RuntimeContractError("an invalid observation needs a fault code")


ContactT_co = TypeVar("ContactT_co", covariant=True)
ContactT_contra = TypeVar("ContactT_contra", contravariant=True)


@dataclass(frozen=True, slots=True)
class DeviceContactRequest(Generic[ContactT_co]):
    """Opaque achieved contact supplied to a device truth model.

    ``contact`` should be the immutable contact event from the contact-truth
    domain.  This request intentionally has no planned target, expected key, or
    expected character field.
    """

    mission_id: str
    operation_id: str
    action_index: int
    contact: ContactT_co
    deadline: RuntimeDeadline | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(
            self, "action_index", _integer(self.action_index, "action_index")
        )
        if self.deadline is not None and not isinstance(self.deadline, RuntimeDeadline):
            raise RuntimeContractError("deadline must be RuntimeDeadline or None")


@dataclass(frozen=True, slots=True)
class DeviceContactResult:
    operation_id: str
    observed_at: RuntimeInstant
    accepted: bool
    activation_count: int
    device_event_ids: tuple[str, ...]
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        if not isinstance(self.accepted, bool):
            raise RuntimeContractError("accepted must be boolean")
        object.__setattr__(
            self,
            "activation_count",
            _integer(self.activation_count, "activation_count", maximum=1_000_000),
        )
        object.__setattr__(
            self,
            "device_event_ids",
            _tuple_of_ids(self.device_event_ids, "device_event_ids"),
        )
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.accepted != (self.fault_code is None):
            raise RuntimeContractError(
                "an accepted contact has no fault; a rejected contact needs one"
            )
        if self.activation_count != len(self.device_event_ids):
            raise RuntimeContractError(
                "activation_count must match the number of device event IDs"
            )
        if self.accepted and self.activation_count == 0:
            raise RuntimeContractError(
                "an accepted contact needs at least one device activation"
            )
        if not self.accepted and self.activation_count != 0:
            raise RuntimeContractError(
                "a rejected contact cannot retain a device activation"
            )


@dataclass(frozen=True, slots=True)
class OutcomeRequest:
    """Observe actual device state without giving the observer an answer oracle."""

    mission_id: str
    checkpoint_id: str
    action_index: int | None = None
    deadline: RuntimeDeadline | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self, "checkpoint_id", _identifier(self.checkpoint_id, "checkpoint_id")
        )
        if self.action_index is not None:
            object.__setattr__(
                self, "action_index", _integer(self.action_index, "action_index")
            )
        if self.deadline is not None and not isinstance(self.deadline, RuntimeDeadline):
            raise RuntimeContractError("deadline must be RuntimeDeadline or None")


OutcomeT_co = TypeVar("OutcomeT_co", covariant=True)


@dataclass(frozen=True, slots=True)
class OutcomeObservation(Generic[OutcomeT_co]):
    checkpoint_id: str
    observed_at: RuntimeInstant
    sequence: int
    outcome: OutcomeT_co | None
    valid: bool
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "checkpoint_id", _identifier(self.checkpoint_id, "checkpoint_id")
        )
        if not isinstance(self.observed_at, RuntimeInstant):
            raise RuntimeContractError("observed_at must be RuntimeInstant")
        object.__setattr__(self, "sequence", _integer(self.sequence, "sequence"))
        if not isinstance(self.valid, bool):
            raise RuntimeContractError("valid must be boolean")
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.valid and (self.outcome is None or self.fault_code is not None):
            raise RuntimeContractError(
                "a valid outcome needs a value and cannot have a fault"
            )
        if not self.valid and self.fault_code is None:
            raise RuntimeContractError("an invalid outcome needs a fault code")


@dataclass(frozen=True, slots=True)
class EvidenceWriteRequest:
    """One immutable evidence payload and its caller-computed integrity digest."""

    mission_id: str
    record_id: str
    role: str
    sequence: int
    media_type: str
    payload: bytes
    payload_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(self, "record_id", _identifier(self.record_id, "record_id"))
        object.__setattr__(self, "role", _identifier(self.role, "role"))
        object.__setattr__(self, "sequence", _integer(self.sequence, "sequence"))
        object.__setattr__(
            self, "media_type", _identifier(self.media_type, "media_type", maximum=128)
        )
        if not isinstance(self.payload, bytes):
            raise RuntimeContractError("evidence payload must be immutable bytes")
        if len(self.payload) > MAX_RUNTIME_PAYLOAD_BYTES:
            raise RuntimeContractError(
                f"evidence payload exceeds {MAX_RUNTIME_PAYLOAD_BYTES} bytes"
            )
        object.__setattr__(
            self, "payload_sha256", _digest(self.payload_sha256, "payload_sha256")
        )
        actual = hashlib.sha256(self.payload).hexdigest()
        if actual != self.payload_sha256:
            raise RuntimeContractError("payload_sha256 does not match evidence payload")

    @classmethod
    def from_payload(
        cls,
        *,
        mission_id: str,
        record_id: str,
        role: str,
        sequence: int,
        media_type: str,
        payload: bytes,
    ) -> "EvidenceWriteRequest":
        if not isinstance(payload, bytes):
            raise RuntimeContractError("evidence payload must be immutable bytes")
        return cls(
            mission_id=mission_id,
            record_id=record_id,
            role=role,
            sequence=sequence,
            media_type=media_type,
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class EvidenceWriteResult:
    record_id: str
    committed_at: RuntimeInstant
    payload_sha256: str
    size_bytes: int
    committed: bool
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _identifier(self.record_id, "record_id"))
        if not isinstance(self.committed_at, RuntimeInstant):
            raise RuntimeContractError("committed_at must be RuntimeInstant")
        object.__setattr__(
            self, "payload_sha256", _digest(self.payload_sha256, "payload_sha256")
        )
        object.__setattr__(
            self,
            "size_bytes",
            _integer(self.size_bytes, "size_bytes", maximum=MAX_RUNTIME_PAYLOAD_BYTES),
        )
        if not isinstance(self.committed, bool):
            raise RuntimeContractError("committed must be boolean")
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.committed == (self.fault_code is not None):
            raise RuntimeContractError(
                "a committed write must have no fault; a failed write must have one"
            )


@dataclass(frozen=True, slots=True)
class EvidenceFinalizeRequest:
    mission_id: str
    terminal_status: str
    expected_record_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _identifier(self.mission_id, "mission_id"))
        object.__setattr__(
            self,
            "terminal_status",
            _identifier(self.terminal_status, "terminal_status"),
        )
        object.__setattr__(
            self,
            "expected_record_ids",
            _tuple_of_ids(self.expected_record_ids, "expected_record_ids"),
        )


@dataclass(frozen=True, slots=True)
class EvidenceFinalizeResult:
    manifest_id: str
    committed_at: RuntimeInstant
    manifest_sha256: str
    record_count: int
    committed: bool
    fault_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", _identifier(self.manifest_id, "manifest_id"))
        if not isinstance(self.committed_at, RuntimeInstant):
            raise RuntimeContractError("committed_at must be RuntimeInstant")
        object.__setattr__(
            self, "manifest_sha256", _digest(self.manifest_sha256, "manifest_sha256")
        )
        object.__setattr__(
            self,
            "record_count",
            _integer(self.record_count, "record_count", maximum=1_000_000),
        )
        if not isinstance(self.committed, bool):
            raise RuntimeContractError("committed must be boolean")
        object.__setattr__(
            self, "fault_code", _optional_text(self.fault_code, "fault_code")
        )
        if self.committed == (self.fault_code is not None):
            raise RuntimeContractError(
                "a committed manifest must have no fault; a failed manifest must have one"
            )


@runtime_checkable
class RuntimePort(Protocol):
    """Metadata common to all application-level runtime ports."""

    @property
    def runtime_metadata(self) -> RuntimePortMetadata: ...


@runtime_checkable
class ClockPort(RuntimePort, Protocol):
    def now(self) -> RuntimeInstant: ...


@runtime_checkable
class CancellationPort(RuntimePort, Protocol):
    def poll(self, request: CancellationCheck) -> CancellationStatus: ...


@runtime_checkable
class ArmLifecyclePort(RuntimePort, Protocol):
    def connect(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult: ...

    def reference(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult: ...

    def stop(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult: ...

    def close(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult: ...


@runtime_checkable
class ArmExecutionPort(
    RuntimePort, Protocol[CommandT_contra, FeedbackT_co]
):
    def execute(
        self,
        request: ArmExecutionRequest[CommandT_contra],
        cancellation: CancellationPort,
    ) -> ArmExecutionResult[FeedbackT_co]: ...


@runtime_checkable
class ArmFeedbackPort(RuntimePort, Protocol[FeedbackT_co]):
    def read_feedback(
        self,
        request: ArmFeedbackRequest,
        cancellation: CancellationPort,
    ) -> ArmFeedbackSample[FeedbackT_co]: ...


@runtime_checkable
class ObservationPort(RuntimePort, Protocol[ObservationT_co]):
    def observe(
        self,
        request: ObservationRequest,
        cancellation: CancellationPort,
    ) -> ObservationResult[ObservationT_co]: ...


@runtime_checkable
class DeviceContactPort(RuntimePort, Protocol[ContactT_contra]):
    def apply_contact(
        self,
        request: DeviceContactRequest[ContactT_contra],
        cancellation: CancellationPort,
    ) -> DeviceContactResult: ...


@runtime_checkable
class OutcomeObserverPort(RuntimePort, Protocol[OutcomeT_co]):
    def observe_outcome(
        self,
        request: OutcomeRequest,
        cancellation: CancellationPort,
    ) -> OutcomeObservation[OutcomeT_co]: ...


@runtime_checkable
class EvidenceSinkPort(RuntimePort, Protocol):
    def append(
        self,
        request: EvidenceWriteRequest,
        cancellation: CancellationPort,
    ) -> EvidenceWriteResult: ...

    def finalize(
        self,
        request: EvidenceFinalizeRequest,
        cancellation: CancellationPort,
    ) -> EvidenceFinalizeResult: ...


ArmCommandT = TypeVar("ArmCommandT")
ArmFeedbackT = TypeVar("ArmFeedbackT")
ObservationT = TypeVar("ObservationT")
ContactT = TypeVar("ContactT")
OutcomeT = TypeVar("OutcomeT")


@dataclass(frozen=True, slots=True)
class MissionRuntimePorts(
    Generic[ArmCommandT, ArmFeedbackT, ObservationT, ContactT, OutcomeT]
):
    """All replaceable dependencies consumed by one mission orchestrator."""

    clock: ClockPort
    arm_lifecycle: ArmLifecyclePort
    arm_execution: ArmExecutionPort[ArmCommandT, ArmFeedbackT]
    arm_feedback: ArmFeedbackPort[ArmFeedbackT]
    observation: ObservationPort[ObservationT]
    device_contact: DeviceContactPort[ContactT]
    outcome_observer: OutcomeObserverPort[OutcomeT]
    cancellation: CancellationPort
    evidence: EvidenceSinkPort


@dataclass(frozen=True, slots=True)
class RuntimeContractReport:
    """Deterministic proof that a complete port bundle passed validation."""

    runtime_id: str
    contract: str
    validated_roles: tuple[RuntimePortRole, ...]
    unique_port_ids: tuple[str, ...]
    execution_modes: tuple[RuntimeExecutionMode, ...]
    zero_authority: bool
    hardware_accessed: bool
    hardware_commands_generated: int


_REQUIRED_PORTS: tuple[tuple[str, RuntimePortRole, type[RuntimePort]], ...] = (
    ("clock", RuntimePortRole.CLOCK, ClockPort),
    ("arm_lifecycle", RuntimePortRole.ARM_LIFECYCLE, ArmLifecyclePort),
    ("arm_execution", RuntimePortRole.ARM_EXECUTION, ArmExecutionPort),
    ("arm_feedback", RuntimePortRole.ARM_FEEDBACK, ArmFeedbackPort),
    ("observation", RuntimePortRole.OBSERVATION, ObservationPort),
    ("device_contact", RuntimePortRole.DEVICE_CONTACT, DeviceContactPort),
    ("outcome_observer", RuntimePortRole.OUTCOME_OBSERVER, OutcomeObserverPort),
    ("cancellation", RuntimePortRole.CANCELLATION, CancellationPort),
    ("evidence", RuntimePortRole.EVIDENCE, EvidenceSinkPort),
)


def validate_runtime_ports(
    ports: MissionRuntimePorts[
        ArmCommandT, ArmFeedbackT, ObservationT, ContactT, OutcomeT
    ],
    *,
    require_zero_authority: bool = True,
) -> RuntimeContractReport:
    """Fail closed unless every orchestrator dependency satisfies its contract.

    Runtime protocol checks establish member presence.  Static checking and the
    shared contract tests establish signatures and semantics.  The validator
    additionally correlates role declarations, runtime identity, port identity,
    and authority footprints before a mission starts.
    """

    if not isinstance(require_zero_authority, bool):
        raise RuntimeContractError("require_zero_authority must be boolean")

    metadata_by_id: dict[str, RuntimePortMetadata] = {}
    runtime_id: str | None = None
    validated_roles: list[RuntimePortRole] = []

    for attribute, role, protocol_type in _REQUIRED_PORTS:
        port = getattr(ports, attribute)
        if not isinstance(port, protocol_type):
            raise RuntimeContractError(
                f"{attribute} does not implement the {role.value} runtime contract"
            )
        metadata = port.runtime_metadata
        if not isinstance(metadata, RuntimePortMetadata):
            raise RuntimeContractError(
                f"{attribute}.runtime_metadata must be RuntimePortMetadata"
            )
        if role not in metadata.roles:
            raise RuntimeContractError(
                f"{attribute} metadata does not declare role {role.value}"
            )
        if runtime_id is None:
            runtime_id = metadata.runtime_id
        elif metadata.runtime_id != runtime_id:
            raise RuntimeContractError(
                "all mission ports must belong to the same runtime_id"
            )
        previous = metadata_by_id.get(metadata.port_id)
        if previous is not None and previous != metadata:
            raise RuntimeContractError(
                f"port_id {metadata.port_id!r} has inconsistent metadata"
            )
        metadata_by_id[metadata.port_id] = metadata
        if require_zero_authority and not metadata.authority.is_zero_authority:
            raise RuntimeContractError(
                f"{attribute} is not zero-authority; pre-hardware runtime rejected"
            )
        validated_roles.append(role)

    if runtime_id is None:  # Defensive: _REQUIRED_PORTS is intentionally non-empty.
        raise RuntimeContractError("runtime bundle contains no ports")

    unique_metadata = tuple(metadata_by_id.values())
    total_commands = sum(
        metadata.authority.hardware_commands_generated
        for metadata in unique_metadata
    )
    modes = tuple(
        sorted(
            {metadata.authority.execution_mode for metadata in unique_metadata},
            key=lambda mode: mode.value,
        )
    )
    zero_authority = all(
        metadata.authority.is_zero_authority for metadata in unique_metadata
    )
    return RuntimeContractReport(
        runtime_id=runtime_id,
        contract=RUNTIME_PORT_CONTRACT,
        validated_roles=tuple(validated_roles),
        unique_port_ids=tuple(sorted(metadata_by_id)),
        execution_modes=modes,
        zero_authority=zero_authority,
        hardware_accessed=any(
            metadata.authority.hardware_accessed for metadata in unique_metadata
        ),
        hardware_commands_generated=total_commands,
    )


__all__ = [
    "RUNTIME_PORT_CONTRACT",
    "MAX_RUNTIME_PAYLOAD_BYTES",
    "RuntimeContractError",
    "RuntimePortOperationError",
    "RuntimeExecutionMode",
    "RuntimePortRole",
    "RuntimeAuthority",
    "RuntimePortMetadata",
    "RuntimeInstant",
    "RuntimeDeadline",
    "LifecycleRequest",
    "LifecycleResult",
    "ArmExecutionRequest",
    "ArmExecutionResult",
    "ArmFeedbackRequest",
    "ArmFeedbackSample",
    "validate_arm_feedback_sample",
    "CancellationCheck",
    "CancellationStatus",
    "ObservationRequest",
    "ObservationResult",
    "DeviceContactRequest",
    "DeviceContactResult",
    "OutcomeRequest",
    "OutcomeObservation",
    "EvidenceWriteRequest",
    "EvidenceWriteResult",
    "EvidenceFinalizeRequest",
    "EvidenceFinalizeResult",
    "RuntimePort",
    "ClockPort",
    "CancellationPort",
    "ArmLifecyclePort",
    "ArmExecutionPort",
    "ArmFeedbackPort",
    "ObservationPort",
    "DeviceContactPort",
    "OutcomeObserverPort",
    "EvidenceSinkPort",
    "MissionRuntimePorts",
    "RuntimeContractReport",
    "validate_runtime_ports",
]
