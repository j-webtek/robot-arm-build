"""Raw-request to zero-hardware v2 shadow trace orchestration.

This runner does not claim perception qualification. A supported request may
enter the actual v2 assembler only when the caller supplies a complete typed
integration fixture. Production use must replace that fixture with qualified,
authenticated perception evidence. No exception path grants authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from rocell.application import (
    ArmMotionPolicyV2,
    ObservedPlannerStartState,
    SimulationContext,
    TrustedMotionRegistryV2,
    run_model_motion_shadow_v2,
)
from rocell.models import (
    MotionCapabilityV2,
    MotionEvidenceV2,
    MotionGeometryV2,
    MotionUncertaintyV2,
)
from rocell.typing import compile_development_text

from .adapter import inspect
from .batch_emitter_v2 import TargetObservationV2, assemble
from .grounded import propose

SCHEMA = "rocell.ai_arm_shared_shadow.v2"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SharedShadowInputsV2:
    batch_id: str
    capability: MotionCapabilityV2
    geometry: MotionGeometryV2
    evidence: MotionEvidenceV2
    uncertainty: MotionUncertaintyV2
    observations: Mapping[str, TargetObservationV2]
    registry: TrustedMotionRegistryV2
    policy: ArmMotionPolicyV2
    observed_start_state: ObservedPlannerStartState
    current_time_epoch_ms: int
    ingress_monotonic_ns: int
    preplanner_monotonic_ns: int
    planner_monotonic_ns: int
    fixture_scope: str = "SYNTHETIC_INTEGRATION_ONLY"

    def __post_init__(self) -> None:
        if self.fixture_scope != "SYNTHETIC_INTEGRATION_ONLY":
            raise ValueError("shared runner currently accepts integration fixtures only")


def _terminal(
    *, request_id: str, request_sha256: str, observation_ref: str,
    status: str, reason: str, proposal: Mapping[str, Any],
    plan_hash: str | None = None, arm_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "request_id": request_id,
        "requested_text_sha256": request_sha256,
        "observation_ref": observation_ref,
        "status": status,
        "reason": reason,
        "grounded_proposal_sha256": hashlib.sha256(
            _canonical(dict(proposal))).hexdigest(),
        "intent_plan_sha256": plan_hash,
        "arm_shadow_trace_sha256": (
            None if arm_trace is None else arm_trace["shadow_trace_sha256"]),
        "arm_shadow_trace": arm_trace,
        "controller_commands": [],
        "waveshare_bytes": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {
        **report,
        "shared_shadow_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }


def run_shared_shadow_v2(
    *, request_id: str, request: str, observation: dict[str, Any],
    context: SimulationContext, inputs: SharedShadowInputsV2 | None,
) -> dict[str, Any]:
    """Run one raw request to a terminal zero-hardware outcome."""
    request_sha256 = hashlib.sha256(request.encode("utf-8")).hexdigest()
    grounded = propose(
        request_id=request_id, request=request, observation=observation)
    observation_ref = grounded["observation_ref"]
    if grounded["decision"] != "type_text":
        reason = grounded["reason"]
        status = {
            "stale_observation": "STALE_OBSERVATION",
        }.get(reason, "CLARIFICATION_REQUIRED" if grounded["decision"] == "clarify"
              else "UNSUPPORTED_REQUEST")
        return _terminal(
            request_id=request_id, request_sha256=request_sha256,
            observation_ref=observation_ref, status=status, reason=reason,
            proposal=grounded)
    inspected = inspect(grounded, observation)
    if inspected["status"] != "accepted":
        return _terminal(
            request_id=request_id, request_sha256=request_sha256,
            observation_ref=observation_ref, status="SEMANTIC_PLAN_BLOCKED",
            reason=inspected["reason"], proposal=grounded)
    plan = compile_development_text(grounded["device"], grounded["text"])
    if plan.plan_hash != inspected["plan_hash"]:
        raise ValueError("deterministic compiler hash changed within one run")
    if observation.get("obstructed") is True:
        return _terminal(
            request_id=request_id, request_sha256=request_sha256,
            observation_ref=observation_ref,
            status="PERCEPTION_ABSTAIN_OBSTRUCTED", reason="working_area_obstructed",
            proposal=grounded, plan_hash=plan.plan_hash)
    if inputs is None:
        return _terminal(
            request_id=request_id, request_sha256=request_sha256,
            observation_ref=observation_ref,
            status="PERCEPTION_EVIDENCE_REQUIRED",
            reason="qualified_v2_perception_not_supplied",
            proposal=grounded, plan_hash=plan.plan_hash)
    try:
        payload = assemble(
            plan, batch_id=inputs.batch_id, request_id=request_id,
            capability=inputs.capability, geometry=inputs.geometry,
            evidence=inputs.evidence, observations=inputs.observations,
            uncertainty=inputs.uncertainty)
        if payload is None:
            raise ValueError("assembler abstained")
        arm_trace = run_model_motion_shadow_v2(
            payload, plan, context, registry=inputs.registry,
            policy=inputs.policy,
            observed_start_state=inputs.observed_start_state,
            current_time_epoch_ms=inputs.current_time_epoch_ms,
            ingress_monotonic_ns=inputs.ingress_monotonic_ns,
            preplanner_monotonic_ns=inputs.preplanner_monotonic_ns,
            planner_monotonic_ns=inputs.planner_monotonic_ns)
    except ValueError as exc:
        return _terminal(
            request_id=request_id, request_sha256=request_sha256,
            observation_ref=observation_ref,
            status="REJECTED_BEFORE_PLANNING", reason=type(exc).__name__,
            proposal=grounded, plan_hash=plan.plan_hash)
    return _terminal(
        request_id=request_id, request_sha256=request_sha256,
        observation_ref=observation_ref, status=arm_trace["status"],
        reason="arm_shadow_terminal", proposal=grounded,
        plan_hash=plan.plan_hash, arm_trace=arm_trace)


__all__ = ["SCHEMA", "SharedShadowInputsV2", "run_shared_shadow_v2"]
