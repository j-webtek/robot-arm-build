"""Bounded end-to-end rehearsal over the application runtime-port boundary.

This module is intentionally small and hardware-neutral.  It drives one opaque
command and one opaque contact through :class:`MissionRuntimePorts`, records a
fixed sequence of boundary outcomes, and returns a canonical hash-bound report.
It neither imports physical adapters nor grants motion/contact authority.

The rehearsal validates the port bundle both before and after the run.  A
report therefore exists only when every adapter continues to declare a zero
physical footprint.  All operational failures are converted to deterministic
step records.  Stop and close are attempted independently after every earlier
failure; evidence finalization follows cleanup so its terminal status is final.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Callable, Generic, TypeVar, cast

from .runtime_ports import (
    ArmExecutionRequest,
    ArmExecutionResult,
    ArmFeedbackRequest,
    ArmFeedbackSample,
    CancellationCheck,
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
    RuntimeContractReport,
    RuntimeDeadline,
    RuntimeExecutionMode,
    RuntimeInstant,
    RuntimePortOperationError,
    validate_arm_feedback_sample,
    validate_runtime_ports,
)


ZERO_AUTHORITY_MISSION_REHEARSAL_SCHEMA = (
    "rocell.zero_authority_mission_rehearsal.v1"
)
ZERO_AUTHORITY_MISSION_REHEARSAL_SPEC_SCHEMA = (
    "rocell.zero_authority_mission_rehearsal_spec.v1"
)
_MAX_BINDING_BYTES = 1024 * 1024


class MissionRehearsalError(ValueError):
    """The rehearsal definition, result, or authority proof is invalid."""


def _identifier(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise MissionRehearsalError(f"{label} must be non-empty trimmed text")
    if len(value) > maximum:
        raise MissionRehearsalError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise MissionRehearsalError(f"{label} contains a control character")
    return value


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MissionRehearsalError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _canonical_bytes(document: object) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionRehearsalError("report document is not canonical JSON") from exc


def _stable_hash(document: object) -> str:
    return hashlib.sha256(_canonical_bytes(document)).hexdigest()


def _instant_dict(instant: RuntimeInstant) -> dict[str, object]:
    return {
        "clock_id": instant.clock_id,
        "tick": instant.tick,
        "tick_period_ns": instant.tick_period_ns,
    }


def _contract_dict(report: RuntimeContractReport) -> dict[str, object]:
    return {
        "runtime_id": report.runtime_id,
        "contract": report.contract,
        "validated_roles": [role.value for role in report.validated_roles],
        "unique_port_ids": list(report.unique_port_ids),
        "execution_modes": [mode.value for mode in report.execution_modes],
        "zero_authority": report.zero_authority,
        "hardware_accessed": report.hardware_accessed,
        "hardware_commands_generated": report.hardware_commands_generated,
    }


class MissionRehearsalStep(str, Enum):
    """Fixed boundary order for one test-fixture-scale mission."""

    VALIDATE_PORTS_INITIAL = "VALIDATE_PORTS_INITIAL"
    CONNECT = "CONNECT"
    REFERENCE = "REFERENCE"
    OBSERVATION = "OBSERVATION"
    ARM_EXECUTE = "ARM_EXECUTE"
    ARM_FEEDBACK_BASELINE = "ARM_FEEDBACK_BASELINE"
    ARM_FEEDBACK = "ARM_FEEDBACK"
    DEVICE_CONTACT = "DEVICE_CONTACT"
    OUTCOME_OBSERVATION = "OUTCOME_OBSERVATION"
    EVIDENCE_APPEND = "EVIDENCE_APPEND"
    STOP = "STOP"
    CLOSE = "CLOSE"
    EVIDENCE_FINALIZE = "EVIDENCE_FINALIZE"
    VALIDATE_PORTS_FINAL = "VALIDATE_PORTS_FINAL"


class MissionRehearsalStepStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


_STEP_ORDER = tuple(MissionRehearsalStep)
_CORE_STEPS = (
    MissionRehearsalStep.CONNECT,
    MissionRehearsalStep.REFERENCE,
    MissionRehearsalStep.OBSERVATION,
    MissionRehearsalStep.ARM_EXECUTE,
    MissionRehearsalStep.ARM_FEEDBACK_BASELINE,
    MissionRehearsalStep.ARM_FEEDBACK,
    MissionRehearsalStep.DEVICE_CONTACT,
    MissionRehearsalStep.OUTCOME_OBSERVATION,
)
_DEADLINE_CAPABLE_STEPS = frozenset(
    (
        *_CORE_STEPS,
        MissionRehearsalStep.STOP,
        MissionRehearsalStep.CLOSE,
    )
)


ValueT = TypeVar("ValueT")
CommandT = TypeVar("CommandT")
FeedbackT = TypeVar("FeedbackT")
ObservationT = TypeVar("ObservationT")
ContactT = TypeVar("ContactT")
OutcomeT = TypeVar("OutcomeT")


@dataclass(frozen=True, slots=True)
class HashBoundPortValue(Generic[ValueT]):
    """An opaque adapter value plus caller-owned canonical binding bytes.

    The rehearsal never interprets ``value``.  The domain fixture supplies the
    bytes that identify it, and only their digest enters evidence and reports.
    This avoids leaking planned characters or device truth into generic ports.
    """

    value: ValueT = field(repr=False)
    binding_bytes: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.binding_bytes, bytes):
            raise MissionRehearsalError("binding_bytes must be immutable bytes")
        if not self.binding_bytes:
            raise MissionRehearsalError("binding_bytes must not be empty")
        if len(self.binding_bytes) > _MAX_BINDING_BYTES:
            raise MissionRehearsalError(
                f"binding_bytes exceeds {_MAX_BINDING_BYTES} bytes"
            )

    @property
    def binding_sha256(self) -> str:
        return hashlib.sha256(self.binding_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class ZeroAuthorityMissionRehearsalSpec(Generic[CommandT, ContactT]):
    """One bounded generic mission definition.

    ``deadline_expiry_step`` is a deterministic negative-test fixture.  Normal
    operations receive an inclusive deadline ``deadline_budget_ticks`` ahead of
    the shared runtime clock; the selected negative-test step receives a
    deadline at its starting tick and must therefore fail if it completes late.
    """

    rehearsal_id: str
    mission_id: str
    action_index: int
    waypoint_sequence: int
    arm_command: HashBoundPortValue[CommandT]
    device_contact: HashBoundPortValue[ContactT]
    observation_phase: str = "PRE_CONTACT"
    deadline_budget_ticks: int = 2
    deadline_expiry_step: MissionRehearsalStep | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rehearsal_id",
            _identifier(self.rehearsal_id, "rehearsal_id", maximum=96),
        )
        object.__setattr__(
            self,
            "mission_id",
            _identifier(self.mission_id, "mission_id", maximum=96),
        )
        for name in ("action_index", "waypoint_sequence"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise MissionRehearsalError(f"{name} must be a nonnegative integer")
        if not isinstance(self.arm_command, HashBoundPortValue):
            raise MissionRehearsalError(
                "arm_command must be a HashBoundPortValue"
            )
        if not isinstance(self.device_contact, HashBoundPortValue):
            raise MissionRehearsalError(
                "device_contact must be a HashBoundPortValue"
            )
        object.__setattr__(
            self,
            "observation_phase",
            _identifier(self.observation_phase, "observation_phase", maximum=128),
        )
        if (
            isinstance(self.deadline_budget_ticks, bool)
            or not isinstance(self.deadline_budget_ticks, int)
            or not 1 <= self.deadline_budget_ticks <= 1_000_000
        ):
            raise MissionRehearsalError(
                "deadline_budget_ticks must be within [1, 1000000]"
            )
        if self.deadline_expiry_step is not None:
            try:
                parsed_step = MissionRehearsalStep(self.deadline_expiry_step)
            except (TypeError, ValueError) as exc:
                raise MissionRehearsalError(
                    "deadline_expiry_step is unsupported"
                ) from exc
            if parsed_step not in _DEADLINE_CAPABLE_STEPS:
                raise MissionRehearsalError(
                    "deadline_expiry_step must name a deadline-capable port operation"
                )
            object.__setattr__(self, "deadline_expiry_step", parsed_step)

    def operation_id(self, step: MissionRehearsalStep) -> str:
        """Return the exact correlation/fault-injection ID for ``step``."""

        if not isinstance(step, MissionRehearsalStep):
            try:
                step = MissionRehearsalStep(step)
            except (TypeError, ValueError) as exc:
                raise MissionRehearsalError("step is unsupported") from exc
        if step is MissionRehearsalStep.EVIDENCE_FINALIZE:
            # EvidenceFinalizeRequest intentionally has no caller operation ID;
            # the deterministic sink uses this stable manifest correlation ID.
            return f"manifest-{self.mission_id}"
        suffix = step.value.lower().replace("_", "-")
        return f"{self.rehearsal_id}.{suffix}"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ZERO_AUTHORITY_MISSION_REHEARSAL_SPEC_SCHEMA,
            "rehearsal_id": self.rehearsal_id,
            "mission_id": self.mission_id,
            "action_index": self.action_index,
            "waypoint_sequence": self.waypoint_sequence,
            "arm_command_binding_sha256": self.arm_command.binding_sha256,
            "device_contact_binding_sha256": self.device_contact.binding_sha256,
            "observation_phase": self.observation_phase,
            "deadline_budget_ticks": self.deadline_budget_ticks,
            "deadline_expiry_step": (
                self.deadline_expiry_step.value
                if self.deadline_expiry_step is not None
                else None
            ),
        }

    @property
    def definition_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class MissionRehearsalStepRecord:
    step: MissionRehearsalStep
    operation_id: str
    status: MissionRehearsalStepStatus
    started_at: RuntimeInstant
    completed_at: RuntimeInstant
    fault_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step, MissionRehearsalStep):
            raise MissionRehearsalError("step must be MissionRehearsalStep")
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        if not isinstance(self.status, MissionRehearsalStepStatus):
            raise MissionRehearsalError("status must be MissionRehearsalStepStatus")
        if not isinstance(self.started_at, RuntimeInstant) or not isinstance(
            self.completed_at, RuntimeInstant
        ):
            raise MissionRehearsalError("step timestamps must be RuntimeInstant")
        if (
            self.started_at.clock_id != self.completed_at.clock_id
            or self.started_at.tick_period_ns != self.completed_at.tick_period_ns
            or self.completed_at.tick < self.started_at.tick
        ):
            raise MissionRehearsalError(
                "step timestamps must be ordered values from one clock"
            )
        if self.fault_code is not None:
            object.__setattr__(
                self,
                "fault_code",
                _identifier(self.fault_code, "fault_code", maximum=128),
            )
        if (self.status is MissionRehearsalStepStatus.PASSED) == (
            self.fault_code is not None
        ):
            raise MissionRehearsalError(
                "passed steps have no fault; failed/skipped steps require one"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "step": self.step.value,
            "operation_id": self.operation_id,
            "status": self.status.value,
            "started_at": _instant_dict(self.started_at),
            "completed_at": _instant_dict(self.completed_at),
            "fault_code": self.fault_code,
        }


@dataclass(frozen=True, slots=True)
class ZeroAuthorityMissionRehearsalReport:
    """Canonical evidence that one complete port-boundary rehearsal ran."""

    rehearsal_id: str
    mission_id: str
    runtime_id: str
    spec_sha256: str
    runtime_contract_sha256: str
    execution_modes: tuple[RuntimeExecutionMode, ...]
    port_ids: tuple[str, ...]
    steps: tuple[MissionRehearsalStepRecord, ...]
    trace_payload_sha256: str
    achieved_feedback_sha256: str | None
    evidence_manifest_sha256: str | None
    zero_authority: bool
    hardware_accessed: bool
    hardware_commands_generated: int

    def __post_init__(self) -> None:
        for name in ("rehearsal_id", "mission_id", "runtime_id"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        _digest(self.spec_sha256, "spec_sha256")
        _digest(self.runtime_contract_sha256, "runtime_contract_sha256")
        _digest(self.trace_payload_sha256, "trace_payload_sha256")
        if self.achieved_feedback_sha256 is not None:
            _digest(
                self.achieved_feedback_sha256,
                "achieved_feedback_sha256",
            )
        if self.evidence_manifest_sha256 is not None:
            _digest(
                self.evidence_manifest_sha256,
                "evidence_manifest_sha256",
            )
        if not isinstance(self.execution_modes, tuple) or not self.execution_modes:
            raise MissionRehearsalError("execution_modes must be a non-empty tuple")
        if any(
            mode not in (RuntimeExecutionMode.VIRTUAL, RuntimeExecutionMode.REPLAY)
            for mode in self.execution_modes
        ):
            raise MissionRehearsalError(
                "a zero-authority rehearsal supports only virtual/replay modes"
            )
        if (
            not isinstance(self.port_ids, tuple)
            or not self.port_ids
            or len(self.port_ids) != len(set(self.port_ids))
        ):
            raise MissionRehearsalError("port_ids must be a unique non-empty tuple")
        for port_id in self.port_ids:
            _identifier(port_id, "port_id")
        if not isinstance(self.steps, tuple):
            raise MissionRehearsalError("steps must be an immutable tuple")
        if tuple(record.step for record in self.steps) != _STEP_ORDER:
            raise MissionRehearsalError(
                "report must contain every rehearsal step in canonical order"
            )
        if self.steps[0].status is not MissionRehearsalStepStatus.PASSED:
            raise MissionRehearsalError("initial runtime validation must pass")
        if self.steps[-1].status is not MissionRehearsalStepStatus.PASSED:
            raise MissionRehearsalError("final runtime validation must pass")
        seen_failure = False
        for record in self.steps:
            if record.status is MissionRehearsalStepStatus.SKIPPED and not seen_failure:
                raise MissionRehearsalError(
                    "a step cannot be skipped before an earlier failure"
                )
            if record.status is MissionRehearsalStepStatus.FAILED:
                seen_failure = True
        for step in (
            MissionRehearsalStep.EVIDENCE_APPEND,
            MissionRehearsalStep.STOP,
            MissionRehearsalStep.CLOSE,
            MissionRehearsalStep.EVIDENCE_FINALIZE,
        ):
            if self.step(step).status is MissionRehearsalStepStatus.SKIPPED:
                raise MissionRehearsalError(f"{step.value} must always be attempted")
        feedback_passed = (
            self.step(MissionRehearsalStep.ARM_FEEDBACK).status
            is MissionRehearsalStepStatus.PASSED
        )
        if feedback_passed != (self.achieved_feedback_sha256 is not None):
            raise MissionRehearsalError(
                "passed achieved feedback must carry exactly one binding hash"
            )
        if not isinstance(self.zero_authority, bool) or not self.zero_authority:
            raise MissionRehearsalError("report requires a zero-authority proof")
        if not isinstance(self.hardware_accessed, bool) or self.hardware_accessed:
            raise MissionRehearsalError("rehearsal cannot report hardware access")
        if (
            isinstance(self.hardware_commands_generated, bool)
            or not isinstance(self.hardware_commands_generated, int)
            or self.hardware_commands_generated != 0
        ):
            raise MissionRehearsalError(
                "rehearsal cannot report generated hardware commands"
            )

    def step(self, step: MissionRehearsalStep) -> MissionRehearsalStepRecord:
        for record in self.steps:
            if record.step is step:
                return record
        raise MissionRehearsalError(f"report has no {step.value} step")

    @property
    def primary_failure(self) -> MissionRehearsalStepRecord | None:
        return next(
            (
                record
                for record in self.steps
                if record.status is MissionRehearsalStepStatus.FAILED
            ),
            None,
        )

    @property
    def cleanup_succeeded(self) -> bool:
        return all(
            self.step(step).status is MissionRehearsalStepStatus.PASSED
            for step in (MissionRehearsalStep.STOP, MissionRehearsalStep.CLOSE)
        )

    @property
    def passed(self) -> bool:
        return all(
            record.status is MissionRehearsalStepStatus.PASSED
            for record in self.steps
        )

    @property
    def status(self) -> str:
        return (
            "ZERO_AUTHORITY_MISSION_REHEARSAL_PASS"
            if self.passed
            else "ZERO_AUTHORITY_MISSION_REHEARSAL_FAIL_CLOSED"
        )

    def _without_hash(self) -> dict[str, object]:
        failure = self.primary_failure
        return {
            "schema": ZERO_AUTHORITY_MISSION_REHEARSAL_SCHEMA,
            "status": self.status,
            "rehearsal_id": self.rehearsal_id,
            "mission_id": self.mission_id,
            "runtime_id": self.runtime_id,
            "spec_sha256": self.spec_sha256,
            "runtime_contract_sha256": self.runtime_contract_sha256,
            "execution_modes": [mode.value for mode in self.execution_modes],
            "port_ids": list(self.port_ids),
            "steps": [record.to_dict() for record in self.steps],
            "summary": {
                "passed": self.passed,
                "primary_failure_step": failure.step.value if failure else None,
                "primary_fault_code": failure.fault_code if failure else None,
                "cleanup_succeeded": self.cleanup_succeeded,
                "trace_payload_sha256": self.trace_payload_sha256,
                "achieved_feedback_sha256": self.achieved_feedback_sha256,
                "evidence_manifest_sha256": self.evidence_manifest_sha256,
            },
            "authority": {
                "zero_authority": self.zero_authority,
                "hardware_accessed": self.hardware_accessed,
                "hardware_commands_generated": self.hardware_commands_generated,
                "live_motion_authorized": False,
                "physical_contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_sha256": self.report_hash}


class _BoundaryFailure(RuntimeError):
    def __init__(self, fault_code: str) -> None:
        self.fault_code = _identifier(fault_code, "fault_code", maximum=128)
        super().__init__(self.fault_code)


ResultT = TypeVar("ResultT")


def _deadline_for(
    spec: ZeroAuthorityMissionRehearsalSpec[object, object],
    step: MissionRehearsalStep,
    now: RuntimeInstant,
) -> RuntimeDeadline:
    budget = 0 if spec.deadline_expiry_step is step else spec.deadline_budget_ticks
    return RuntimeDeadline(
        RuntimeInstant(
            now.clock_id,
            now.tick + budget,
            now.tick_period_ns,
        )
    )


def _validate_instant(
    instant: RuntimeInstant,
    *,
    started_at: RuntimeInstant,
    deadline: RuntimeDeadline,
    prefix: str,
) -> None:
    if (
        instant.clock_id != started_at.clock_id
        or instant.tick_period_ns != started_at.tick_period_ns
        or instant.clock_id != deadline.at.clock_id
        or instant.tick_period_ns != deadline.at.tick_period_ns
    ):
        raise _BoundaryFailure(f"{prefix}_CLOCK_MISMATCH")
    if instant.tick < started_at.tick:
        raise _BoundaryFailure(f"{prefix}_TIMESTAMP_REORDERED")
    if instant.tick > deadline.at.tick:
        raise _BoundaryFailure(f"{prefix}_DEADLINE_EXPIRED")


def _poll_cancellation(
    *,
    ports: MissionRuntimePorts[object, object, object, object, object],
    mission_id: str,
    operation_id: str,
    started_at: RuntimeInstant,
    deadline: RuntimeDeadline,
) -> None:
    status = ports.cancellation.poll(CancellationCheck(mission_id, operation_id))
    if not isinstance(status, CancellationStatus):
        raise _BoundaryFailure("CANCELLATION_RESULT_INVALID")
    if status.checkpoint_id != operation_id:
        raise _BoundaryFailure("CANCELLATION_CORRELATION_MISMATCH")
    _validate_instant(
        status.observed_at,
        started_at=started_at,
        deadline=deadline,
        prefix="CANCELLATION",
    )
    if status.cancelled:
        raise _BoundaryFailure("OPERATION_CANCELLED")


def _fault_code(exc: Exception) -> str:
    if isinstance(exc, (RuntimePortOperationError, _BoundaryFailure)):
        return exc.fault_code
    return "UNEXPECTED_PORT_EXCEPTION"


def _attempt(
    *,
    ports: MissionRuntimePorts[object, object, object, object, object],
    spec: ZeroAuthorityMissionRehearsalSpec[object, object],
    step: MissionRehearsalStep,
    invoke: Callable[[RuntimeDeadline], ResultT],
    validate: Callable[[ResultT, RuntimeInstant, RuntimeDeadline], None],
) -> tuple[MissionRehearsalStepRecord, ResultT | None]:
    operation_id = spec.operation_id(step)
    started_at = ports.clock.now()
    deadline = _deadline_for(spec, step, started_at)
    try:
        _poll_cancellation(
            ports=ports,
            mission_id=spec.mission_id,
            operation_id=operation_id,
            started_at=started_at,
            deadline=deadline,
        )
        result = invoke(deadline)
        validate(result, started_at, deadline)
        completed_at = ports.clock.now()
        _validate_instant(
            completed_at,
            started_at=started_at,
            deadline=deadline,
            prefix="BOUNDARY",
        )
        return (
            MissionRehearsalStepRecord(
                step,
                operation_id,
                MissionRehearsalStepStatus.PASSED,
                started_at,
                completed_at,
            ),
            result,
        )
    except Exception as exc:
        completed_at = ports.clock.now()
        return (
            MissionRehearsalStepRecord(
                step,
                operation_id,
                MissionRehearsalStepStatus.FAILED,
                started_at,
                completed_at,
                _fault_code(exc),
            ),
            None,
        )


def _skipped(
    ports: MissionRuntimePorts[object, object, object, object, object],
    spec: ZeroAuthorityMissionRehearsalSpec[object, object],
    step: MissionRehearsalStep,
    blocker: MissionRehearsalStep,
) -> MissionRehearsalStepRecord:
    now = ports.clock.now()
    return MissionRehearsalStepRecord(
        step,
        spec.operation_id(step),
        MissionRehearsalStepStatus.SKIPPED,
        now,
        now,
        f"BLOCKED_BY_{blocker.value}",
    )


def _result_instant(
    instant: RuntimeInstant,
    started_at: RuntimeInstant,
    deadline: RuntimeDeadline,
) -> None:
    _validate_instant(
        instant,
        started_at=started_at,
        deadline=deadline,
        prefix="RESULT",
    )


def _require(condition: bool, fault_code: str) -> None:
    if not condition:
        raise _BoundaryFailure(fault_code)


def run_zero_authority_mission_rehearsal(
    ports: MissionRuntimePorts[
        CommandT,
        FeedbackT,
        ObservationT,
        ContactT,
        OutcomeT,
    ],
    spec: ZeroAuthorityMissionRehearsalSpec[CommandT, ContactT],
) -> ZeroAuthorityMissionRehearsalReport:
    """Run one bounded mission entirely through validated runtime ports.

    Operational failures are evidence, not exceptions.  Contract/authority
    failures raise before a report is created because a zero-authority claim
    could not be proven.  The function never retries a failed port operation.
    """

    if not isinstance(spec, ZeroAuthorityMissionRehearsalSpec):
        raise TypeError("spec must be ZeroAuthorityMissionRehearsalSpec")

    # Structural typing makes this safe after validation; local aliases keep
    # the generic public signature while the orchestration helpers stay small.
    generic_ports = cast(
        MissionRuntimePorts[object, object, object, object, object],
        ports,
    )
    generic_spec = cast(
        ZeroAuthorityMissionRehearsalSpec[object, object],
        spec,
    )
    contract_before = validate_runtime_ports(generic_ports)
    contract_document = _contract_dict(contract_before)
    contract_sha256 = _stable_hash(contract_document)

    initial_now = generic_ports.clock.now()
    records: list[MissionRehearsalStepRecord] = [
        MissionRehearsalStepRecord(
            MissionRehearsalStep.VALIDATE_PORTS_INITIAL,
            generic_spec.operation_id(
                MissionRehearsalStep.VALIDATE_PORTS_INITIAL
            ),
            MissionRehearsalStepStatus.PASSED,
            initial_now,
            initial_now,
        )
    ]
    blocker: MissionRehearsalStep | None = None
    baseline_sequence: int | None = None
    achieved_feedback_sha256: str | None = None

    def core_attempt(
        step: MissionRehearsalStep,
        invoke: Callable[[RuntimeDeadline], object],
        validate: Callable[[object, RuntimeInstant, RuntimeDeadline], None],
    ) -> object | None:
        nonlocal blocker
        if blocker is not None:
            records.append(_skipped(generic_ports, generic_spec, step, blocker))
            return None
        record, result = _attempt(
            ports=generic_ports,
            spec=generic_spec,
            step=step,
            invoke=invoke,
            validate=validate,
        )
        records.append(record)
        if record.status is MissionRehearsalStepStatus.FAILED:
            blocker = step
        return result

    def validate_lifecycle(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
        *,
        operation_id: str,
        expected_state: str,
    ) -> None:
        _require(isinstance(value, LifecycleResult), "LIFECYCLE_RESULT_INVALID")
        assert isinstance(value, LifecycleResult)
        _require(
            value.operation_id == operation_id,
            "LIFECYCLE_CORRELATION_MISMATCH",
        )
        _result_instant(value.observed_at, started_at, deadline)
        _require(value.succeeded, value.fault_code or "LIFECYCLE_FAILED")
        _require(value.state == expected_state, "LIFECYCLE_STATE_MISMATCH")

    connect_id = generic_spec.operation_id(MissionRehearsalStep.CONNECT)
    core_attempt(
        MissionRehearsalStep.CONNECT,
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

    reference_id = generic_spec.operation_id(MissionRehearsalStep.REFERENCE)
    core_attempt(
        MissionRehearsalStep.REFERENCE,
        lambda deadline: generic_ports.arm_lifecycle.reference(
            LifecycleRequest(generic_spec.mission_id, reference_id, deadline),
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

    observation_id = generic_spec.operation_id(MissionRehearsalStep.OBSERVATION)

    def validate_observation(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, ObservationResult), "OBSERVATION_RESULT_INVALID")
        assert isinstance(value, ObservationResult)
        _require(
            value.observation_id == observation_id,
            "OBSERVATION_CORRELATION_MISMATCH",
        )
        _result_instant(value.observed_at, started_at, deadline)
        _require(value.valid, value.fault_code or "OBSERVATION_INVALID")

    core_attempt(
        MissionRehearsalStep.OBSERVATION,
        lambda deadline: generic_ports.observation.observe(
            ObservationRequest(
                generic_spec.mission_id,
                observation_id,
                generic_spec.action_index,
                generic_spec.observation_phase,
                deadline,
            ),
            generic_ports.cancellation,
        ),
        validate_observation,
    )

    execute_id = generic_spec.operation_id(MissionRehearsalStep.ARM_EXECUTE)

    def validate_execution(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, ArmExecutionResult), "ARM_RESULT_INVALID")
        assert isinstance(value, ArmExecutionResult)
        _require(
            value.operation_id == execute_id,
            "ARM_EXECUTION_CORRELATION_MISMATCH",
        )
        _result_instant(value.observed_at, started_at, deadline)
        _require(
            value.accepted and value.completed,
            value.fault_code or "ARM_EXECUTION_INCOMPLETE",
        )

    core_attempt(
        MissionRehearsalStep.ARM_EXECUTE,
        lambda deadline: generic_ports.arm_execution.execute(
            ArmExecutionRequest(
                generic_spec.mission_id,
                execute_id,
                generic_spec.action_index,
                generic_spec.waypoint_sequence,
                generic_spec.arm_command.value,
                deadline,
            ),
            generic_ports.cancellation,
        ),
        validate_execution,
    )

    baseline_id = generic_spec.operation_id(
        MissionRehearsalStep.ARM_FEEDBACK_BASELINE
    )

    def validate_feedback_baseline(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, ArmFeedbackSample), "ARM_FEEDBACK_RESULT_INVALID")
        assert isinstance(value, ArmFeedbackSample)
        request = ArmFeedbackRequest(
            generic_spec.mission_id,
            baseline_id,
            generic_spec.action_index,
            deadline,
        )
        validate_arm_feedback_sample(request, value)
        _result_instant(value.observed_at, started_at, deadline)
        _require(
            value.feedback_binding_sha256 is not None,
            "ARM_FEEDBACK_BINDING_MISSING",
        )

    baseline = core_attempt(
        MissionRehearsalStep.ARM_FEEDBACK_BASELINE,
        lambda deadline: generic_ports.arm_feedback.read_feedback(
            ArmFeedbackRequest(
                generic_spec.mission_id,
                baseline_id,
                generic_spec.action_index,
                deadline,
            ),
            generic_ports.cancellation,
        ),
        validate_feedback_baseline,
    )
    if isinstance(baseline, ArmFeedbackSample):
        baseline_sequence = baseline.sequence

    feedback_id = generic_spec.operation_id(MissionRehearsalStep.ARM_FEEDBACK)

    def validate_feedback(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, ArmFeedbackSample), "ARM_FEEDBACK_RESULT_INVALID")
        assert isinstance(value, ArmFeedbackSample)
        request = ArmFeedbackRequest(
            generic_spec.mission_id,
            feedback_id,
            generic_spec.action_index,
            deadline,
        )
        validate_arm_feedback_sample(
            request,
            value,
            previous_sequence=baseline_sequence,
        )
        _result_instant(value.observed_at, started_at, deadline)
        _require(
            value.feedback_binding_sha256 is not None,
            "ARM_FEEDBACK_BINDING_MISSING",
        )

    achieved_feedback = core_attempt(
        MissionRehearsalStep.ARM_FEEDBACK,
        lambda deadline: generic_ports.arm_feedback.read_feedback(
            ArmFeedbackRequest(
                generic_spec.mission_id,
                feedback_id,
                generic_spec.action_index,
                deadline,
            ),
            generic_ports.cancellation,
        ),
        validate_feedback,
    )
    if isinstance(achieved_feedback, ArmFeedbackSample):
        achieved_feedback_sha256 = achieved_feedback.feedback_binding_sha256

    contact_id = generic_spec.operation_id(MissionRehearsalStep.DEVICE_CONTACT)

    def validate_contact(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, DeviceContactResult), "CONTACT_RESULT_INVALID")
        assert isinstance(value, DeviceContactResult)
        _require(
            value.operation_id == contact_id,
            "CONTACT_CORRELATION_MISMATCH",
        )
        _result_instant(value.observed_at, started_at, deadline)
        _require(value.accepted, value.fault_code or "CONTACT_REJECTED")

    core_attempt(
        MissionRehearsalStep.DEVICE_CONTACT,
        lambda deadline: generic_ports.device_contact.apply_contact(
            DeviceContactRequest(
                generic_spec.mission_id,
                contact_id,
                generic_spec.action_index,
                generic_spec.device_contact.value,
                deadline,
            ),
            generic_ports.cancellation,
        ),
        validate_contact,
    )

    outcome_id = generic_spec.operation_id(
        MissionRehearsalStep.OUTCOME_OBSERVATION
    )

    def validate_outcome(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, OutcomeObservation), "OUTCOME_RESULT_INVALID")
        assert isinstance(value, OutcomeObservation)
        _require(
            value.checkpoint_id == outcome_id,
            "OUTCOME_CORRELATION_MISMATCH",
        )
        _result_instant(value.observed_at, started_at, deadline)
        _require(value.valid, value.fault_code or "OUTCOME_INVALID")

    core_attempt(
        MissionRehearsalStep.OUTCOME_OBSERVATION,
        lambda deadline: generic_ports.outcome_observer.observe_outcome(
            OutcomeRequest(
                generic_spec.mission_id,
                outcome_id,
                generic_spec.action_index,
                deadline,
            ),
            generic_ports.cancellation,
        ),
        validate_outcome,
    )

    trace_document = {
        "schema": f"{ZERO_AUTHORITY_MISSION_REHEARSAL_SCHEMA}.trace",
        "rehearsal_id": generic_spec.rehearsal_id,
        "mission_id": generic_spec.mission_id,
        "spec_sha256": generic_spec.definition_hash,
        "runtime_contract_sha256": contract_sha256,
        "achieved_feedback_sha256": achieved_feedback_sha256,
        "core_steps": [record.to_dict() for record in records],
    }
    trace_payload = _canonical_bytes(trace_document)
    append_id = generic_spec.operation_id(MissionRehearsalStep.EVIDENCE_APPEND)
    append_request = EvidenceWriteRequest.from_payload(
        mission_id=generic_spec.mission_id,
        record_id=append_id,
        role="runtime-port-rehearsal-trace",
        sequence=0,
        media_type="application/json",
        payload=trace_payload,
    )

    def validate_append(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(isinstance(value, EvidenceWriteResult), "EVIDENCE_RESULT_INVALID")
        assert isinstance(value, EvidenceWriteResult)
        _require(
            value.record_id == append_id,
            "EVIDENCE_APPEND_CORRELATION_MISMATCH",
        )
        _result_instant(value.committed_at, started_at, deadline)
        _require(
            value.payload_sha256 == append_request.payload_sha256,
            "EVIDENCE_APPEND_DIGEST_MISMATCH",
        )
        _require(
            value.size_bytes == len(append_request.payload),
            "EVIDENCE_APPEND_SIZE_MISMATCH",
        )
        _require(value.committed, value.fault_code or "EVIDENCE_APPEND_FAILED")

    append_record, append_result = _attempt(
        ports=generic_ports,
        spec=generic_spec,
        step=MissionRehearsalStep.EVIDENCE_APPEND,
        invoke=lambda _deadline: generic_ports.evidence.append(
            append_request,
            generic_ports.cancellation,
        ),
        validate=validate_append,
    )
    records.append(append_record)

    stop_id = generic_spec.operation_id(MissionRehearsalStep.STOP)
    stop_record, _ = _attempt(
        ports=generic_ports,
        spec=generic_spec,
        step=MissionRehearsalStep.STOP,
        invoke=lambda deadline: generic_ports.arm_lifecycle.stop(
            LifecycleRequest(generic_spec.mission_id, stop_id, deadline),
            generic_ports.cancellation,
        ),
        validate=lambda value, started, deadline: validate_lifecycle(
            value,
            started,
            deadline,
            operation_id=stop_id,
            expected_state="STOPPED",
        ),
    )
    records.append(stop_record)

    close_id = generic_spec.operation_id(MissionRehearsalStep.CLOSE)
    close_record, _ = _attempt(
        ports=generic_ports,
        spec=generic_spec,
        step=MissionRehearsalStep.CLOSE,
        invoke=lambda deadline: generic_ports.arm_lifecycle.close(
            LifecycleRequest(generic_spec.mission_id, close_id, deadline),
            generic_ports.cancellation,
        ),
        validate=lambda value, started, deadline: validate_lifecycle(
            value,
            started,
            deadline,
            operation_id=close_id,
            expected_state="CLOSED",
        ),
    )
    records.append(close_record)

    expected_record_ids = (
        (append_id,)
        if isinstance(append_result, EvidenceWriteResult)
        and append_record.status is MissionRehearsalStepStatus.PASSED
        else ()
    )
    terminal_status = (
        "PASS"
        if all(
            record.status is MissionRehearsalStepStatus.PASSED
            for record in records
        )
        else "FAIL_CLOSED"
    )
    finalize_id = generic_spec.operation_id(MissionRehearsalStep.EVIDENCE_FINALIZE)
    finalize_request = EvidenceFinalizeRequest(
        generic_spec.mission_id,
        terminal_status,
        expected_record_ids,
    )

    def validate_finalize(
        value: object,
        started_at: RuntimeInstant,
        deadline: RuntimeDeadline,
    ) -> None:
        _require(
            isinstance(value, EvidenceFinalizeResult),
            "EVIDENCE_FINALIZE_RESULT_INVALID",
        )
        assert isinstance(value, EvidenceFinalizeResult)
        _result_instant(value.committed_at, started_at, deadline)
        _require(
            value.record_count == len(expected_record_ids),
            "EVIDENCE_FINALIZE_COUNT_MISMATCH",
        )
        _require(
            value.committed,
            value.fault_code or "EVIDENCE_FINALIZE_FAILED",
        )

    finalize_record, finalize_result = _attempt(
        ports=generic_ports,
        spec=generic_spec,
        step=MissionRehearsalStep.EVIDENCE_FINALIZE,
        invoke=lambda _deadline: generic_ports.evidence.finalize(
            finalize_request,
            generic_ports.cancellation,
        ),
        validate=validate_finalize,
    )
    records.append(finalize_record)

    contract_after = validate_runtime_ports(generic_ports)
    if _contract_dict(contract_after) != contract_document:
        raise MissionRehearsalError(
            "runtime authority/identity metadata changed during rehearsal"
        )
    final_now = generic_ports.clock.now()
    records.append(
        MissionRehearsalStepRecord(
            MissionRehearsalStep.VALIDATE_PORTS_FINAL,
            generic_spec.operation_id(MissionRehearsalStep.VALIDATE_PORTS_FINAL),
            MissionRehearsalStepStatus.PASSED,
            final_now,
            final_now,
        )
    )
    manifest_sha256 = (
        finalize_result.manifest_sha256
        if isinstance(finalize_result, EvidenceFinalizeResult)
        else None
    )
    return ZeroAuthorityMissionRehearsalReport(
        rehearsal_id=generic_spec.rehearsal_id,
        mission_id=generic_spec.mission_id,
        runtime_id=contract_before.runtime_id,
        spec_sha256=generic_spec.definition_hash,
        runtime_contract_sha256=contract_sha256,
        execution_modes=contract_before.execution_modes,
        port_ids=contract_before.unique_port_ids,
        steps=tuple(records),
        trace_payload_sha256=append_request.payload_sha256,
        achieved_feedback_sha256=achieved_feedback_sha256,
        evidence_manifest_sha256=manifest_sha256,
        zero_authority=contract_before.zero_authority,
        hardware_accessed=contract_before.hardware_accessed,
        hardware_commands_generated=contract_before.hardware_commands_generated,
    )


__all__ = [
    "ZERO_AUTHORITY_MISSION_REHEARSAL_SCHEMA",
    "ZERO_AUTHORITY_MISSION_REHEARSAL_SPEC_SCHEMA",
    "HashBoundPortValue",
    "MissionRehearsalError",
    "MissionRehearsalStep",
    "MissionRehearsalStepRecord",
    "MissionRehearsalStepStatus",
    "ZeroAuthorityMissionRehearsalReport",
    "ZeroAuthorityMissionRehearsalSpec",
    "run_zero_authority_mission_rehearsal",
]
