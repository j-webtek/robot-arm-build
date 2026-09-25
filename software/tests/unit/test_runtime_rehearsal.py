from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import cast

import pytest

from rocell.application.runtime_emulation import (
    DeterministicControllerPort,
    InMemoryEvidenceSinkPort,
    RuntimeEmulationFault,
    RuntimeEmulationFaultTrigger,
    make_deterministic_runtime_ports,
)
from rocell.application.runtime_ports import (
    RuntimeAuthority,
    RuntimeContractError,
    RuntimeExecutionMode,
    MissionRuntimePorts,
    RuntimePortMetadata,
)
from rocell.application.runtime_rehearsal import (
    ZERO_AUTHORITY_MISSION_REHEARSAL_SCHEMA,
    HashBoundPortValue,
    MissionRehearsalError,
    MissionRehearsalStep,
    MissionRehearsalStepStatus,
    ZeroAuthorityMissionRehearsalReport,
    ZeroAuthorityMissionRehearsalSpec,
    run_zero_authority_mission_rehearsal,
)


@dataclass(frozen=True, slots=True)
class _OpaqueContact:
    private_fixture_value: str


def _spec(
    *,
    deadline_expiry_step: MissionRehearsalStep | None = None,
) -> ZeroAuthorityMissionRehearsalSpec[dict[str, object], _OpaqueContact]:
    return ZeroAuthorityMissionRehearsalSpec(
        rehearsal_id="mission-through-ports",
        mission_id="mission-001",
        action_index=2,
        waypoint_sequence=7,
        arm_command=HashBoundPortValue(
            {"private_command": "DO_NOT_LEAK_COMMAND", "axis": [0.1, 0.2]},
            b"canonical-command-binding-v1",
        ),
        device_contact=HashBoundPortValue(
            _OpaqueContact("DO_NOT_LEAK_CONTACT"),
            b"canonical-contact-binding-v1",
        ),
        deadline_expiry_step=deadline_expiry_step,
    )


def _run(
    spec: ZeroAuthorityMissionRehearsalSpec[
        dict[str, object], _OpaqueContact
    ],
    *,
    mode: RuntimeExecutionMode = RuntimeExecutionMode.VIRTUAL,
    fault: RuntimeEmulationFault | None = None,
    fault_step: MissionRehearsalStep | None = None,
) -> tuple[object, ZeroAuthorityMissionRehearsalReport]:
    triggers: tuple[RuntimeEmulationFaultTrigger, ...] = ()
    if fault is not None:
        assert fault_step is not None
        triggers = (
            RuntimeEmulationFaultTrigger(spec.operation_id(fault_step), fault),
        )
    ports = make_deterministic_runtime_ports(
        "mission-through-ports-runtime",
        execution_mode=mode,
        fault_triggers=triggers,
    )
    typed_ports = cast(
        MissionRuntimePorts[
            dict[str, object],
            object,
            object,
            _OpaqueContact,
            object,
        ],
        ports,
    )
    return ports, run_zero_authority_mission_rehearsal(typed_ports, spec)


@pytest.mark.parametrize(
    "mode",
    (RuntimeExecutionMode.VIRTUAL, RuntimeExecutionMode.REPLAY),
)
def test_nominal_rehearsal_is_deterministic_hash_bound_and_zero_authority(
    mode: RuntimeExecutionMode,
) -> None:
    spec = _spec()
    ports_a, report_a = _run(spec, mode=mode)
    ports_b, report_b = _run(spec, mode=mode)

    assert report_a.passed is True
    assert report_a.status == "ZERO_AUTHORITY_MISSION_REHEARSAL_PASS"
    assert report_a.cleanup_succeeded is True
    assert report_a.primary_failure is None
    assert report_a.report_hash == report_b.report_hash
    assert report_a.to_dict() == report_b.to_dict()
    assert report_a.spec_sha256 == spec.definition_hash
    assert report_a.zero_authority is True
    assert report_a.hardware_accessed is False
    assert report_a.hardware_commands_generated == 0
    assert report_a.execution_modes == (mode,)
    assert all(
        record.status is MissionRehearsalStepStatus.PASSED
        for record in report_a.steps
    )

    serialized = json.dumps(report_a.to_dict(), sort_keys=True)
    assert report_a.to_dict()["schema"] == ZERO_AUTHORITY_MISSION_REHEARSAL_SCHEMA
    assert "DO_NOT_LEAK_COMMAND" not in serialized
    assert "DO_NOT_LEAK_CONTACT" not in serialized
    without_hash = dict(report_a.to_dict())
    del without_hash["report_sha256"]
    expected_hash = hashlib.sha256(
        json.dumps(
            without_hash,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert report_a.report_hash == expected_hash

    controller = ports_a.arm_lifecycle  # type: ignore[attr-defined]
    sink = ports_a.evidence  # type: ignore[attr-defined]
    assert isinstance(controller, DeterministicControllerPort)
    assert isinstance(sink, InMemoryEvidenceSinkPort)
    assert controller.state == "CLOSED"
    assert any(value != 0.0 for value in controller.latest_feedback.achieved_deviation_units)
    assert (
        controller.latest_feedback.achieved_state_sha256
        != controller.latest_feedback.command_sha256
    )
    assert report_a.achieved_feedback_sha256 == controller.latest_feedback.feedback_hash
    assert len(sink.records) == 1
    assert b"DO_NOT_LEAK_COMMAND" not in sink.records[0].payload
    assert b"DO_NOT_LEAK_CONTACT" not in sink.records[0].payload
    trace = json.loads(sink.records[0].payload)
    assert trace["achieved_feedback_sha256"] == report_a.achieved_feedback_sha256


def test_runtime_test_infrastructure_has_intentional_package_exports() -> None:
    import rocell.application as application
    import rocell.arm as arm

    assert application.run_zero_authority_mission_rehearsal is (
        run_zero_authority_mission_rehearsal
    )
    assert application.make_deterministic_runtime_ports is (
        make_deterministic_runtime_ports
    )
    assert application.HashBoundPortValue is HashBoundPortValue
    assert arm.DeterministicProtocolController.__name__ == (
        "DeterministicProtocolController"
    )
    assert arm.ProtocolEmulatorFault.__name__ == "ProtocolEmulatorFault"


def test_failure_report_replays_byte_canonically() -> None:
    spec = _spec()
    _, first = _run(
        spec,
        fault=RuntimeEmulationFault.REORDERED_FEEDBACK,
        fault_step=MissionRehearsalStep.ARM_FEEDBACK,
    )
    _, replay = _run(
        spec,
        fault=RuntimeEmulationFault.REORDERED_FEEDBACK,
        fault_step=MissionRehearsalStep.ARM_FEEDBACK,
    )

    assert first.passed is False
    assert first.to_dict() == replay.to_dict()
    assert first.report_hash == replay.report_hash


@pytest.mark.parametrize(
    ("step", "fault", "expected_fault_code"),
    (
        (
            MissionRehearsalStep.CONNECT,
            RuntimeEmulationFault.TIMEOUT,
            "ARM_TIMEOUT",
        ),
        (
            MissionRehearsalStep.REFERENCE,
            RuntimeEmulationFault.RESET,
            "ARM_RESET",
        ),
        (
            MissionRehearsalStep.OBSERVATION,
            RuntimeEmulationFault.OBSERVATION_FAILURE,
            "EMULATED_OBSERVATION_FAILURE",
        ),
        (
            MissionRehearsalStep.ARM_EXECUTE,
            RuntimeEmulationFault.DISCONNECT,
            "ARM_DISCONNECT",
        ),
        (
            MissionRehearsalStep.ARM_FEEDBACK_BASELINE,
            RuntimeEmulationFault.STALE_FEEDBACK,
            "ARM_FEEDBACK_STALE",
        ),
        (
            MissionRehearsalStep.ARM_FEEDBACK,
            RuntimeEmulationFault.STALE_FEEDBACK,
            "ARM_FEEDBACK_STALE",
        ),
        (
            MissionRehearsalStep.ARM_FEEDBACK,
            RuntimeEmulationFault.REORDERED_FEEDBACK,
            "ARM_FEEDBACK_REORDERED",
        ),
        (
            MissionRehearsalStep.ARM_FEEDBACK,
            RuntimeEmulationFault.FEEDBACK_CORRELATION_MISMATCH,
            "ARM_FEEDBACK_CORRELATION_MISMATCH",
        ),
        (
            MissionRehearsalStep.DEVICE_CONTACT,
            RuntimeEmulationFault.CONTACT_FAILURE,
            "EMULATED_CONTACT_FAILURE",
        ),
        (
            MissionRehearsalStep.OUTCOME_OBSERVATION,
            RuntimeEmulationFault.OUTCOME_FAILURE,
            "EMULATED_OUTCOME_FAILURE",
        ),
        (
            MissionRehearsalStep.EVIDENCE_APPEND,
            RuntimeEmulationFault.EVIDENCE_APPEND_FAILURE,
            "EMULATED_EVIDENCE_APPEND_FAILURE",
        ),
        (
            MissionRehearsalStep.STOP,
            RuntimeEmulationFault.TIMEOUT,
            "ARM_TIMEOUT",
        ),
        (
            MissionRehearsalStep.CLOSE,
            RuntimeEmulationFault.RESET,
            "ARM_RESET",
        ),
        (
            MissionRehearsalStep.EVIDENCE_FINALIZE,
            RuntimeEmulationFault.EVIDENCE_FINALIZE_FAILURE,
            "EMULATED_EVIDENCE_FINALIZE_FAILURE",
        ),
    ),
)
def test_every_emulated_boundary_failure_is_reported_and_cleanup_is_attempted(
    step: MissionRehearsalStep,
    fault: RuntimeEmulationFault,
    expected_fault_code: str,
) -> None:
    ports, report = _run(_spec(), fault=fault, fault_step=step)

    assert report.passed is False
    assert report.status == "ZERO_AUTHORITY_MISSION_REHEARSAL_FAIL_CLOSED"
    assert report.primary_failure is not None
    assert report.primary_failure.step is step
    assert report.primary_failure.fault_code == expected_fault_code
    assert report.step(step).status is MissionRehearsalStepStatus.FAILED
    assert report.step(MissionRehearsalStep.STOP).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )
    assert report.step(MissionRehearsalStep.CLOSE).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )
    assert report.step(MissionRehearsalStep.VALIDATE_PORTS_FINAL).status is (
        MissionRehearsalStepStatus.PASSED
    )
    assert report.zero_authority is True
    assert report.hardware_accessed is False
    assert report.hardware_commands_generated == 0

    controller = ports.arm_lifecycle  # type: ignore[attr-defined]
    assert isinstance(controller, DeterministicControllerPort)
    if step is not MissionRehearsalStep.CLOSE:
        assert controller.state == "CLOSED"


_CANCELLABLE_STEPS = (
    MissionRehearsalStep.CONNECT,
    MissionRehearsalStep.REFERENCE,
    MissionRehearsalStep.OBSERVATION,
    MissionRehearsalStep.ARM_EXECUTE,
    MissionRehearsalStep.ARM_FEEDBACK_BASELINE,
    MissionRehearsalStep.ARM_FEEDBACK,
    MissionRehearsalStep.DEVICE_CONTACT,
    MissionRehearsalStep.OUTCOME_OBSERVATION,
    MissionRehearsalStep.EVIDENCE_APPEND,
    MissionRehearsalStep.STOP,
    MissionRehearsalStep.CLOSE,
    MissionRehearsalStep.EVIDENCE_FINALIZE,
)


@pytest.mark.parametrize("step", _CANCELLABLE_STEPS)
def test_every_operational_boundary_has_a_correlated_cancellation_checkpoint(
    step: MissionRehearsalStep,
) -> None:
    _, report = _run(
        _spec(),
        fault=RuntimeEmulationFault.CANCELLED,
        fault_step=step,
    )

    assert report.primary_failure is not None
    assert report.primary_failure.step is step
    assert report.primary_failure.fault_code == "OPERATION_CANCELLED"
    assert report.step(MissionRehearsalStep.STOP).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )
    assert report.step(MissionRehearsalStep.CLOSE).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )


@pytest.mark.parametrize("step", _CANCELLABLE_STEPS)
def test_cancellation_correlation_mismatch_fails_the_exact_boundary(
    step: MissionRehearsalStep,
) -> None:
    _, report = _run(
        _spec(),
        fault=RuntimeEmulationFault.CANCELLATION_CORRELATION_MISMATCH,
        fault_step=step,
    )

    assert report.primary_failure is not None
    assert report.primary_failure.step is step
    assert report.primary_failure.fault_code == "CANCELLATION_CORRELATION_MISMATCH"
    assert report.step(MissionRehearsalStep.STOP).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )
    assert report.step(MissionRehearsalStep.CLOSE).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )


_DEADLINE_STEPS = (
    MissionRehearsalStep.CONNECT,
    MissionRehearsalStep.REFERENCE,
    MissionRehearsalStep.OBSERVATION,
    MissionRehearsalStep.ARM_EXECUTE,
    MissionRehearsalStep.ARM_FEEDBACK_BASELINE,
    MissionRehearsalStep.ARM_FEEDBACK,
    MissionRehearsalStep.DEVICE_CONTACT,
    MissionRehearsalStep.OUTCOME_OBSERVATION,
    MissionRehearsalStep.STOP,
    MissionRehearsalStep.CLOSE,
)


@pytest.mark.parametrize("step", _DEADLINE_STEPS)
def test_each_deadline_capable_boundary_fails_late_completion_and_still_cleans_up(
    step: MissionRehearsalStep,
) -> None:
    _, report = _run(_spec(deadline_expiry_step=step))

    assert report.primary_failure is not None
    assert report.primary_failure.step is step
    assert report.primary_failure.fault_code == "DEADLINE_EXPIRED"
    assert report.step(MissionRehearsalStep.STOP).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )
    assert report.step(MissionRehearsalStep.CLOSE).status is not (
        MissionRehearsalStepStatus.SKIPPED
    )


def test_initial_port_validation_rejects_authority_before_any_operation() -> None:
    spec = _spec()
    ports = make_deterministic_runtime_ports("authority-rejected-runtime")
    controller = ports.arm_lifecycle
    assert isinstance(controller, DeterministicControllerPort)
    original = controller.runtime_metadata
    controller.runtime_metadata = RuntimePortMetadata(
        runtime_id=original.runtime_id,
        port_id=original.port_id,
        implementation_id=original.implementation_id,
        roles=original.roles,
        authority=RuntimeAuthority(
            execution_mode=RuntimeExecutionMode.PHYSICAL,
            hardware_accessed=True,
            hardware_commands_generated=1,
            live_motion_authorized=False,
            physical_contact_authorized=False,
            physical_release_effect="NONE",
        ),
    )

    with pytest.raises(RuntimeContractError, match="not zero-authority"):
        typed_ports = cast(
            MissionRuntimePorts[
                dict[str, object],
                object,
                object,
                _OpaqueContact,
                object,
            ],
            ports,
        )
        run_zero_authority_mission_rehearsal(typed_ports, spec)

    assert controller.state == "NEW"
    assert controller.runtime_metadata.authority.hardware_commands_generated == 1


def test_spec_rejects_unbounded_bindings_and_non_deadline_steps() -> None:
    with pytest.raises(MissionRehearsalError, match="must not be empty"):
        HashBoundPortValue("value", b"")

    with pytest.raises(MissionRehearsalError, match="deadline-capable"):
        ZeroAuthorityMissionRehearsalSpec(
            rehearsal_id="invalid-deadline-target",
            mission_id="mission",
            action_index=0,
            waypoint_sequence=0,
            arm_command=HashBoundPortValue("command", b"command"),
            device_contact=HashBoundPortValue("contact", b"contact"),
            deadline_expiry_step=MissionRehearsalStep.EVIDENCE_APPEND,
        )
