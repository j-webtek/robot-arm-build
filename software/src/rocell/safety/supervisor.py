"""State-aware preflight evaluation and permit issuance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rocell.calibration.artifacts import CalibrationResolution
from rocell.rc03.build_snapshot import BuildSnapshot, Capability, assess_capability

from .interlocks import InterlockSnapshot
from .permit import FeedbackPermit, MotionPermit
from .preflight import PreflightReport, RuntimeStatus, evaluate_preflight
from .state_machine import SafetyState, SafetyStateMachine


class AuthorizationError(PermissionError):
    """The current build, calibration, interlock, or state cannot issue a permit."""


@dataclass(frozen=True, slots=True)
class _EvaluationContext:
    """Immutable inputs retained only long enough to recheck authorization."""

    calibrations: CalibrationResolution | None
    interlocks: InterlockSnapshot | None
    runtime: RuntimeStatus | None


class SafetySupervisor:
    """Issue single-use permits only from fresh reports evaluated by this instance."""

    def __init__(self, snapshot: BuildSnapshot) -> None:
        self.snapshot = snapshot
        self.state_machine = SafetyStateMachine()
        self._active_permit: MotionPermit | None = None
        self._active_feedback_permit: FeedbackPermit | None = None
        self._pending_report: PreflightReport | None = None
        self._pending_context: _EvaluationContext | None = None

    def evaluate(
        self,
        capability: Capability,
        *,
        plan_hash: str,
        calibrations: CalibrationResolution | None = None,
        interlocks: InterlockSnapshot | None = None,
        runtime: RuntimeStatus | None = None,
        now_monotonic: float | None = None,
    ) -> PreflightReport:
        report = evaluate_preflight(
            capability,
            self.snapshot,
            plan_hash=plan_hash,
            calibrations=calibrations,
            interlocks=interlocks,
            runtime=runtime,
            now_monotonic=now_monotonic,
        )
        # Only the most recent report from this supervisor may be consumed.
        # Retaining the immutable inputs lets authorize() check freshness again
        # instead of trusting a once-true result at the motion boundary.
        self._pending_report = report
        self._pending_context = _EvaluationContext(calibrations, interlocks, runtime)
        return report

    def authorize(
        self,
        report: PreflightReport,
        *,
        goals: Iterable[object],
        ttl_s: float = 2.0,
        now_monotonic: float | None = None,
    ) -> MotionPermit:
        if report is not self._pending_report or self._pending_context is None:
            raise AuthorizationError(
                "Preflight report was not issued by this supervisor or is no longer current"
            )
        context = self._pending_context
        # A report is a single-use authorization input even when permit creation
        # later fails; callers must evaluate current conditions again.
        self._pending_report = None
        self._pending_context = None
        if report.snapshot_hash != self.snapshot.snapshot_hash:
            raise AuthorizationError("Preflight report belongs to another build snapshot")
        if not report.allowed:
            raise AuthorizationError("Preflight is blocked: " + "; ".join(report.blockers))
        if report.capability not in (
            Capability.EMPTY_CELL_MOTION,
            Capability.KEYBOARD_CONTACT,
            Capability.PHONE_CONTACT,
        ):
            raise AuthorizationError(
                f"Capability {report.capability.value} cannot issue a motion permit"
            )
        if self.state_machine.state is not SafetyState.ARMED:
            raise AuthorizationError("Safety state must be ARMED before issuing motion")
        current = evaluate_preflight(
            report.capability,
            self.snapshot,
            plan_hash=report.plan_hash,
            calibrations=context.calibrations,
            interlocks=context.interlocks,
            runtime=context.runtime,
            now_monotonic=now_monotonic,
        )
        if not current.allowed:
            raise AuthorizationError(
                "Preflight became blocked before permit issuance: "
                + "; ".join(current.blockers)
            )
        if current != report:
            raise AuthorizationError("Preflight conditions changed before permit issuance")
        permit = MotionPermit._issue(
            capability=report.capability,
            snapshot_hash=report.snapshot_hash,
            plan_hash=report.plan_hash,
            goals=goals,
            ttl_s=ttl_s,
            now_monotonic=now_monotonic,
        )
        if self._active_permit is not None:
            self._active_permit.revoke()
        self._active_permit = permit
        return permit

    def authorize_feedback(
        self,
        *,
        ttl_s: float = 5.0,
        now_monotonic: float | None = None,
    ) -> FeedbackPermit:
        """Issue one T=105 capability only when this build may power the arm.

        Feedback does not advance the motion state machine, but it writes a
        request to a powered controller. Reassessing ARM_FEEDBACK here keeps the
        build-power decision inside the same authority that issues the token.
        """

        assessment = assess_capability(self.snapshot, Capability.ARM_FEEDBACK)
        if not assessment.allowed:
            raise AuthorizationError(
                "Arm feedback is blocked: " + "; ".join(assessment.reasons)
            )
        permit = FeedbackPermit._issue(
            snapshot_hash=assessment.snapshot_hash,
            ttl_s=ttl_s,
            now_monotonic=now_monotonic,
        )
        if self._active_feedback_permit is not None:
            self._active_feedback_permit.revoke()
        self._active_feedback_permit = permit
        return permit

    def fault(self) -> None:
        self._pending_report = None
        self._pending_context = None
        if self._active_permit is not None:
            self._active_permit.revoke()
            self._active_permit = None
        if self._active_feedback_permit is not None:
            self._active_feedback_permit.revoke()
            self._active_feedback_permit = None
        self.state_machine.fault()

    def restart(self) -> None:
        self._pending_report = None
        self._pending_context = None
        if self._active_permit is not None:
            self._active_permit.revoke()
            self._active_permit = None
        if self._active_feedback_permit is not None:
            self._active_feedback_permit.revoke()
            self._active_feedback_permit = None
        self.state_machine.restart()
