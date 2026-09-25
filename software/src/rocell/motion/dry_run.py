"""Deterministic semantic action expansion with no hardware imports."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from rocell.models.actions import ActionPlan, PressKey, TapPhoneTarget, VerifyPhoneState
from rocell.rc03.build_snapshot import BuildSnapshot, Capability
from rocell.safety.supervisor import SafetySupervisor

from .primitives import DryRunStep, MotionPhase


class DryRunError(RuntimeError):
    """A semantic dry-run was denied or could not be expanded safely."""


@dataclass(frozen=True, slots=True)
class DryRunReport:
    plan_hash: str
    snapshot_hash: str
    steps: tuple[DryRunStep, ...]
    schema: str = "rocell.dry_run.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "plan_hash": self.plan_hash,
            "snapshot_hash": self.snapshot_hash,
            "hardware_accessed": False,
            "steps": [step.to_dict() for step in self.steps],
        }

    @property
    def report_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class DryRunEngine:
    """Expand semantic actions into standard phases without producing poses."""

    _CONTACT_PHASES = (
        MotionPhase.TRANSIT,
        MotionPhase.HOVER,
        MotionPhase.VISION_CORRECT,
        MotionPhase.APPROACH,
        MotionPhase.CONTACT,
        MotionPhase.RETRACT,
    )

    def run(self, plan: ActionPlan, snapshot: BuildSnapshot) -> DryRunReport:
        if not isinstance(plan, ActionPlan):
            raise TypeError("plan must be an ActionPlan")
        if not isinstance(snapshot, BuildSnapshot):
            raise TypeError("snapshot must be a BuildSnapshot")
        preflight = SafetySupervisor(snapshot).evaluate(
            Capability.SIMULATED_DRY_RUN,
            plan_hash=plan.plan_hash,
        )
        if not preflight.allowed:
            raise DryRunError("Simulation preflight failed: " + "; ".join(preflight.blockers))

        steps: list[DryRunStep] = []

        def append(
            phase: MotionPhase,
            action_index: int | None,
            target: str | None,
        ) -> None:
            steps.append(DryRunStep(len(steps), phase, action_index, target))

        append(MotionPhase.PARK, None, None)
        for action_index, action in enumerate(plan.actions):
            if isinstance(action, PressKey):
                target = f"keyboard:{action.key_id}"
                for phase in self._CONTACT_PHASES:
                    append(phase, action_index, target)
                append(MotionPhase.VERIFY, action_index, target)
            elif isinstance(action, TapPhoneTarget):
                target = f"phone:{action.target_id}@{action.required_state}"
                for phase in self._CONTACT_PHASES:
                    append(phase, action_index, target)
                append(MotionPhase.VERIFY, action_index, target)
            elif isinstance(action, VerifyPhoneState):
                append(MotionPhase.VERIFY, action_index, f"phone_state:{action.state_id}")
            else:  # ActionPlan validation should make this unreachable.
                raise DryRunError(f"Unsupported action {type(action).__name__}")
        append(MotionPhase.PARK, None, None)
        append(MotionPhase.COMPLETE, None, None)
        return DryRunReport(plan.plan_hash, snapshot.snapshot_hash, tuple(steps))
