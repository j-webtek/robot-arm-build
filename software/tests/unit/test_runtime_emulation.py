from __future__ import annotations

import hashlib

import pytest

from rocell.application.runtime_emulation import (
    DeterministicControllerPort,
    DeterministicRuntimeClock,
    EmulatedControllerFeedback,
    InMemoryEvidenceSinkPort,
    RuntimeEmulationFault,
    RuntimeEmulationFaultScript,
    RuntimeEmulationFaultTrigger,
    make_deterministic_runtime_ports,
)
from rocell.application.runtime_ports import (
    ArmExecutionRequest,
    ArmFeedbackRequest,
    DeviceContactRequest,
    EvidenceFinalizeRequest,
    EvidenceWriteRequest,
    LifecycleRequest,
    ObservationRequest,
    OutcomeRequest,
    RuntimeDeadline,
    RuntimeExecutionMode,
    RuntimeInstant,
    RuntimePortOperationError,
    validate_runtime_ports,
)


def _connect_and_reference(ports: object) -> DeterministicControllerPort:
    bundle = ports
    controller = bundle.arm_lifecycle  # type: ignore[attr-defined]
    cancellation = bundle.cancellation  # type: ignore[attr-defined]
    assert isinstance(controller, DeterministicControllerPort)
    assert controller.connect(
        LifecycleRequest("mission", "connect"), cancellation
    ).succeeded
    assert controller.reference(
        LifecycleRequest("mission", "reference"), cancellation
    ).succeeded
    return controller


@pytest.mark.parametrize(
    "mode", (RuntimeExecutionMode.VIRTUAL, RuntimeExecutionMode.REPLAY)
)
def test_complete_zero_authority_bundle_exercises_every_port(mode: RuntimeExecutionMode) -> None:
    ports = make_deterministic_runtime_ports("emulated-runtime", execution_mode=mode)
    contract = validate_runtime_ports(ports)

    assert contract.execution_modes == (mode,)
    assert contract.zero_authority is True
    assert contract.hardware_accessed is False
    assert contract.hardware_commands_generated == 0

    controller = _connect_and_reference(ports)
    execution = ports.arm_execution.execute(
        ArmExecutionRequest("mission", "move-1", 0, 7, (0.1, 0.2, 0.3)),
        ports.cancellation,
    )
    assert execution.accepted and execution.completed
    assert isinstance(execution.feedback, EmulatedControllerFeedback)
    feedback = ports.arm_feedback.read_feedback(
        ArmFeedbackRequest("mission", "feedback-1", 0), ports.cancellation
    )
    assert feedback.request_operation_id == "feedback-1"
    assert feedback.action_index == 0
    assert feedback.stale is False
    assert feedback.feedback.source_operation_id == "move-1"
    assert feedback.feedback_binding_sha256 == feedback.feedback.feedback_hash
    assert any(
        value != 0.0 for value in feedback.feedback.achieved_deviation_units
    )
    assert feedback.feedback.achieved_state_sha256 != feedback.feedback.command_sha256

    observation = ports.observation.observe(
        ObservationRequest("mission", "image-1", 0, "HOVER"),
        ports.cancellation,
    )
    assert observation.valid is True
    contact = ports.device_contact.apply_contact(
        DeviceContactRequest("mission", "contact-1", 0, (1.0, 2.0, 3.0)),
        ports.cancellation,
    )
    assert contact.accepted is True
    assert contact.activation_count == 1
    outcome = ports.outcome_observer.observe_outcome(
        OutcomeRequest("mission", "verify-1", 0), ports.cancellation
    )
    assert outcome.valid is True

    write = EvidenceWriteRequest.from_payload(
        mission_id="mission",
        record_id="record-0",
        role="trace",
        sequence=0,
        media_type="application/json",
        payload=b"{}",
    )
    written = ports.evidence.append(write, ports.cancellation)
    assert written.committed is True
    finalized = ports.evidence.finalize(
        EvidenceFinalizeRequest("mission", "COMPLETE", ("record-0",)),
        ports.cancellation,
    )
    assert finalized.committed is True
    assert finalized.record_count == 1
    assert controller.close(
        LifecycleRequest("mission", "close"), ports.cancellation
    ).succeeded


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    (
        (RuntimeEmulationFault.STALE_FEEDBACK, "ARM_FEEDBACK_STALE"),
        (RuntimeEmulationFault.REORDERED_FEEDBACK, "ARM_FEEDBACK_REORDERED"),
        (
            RuntimeEmulationFault.FEEDBACK_CORRELATION_MISMATCH,
            "ARM_FEEDBACK_CORRELATION_MISMATCH",
        ),
    ),
)
def test_feedback_staleness_order_and_correlation_fail_closed(
    fault: RuntimeEmulationFault, expected_code: str
) -> None:
    ports = make_deterministic_runtime_ports(
        "feedback-fault-runtime",
        fault_triggers=(RuntimeEmulationFaultTrigger("feedback-2", fault),),
    )
    controller = _connect_and_reference(ports)
    ports.arm_execution.execute(
        ArmExecutionRequest("mission", "move-1", 0, 1, (0.0,) * 5),
        ports.cancellation,
    )
    first = ports.arm_feedback.read_feedback(
        ArmFeedbackRequest("mission", "feedback-1", 0), ports.cancellation
    )
    assert first.sequence == 1

    with pytest.raises(RuntimePortOperationError) as caught:
        ports.arm_feedback.read_feedback(
            ArmFeedbackRequest("mission", "feedback-2", 0), ports.cancellation
        )

    assert caught.value.fault_code == expected_code
    assert controller.state == "FAULTED"


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    (
        (RuntimeEmulationFault.TIMEOUT, "ARM_TIMEOUT"),
        (RuntimeEmulationFault.DISCONNECT, "ARM_DISCONNECT"),
        (RuntimeEmulationFault.RESET, "ARM_RESET"),
    ),
)
def test_controller_timeout_disconnect_and_reset_are_terminal_faults(
    fault: RuntimeEmulationFault, expected_code: str
) -> None:
    ports = make_deterministic_runtime_ports(
        "controller-fault-runtime",
        fault_triggers=(RuntimeEmulationFaultTrigger("move-1", fault),),
    )
    controller = _connect_and_reference(ports)

    with pytest.raises(RuntimePortOperationError) as caught:
        ports.arm_execution.execute(
            ArmExecutionRequest("mission", "move-1", 0, 1, (0.0,) * 5),
            ports.cancellation,
        )

    assert caught.value.fault_code == expected_code
    assert controller.state == "FAULTED"


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    (
        (RuntimeEmulationFault.CANCELLED, "OPERATION_CANCELLED"),
        (
            RuntimeEmulationFault.CANCELLATION_CORRELATION_MISMATCH,
            "CANCELLATION_CORRELATION_MISMATCH",
        ),
    ),
)
def test_cancellation_and_its_correlation_are_checked_before_state_change(
    fault: RuntimeEmulationFault, expected_code: str
) -> None:
    ports = make_deterministic_runtime_ports(
        "cancel-runtime",
        fault_triggers=(RuntimeEmulationFaultTrigger("connect", fault),),
    )
    controller = ports.arm_lifecycle
    assert isinstance(controller, DeterministicControllerPort)

    with pytest.raises(RuntimePortOperationError) as caught:
        controller.connect(
            LifecycleRequest("mission", "connect"), ports.cancellation
        )

    assert caught.value.fault_code == expected_code
    assert controller.state == "NEW"


def test_inclusive_deadline_rejects_late_completion_without_committing_state() -> None:
    ports = make_deterministic_runtime_ports("deadline-runtime")
    clock = ports.clock
    controller = ports.arm_lifecycle
    assert isinstance(clock, DeterministicRuntimeClock)
    assert isinstance(controller, DeterministicControllerPort)
    now = clock.now()
    deadline = RuntimeDeadline(
        RuntimeInstant(now.clock_id, now.tick, now.tick_period_ns)
    )

    with pytest.raises(RuntimePortOperationError) as caught:
        controller.connect(
            LifecycleRequest("mission", "connect", deadline), ports.cancellation
        )

    assert caught.value.fault_code == "DEADLINE_EXPIRED"
    assert controller.state == "NEW"


def test_deadline_clock_mismatch_fails_before_any_controller_state_change() -> None:
    ports = make_deterministic_runtime_ports("clock-mismatch-runtime")
    controller = ports.arm_lifecycle
    assert isinstance(controller, DeterministicControllerPort)

    with pytest.raises(RuntimePortOperationError) as caught:
        controller.connect(
            LifecycleRequest(
                "mission",
                "connect",
                RuntimeDeadline(RuntimeInstant("wrong-clock", 100, 1_000_000)),
            ),
            ports.cancellation,
        )

    assert caught.value.fault_code == "DEADLINE_CLOCK_MISMATCH"
    assert controller.state == "NEW"


def test_evidence_failures_are_nonmutating_and_exact_once() -> None:
    ports = make_deterministic_runtime_ports(
        "evidence-runtime",
        fault_triggers=(
            RuntimeEmulationFaultTrigger(
                "record-0", RuntimeEmulationFault.EVIDENCE_APPEND_FAILURE
            ),
            RuntimeEmulationFaultTrigger(
                "manifest-mission", RuntimeEmulationFault.EVIDENCE_FINALIZE_FAILURE
            ),
        ),
    )
    sink = ports.evidence
    assert isinstance(sink, InMemoryEvidenceSinkPort)
    request = EvidenceWriteRequest.from_payload(
        mission_id="mission",
        record_id="record-0",
        role="trace",
        sequence=0,
        media_type="application/octet-stream",
        payload=b"payload",
    )

    failed = sink.append(request, ports.cancellation)
    assert failed.committed is False
    assert failed.fault_code == "EMULATED_EVIDENCE_APPEND_FAILURE"
    assert sink.records == ()
    succeeded = sink.append(request, ports.cancellation)
    assert succeeded.committed is True
    assert len(sink.records) == 1
    assert sink.records[0].payload_sha256 == hashlib.sha256(b"payload").hexdigest()

    finalize_request = EvidenceFinalizeRequest(
        "mission", "COMPLETE", ("record-0",)
    )
    finalize_failed = sink.finalize(finalize_request, ports.cancellation)
    assert finalize_failed.committed is False
    assert finalize_failed.fault_code == "EMULATED_EVIDENCE_FINALIZE_FAILURE"
    finalize_succeeded = sink.finalize(finalize_request, ports.cancellation)
    assert finalize_succeeded.committed is True


@pytest.mark.parametrize(
    ("fault", "port_name", "operation"),
    (
        (RuntimeEmulationFault.OBSERVATION_FAILURE, "observation", "observe"),
        (RuntimeEmulationFault.CONTACT_FAILURE, "device_contact", "contact"),
        (RuntimeEmulationFault.OUTCOME_FAILURE, "outcome_observer", "outcome"),
    ),
)
def test_non_arm_port_failures_return_explicit_invalid_results(
    fault: RuntimeEmulationFault, port_name: str, operation: str
) -> None:
    ports = make_deterministic_runtime_ports(
        "peripheral-fault-runtime",
        fault_triggers=(RuntimeEmulationFaultTrigger(operation, fault),),
    )

    if port_name == "observation":
        observation_result = ports.observation.observe(
            ObservationRequest("mission", operation, 0, "HOVER"),
            ports.cancellation,
        )
        assert observation_result.valid is False
        assert observation_result.observation is None
    elif port_name == "device_contact":
        contact_result = ports.device_contact.apply_contact(
            DeviceContactRequest("mission", operation, 0, (0.0,) * 3),
            ports.cancellation,
        )
        assert contact_result.accepted is False
        assert contact_result.activation_count == 0
    else:
        outcome_result = ports.outcome_observer.observe_outcome(
            OutcomeRequest("mission", operation, 0), ports.cancellation
        )
        assert outcome_result.valid is False
        assert outcome_result.outcome is None


def test_fault_script_does_not_consume_at_the_wrong_boundary_or_twice() -> None:
    trigger = RuntimeEmulationFaultTrigger(
        "feedback", RuntimeEmulationFault.STALE_FEEDBACK
    )
    script = RuntimeEmulationFaultScript((trigger,))

    assert script.consume("feedback", (RuntimeEmulationFault.TIMEOUT,)) is None
    assert script.remaining == (trigger,)
    assert script.consume(
        "feedback", (RuntimeEmulationFault.STALE_FEEDBACK,)
    ) is RuntimeEmulationFault.STALE_FEEDBACK
    assert script.consume(
        "feedback", (RuntimeEmulationFault.STALE_FEEDBACK,)
    ) is None
    assert script.remaining == ()
    assert script.consumed == (trigger,)
