"""Run admitted v2 bytes through a zero-hardware planning trace.

This boundary is intentionally terminal before transport. It decodes the exact
producer bytes, resolves consumer-owned trust, checks the monotonic planning
lease and observed-state freshness, and evaluates actions in order until the
first deterministic planner blocker. It never creates an execution envelope
from a blocked plan and never encodes controller bytes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from rocell.models import ActionPlan, decode_model_motion_batch_v2_json

from .context import SimulationContext
from .model_motion_planner_gate_v2 import ArmMotionPolicyV2
from .model_motion_registry_v2 import (
    TrustedMotionRegistryV2,
    ingest_with_trusted_registry_v2,
    revalidate_with_trusted_registry_v2,
)
from .model_motion_sequence_coordinator_v2 import (
    ModelMotionSequenceCoordinatorV2,
)
from .observed_planner_start_state import ObservedPlannerStartState

SCHEMA = "rocell.model_motion_shadow_trace.v2"


class ModelMotionShadowV2Error(ValueError):
    """The v2 shadow trace cannot preserve a trusted zero-authority chain."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def run_model_motion_shadow_v2(
    payload: bytes,
    plan: ActionPlan,
    context: SimulationContext,
    *,
    registry: TrustedMotionRegistryV2,
    policy: ArmMotionPolicyV2,
    observed_start_state: ObservedPlannerStartState,
    current_time_epoch_ms: int,
    ingress_monotonic_ns: int,
    preplanner_monotonic_ns: int,
    planner_monotonic_ns: int,
) -> dict[str, Any]:
    """Return one hash-linked shadow trace and stop at the first blocker."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not isinstance(plan, ActionPlan):
        raise TypeError("plan must be an ActionPlan")
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    if not isinstance(observed_start_state, ObservedPlannerStartState):
        raise TypeError("observed_start_state must be an ObservedPlannerStartState")
    if not (
        observed_start_state.available_monotonic_ns
        <= planner_monotonic_ns
        <= observed_start_state.valid_until_monotonic_ns
    ):
        raise ModelMotionShadowV2Error("observed start state is not fresh")
    observed_document = observed_start_state.to_dict()
    if (
        observed_document.get("controller_commands") != []
        or observed_document.get("hardware_access") is not False
        or observed_document.get("physical_authority") is not False
    ):
        raise ModelMotionShadowV2Error("observed state violates zero authority")

    batch = decode_model_motion_batch_v2_json(payload)
    ingress = ingest_with_trusted_registry_v2(
        batch, plan, context, registry=registry,
        current_time_epoch_ms=current_time_epoch_ms,
        current_monotonic_ns=ingress_monotonic_ns,
    )
    preplanner = revalidate_with_trusted_registry_v2(
        ingress, registry=registry,
        current_monotonic_ns=preplanner_monotonic_ns,
    )
    coordinator = ModelMotionSequenceCoordinatorV2(
        batch, ingress, preplanner, context, policy=policy)
    proposal = coordinator.current_proposal
    if proposal is None:
        raise ModelMotionShadowV2Error("v2 batch contains no action")
    planner = coordinator.evaluate_next(
        observed_start_state, evaluation_monotonic_ns=planner_monotonic_ns)
    actions = [{
        "action_index": proposal.action_index,
        "target_id": proposal.target_id,
        "proposal_sha256": proposal.proposal_sha256,
        "planner_gate_v2_sha256": planner["planner_gate_v2_sha256"],
        "status": planner["status"],
        "next_required_stage": planner["next_required_stage"],
        "trajectory_execution_envelope_sha256": None,
    }]
    terminal_status = planner["status"]
    sequence = coordinator.snapshot()

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": terminal_status,
        "requested_text_sha256": plan.requested_text_sha256,
        "intent_plan_sha256": plan.plan_hash,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "batch_sha256": batch.batch_sha256,
        "capture_id": batch.evidence.capture_id,
        "frame_id": batch.evidence.frame_id,
        "image_sha256": batch.evidence.image_sha256,
        "scene_observation_sha256": batch.evidence.scene_observation_sha256,
        "precision_observation_sha256": (
            batch.evidence.precision_observation_sha256
        ),
        "fusion_decision_sha256": batch.evidence.fusion_decision_sha256,
        "ingress_sha256": ingress["ingress_sha256"],
        "preplanner_gate_sha256": preplanner["preplanner_gate_sha256"],
        "observed_start_state_sha256": (
            observed_start_state.observed_start_state_sha256
        ),
        "arm_motion_policy_sha256": policy.policy_sha256,
        "sequence_snapshot_v2_sha256": sequence["sequence_snapshot_v2_sha256"],
        "sequence_snapshot": sequence,
        "actions": actions,
        "trajectory_execution_envelope_sha256": None,
        "waveshare_bytes": [],
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {
        **report,
        "shadow_trace_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }


__all__ = [
    "SCHEMA",
    "ModelMotionShadowV2Error",
    "run_model_motion_shadow_v2",
]
