"""Fail-closed, one-action-at-a-time coordination for model motion batches.

This is an orchestration boundary, not an executor.  It selects exactly one
proposal, requires a fresh observed arm state, evaluates the deterministic
planner gate, and then waits for independently supplied completion evidence.
It never encodes a controller command, opens a transport, retries an action, or
plans a successor from a predecessor's stale state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Callable, Mapping

from rocell.models import ModelMotionBatch, ModelMotionProposal

from .context import SimulationContext, revalidate_simulation_context
from .observed_planner_start_state import ObservedPlannerStartState


SCHEMA = "rocell.model_motion_sequence_snapshot.v1"
READY_PLANNER_STATUS = "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ModelMotionSequenceError(ValueError):
    """The ordered model-to-arm lifecycle is inconsistent or out of order."""


class SequencePhase(str, Enum):
    WAITING_FOR_FRESH_STATE = "WAITING_FOR_FRESH_STATE"
    READY_FOR_SINGLE_ACTION_EXECUTOR = "READY_FOR_SINGLE_ACTION_EXECUTOR"
    WAITING_FOR_EXECUTION_RESULT = "WAITING_FOR_EXECUTION_RESULT"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"


class ActionDisposition(str, Enum):
    VERIFIED_COMPLETED = "VERIFIED_COMPLETED"
    FAILED_BEFORE_DISPATCH = "FAILED_BEFORE_DISPATCH"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ModelMotionSequenceError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class VerifiedActionResult:
    """Evidence-only result supplied by a future single-action executor.

    The coordinator does not create this result.  A physical implementation
    must durably commit its dispatch boundary before writing to the arm and
    must derive outcome evidence independently of the requested command.
    """

    batch_sha256: str
    action_index: int
    proposal_sha256: str
    planner_gate_sha256: str
    execution_receipt_sha256: str
    outcome_evidence_sha256: str | None
    disposition: ActionDisposition

    def __post_init__(self) -> None:
        _digest(self.batch_sha256, "batch_sha256")
        _digest(self.proposal_sha256, "proposal_sha256")
        _digest(self.planner_gate_sha256, "planner_gate_sha256")
        _digest(self.execution_receipt_sha256, "execution_receipt_sha256")
        if isinstance(self.action_index, bool) or not isinstance(
            self.action_index, int
        ):
            raise ModelMotionSequenceError("action_index must be an integer")
        if self.action_index < 0:
            raise ModelMotionSequenceError("action_index must be nonnegative")
        if not isinstance(self.disposition, ActionDisposition):
            raise ModelMotionSequenceError("disposition must be an ActionDisposition")
        if self.disposition is ActionDisposition.VERIFIED_COMPLETED:
            _digest(self.outcome_evidence_sha256, "outcome_evidence_sha256")
        elif self.outcome_evidence_sha256 is not None:
            _digest(self.outcome_evidence_sha256, "outcome_evidence_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "batch_sha256": self.batch_sha256,
            "action_index": self.action_index,
            "proposal_sha256": self.proposal_sha256,
            "planner_gate_sha256": self.planner_gate_sha256,
            "execution_receipt_sha256": self.execution_receipt_sha256,
            "outcome_evidence_sha256": self.outcome_evidence_sha256,
            "disposition": self.disposition.value,
        }


PlannerGate = Callable[..., Mapping[str, Any]]


def _require_report_hash(
    report: Mapping[str, Any], field: str, *, label: str
) -> str:
    claimed = _digest(report.get(field), field)
    unsigned = {key: value for key, value in report.items() if key != field}
    actual = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if claimed != actual:
        raise ModelMotionSequenceError(f"{label} content hash is invalid")
    return claimed


class ModelMotionSequenceCoordinator:
    """Advance an admitted model batch without planning ahead or retrying."""

    def __init__(
        self,
        batch: ModelMotionBatch,
        ingress_report: Mapping[str, Any],
        context: SimulationContext,
        *,
        planner_gate: PlannerGate,
    ) -> None:
        if not isinstance(batch, ModelMotionBatch):
            raise TypeError("batch must be a ModelMotionBatch")
        if not isinstance(context, SimulationContext):
            raise TypeError("context must be a SimulationContext")
        if not isinstance(ingress_report, Mapping):
            raise TypeError("ingress_report must be a mapping")
        if not callable(planner_gate):
            raise TypeError("planner_gate must be callable")
        revalidate_simulation_context(context)
        if ingress_report.get("status") != "ACCEPTED_OFFLINE_FOR_ORDERED_PLANNER_GATES":
            raise ModelMotionSequenceError("batch lacks an accepted ingress report")
        if ingress_report.get("batch_sha256") != batch.batch_sha256:
            raise ModelMotionSequenceError("ingress report binds a different batch")
        ingress_sha256 = _require_report_hash(
            ingress_report, "ingress_sha256", label="ingress report"
        )
        candidates = ingress_report.get("ordered_candidate_sha256")
        if not isinstance(candidates, list) or len(candidates) != len(batch.proposals):
            raise ModelMotionSequenceError("ingress candidate order is incomplete")
        self._candidate_sha256 = tuple(
            _digest(item, "ordered candidate digest") for item in candidates
        )
        self._batch = batch
        self._context = context
        self._planner_gate = planner_gate
        self._ingress_sha256 = ingress_sha256
        self._phase = SequencePhase.WAITING_FOR_FRESH_STATE
        self._action_index = 0
        self._used_observed_states: set[str] = set()
        self._planner_reports: list[dict[str, Any]] = []
        self._results: list[VerifiedActionResult] = []
        self._dispatch_request_sha256: str | None = None
        self._used_dispatch_request_sha256: set[str] = set()
        self._blocker: str | None = None

    @property
    def phase(self) -> SequencePhase:
        return self._phase

    @property
    def action_index(self) -> int:
        return self._action_index

    @property
    def current_proposal(self) -> ModelMotionProposal | None:
        if self._action_index >= len(self._batch.proposals):
            return None
        return self._batch.proposals[self._action_index]

    def evaluate_next(
        self, observed_state: ObservedPlannerStartState, *, evaluation_monotonic_ns: int
    ) -> dict[str, Any]:
        """Evaluate only the current action from one never-before-used observation."""

        if self._phase is not SequencePhase.WAITING_FOR_FRESH_STATE:
            raise ModelMotionSequenceError("coordinator is not waiting for fresh state")
        if not isinstance(observed_state, ObservedPlannerStartState):
            raise TypeError("observed_state must be an ObservedPlannerStartState")
        if (
            isinstance(evaluation_monotonic_ns, bool)
            or not isinstance(evaluation_monotonic_ns, int)
            or evaluation_monotonic_ns < 1
        ):
            raise ModelMotionSequenceError("evaluation_monotonic_ns must be positive")
        observed_sha256 = observed_state.observed_start_state_sha256
        if observed_sha256 in self._used_observed_states:
            raise ModelMotionSequenceError(
                "an observed state cannot be reused across actions"
            )
        if not (
            observed_state.available_monotonic_ns
            <= evaluation_monotonic_ns
            <= observed_state.valid_until_monotonic_ns
        ):
            raise ModelMotionSequenceError("observed state is unavailable or stale")

        proposal = self.current_proposal
        if proposal is None:  # pragma: no cover - protected by phase transitions
            raise ModelMotionSequenceError("no current proposal exists")
        raw_report = self._planner_gate(
            proposal,
            self._context,
            observed_start_state=observed_state,
            evaluation_monotonic_ns=evaluation_monotonic_ns,
        )
        if not isinstance(raw_report, Mapping):
            raise ModelMotionSequenceError("planner gate did not return a mapping")
        report = dict(raw_report)
        _require_report_hash(report, "planner_gate_sha256", label="planner gate")
        if report.get("model_motion_candidate_sha256") != self._candidate_sha256[
            self._action_index
        ]:
            raise ModelMotionSequenceError("planner gate binds a different candidate")
        if (
            report.get("controller_commands") != []
            or report.get("hardware_commands_generated") != 0
        ):
            raise ModelMotionSequenceError(
                "planner gate crossed the zero-command boundary"
            )
        if (
            report.get("hardware_access") is not False
            or report.get("physical_authority") is not False
        ):
            raise ModelMotionSequenceError(
                "planner gate claimed hardware access or authority"
            )
        trajectory = report.get("trajectory_candidate")
        if isinstance(trajectory, Mapping):
            bound_observation = trajectory.get("observed_start_state_sha256")
            if bound_observation is not None and bound_observation != observed_sha256:
                raise ModelMotionSequenceError(
                    "planner gate binds a different observed state"
                )

        self._used_observed_states.add(observed_sha256)
        self._planner_reports.append(report)
        if report.get("status") == READY_PLANNER_STATUS:
            self._phase = SequencePhase.READY_FOR_SINGLE_ACTION_EXECUTOR
        else:
            self._phase = SequencePhase.BLOCKED
            self._blocker = str(report.get("status", "PLANNER_GATE_REJECTED"))
        return report

    def record_result(self, result: VerifiedActionResult) -> None:
        """Consume a single-use downstream result; never infer or retry one."""

        if self._phase is not SequencePhase.WAITING_FOR_EXECUTION_RESULT:
            raise ModelMotionSequenceError("no action is awaiting an executor result")
        if not isinstance(result, VerifiedActionResult):
            raise TypeError("result must be a VerifiedActionResult")
        if result.disposition is ActionDisposition.FAILED_BEFORE_DISPATCH:
            raise ModelMotionSequenceError(
                "a pre-dispatch failure cannot follow a committed dispatch boundary"
            )
        proposal = self.current_proposal
        assert proposal is not None
        expected_gate = self._planner_reports[-1]["planner_gate_sha256"]
        if (
            result.batch_sha256 != self._batch.batch_sha256
            or result.action_index != self._action_index
            or result.proposal_sha256 != proposal.proposal_sha256
            or result.planner_gate_sha256 != expected_gate
        ):
            raise ModelMotionSequenceError(
                "executor result does not bind the current action"
            )
        if any(
            item.execution_receipt_sha256 == result.execution_receipt_sha256
            for item in self._results
        ):
            raise ModelMotionSequenceError("execution receipt cannot be reused")
        self._results.append(result)
        if result.disposition is ActionDisposition.VERIFIED_COMPLETED:
            self._action_index += 1
            self._dispatch_request_sha256 = None
            self._phase = (
                SequencePhase.COMPLETED
                if self._action_index == len(self._batch.proposals)
                else SequencePhase.WAITING_FOR_FRESH_STATE
            )
        elif result.disposition is ActionDisposition.OUTCOME_UNCERTAIN:
            self._phase = SequencePhase.OUTCOME_UNCERTAIN
            self._blocker = "OUTCOME_UNCERTAIN_RETRY_FORBIDDEN"

    def commit_dispatch_boundary(self, execution_request_sha256: str) -> None:
        """Mark that dispatch may occur; callers must persist this before I/O."""

        if self._phase is not SequencePhase.READY_FOR_SINGLE_ACTION_EXECUTOR:
            raise ModelMotionSequenceError("current action is not ready for dispatch")
        request_sha256 = _digest(
            execution_request_sha256, "execution_request_sha256"
        )
        if request_sha256 in self._used_dispatch_request_sha256:
            raise ModelMotionSequenceError("execution request cannot be reused")
        self._used_dispatch_request_sha256.add(request_sha256)
        self._dispatch_request_sha256 = request_sha256
        self._phase = SequencePhase.WAITING_FOR_EXECUTION_RESULT

    def snapshot(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "schema": SCHEMA,
            "phase": self._phase.value,
            "batch_sha256": self._batch.batch_sha256,
            "ingress_sha256": self._ingress_sha256,
            "action_count": len(self._batch.proposals),
            "current_action_index": (
                None if self._phase is SequencePhase.COMPLETED else self._action_index
            ),
            "completed_action_count": sum(
                item.disposition is ActionDisposition.VERIFIED_COMPLETED
                for item in self._results
            ),
            "used_observed_start_state_sha256": sorted(self._used_observed_states),
            "planner_gate_sha256": [
                item["planner_gate_sha256"] for item in self._planner_reports
            ],
            "results": [item.to_dict() for item in self._results],
            "dispatch_request_sha256": self._dispatch_request_sha256,
            "used_dispatch_request_sha256": sorted(
                self._used_dispatch_request_sha256
            ),
            "blocker": self._blocker,
            "automatic_retry_allowed": False,
            "lookahead_planning_allowed": False,
            "controller_commands": [],
            "hardware_commands_generated": 0,
            "hardware_access": False,
            "physical_authority": False,
        }
        return {
            **report,
            "sequence_snapshot_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
        }


__all__ = [
    "SCHEMA",
    "READY_PLANNER_STATUS",
    "ActionDisposition",
    "ModelMotionSequenceCoordinator",
    "ModelMotionSequenceError",
    "SequencePhase",
    "VerifiedActionResult",
]
