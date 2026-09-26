"""Policy-owned adapter from admitted v2 proposals to measured planning.

V2 deliberately carries no model-selected speed or clearance. This adapter
derives those values from an arm-owned policy, preserves the original v2 lineage,
and invokes the existing measured calibration/reprojection/IK screening gate. It
does not encode controller bytes or grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping

from rocell.models import (ModelMotionBatchV2, ModelMotionProposal,
                           ModelMotionProposalV2, ProposalSource, SpeedClass)
from .context import SimulationContext
from .model_motion_planner_gate import evaluate_model_motion_planner_gate
from .observed_planner_start_state import ObservedPlannerStartState

SCHEMA = "rocell.model_motion_planner_gate.v2"


class ModelMotionPlannerGateV2Error(ValueError):
    """V2 lineage or arm-owned policy cannot enter measured planning."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _require_hash(document: Mapping[str, Any], field: str, label: str) -> str:
    claimed = document.get(field)
    if not isinstance(claimed, str) or len(claimed) != 64:
        raise ModelMotionPlannerGateV2Error(f"{label} hash is missing")
    unsigned = {key: value for key, value in document.items() if key != field}
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != claimed:
        raise ModelMotionPlannerGateV2Error(f"{label} hash is invalid")
    return claimed


@dataclass(frozen=True, slots=True)
class ArmMotionPolicyV2:
    policy_id: str
    approach_clearance_mm: float
    speed_class: SpeedClass

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ModelMotionPlannerGateV2Error("policy_id must be nonempty")
        if isinstance(self.approach_clearance_mm, bool) or not isinstance(
                self.approach_clearance_mm, (int, float)) \
                or not math.isfinite(float(self.approach_clearance_mm)) \
                or not 0.0 < float(self.approach_clearance_mm) <= 100.0:
            raise ModelMotionPlannerGateV2Error(
                "approach clearance must be finite and in (0, 100]")
        try:
            object.__setattr__(self, "speed_class", SpeedClass(self.speed_class))
        except ValueError as exc:
            raise ModelMotionPlannerGateV2Error(str(exc)) from exc

    def to_dict(self) -> dict[str, object]:
        return {"policy_id": self.policy_id,
                "approach_clearance_mm": float(self.approach_clearance_mm),
                "speed_class": self.speed_class.value}

    @property
    def policy_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict())).hexdigest()


def evaluate_model_motion_planner_gate_v2(
    proposal: ModelMotionProposalV2, batch: ModelMotionBatchV2,
    ingress_report: Mapping[str, Any], preplanner_report: Mapping[str, Any],
    context: SimulationContext, *, policy: ArmMotionPolicyV2,
    observed_start_state: ObservedPlannerStartState | None = None,
    evaluation_monotonic_ns: int,
) -> dict[str, Any]:
    """Evaluate one admitted v2 action through the existing measured gate."""
    if not isinstance(proposal, ModelMotionProposalV2):
        raise TypeError("proposal must be ModelMotionProposalV2")
    if not isinstance(batch, ModelMotionBatchV2):
        raise TypeError("batch must be ModelMotionBatchV2")
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be SimulationContext")
    if not isinstance(policy, ArmMotionPolicyV2):
        raise TypeError("policy must be ArmMotionPolicyV2")
    if not isinstance(ingress_report, Mapping) or not isinstance(preplanner_report, Mapping):
        raise TypeError("ingress and preplanner reports must be mappings")
    if isinstance(evaluation_monotonic_ns, bool) or not isinstance(
            evaluation_monotonic_ns, int) or evaluation_monotonic_ns <= 0:
        raise ModelMotionPlannerGateV2Error("evaluation time must be positive")

    ingress_sha256 = _require_hash(ingress_report, "ingress_sha256", "ingress")
    preplanner_sha256 = _require_hash(
        preplanner_report, "preplanner_gate_sha256", "preplanner")
    if ingress_report.get("batch_sha256") != batch.batch_sha256 \
            or preplanner_report.get("batch_sha256") != batch.batch_sha256 \
            or preplanner_report.get("ingress_sha256") != ingress_sha256:
        raise ModelMotionPlannerGateV2Error("v2 batch lineage differs")
    if preplanner_report.get("status") != "FRESH_FOR_DETERMINISTIC_PLANNING":
        raise ModelMotionPlannerGateV2Error("preplanner gate is not fresh")
    deadline = preplanner_report.get("valid_until_monotonic_ns")
    checked = preplanner_report.get("checked_at_monotonic_ns")
    if not isinstance(deadline, int) or not isinstance(checked, int) \
            or not checked <= evaluation_monotonic_ns < deadline:
        raise ModelMotionPlannerGateV2Error("v2 planning lease is stale")
    if proposal.action_index >= len(batch.proposals) \
            or batch.proposals[proposal.action_index] != proposal:
        raise ModelMotionPlannerGateV2Error("proposal is not the indexed batch action")
    admitted = ingress_report.get("admitted_actions")
    if not isinstance(admitted, list) or proposal.action_index >= len(admitted):
        raise ModelMotionPlannerGateV2Error("ingress action lineage is incomplete")
    admitted_action = admitted[proposal.action_index]
    if not isinstance(admitted_action, Mapping) \
            or admitted_action.get("proposal_sha256") != proposal.proposal_sha256 \
            or admitted_action.get("action_index") != proposal.action_index:
        raise ModelMotionPlannerGateV2Error("ingress binds a different proposal")
    for report in (ingress_report, preplanner_report):
        if report.get("controller_commands") != [] \
                or report.get("hardware_access") is not False \
                or report.get("physical_authority") is not False:
            raise ModelMotionPlannerGateV2Error("upstream report violates zero authority")

    surrogate = ModelMotionProposal(
        proposal_id=f"v2-policy:{proposal.proposal_id}", device=proposal.device,
        target_id=proposal.target_id, target=proposal.target,
        interaction=proposal.interaction,
        approach_clearance_mm=float(policy.approach_clearance_mm),
        speed_class=policy.speed_class,
        confidence=proposal.observation_confidence,
        source=ProposalSource(batch.evidence.model_id, batch.evidence.frame_id,
                              batch.evidence.image_sha256))
    downstream = evaluate_model_motion_planner_gate(
        surrogate, context, minimum_confidence=0.0,
        observed_start_state=observed_start_state,
        evaluation_monotonic_ns=evaluation_monotonic_ns)
    if downstream.get("controller_commands") != [] \
            or downstream.get("hardware_commands_generated") != 0 \
            or downstream.get("hardware_access") is not False \
            or downstream.get("physical_authority") is not False:
        raise ModelMotionPlannerGateV2Error("measured planner crossed zero authority")
    report = {
        "schema": SCHEMA, "status": downstream["status"],
        "batch_sha256": batch.batch_sha256,
        "action_index": proposal.action_index,
        "proposal_sha256": proposal.proposal_sha256,
        "ingress_sha256": ingress_sha256,
        "preplanner_gate_sha256": preplanner_sha256,
        "arm_motion_policy": policy.to_dict(),
        "arm_motion_policy_sha256": policy.policy_sha256,
        "derived_v1_surrogate_sha256": surrogate.proposal_sha256,
        "measured_planner_gate_sha256": downstream["planner_gate_sha256"],
        "measured_planner_gate": downstream,
        "next_required_stage": downstream["next_required_stage"],
        "controller_commands": [], "hardware_commands_generated": 0,
        "hardware_access": False, "physical_authority": False,
    }
    return {**report, "planner_gate_v2_sha256": hashlib.sha256(
        _canonical(report)).hexdigest()}


__all__ = ["SCHEMA", "ArmMotionPolicyV2", "ModelMotionPlannerGateV2Error",
           "evaluate_model_motion_planner_gate_v2"]
