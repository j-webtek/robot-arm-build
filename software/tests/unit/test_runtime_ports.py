"""Shared contract tests for virtual, replay, and future physical adapters."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, dataclass, fields
import hashlib
from pathlib import Path

import pytest

from rocell.application.runtime_ports import (
    ArmExecutionPort,
    ArmExecutionRequest,
    ArmExecutionResult,
    ArmFeedbackPort,
    ArmFeedbackRequest,
    ArmFeedbackSample,
    ArmLifecyclePort,
    CancellationCheck,
    CancellationPort,
    CancellationStatus,
    ClockPort,
    DeviceContactPort,
    DeviceContactRequest,
    DeviceContactResult,
    EvidenceFinalizeRequest,
    EvidenceFinalizeResult,
    EvidenceSinkPort,
    EvidenceWriteRequest,
    EvidenceWriteResult,
    LifecycleRequest,
    LifecycleResult,
    MissionRuntimePorts,
    ObservationPort,
    ObservationRequest,
    ObservationResult,
    OutcomeObservation,
    OutcomeObserverPort,
    OutcomeRequest,
    RuntimeAuthority,
    RuntimeContractError,
    RuntimeDeadline,
    RuntimeExecutionMode,
    RuntimeInstant,
    RuntimePortMetadata,
    RuntimePortRole,
    validate_runtime_ports,
)


RUNTIME_ID = "runtime-contract-test"


def _metadata(
    port_id: str,
    *roles: RuntimePortRole,
    authority: RuntimeAuthority | None = None,
    runtime_id: str = RUNTIME_ID,
) -> RuntimePortMetadata:
    return RuntimePortMetadata(
        runtime_id=runtime_id,
        port_id=port_id,
        implementation_id=f"test.{port_id}.v1",
        roles=tuple(roles),
        authority=authority or RuntimeAuthority.zero(),
    )


class _Clock:
    runtime_metadata = _metadata("clock", RuntimePortRole.CLOCK)

    def now(self) -> RuntimeInstant:
        return RuntimeInstant("test-clock", 10, tick_period_ns=1_000_000)


class _Cancellation:
    runtime_metadata = _metadata("cancel", RuntimePortRole.CANCELLATION)

    def poll(self, request: CancellationCheck) -> CancellationStatus:
        return CancellationStatus(request.checkpoint_id, _Clock().now(), False)


class _Arm:
    runtime_metadata = _metadata(
        "arm",
        RuntimePortRole.ARM_LIFECYCLE,
        RuntimePortRole.ARM_EXECUTION,
        RuntimePortRole.ARM_FEEDBACK,
    )

    def connect(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        cancellation.poll(CancellationCheck(request.mission_id, request.operation_id))
        return LifecycleResult(request.operation_id, "CONNECTED", _Clock().now(), True)

    def reference(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return LifecycleResult(request.operation_id, "REFERENCED", _Clock().now(), True)

    def stop(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return LifecycleResult(request.operation_id, "STOPPED", _Clock().now(), True)

    def close(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return LifecycleResult(request.operation_id, "CLOSED", _Clock().now(), True)

    def execute(
        self,
        request: ArmExecutionRequest[object],
        cancellation: CancellationPort,
    ) -> ArmExecutionResult[object]:
        return ArmExecutionResult(
            request.operation_id,
            _Clock().now(),
            accepted=True,
            completed=True,
            feedback={"achieved": request.command},
        )

    def read_feedback(
        self,
        request: ArmFeedbackRequest,
        cancellation: CancellationPort,
    ) -> ArmFeedbackSample[object]:
        return ArmFeedbackSample(
            sample_id=f"feedback-{request.operation_id}",
            observed_at=_Clock().now(),
            sequence=1,
            feedback={"joint": 0.0},
        )


class _Observation:
    runtime_metadata = _metadata("observation", RuntimePortRole.OBSERVATION)

    def observe(
        self,
        request: ObservationRequest,
        cancellation: CancellationPort,
    ) -> ObservationResult[object]:
        return ObservationResult(
            request.observation_id,
            _Clock().now(),
            sequence=1,
            observation={"frame_sha256": "0" * 64},
            valid=True,
        )


@dataclass(frozen=True, slots=True)
class _OpaqueContact:
    """Test-only stand-in proving this port does not own contact geometry."""

    sample_id: str


class _Device:
    runtime_metadata = _metadata("device", RuntimePortRole.DEVICE_CONTACT)

    def apply_contact(
        self,
        request: DeviceContactRequest[_OpaqueContact],
        cancellation: CancellationPort,
    ) -> DeviceContactResult:
        return DeviceContactResult(
            request.operation_id,
            _Clock().now(),
            accepted=True,
            activation_count=1,
            device_event_ids=(f"event-{request.contact.sample_id}",),
        )


class _Outcome:
    runtime_metadata = _metadata("outcome", RuntimePortRole.OUTCOME_OBSERVER)

    def observe_outcome(
        self,
        request: OutcomeRequest,
        cancellation: CancellationPort,
    ) -> OutcomeObservation[object]:
        return OutcomeObservation(
            request.checkpoint_id,
            _Clock().now(),
            sequence=1,
            outcome={"output_length": 1, "output_sha256": "1" * 64},
            valid=True,
        )


class _Evidence:
    runtime_metadata = _metadata("evidence", RuntimePortRole.EVIDENCE)

    def append(
        self,
        request: EvidenceWriteRequest,
        cancellation: CancellationPort,
    ) -> EvidenceWriteResult:
        return EvidenceWriteResult(
            request.record_id,
            _Clock().now(),
            request.payload_sha256,
            len(request.payload),
            committed=True,
        )

    def finalize(
        self,
        request: EvidenceFinalizeRequest,
        cancellation: CancellationPort,
    ) -> EvidenceFinalizeResult:
        digest = hashlib.sha256("|".join(request.expected_record_ids).encode()).hexdigest()
        return EvidenceFinalizeResult(
            manifest_id=f"manifest-{request.mission_id}",
            committed_at=_Clock().now(),
            manifest_sha256=digest,
            record_count=len(request.expected_record_ids),
            committed=True,
        )


def _ports(
    *,
    clock: object | None = None,
    arm: object | None = None,
    observation: object | None = None,
    device: object | None = None,
    outcome: object | None = None,
    cancellation: object | None = None,
    evidence: object | None = None,
) -> MissionRuntimePorts[object, object, object, _OpaqueContact, object]:
    typed_arm = arm or _Arm()
    return MissionRuntimePorts(
        clock=clock or _Clock(),  # type: ignore[arg-type]
        arm_lifecycle=typed_arm,  # type: ignore[arg-type]
        arm_execution=typed_arm,  # type: ignore[arg-type]
        arm_feedback=typed_arm,  # type: ignore[arg-type]
        observation=observation or _Observation(),  # type: ignore[arg-type]
        device_contact=device or _Device(),  # type: ignore[arg-type]
        outcome_observer=outcome or _Outcome(),  # type: ignore[arg-type]
        cancellation=cancellation or _Cancellation(),  # type: ignore[arg-type]
        evidence=evidence or _Evidence(),  # type: ignore[arg-type]
    )


def test_complete_runtime_bundle_passes_structural_zero_authority_contract() -> None:
    ports = _ports()

    report = validate_runtime_ports(ports)

    assert report.runtime_id == RUNTIME_ID
    assert report.zero_authority is True
    assert report.hardware_accessed is False
    assert report.hardware_commands_generated == 0
    assert report.execution_modes == (RuntimeExecutionMode.VIRTUAL,)
    assert report.validated_roles == tuple(RuntimePortRole)
    assert report.unique_port_ids == (
        "arm",
        "cancel",
        "clock",
        "device",
        "evidence",
        "observation",
        "outcome",
    )


def test_test_adapters_satisfy_each_runtime_checkable_protocol() -> None:
    arm = _Arm()
    assert isinstance(_Clock(), ClockPort)
    assert isinstance(_Cancellation(), CancellationPort)
    assert isinstance(arm, ArmLifecyclePort)
    assert isinstance(arm, ArmExecutionPort)
    assert isinstance(arm, ArmFeedbackPort)
    assert isinstance(_Observation(), ObservationPort)
    assert isinstance(_Device(), DeviceContactPort)
    assert isinstance(_Outcome(), OutcomeObserverPort)
    assert isinstance(_Evidence(), EvidenceSinkPort)


def test_contract_scaffold_exercises_correlated_calls_without_hardware_types() -> None:
    ports = _ports()
    cancellation = ports.cancellation
    connect = ports.arm_lifecycle.connect(
        LifecycleRequest("mission-1", "connect-1"), cancellation
    )
    execution = ports.arm_execution.execute(
        ArmExecutionRequest("mission-1", "move-1", 0, 0, (0.0,) * 5),
        cancellation,
    )
    feedback = ports.arm_feedback.read_feedback(
        ArmFeedbackRequest("mission-1", "sample-1", 0), cancellation
    )
    observed = ports.observation.observe(
        ObservationRequest("mission-1", "image-1", 0, "VISION_CORRECT"),
        cancellation,
    )
    contact = ports.device_contact.apply_contact(
        DeviceContactRequest("mission-1", "contact-1", 0, _OpaqueContact("c1")),
        cancellation,
    )
    outcome = ports.outcome_observer.observe_outcome(
        OutcomeRequest("mission-1", "verify-1", 0), cancellation
    )
    write_request = EvidenceWriteRequest.from_payload(
        mission_id="mission-1",
        record_id="record-1",
        role="observation",
        sequence=0,
        media_type="application/json",
        payload=b"{}",
    )
    written = ports.evidence.append(write_request, cancellation)
    finalized = ports.evidence.finalize(
        EvidenceFinalizeRequest("mission-1", "COMPLETE", ("record-1",)),
        cancellation,
    )

    assert connect.state == "CONNECTED"
    assert execution.completed is True
    assert feedback.sequence == 1
    assert observed.valid is True
    assert contact.device_event_ids == ("event-c1",)
    assert outcome.valid is True
    assert written.committed is True
    assert finalized.record_count == 1


def test_requests_are_frozen_and_outcome_observer_has_no_expected_answer_fields() -> None:
    request = OutcomeRequest("mission-1", "check-1", 0)
    with pytest.raises(FrozenInstanceError):
        request.action_index = 2  # type: ignore[misc]

    forbidden_oracle_fields = {
        "expected",
        "expected_character",
        "expected_target",
        "planned_target",
        "target_id",
    }
    assert forbidden_oracle_fields.isdisjoint(
        field.name for field in fields(OutcomeRequest)
    )
    assert forbidden_oracle_fields.isdisjoint(
        field.name for field in fields(DeviceContactRequest)
    )


def test_evidence_envelope_rejects_mutable_or_tampered_payload() -> None:
    with pytest.raises(RuntimeContractError, match="immutable bytes"):
        EvidenceWriteRequest.from_payload(
            mission_id="m",
            record_id="r",
            role="event",
            sequence=0,
            media_type="application/json",
            payload=bytearray(b"{}"),  # type: ignore[arg-type]
        )

    with pytest.raises(RuntimeContractError, match="does not match"):
        EvidenceWriteRequest(
            "m",
            "r",
            "event",
            0,
            "application/json",
            b"{}",
            "0" * 64,
        )


def test_invalid_result_state_combinations_fail_closed() -> None:
    now = RuntimeInstant("clock", 0)
    with pytest.raises(RuntimeContractError, match="unaccepted"):
        ArmExecutionResult("move", now, accepted=False, completed=True)
    with pytest.raises(RuntimeContractError, match="incomplete"):
        ArmExecutionResult("move", now, accepted=True, completed=False)
    with pytest.raises(RuntimeContractError, match="achieved feedback"):
        ArmExecutionResult("move", now, accepted=True, completed=True)
    with pytest.raises(RuntimeContractError, match="failed result needs"):
        LifecycleResult("connect", "FAULTED", now, succeeded=False)
    with pytest.raises(RuntimeContractError, match="needs a fault"):
        ObservationResult("frame", now, 0, observation=None, valid=False)
    with pytest.raises(RuntimeContractError, match="reason"):
        CancellationStatus("checkpoint", now, cancelled=True, reason=None)
    with pytest.raises(RuntimeContractError, match="activation_count"):
        DeviceContactResult("contact", now, True, 2, ("event-1",))
    with pytest.raises(RuntimeContractError, match="rejected contact needs"):
        DeviceContactResult("contact", now, False, 0, ())
    with pytest.raises(RuntimeContractError, match="at least one"):
        DeviceContactResult("contact", now, True, 0, ())
    with pytest.raises(RuntimeContractError, match="SHA-256"):
        ArmFeedbackSample(
            "sample",
            now,
            0,
            object(),
            feedback_binding_sha256="not-a-digest",
        )


def test_validator_rejects_missing_member_wrong_role_and_mixed_runtime() -> None:
    class _NoClockMethod:
        runtime_metadata = _metadata("bad-clock", RuntimePortRole.CLOCK)

    with pytest.raises(RuntimeContractError, match="CLOCK runtime contract"):
        validate_runtime_ports(_ports(clock=_NoClockMethod()))

    class _WrongRoleClock(_Clock):
        runtime_metadata = _metadata("bad-role", RuntimePortRole.OBSERVATION)

    with pytest.raises(RuntimeContractError, match="does not declare role CLOCK"):
        validate_runtime_ports(_ports(clock=_WrongRoleClock()))

    class _OtherRuntimeClock(_Clock):
        runtime_metadata = _metadata(
            "other-clock", RuntimePortRole.CLOCK, runtime_id="other-runtime"
        )

    with pytest.raises(RuntimeContractError, match="same runtime_id"):
        validate_runtime_ports(_ports(clock=_OtherRuntimeClock()))


def test_zero_authority_default_rejects_physical_footprint_but_generic_mode_can_audit() -> None:
    physical = RuntimeAuthority(
        execution_mode=RuntimeExecutionMode.PHYSICAL,
        hardware_accessed=True,
        hardware_commands_generated=2,
        live_motion_authorized=False,
        physical_contact_authorized=False,
        physical_release_effect="NONE",
    )

    class _PhysicalClock(_Clock):
        runtime_metadata = _metadata(
            "physical-clock", RuntimePortRole.CLOCK, authority=physical
        )

    ports = _ports(clock=_PhysicalClock())
    with pytest.raises(RuntimeContractError, match="not zero-authority"):
        validate_runtime_ports(ports)

    report = validate_runtime_ports(ports, require_zero_authority=False)
    assert report.zero_authority is False
    assert report.hardware_accessed is True
    assert report.hardware_commands_generated == 2
    # Validation audits declarations; it never returns or manufactures a permit.
    assert not hasattr(report, "permit")
    assert not hasattr(report, "motion_token")


def test_deadlines_retain_explicit_clock_identity_and_unit() -> None:
    deadline = RuntimeDeadline(RuntimeInstant("monotonic", 12, tick_period_ns=1_000))
    request = LifecycleRequest("mission", "connect", deadline)
    assert request.deadline is not None
    assert request.deadline.at.clock_id == "monotonic"
    assert request.deadline.at.tick_period_ns == 1_000
    with pytest.raises(RuntimeContractError, match="tick_period_ns"):
        RuntimeInstant("monotonic", 12, tick_period_ns=0)


def test_runtime_contract_module_has_no_hardware_or_simulator_imports() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "rocell"
        / "application"
        / "runtime_ports.py"
    ).read_text(encoding="utf-8")
    imported_modules = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    )
    forbidden_prefixes = (
        "rocell.arm",
        "rocell.vision",
        "rocell.simulation",
        "serial",
        "cv2",
    )
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imported_modules
        for prefix in forbidden_prefixes
    )
