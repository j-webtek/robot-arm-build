"""Ordered, zero-authority coordination for admitted v2 motion batches.

The v1 execution envelope binds the measured-planner compatibility surrogate,
not the original v2 proposal. Until a v2 envelope binding carries both hashes,
this coordinator may evaluate exactly one current action but cannot authorize or
commit dispatch. That limitation is explicit and fail closed.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Mapping

from rocell.models import ModelMotionBatchV2, ModelMotionProposalV2

from .context import SimulationContext, revalidate_simulation_context
from .model_motion_planner_gate_v2 import (
    ArmMotionPolicyV2,
    evaluate_model_motion_planner_gate_v2,
)
from .observed_planner_start_state import ObservedPlannerStartState

SCHEMA = "rocell.model_motion_sequence_snapshot.v2"
READY_PLANNER_STATUS = "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION"


class ModelMotionSequenceV2Error(ValueError):
    """The ordered v2 planning lifecycle is inconsistent or unsafe."""


class SequencePhaseV2(str, Enum):
    WAITING_FOR_FRESH_STATE = "WAITING_FOR_FRESH_STATE"
    READY_FOR_V2_ENVELOPE_BINDING = "READY_FOR_V2_ENVELOPE_BINDING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _require_hash(
    report: Mapping[str, Any], field: str, *, label: str,
) -> str:
    claimed = report.get(field)
    if not isinstance(claimed, str) or len(claimed) != 64:
        raise ModelMotionSequenceV2Error(f"{label} hash is missing")
    unsigned = {key: value for key, value in report.items() if key != field}
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != claimed:
        raise ModelMotionSequenceV2Error(f"{label} content hash is invalid")
    return claimed


class ModelMotionSequenceCoordinatorV2:
    """Evaluate only the current v2 action from one fresh observed state."""

    def __init__(
        self,
        batch: ModelMotionBatchV2,
        ingress_report: Mapping[str, Any],
        preplanner_report: Mapping[str, Any],
        context: SimulationContext,
        *,
        policy: ArmMotionPolicyV2,
    ) -> None:
        if not isinstance(batch, ModelMotionBatchV2):
            raise TypeError("batch must be a ModelMotionBatchV2")
        if not isinstance(context, SimulationContext):
            raise TypeError("context must be a SimulationContext")
        if not isinstance(policy, ArmMotionPolicyV2):
            raise TypeError("policy must be an ArmMotionPolicyV2")
        if not isinstance(ingress_report, Mapping) or not isinstance(
            preplanner_report, Mapping
        ):
            raise TypeError("ingress and preplanner reports must be mappings")
        revalidate_simulation_context(context)
        ingress_sha256 = _require_hash(
            ingress_report, "ingress_sha256", label="ingress report")
        preplanner_sha256 = _require_hash(
            preplanner_report, "preplanner_gate_sha256",
            label="preplanner report")
        if (
            ingress_report.get("batch_sha256") != batch.batch_sha256
            or preplanner_report.get("batch_sha256") != batch.batch_sha256
            or preplanner_report.get("ingress_sha256") != ingress_sha256
        ):
            raise ModelMotionSequenceV2Error("reports bind a different v2 batch")
        if preplanner_report.get("status") != "FRESH_FOR_DETERMINISTIC_PLANNING":
            raise ModelMotionSequenceV2Error("preplanner report is not fresh")
        for report in (ingress_report, preplanner_report):
            if (
                report.get("controller_commands") != []
                or report.get("hardware_access") is not False
                or report.get("physical_authority") is not False
            ):
                raise ModelMotionSequenceV2Error(
                    "upstream report violates zero authority")
        self._batch = batch
        self._ingress = dict(ingress_report)
        self._preplanner = dict(preplanner_report)
        self._context = context
        self._policy = policy
        self._ingress_sha256 = ingress_sha256
        self._preplanner_sha256 = preplanner_sha256
        self._phase = SequencePhaseV2.WAITING_FOR_FRESH_STATE
        self._action_index = 0
        self._used_observed_states: set[str] = set()
        self._planner_reports: list[dict[str, Any]] = []
        self._blocker: str | None = None

    @property
    def phase(self) -> SequencePhaseV2:
        return self._phase

    @property
    def current_proposal(self) -> ModelMotionProposalV2 | None:
        if self._action_index >= len(self._batch.proposals):
            return None
        return self._batch.proposals[self._action_index]

    def evaluate_next(
        self,
        observed_state: ObservedPlannerStartState,
        *,
        evaluation_monotonic_ns: int,
    ) -> dict[str, Any]:
        if self._phase is not SequencePhaseV2.WAITING_FOR_FRESH_STATE:
            raise ModelMotionSequenceV2Error(
                "coordinator is not waiting for fresh state")
        if not isinstance(observed_state, ObservedPlannerStartState):
            raise TypeError("observed_state must be an ObservedPlannerStartState")
        observed_sha256 = observed_state.observed_start_state_sha256
        if observed_sha256 in self._used_observed_states:
            raise ModelMotionSequenceV2Error(
                "an observed state cannot be reused across actions")
        if not (
            observed_state.available_monotonic_ns
            <= evaluation_monotonic_ns
            <= observed_state.valid_until_monotonic_ns
        ):
            raise ModelMotionSequenceV2Error(
                "observed state is unavailable or stale")
        proposal = self.current_proposal
        if proposal is None:
            raise ModelMotionSequenceV2Error("no current proposal exists")
        report = evaluate_model_motion_planner_gate_v2(
            proposal, self._batch, self._ingress, self._preplanner,
            self._context, policy=self._policy,
            observed_start_state=observed_state,
            evaluation_monotonic_ns=evaluation_monotonic_ns,
        )
        _require_hash(report, "planner_gate_v2_sha256", label="planner report")
        if (
            report.get("batch_sha256") != self._batch.batch_sha256
            or report.get("action_index") != self._action_index
            or report.get("proposal_sha256") != proposal.proposal_sha256
        ):
            raise ModelMotionSequenceV2Error(
                "planner report binds a different current action")
        if (
            report.get("controller_commands") != []
            or report.get("hardware_commands_generated") != 0
            or report.get("hardware_access") is not False
            or report.get("physical_authority") is not False
        ):
            raise ModelMotionSequenceV2Error(
                "planner report crossed the zero-authority boundary")
        self._used_observed_states.add(observed_sha256)
        self._planner_reports.append(dict(report))
        if report.get("status") == READY_PLANNER_STATUS:
            self._phase = SequencePhaseV2.READY_FOR_V2_ENVELOPE_BINDING
            self._blocker = "V2_ENVELOPE_DUAL_LINEAGE_BINDING_REQUIRED"
        else:
            self._phase = SequencePhaseV2.BLOCKED
            self._blocker = str(report.get("status", "PLANNER_GATE_REJECTED"))
        return report

    def snapshot(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "schema": SCHEMA,
            "phase": self._phase.value,
            "batch_sha256": self._batch.batch_sha256,
            "ingress_sha256": self._ingress_sha256,
            "preplanner_gate_sha256": self._preplanner_sha256,
            "arm_motion_policy_sha256": self._policy.policy_sha256,
            "action_count": len(self._batch.proposals),
            "ordered_proposal_sha256": [
                proposal.proposal_sha256 for proposal in self._batch.proposals
            ],
            "current_action_index": self._action_index,
            "used_observed_start_state_sha256": sorted(
                self._used_observed_states),
            "planner_gate_v2_sha256": [
                item["planner_gate_v2_sha256"]
                for item in self._planner_reports
            ],
            "blocker": self._blocker,
            "automatic_retry_allowed": False,
            "lookahead_planning_allowed": False,
            "v1_envelope_auto_upgrade_allowed": False,
            "controller_commands": [],
            "hardware_commands_generated": 0,
            "hardware_access": False,
            "physical_authority": False,
        }
        return {
            **report,
            "sequence_snapshot_v2_sha256": hashlib.sha256(
                _canonical(report)).hexdigest(),
        }


__all__ = [
    "SCHEMA",
    "READY_PLANNER_STATUS",
    "ModelMotionSequenceCoordinatorV2",
    "ModelMotionSequenceV2Error",
    "SequencePhaseV2",
]
