"""Reusable deterministic zero-authority implementations of runtime ports.

These components exercise the same ``MissionRuntimePorts`` boundary intended
for a later adaptive orchestrator, but they cannot open hardware or authorize
motion/contact.  Virtual and replay modes differ only in provenance metadata;
both execute entirely in memory from an exact-once fault script.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from threading import RLock
from typing import Iterable

from .runtime_ports import (
    ArmExecutionRequest,
    ArmExecutionResult,
    ArmFeedbackRequest,
    ArmFeedbackSample,
    CancellationCheck,
    CancellationPort,
    CancellationStatus,
    DeviceContactRequest,
    DeviceContactResult,
    EvidenceFinalizeRequest,
    EvidenceFinalizeResult,
    EvidenceWriteRequest,
    EvidenceWriteResult,
    LifecycleRequest,
    LifecycleResult,
    MissionRuntimePorts,
    ObservationRequest,
    ObservationResult,
    OutcomeObservation,
    OutcomeRequest,
    RuntimeAuthority,
    RuntimeDeadline,
    RuntimeExecutionMode,
    RuntimeInstant,
    RuntimePortMetadata,
    RuntimePortOperationError,
    RuntimePortRole,
    validate_arm_feedback_sample,
    validate_runtime_ports,
)


_MAX_EMULATION_TRIGGERS = 1024
_NO_COMMAND_SHA256 = hashlib.sha256(b"NO_COMMAND").hexdigest()
_ACHIEVED_DEVIATION_UNITS = (0.125, -0.075, 0.05)


class RuntimeEmulationError(ValueError):
    """A zero-authority emulator definition or state transition is invalid."""


def _identifier(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise RuntimeEmulationError(f"{label} must be non-empty trimmed text")
    if len(value) > maximum:
        raise RuntimeEmulationError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise RuntimeEmulationError(f"{label} contains a control character")
    return value


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeEmulationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _canonical_payload(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    method = getattr(value, "to_dict", None)
    document = method() if callable(method) else value
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RuntimeEmulationError(
            "emulated payload must be immutable bytes or canonical JSON data"
        ) from exc


class RuntimeEmulationFault(str, Enum):
    """Faults consumed exactly once at their named operation boundary."""

    CANCELLED = "CANCELLED"
    CANCELLATION_CORRELATION_MISMATCH = "CANCELLATION_CORRELATION_MISMATCH"
    TIMEOUT = "TIMEOUT"
    DISCONNECT = "DISCONNECT"
    RESET = "RESET"
    STALE_FEEDBACK = "STALE_FEEDBACK"
    REORDERED_FEEDBACK = "REORDERED_FEEDBACK"
    FEEDBACK_CORRELATION_MISMATCH = "FEEDBACK_CORRELATION_MISMATCH"
    OBSERVATION_FAILURE = "OBSERVATION_FAILURE"
    CONTACT_FAILURE = "CONTACT_FAILURE"
    OUTCOME_FAILURE = "OUTCOME_FAILURE"
    EVIDENCE_APPEND_FAILURE = "EVIDENCE_APPEND_FAILURE"
    EVIDENCE_FINALIZE_FAILURE = "EVIDENCE_FINALIZE_FAILURE"


@dataclass(frozen=True, slots=True)
class RuntimeEmulationFaultTrigger:
    operation_id: str
    fault: RuntimeEmulationFault

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        if not isinstance(self.fault, RuntimeEmulationFault):
            try:
                object.__setattr__(self, "fault", RuntimeEmulationFault(self.fault))
            except (TypeError, ValueError) as exc:
                raise RuntimeEmulationError("unsupported emulation fault") from exc


class RuntimeEmulationFaultScript:
    """Immutable definition with thread-safe exact-once consumption state."""

    def __init__(
        self,
        triggers: Iterable[RuntimeEmulationFaultTrigger] = (),
    ) -> None:
        parsed = tuple(triggers)
        if len(parsed) > _MAX_EMULATION_TRIGGERS:
            raise RuntimeEmulationError("emulation fault script exceeds hard limit")
        if not all(isinstance(item, RuntimeEmulationFaultTrigger) for item in parsed):
            raise TypeError("triggers must contain RuntimeEmulationFaultTrigger values")
        operation_ids = tuple(item.operation_id for item in parsed)
        if len(operation_ids) != len(set(operation_ids)):
            raise RuntimeEmulationError(
                "only one deterministic fault may target an operation_id"
            )
        self._definition = parsed
        self._remaining = {item.operation_id: item.fault for item in parsed}
        self._consumed: list[RuntimeEmulationFaultTrigger] = []
        self._lock = RLock()

    @property
    def definition_sha256(self) -> str:
        document = [
            {"operation_id": item.operation_id, "fault": item.fault.value}
            for item in self._definition
        ]
        return hashlib.sha256(_canonical_payload(document)).hexdigest()

    @property
    def remaining(self) -> tuple[RuntimeEmulationFaultTrigger, ...]:
        with self._lock:
            return tuple(
                item for item in self._definition if item.operation_id in self._remaining
            )

    @property
    def consumed(self) -> tuple[RuntimeEmulationFaultTrigger, ...]:
        with self._lock:
            return tuple(self._consumed)

    def consume(
        self,
        operation_id: str,
        allowed: Iterable[RuntimeEmulationFault],
    ) -> RuntimeEmulationFault | None:
        parsed_id = _identifier(operation_id, "operation_id")
        allowed_set = frozenset(allowed)
        if not all(isinstance(item, RuntimeEmulationFault) for item in allowed_set):
            raise TypeError("allowed must contain RuntimeEmulationFault values")
        with self._lock:
            fault = self._remaining.get(parsed_id)
            if fault is None or fault not in allowed_set:
                return None
            del self._remaining[parsed_id]
            self._consumed.append(RuntimeEmulationFaultTrigger(parsed_id, fault))
            return fault


def _metadata(
    runtime_id: str,
    port_id: str,
    mode: RuntimeExecutionMode,
    *roles: RuntimePortRole,
) -> RuntimePortMetadata:
    return RuntimePortMetadata(
        runtime_id=runtime_id,
        port_id=port_id,
        implementation_id=f"rocell.deterministic_runtime_emulation.{port_id}.v1",
        roles=roles,
        authority=RuntimeAuthority.zero(mode),
    )


class DeterministicRuntimeClock:
    """Manually advanced monotonic clock shared by one emulated runtime."""

    def __init__(
        self,
        runtime_id: str,
        mode: RuntimeExecutionMode,
        *,
        initial_tick: int = 0,
        tick_period_ns: int = 1_000_000,
    ) -> None:
        if isinstance(initial_tick, bool) or not isinstance(initial_tick, int) or initial_tick < 0:
            raise RuntimeEmulationError("initial_tick must be a nonnegative integer")
        if (
            isinstance(tick_period_ns, bool)
            or not isinstance(tick_period_ns, int)
            or not 1 <= tick_period_ns <= 1_000_000_000_000
        ):
            raise RuntimeEmulationError("tick_period_ns is outside the runtime limit")
        self.runtime_metadata = _metadata(
            runtime_id, "clock", mode, RuntimePortRole.CLOCK
        )
        self.clock_id = f"{runtime_id}.monotonic"
        self.tick_period_ns = tick_period_ns
        self._tick = initial_tick
        self._lock = RLock()

    def now(self) -> RuntimeInstant:
        with self._lock:
            return RuntimeInstant(self.clock_id, self._tick, self.tick_period_ns)

    def advance(self, ticks: int = 1) -> RuntimeInstant:
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks <= 0:
            raise RuntimeEmulationError("clock advance must be a positive integer")
        with self._lock:
            self._tick += ticks
            return RuntimeInstant(self.clock_id, self._tick, self.tick_period_ns)


class DeterministicCancellationPort:
    def __init__(
        self,
        runtime_id: str,
        mode: RuntimeExecutionMode,
        clock: DeterministicRuntimeClock,
        faults: RuntimeEmulationFaultScript,
    ) -> None:
        self.runtime_metadata = _metadata(
            runtime_id, "cancellation", mode, RuntimePortRole.CANCELLATION
        )
        self._clock = clock
        self._faults = faults

    def poll(self, request: CancellationCheck) -> CancellationStatus:
        if not isinstance(request, CancellationCheck):
            raise TypeError("request must be CancellationCheck")
        mismatch = self._faults.consume(
            request.checkpoint_id,
            (RuntimeEmulationFault.CANCELLATION_CORRELATION_MISMATCH,),
        )
        if mismatch is not None:
            return CancellationStatus(
                f"{request.checkpoint_id}.mismatch",
                self._clock.now(),
                False,
            )
        cancelled = self._faults.consume(
            request.checkpoint_id,
            (RuntimeEmulationFault.CANCELLED,),
        )
        if cancelled is not None:
            return CancellationStatus(
                request.checkpoint_id,
                self._clock.now(),
                True,
                "EMULATED_CANCELLATION",
            )
        return CancellationStatus(request.checkpoint_id, self._clock.now(), False)


def _check_deadline(
    deadline: RuntimeDeadline | None,
    instant: RuntimeInstant,
    operation_id: str,
) -> None:
    if deadline is None:
        return
    if (
        deadline.at.clock_id != instant.clock_id
        or deadline.at.tick_period_ns != instant.tick_period_ns
    ):
        raise RuntimePortOperationError(
            "DEADLINE_CLOCK_MISMATCH", operation_id
        )
    if instant.tick > deadline.at.tick:
        raise RuntimePortOperationError("DEADLINE_EXPIRED", operation_id)


def _begin_operation(
    *,
    mission_id: str,
    operation_id: str,
    deadline: RuntimeDeadline | None,
    cancellation: CancellationPort,
    clock: DeterministicRuntimeClock,
) -> None:
    try:
        status = cancellation.poll(CancellationCheck(mission_id, operation_id))
    except RuntimePortOperationError:
        raise
    except Exception as exc:
        raise RuntimePortOperationError(
            "CANCELLATION_POLL_FAILED", operation_id, str(exc)
        ) from exc
    if not isinstance(status, CancellationStatus):
        raise RuntimePortOperationError(
            "CANCELLATION_RESULT_INVALID", operation_id
        )
    if status.checkpoint_id != operation_id:
        raise RuntimePortOperationError(
            "CANCELLATION_CORRELATION_MISMATCH", operation_id
        )
    if status.cancelled:
        raise RuntimePortOperationError(
            "OPERATION_CANCELLED", operation_id, status.reason
        )
    _check_deadline(deadline, clock.now(), operation_id)


def _finish_operation(
    clock: DeterministicRuntimeClock,
    deadline: RuntimeDeadline | None,
    operation_id: str,
) -> RuntimeInstant:
    completed_at = clock.advance()
    _check_deadline(deadline, completed_at, operation_id)
    return completed_at


@dataclass(frozen=True, slots=True)
class EmulatedControllerFeedback:
    """Correlated synthetic achieved state from the zero-authority arm port.

    ``achieved_deviation_units`` is deliberately nonzero after execution.  It
    prevents tests from quietly treating a command echo as measured feedback.
    The units remain fixture-defined because this generic boundary does not own
    Cartesian/joint semantics.
    """

    source_operation_id: str | None
    action_index: int | None
    waypoint_sequence: int | None
    controller_sequence: int
    command_sha256: str
    achieved_deviation_units: tuple[float, float, float] = (0.0, 0.0, 0.0)
    achieved_state_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.source_operation_id is not None:
            object.__setattr__(
                self,
                "source_operation_id",
                _identifier(self.source_operation_id, "source_operation_id"),
            )
        for name in ("action_index", "waypoint_sequence"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise RuntimeEmulationError(f"{name} must be nonnegative or None")
        if (
            isinstance(self.controller_sequence, bool)
            or not isinstance(self.controller_sequence, int)
            or self.controller_sequence < 0
        ):
            raise RuntimeEmulationError(
                "controller_sequence must be a nonnegative integer"
            )
        object.__setattr__(
            self,
            "command_sha256",
            _digest(self.command_sha256, "command_sha256"),
        )
        if (
            not isinstance(self.achieved_deviation_units, tuple)
            or len(self.achieved_deviation_units) != 3
        ):
            raise RuntimeEmulationError(
                "achieved_deviation_units must be a three-value tuple"
            )
        parsed_deviation: list[float] = []
        for value in self.achieved_deviation_units:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeEmulationError(
                    "achieved_deviation_units must contain finite numbers"
                )
            parsed = float(value)
            if not math.isfinite(parsed):
                raise RuntimeEmulationError(
                    "achieved_deviation_units must contain finite numbers"
                )
            parsed_deviation.append(parsed)
        object.__setattr__(
            self,
            "achieved_deviation_units",
            tuple(parsed_deviation),
        )
        achieved_document = {
            "command_sha256": self.command_sha256,
            "controller_sequence": self.controller_sequence,
            "achieved_deviation_units": list(parsed_deviation),
        }
        object.__setattr__(
            self,
            "achieved_state_sha256",
            hashlib.sha256(_canonical_payload(achieved_document)).hexdigest(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_operation_id": self.source_operation_id,
            "action_index": self.action_index,
            "waypoint_sequence": self.waypoint_sequence,
            "controller_sequence": self.controller_sequence,
            "command_sha256": self.command_sha256,
            "achieved_deviation_units": list(self.achieved_deviation_units),
            "achieved_state_sha256": self.achieved_state_sha256,
        }

    @property
    def feedback_hash(self) -> str:
        return hashlib.sha256(_canonical_payload(self.to_dict())).hexdigest()


class DeterministicControllerPort:
    """Lifecycle, execution, and feedback emulator with strict correlation."""

    _COMMON_FAULTS = (
        RuntimeEmulationFault.TIMEOUT,
        RuntimeEmulationFault.DISCONNECT,
        RuntimeEmulationFault.RESET,
    )

    def __init__(
        self,
        runtime_id: str,
        mode: RuntimeExecutionMode,
        clock: DeterministicRuntimeClock,
        faults: RuntimeEmulationFaultScript,
    ) -> None:
        self.runtime_metadata = _metadata(
            runtime_id,
            "controller",
            mode,
            RuntimePortRole.ARM_LIFECYCLE,
            RuntimePortRole.ARM_EXECUTION,
            RuntimePortRole.ARM_FEEDBACK,
        )
        self._clock = clock
        self._faults = faults
        self._state = "NEW"
        self._controller_sequence = 0
        self._feedback_sequence = 0
        self._last_delivered_feedback_sequence: int | None = None
        self._latest_feedback = EmulatedControllerFeedback(
            None, None, None, 0, _NO_COMMAND_SHA256
        )
        self._lock = RLock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def latest_feedback(self) -> EmulatedControllerFeedback:
        """Return the immutable latest achieved-state fixture."""

        with self._lock:
            return self._latest_feedback

    def _common_fault(self, operation_id: str) -> None:
        fault = self._faults.consume(operation_id, self._COMMON_FAULTS)
        if fault is None:
            return
        self._state = "FAULTED"
        if fault is RuntimeEmulationFault.RESET:
            self._controller_sequence = 0
        raise RuntimePortOperationError(
            f"ARM_{fault.value}", operation_id
        )

    def _lifecycle(
        self,
        request: LifecycleRequest,
        cancellation: CancellationPort,
        *,
        required_states: tuple[str, ...],
        target_state: str,
    ) -> LifecycleResult:
        if not isinstance(request, LifecycleRequest):
            raise TypeError("request must be LifecycleRequest")
        with self._lock:
            _begin_operation(
                mission_id=request.mission_id,
                operation_id=request.operation_id,
                deadline=request.deadline,
                cancellation=cancellation,
                clock=self._clock,
            )
            self._common_fault(request.operation_id)
            if self._state not in required_states:
                completed_at = _finish_operation(
                    self._clock, request.deadline, request.operation_id
                )
                return LifecycleResult(
                    request.operation_id,
                    self._state,
                    completed_at,
                    False,
                    f"ARM_LIFECYCLE_{target_state}_INVALID_FROM_{self._state}",
                )
            completed_at = _finish_operation(
                self._clock, request.deadline, request.operation_id
            )
            self._state = target_state
            return LifecycleResult(
                request.operation_id,
                self._state,
                completed_at,
                True,
            )

    def connect(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._lifecycle(
            request,
            cancellation,
            required_states=("NEW",),
            target_state="CONNECTED",
        )

    def reference(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._lifecycle(
            request,
            cancellation,
            required_states=("CONNECTED",),
            target_state="REFERENCED",
        )

    def stop(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._lifecycle(
            request,
            cancellation,
            required_states=("CONNECTED", "REFERENCED", "FAULTED"),
            target_state="STOPPED",
        )

    def close(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._lifecycle(
            request,
            cancellation,
            required_states=(
                "NEW",
                "CONNECTED",
                "REFERENCED",
                "STOPPED",
                "FAULTED",
            ),
            target_state="CLOSED",
        )

    def execute(
        self,
        request: ArmExecutionRequest[object],
        cancellation: CancellationPort,
    ) -> ArmExecutionResult[EmulatedControllerFeedback]:
        if not isinstance(request, ArmExecutionRequest):
            raise TypeError("request must be ArmExecutionRequest")
        with self._lock:
            _begin_operation(
                mission_id=request.mission_id,
                operation_id=request.operation_id,
                deadline=request.deadline,
                cancellation=cancellation,
                clock=self._clock,
            )
            self._common_fault(request.operation_id)
            if self._state != "REFERENCED":
                return ArmExecutionResult(
                    request.operation_id,
                    _finish_operation(
                        self._clock, request.deadline, request.operation_id
                    ),
                    accepted=False,
                    completed=False,
                    fault_code="ARM_NOT_REFERENCED",
                )
            command_hash = hashlib.sha256(
                _canonical_payload(request.command)
            ).hexdigest()
            next_controller_sequence = self._controller_sequence + 1
            feedback = EmulatedControllerFeedback(
                source_operation_id=request.operation_id,
                action_index=request.action_index,
                waypoint_sequence=request.waypoint_sequence,
                controller_sequence=next_controller_sequence,
                command_sha256=command_hash,
                achieved_deviation_units=_ACHIEVED_DEVIATION_UNITS,
            )
            completed_at = _finish_operation(
                self._clock, request.deadline, request.operation_id
            )
            self._controller_sequence = next_controller_sequence
            self._latest_feedback = feedback
            return ArmExecutionResult(
                request.operation_id,
                completed_at,
                accepted=True,
                completed=True,
                feedback=feedback,
            )

    def read_feedback(
        self,
        request: ArmFeedbackRequest,
        cancellation: CancellationPort,
    ) -> ArmFeedbackSample[EmulatedControllerFeedback]:
        if not isinstance(request, ArmFeedbackRequest):
            raise TypeError("request must be ArmFeedbackRequest")
        with self._lock:
            _begin_operation(
                mission_id=request.mission_id,
                operation_id=request.operation_id,
                deadline=request.deadline,
                cancellation=cancellation,
                clock=self._clock,
            )
            self._common_fault(request.operation_id)
            if self._state != "REFERENCED":
                raise RuntimePortOperationError(
                    "ARM_NOT_REFERENCED", request.operation_id
                )
            feedback_fault = self._faults.consume(
                request.operation_id,
                (
                    RuntimeEmulationFault.STALE_FEEDBACK,
                    RuntimeEmulationFault.REORDERED_FEEDBACK,
                    RuntimeEmulationFault.FEEDBACK_CORRELATION_MISMATCH,
                ),
            )
            next_sequence = self._feedback_sequence + 1
            stale = feedback_fault is RuntimeEmulationFault.STALE_FEEDBACK
            if feedback_fault is RuntimeEmulationFault.REORDERED_FEEDBACK:
                next_sequence = self._last_delivered_feedback_sequence or 0
            correlated_operation = request.operation_id
            if feedback_fault is RuntimeEmulationFault.FEEDBACK_CORRELATION_MISMATCH:
                correlated_operation = f"{request.operation_id}.mismatch"
            observed_at = _finish_operation(
                self._clock, request.deadline, request.operation_id
            )
            sample = ArmFeedbackSample(
                sample_id=f"feedback-{request.operation_id}",
                observed_at=observed_at,
                sequence=next_sequence,
                feedback=self._latest_feedback,
                stale=stale,
                request_operation_id=correlated_operation,
                action_index=request.action_index,
                feedback_binding_sha256=self._latest_feedback.feedback_hash,
            )
            try:
                validate_arm_feedback_sample(
                    request,
                    sample,
                    previous_sequence=self._last_delivered_feedback_sequence,
                )
            except RuntimePortOperationError:
                self._state = "FAULTED"
                raise
            self._feedback_sequence = next_sequence
            self._last_delivered_feedback_sequence = next_sequence
            return sample


@dataclass(frozen=True, slots=True)
class EmulatedObservation:
    observation_id: str
    action_index: int | None
    phase: str


@dataclass(frozen=True, slots=True)
class EmulatedOutcome:
    checkpoint_id: str
    action_index: int | None


class DeterministicObservationPort:
    def __init__(self, runtime_id: str, mode: RuntimeExecutionMode, clock: DeterministicRuntimeClock, faults: RuntimeEmulationFaultScript) -> None:
        self.runtime_metadata = _metadata(runtime_id, "observation", mode, RuntimePortRole.OBSERVATION)
        self._clock = clock
        self._faults = faults
        self._sequence = 0
        self._lock = RLock()

    def observe(self, request: ObservationRequest, cancellation: CancellationPort) -> ObservationResult[EmulatedObservation]:
        with self._lock:
            _begin_operation(mission_id=request.mission_id, operation_id=request.observation_id, deadline=request.deadline, cancellation=cancellation, clock=self._clock)
            next_sequence = self._sequence + 1
            observed_at = _finish_operation(self._clock, request.deadline, request.observation_id)
            self._sequence = next_sequence
            if self._faults.consume(request.observation_id, (RuntimeEmulationFault.OBSERVATION_FAILURE,)) is not None:
                return ObservationResult(request.observation_id, observed_at, next_sequence, None, False, "EMULATED_OBSERVATION_FAILURE")
            return ObservationResult(request.observation_id, observed_at, next_sequence, EmulatedObservation(request.observation_id, request.action_index, request.phase), True)


class DeterministicDeviceContactPort:
    def __init__(self, runtime_id: str, mode: RuntimeExecutionMode, clock: DeterministicRuntimeClock, faults: RuntimeEmulationFaultScript) -> None:
        self.runtime_metadata = _metadata(runtime_id, "device", mode, RuntimePortRole.DEVICE_CONTACT)
        self._clock = clock
        self._faults = faults
        self._lock = RLock()

    def apply_contact(self, request: DeviceContactRequest[object], cancellation: CancellationPort) -> DeviceContactResult:
        with self._lock:
            _begin_operation(mission_id=request.mission_id, operation_id=request.operation_id, deadline=request.deadline, cancellation=cancellation, clock=self._clock)
            observed_at = _finish_operation(self._clock, request.deadline, request.operation_id)
            if self._faults.consume(request.operation_id, (RuntimeEmulationFault.CONTACT_FAILURE,)) is not None:
                return DeviceContactResult(request.operation_id, observed_at, False, 0, (), "EMULATED_CONTACT_FAILURE")
            return DeviceContactResult(request.operation_id, observed_at, True, 1, (f"event-{request.operation_id}",))


class DeterministicOutcomeObserverPort:
    def __init__(self, runtime_id: str, mode: RuntimeExecutionMode, clock: DeterministicRuntimeClock, faults: RuntimeEmulationFaultScript) -> None:
        self.runtime_metadata = _metadata(runtime_id, "outcome", mode, RuntimePortRole.OUTCOME_OBSERVER)
        self._clock = clock
        self._faults = faults
        self._sequence = 0
        self._lock = RLock()

    def observe_outcome(self, request: OutcomeRequest, cancellation: CancellationPort) -> OutcomeObservation[EmulatedOutcome]:
        with self._lock:
            _begin_operation(mission_id=request.mission_id, operation_id=request.checkpoint_id, deadline=request.deadline, cancellation=cancellation, clock=self._clock)
            next_sequence = self._sequence + 1
            observed_at = _finish_operation(self._clock, request.deadline, request.checkpoint_id)
            self._sequence = next_sequence
            if self._faults.consume(request.checkpoint_id, (RuntimeEmulationFault.OUTCOME_FAILURE,)) is not None:
                return OutcomeObservation(request.checkpoint_id, observed_at, next_sequence, None, False, "EMULATED_OUTCOME_FAILURE")
            return OutcomeObservation(request.checkpoint_id, observed_at, next_sequence, EmulatedOutcome(request.checkpoint_id, request.action_index), True)


@dataclass(frozen=True, slots=True)
class InMemoryEvidenceRecord:
    mission_id: str
    record_id: str
    role: str
    sequence: int
    media_type: str
    payload: bytes
    payload_sha256: str


class InMemoryEvidenceSinkPort:
    """Append-only, exact-order evidence sink with deterministic fault results."""

    def __init__(self, runtime_id: str, mode: RuntimeExecutionMode, clock: DeterministicRuntimeClock, faults: RuntimeEmulationFaultScript) -> None:
        self.runtime_metadata = _metadata(runtime_id, "evidence", mode, RuntimePortRole.EVIDENCE)
        self._clock = clock
        self._faults = faults
        self._records: list[InMemoryEvidenceRecord] = []
        self._record_ids: set[str] = set()
        self._mission_id: str | None = None
        self._finalized = False
        self._lock = RLock()

    @property
    def records(self) -> tuple[InMemoryEvidenceRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def append(self, request: EvidenceWriteRequest, cancellation: CancellationPort) -> EvidenceWriteResult:
        with self._lock:
            _begin_operation(mission_id=request.mission_id, operation_id=request.record_id, deadline=None, cancellation=cancellation, clock=self._clock)
            committed_at = _finish_operation(self._clock, None, request.record_id)
            injected = self._faults.consume(request.record_id, (RuntimeEmulationFault.EVIDENCE_APPEND_FAILURE,))
            invalid = self._finalized or request.record_id in self._record_ids or request.sequence != len(self._records) or self._mission_id not in (None, request.mission_id)
            if injected is not None or invalid:
                fault = "EMULATED_EVIDENCE_APPEND_FAILURE" if injected is not None else "EVIDENCE_APPEND_STATE_INVALID"
                return EvidenceWriteResult(request.record_id, committed_at, request.payload_sha256, len(request.payload), False, fault)
            if self._mission_id is None:
                self._mission_id = request.mission_id
            self._records.append(InMemoryEvidenceRecord(request.mission_id, request.record_id, request.role, request.sequence, request.media_type, bytes(request.payload), request.payload_sha256))
            self._record_ids.add(request.record_id)
            return EvidenceWriteResult(request.record_id, committed_at, request.payload_sha256, len(request.payload), True)

    def finalize(self, request: EvidenceFinalizeRequest, cancellation: CancellationPort) -> EvidenceFinalizeResult:
        operation_id = f"manifest-{request.mission_id}"
        with self._lock:
            _begin_operation(mission_id=request.mission_id, operation_id=operation_id, deadline=None, cancellation=cancellation, clock=self._clock)
            committed_at = _finish_operation(self._clock, None, operation_id)
            manifest_document = {
                "mission_id": request.mission_id,
                "terminal_status": request.terminal_status,
                "records": [
                    {"record_id": item.record_id, "sequence": item.sequence, "payload_sha256": item.payload_sha256}
                    for item in self._records
                ],
            }
            manifest_sha256 = hashlib.sha256(_canonical_payload(manifest_document)).hexdigest()
            injected = self._faults.consume(operation_id, (RuntimeEmulationFault.EVIDENCE_FINALIZE_FAILURE,))
            invalid = self._finalized or self._mission_id not in (None, request.mission_id) or request.expected_record_ids != tuple(item.record_id for item in self._records)
            if injected is not None or invalid:
                fault = "EMULATED_EVIDENCE_FINALIZE_FAILURE" if injected is not None else "EVIDENCE_FINALIZE_STATE_INVALID"
                return EvidenceFinalizeResult(operation_id, committed_at, manifest_sha256, len(self._records), False, fault)
            self._finalized = True
            return EvidenceFinalizeResult(operation_id, committed_at, manifest_sha256, len(self._records), True)


def make_deterministic_runtime_ports(
    runtime_id: str,
    *,
    execution_mode: RuntimeExecutionMode = RuntimeExecutionMode.VIRTUAL,
    fault_triggers: Iterable[RuntimeEmulationFaultTrigger] = (),
) -> MissionRuntimePorts[object, EmulatedControllerFeedback, EmulatedObservation, object, EmulatedOutcome]:
    """Build and validate one complete virtual or replay port bundle."""

    parsed_runtime_id = _identifier(runtime_id, "runtime_id")
    if execution_mode not in (RuntimeExecutionMode.VIRTUAL, RuntimeExecutionMode.REPLAY):
        raise RuntimeEmulationError(
            "deterministic runtime ports support only VIRTUAL or REPLAY mode"
        )
    faults = RuntimeEmulationFaultScript(fault_triggers)
    clock = DeterministicRuntimeClock(parsed_runtime_id, execution_mode)
    cancellation = DeterministicCancellationPort(parsed_runtime_id, execution_mode, clock, faults)
    controller = DeterministicControllerPort(parsed_runtime_id, execution_mode, clock, faults)
    ports: MissionRuntimePorts[object, EmulatedControllerFeedback, EmulatedObservation, object, EmulatedOutcome] = MissionRuntimePorts(
        clock=clock,
        arm_lifecycle=controller,
        arm_execution=controller,
        arm_feedback=controller,
        observation=DeterministicObservationPort(parsed_runtime_id, execution_mode, clock, faults),
        device_contact=DeterministicDeviceContactPort(parsed_runtime_id, execution_mode, clock, faults),
        outcome_observer=DeterministicOutcomeObserverPort(parsed_runtime_id, execution_mode, clock, faults),
        cancellation=cancellation,
        evidence=InMemoryEvidenceSinkPort(parsed_runtime_id, execution_mode, clock, faults),
    )
    validate_runtime_ports(ports)
    return ports


__all__ = [
    "DeterministicCancellationPort",
    "DeterministicControllerPort",
    "DeterministicDeviceContactPort",
    "DeterministicObservationPort",
    "DeterministicOutcomeObserverPort",
    "DeterministicRuntimeClock",
    "EmulatedControllerFeedback",
    "EmulatedObservation",
    "EmulatedOutcome",
    "InMemoryEvidenceRecord",
    "InMemoryEvidenceSinkPort",
    "RuntimeEmulationError",
    "RuntimeEmulationFault",
    "RuntimeEmulationFaultScript",
    "RuntimeEmulationFaultTrigger",
    "make_deterministic_runtime_ports",
]
