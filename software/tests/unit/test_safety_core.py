from __future__ import annotations

import time

import pytest

from rocell.calibration.artifacts import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationResolution,
)
from rocell.arm import (
    CartesianGoal,
    MotionNotPermittedError,
    ReplayTransport,
    RoArmM3,
    SerialTransport,
)
from rocell.rc03.build_snapshot import Capability
from rocell.safety.faults import FaultCode
from rocell.safety.interlocks import HealthState, InterlockSnapshot
from rocell.safety.permit import (
    FeedbackPermit,
    FeedbackPermitError,
    MotionPermit,
    MotionPermitError,
)
from rocell.safety.preflight import (
    PreflightCheck,
    PreflightReport,
    RuntimeStatus,
    evaluate_preflight,
)
from rocell.safety.state_machine import SafetyState, SafetyStateMachine, StateTransitionError
from rocell.safety.supervisor import AuthorizationError, SafetySupervisor


def _valid_calibrations() -> CalibrationResolution:
    return CalibrationResolution(
        {
            "required": ArtifactAssessment(
                "required", ArtifactState.VALID, "a" * 64, ()
            )
        }
    )


def _healthy_interlocks(now: float) -> InterlockSnapshot:
    return InterlockSnapshot(
        now,
        estop_chain=HealthState.PASS,
        board_anti_shift=HealthState.PASS,
        gravity_containment=HealthState.PASS,
        contact_guard=HealthState.PASS,
    )


def _healthy_runtime() -> RuntimeStatus:
    return RuntimeStatus(
        arm_connected=True,
        feedback_fresh=True,
        camera_live=True,
        camera_qualified=True,
        path_clear=True,
        device_verified=True,
        operator_armed=True,
    )


def _advance_to_armed(supervisor: SafetySupervisor) -> None:
    for state in (
        SafetyState.CONNECTED,
        SafetyState.REFERENCED,
        SafetyState.LOCALIZED,
        SafetyState.CALIBRATED,
        SafetyState.DRY_RUN_READY,
        SafetyState.ARMED,
    ):
        supervisor.state_machine.transition(state)


def test_current_blocked_snapshot_cannot_issue_motion(blocked_snapshot: object) -> None:
    supervisor = SafetySupervisor(blocked_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.KEYBOARD_CONTACT,
        plan_hash="p" * 64,
        now_monotonic=10.0,
    )
    assert not report.allowed
    assert any("ROBOT_POWER_NOT_RELEASED" in blocker for blocker in report.blockers)
    with pytest.raises(AuthorizationError):
        supervisor.authorize(report, goals=[{"T": 104}], now_monotonic=10.0)


def test_current_blocked_snapshot_cannot_issue_feedback_capability(
    blocked_snapshot: object,
) -> None:
    supervisor = SafetySupervisor(blocked_snapshot)  # type: ignore[arg-type]
    with pytest.raises(AuthorizationError, match="ROBOT_POWER_NOT_RELEASED"):
        supervisor.authorize_feedback(now_monotonic=10.0)


def test_preflight_report_cannot_be_forged_with_vacuous_empty_checks(
    blocked_snapshot: object,
) -> None:
    snapshot = blocked_snapshot  # keep the fixture's concrete type assertion local
    with pytest.raises(ValueError, match="only be issued"):
        PreflightReport(
            object(),
            Capability.EMPTY_CELL_MOTION,
            snapshot.snapshot_hash,  # type: ignore[attr-defined]
            "p" * 64,
            (),
        )


def test_supervisor_rejects_report_issued_outside_its_evaluate_boundary(
    released_snapshot: object,
) -> None:
    now = 20.0
    report = evaluate_preflight(
        Capability.EMPTY_CELL_MOTION,
        released_snapshot,  # type: ignore[arg-type]
        plan_hash="p" * 64,
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    assert report.allowed
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    _advance_to_armed(supervisor)
    with pytest.raises(AuthorizationError, match="not issued by this supervisor"):
        supervisor.authorize(report, goals=[{"T": 104}], now_monotonic=now)


def test_authorize_rechecks_interlock_freshness_and_consumes_report(
    released_snapshot: object,
) -> None:
    evaluated_at = 30.0
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION,
        plan_hash="p" * 64,
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(evaluated_at),
        runtime=_healthy_runtime(),
        now_monotonic=evaluated_at,
    )
    _advance_to_armed(supervisor)
    with pytest.raises(AuthorizationError, match="became blocked"):
        supervisor.authorize(
            report,
            goals=[{"T": 104}],
            now_monotonic=evaluated_at + 0.51,
        )
    with pytest.raises(AuthorizationError, match="no longer current"):
        supervisor.authorize(
            report,
            goals=[{"T": 104}],
            now_monotonic=evaluated_at,
        )


def test_empty_calibration_resolution_never_satisfies_motion_preflight(
    released_snapshot: object,
) -> None:
    now = 40.0
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION,
        plan_hash="p" * 64,
        calibrations=CalibrationResolution({}),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    assert not report.allowed
    assert any(
        check.fault_code is FaultCode.CALIBRATION_INVALID for check in report.checks
    )


def test_digital_and_simulated_preflight_ignore_physical_holds(blocked_snapshot: object) -> None:
    supervisor = SafetySupervisor(blocked_snapshot)  # type: ignore[arg-type]
    assert supervisor.evaluate(Capability.DIGITAL_PLAN, plan_hash="x").allowed
    assert supervisor.evaluate(Capability.SIMULATED_DRY_RUN, plan_hash="x").allowed


def test_released_contact_requires_runtime_interlocks_and_calibration(released_snapshot: object) -> None:
    now = 100.0
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    denied = supervisor.evaluate(
        Capability.PHONE_CONTACT,
        plan_hash="p" * 64,
        now_monotonic=now,
    )
    assert not denied.allowed
    allowed = supervisor.evaluate(
        Capability.PHONE_CONTACT,
        plan_hash="p" * 64,
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    assert allowed.allowed


def test_motion_permit_is_exact_consumable_and_revocable(released_snapshot: object) -> None:
    now = time.monotonic()
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION,
        plan_hash="p" * 64,
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    assert report.allowed
    _advance_to_armed(supervisor)
    goal = {"T": 104, "x": 1, "y": 2, "z": 3, "t": 0, "r": 0, "g": 0, "spd": 0.1}
    permit = supervisor.authorize(report, goals=[goal], ttl_s=5.0, now_monotonic=now)
    assert permit.allows(goal, now_monotonic=now + 1)
    assert not permit.allows(goal, now_monotonic=now + 1)
    permit.revoke()
    assert permit.revoked


def test_arm_client_accepts_only_supervisor_permit_and_consumes_exact_goals(
    released_snapshot: object,
) -> None:
    now = time.monotonic()
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION,
        plan_hash="p" * 64,
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    assert report.allowed
    _advance_to_armed(supervisor)
    allowed = CartesianGoal(1, 2, 3, 0.1, 0.0, 3.14, 0.25)
    different = CartesianGoal(4, 5, 6, 0.2, 0.0, 3.14, 0.25)
    permit = supervisor.authorize(report, goals=[allowed], ttl_s=5.0, now_monotonic=now)
    transport = ReplayTransport()
    client = RoArmM3(transport, permit_motion=permit)

    with pytest.raises(MotionNotPermittedError):
        client.move_cartesian(different)
    assert transport.sent_lines == ()

    client.move_cartesian(allowed)
    assert transport.sent_messages == (allowed.to_message(),)
    with pytest.raises(MotionNotPermittedError):
        client.move_cartesian(allowed)
    assert len(transport.sent_lines) == 1


def test_motion_permit_cannot_be_constructed_directly() -> None:
    with pytest.raises(MotionPermitError):
        MotionPermit(
            _issuer=object(),
            capability=Capability.EMPTY_CELL_MOTION,
            snapshot_hash="s",
            plan_hash="p",
            allowed_goal_hashes=("a" * 64,),
            expires_at_monotonic=1.0,
        )


@pytest.mark.parametrize('clock', [float('nan'), float('inf'), -float('inf'), True, '100', 10**1000],
                         ids=['nan', 'infinity', 'negative-infinity', 'bool', 'string', 'overflow'])
def test_invalid_clock_cannot_consume_supervisor_motion_permit(released_snapshot, clock):
    now = time.monotonic()
    supervisor = SafetySupervisor(released_snapshot)
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION, plan_hash='p' * 64,
        calibrations=_valid_calibrations(), interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(), now_monotonic=now)
    _advance_to_armed(supervisor)
    goal = CartesianGoal(1, 2, 3, .1, 0, 3.14, .25)
    permit = supervisor.authorize(report, goals=[goal], ttl_s=5, now_monotonic=now)
    assert permit.allows(goal, now_monotonic=clock) is False
    assert permit.remaining_uses == 1
    # Invalid inspection did not consume authority; the final replay boundary
    # still consumes it exactly once using a real monotonic clock.
    replay = ReplayTransport()
    client = RoArmM3(replay, permit_motion=permit)
    client.move_cartesian(goal)
    assert len(replay.sent_lines) == 1
    with pytest.raises(MotionNotPermittedError):
        client.move_cartesian(goal)


@pytest.mark.parametrize('clock', [float('nan'), float('inf'), True, '100', 10**1000],
                         ids=['nan', 'infinity', 'bool', 'string', 'overflow'])
def test_feedback_clock_rejects_invalid_issue_and_consume(clock):
    with pytest.raises(FeedbackPermitError):
        FeedbackPermit._issue(snapshot_hash='s' * 64, ttl_s=5, now_monotonic=clock)
    permit = FeedbackPermit._issue(snapshot_hash='s' * 64, ttl_s=5, now_monotonic=100)
    assert permit.consume(now_monotonic=clock) is False
    assert not permit.consumed
    assert permit.consume(now_monotonic=101)


@pytest.mark.parametrize('clock', [float('nan'), float('inf'), True, '100', 10**1000],
                         ids=['nan', 'infinity', 'bool', 'string', 'overflow'])
def test_motion_clock_rejects_invalid_issuance(clock):
    with pytest.raises(MotionPermitError):
        MotionPermit._issue(capability=Capability.EMPTY_CELL_MOTION,
                            snapshot_hash='s' * 64, plan_hash='p' * 64,
                            goals=[CartesianGoal(1, 2, 3, .1, 0, 3.14, .25)],
                            ttl_s=5, now_monotonic=clock)


def test_feedback_permit_cannot_be_constructed_directly() -> None:
    with pytest.raises(FeedbackPermitError):
        FeedbackPermit(
            _issuer=object(),
            snapshot_hash="s" * 64,
            expires_at_monotonic=10.0,
        )


def test_live_serial_motion_stays_blocked_with_valid_identity_permit(
    released_snapshot: object,
) -> None:
    now = time.monotonic()
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION,
        plan_hash="p" * 64,
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    _advance_to_armed(supervisor)
    goal = CartesianGoal(1, 2, 3, 0.1, 0.0, 1.0, 0.25)
    permit = supervisor.authorize(report, goals=[goal], now_monotonic=now)
    transport = SerialTransport("COM_NEVER_OPEN")

    with pytest.raises(MotionNotPermittedError, match="bounded-goal"):
        transport.send_motion(goal, permit)
    assert permit.remaining_uses == 1


def test_restart_revokes_active_feedback_permit(released_snapshot: object) -> None:
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    permit = supervisor.authorize_feedback(ttl_s=5.0)
    supervisor.restart()
    assert permit.revoked


def test_fault_and_restart_revoke_active_permit(released_snapshot: object) -> None:
    now = time.monotonic()
    supervisor = SafetySupervisor(released_snapshot)  # type: ignore[arg-type]
    report = supervisor.evaluate(
        Capability.EMPTY_CELL_MOTION,
        plan_hash="p",
        calibrations=_valid_calibrations(),
        interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(),
        now_monotonic=now,
    )
    _advance_to_armed(supervisor)
    permit = supervisor.authorize(report, goals=[{"T": 104}], ttl_s=5, now_monotonic=now)
    supervisor.restart()
    assert permit.revoked
    assert supervisor.state_machine.state is SafetyState.POWER_OFF


def test_state_machine_rejects_skips_and_never_resumes_armed() -> None:
    machine = SafetyStateMachine()
    with pytest.raises(StateTransitionError):
        machine.transition(SafetyState.ARMED)
    machine.transition(SafetyState.CONNECTED)
    machine.fault()
    assert machine.state is SafetyState.FAULT
    machine.restart()
    assert machine.state is SafetyState.POWER_OFF
