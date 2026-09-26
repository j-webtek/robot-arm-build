"""Validate one ordered AI proposal batch at the deterministic planner seam.

This boundary does not call a model, solve IK, encode a servo command, or touch
hardware. It proves that an ordered proposal batch matches one semantic action
plan and the active target/build context before later per-action planner gates
may consume it.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from rocell.models import (
    ActionPlan,
    Interaction,
    ModelMotionBatch,
    PressKey,
    TapPhoneTarget,
    VerifyPhoneState,
)

from .context import SimulationContext, revalidate_simulation_context
from .model_motion_bridge import (
    ModelMotionBridgeError,
    compile_model_motion_proposal,
)


SCHEMA = "rocell.model_motion_ingress.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ModelMotionIngressError(ValueError):
    """An AI batch cannot enter the ordered deterministic planning boundary."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _movement_targets(plan: ActionPlan) -> tuple[str, ...]:
    result: list[str] = []
    for action in plan.actions:
        if isinstance(action, PressKey):
            result.append(action.key_id)
        elif isinstance(action, TapPhoneTarget):
            result.append(action.target_id)
        elif not isinstance(action, VerifyPhoneState):  # pragma: no cover - ActionPlan guards
            raise ModelMotionIngressError("semantic plan contains an unsupported action")
    return tuple(result)


def ingest_model_motion_batch(
    batch: ModelMotionBatch,
    plan: ActionPlan,
    context: SimulationContext,
    *,
    expected_scene_observation_sha256: str,
    expected_precision_observation_sha256: str,
    expected_fusion_decision_sha256: str,
    minimum_confidence: float = 0.9,
) -> dict[str, Any]:
    """Bind ordered model coordinates to intent and active nominal target data."""

    if not isinstance(batch, ModelMotionBatch):
        raise TypeError("batch must be a ModelMotionBatch")
    if not isinstance(plan, ActionPlan):
        raise TypeError("plan must be an ActionPlan")
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    expected_evidence = {
        "scene_observation_sha256": expected_scene_observation_sha256,
        "precision_observation_sha256": expected_precision_observation_sha256,
        "fusion_decision_sha256": expected_fusion_decision_sha256,
    }
    for label, digest in expected_evidence.items():
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ModelMotionIngressError(f"expected {label} is not a SHA-256 digest")
        if getattr(batch, label) != digest:
            raise ModelMotionIngressError(f"batch {label} differs from validated evidence")
    if batch.intent_plan_sha256 != plan.plan_hash:
        raise ModelMotionIngressError("batch does not bind the supplied semantic plan")
    if batch.proposals[0].device.value != plan.device.value:
        raise ModelMotionIngressError("batch device differs from the semantic plan")
    expected_targets = _movement_targets(plan)
    proposed_targets = tuple(item.target_id for item in batch.proposals)
    if proposed_targets != expected_targets:
        raise ModelMotionIngressError(
            "proposal target order differs from the semantic movement actions"
        )
    if any(item.interaction is not Interaction.CONTACT for item in batch.proposals):
        raise ModelMotionIngressError(
            "typing/tapping action proposals must request CONTACT"
        )

    candidates: list[dict[str, Any]] = []
    for index, proposal in enumerate(batch.proposals):
        try:
            candidate = compile_model_motion_proposal(
                proposal,
                context.targets,
                minimum_confidence=minimum_confidence,
            )
        except (ModelMotionBridgeError, TypeError, ValueError) as exc:
            raise ModelMotionIngressError(
                f"proposal {index} failed deterministic coordinate admission: {exc}"
            ) from exc
        candidates.append(candidate)

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ACCEPTED_OFFLINE_FOR_ORDERED_PLANNER_GATES",
        "batch_sha256": batch.batch_sha256,
        "intent_plan_sha256": plan.plan_hash,
        "request_id": batch.request_id,
        "source_bindings": {
            "scene_observation_sha256": batch.scene_observation_sha256,
            "precision_observation_sha256": batch.precision_observation_sha256,
            "fusion_decision_sha256": batch.fusion_decision_sha256,
            "frame_id": batch.proposals[0].source.frame_id,
            "image_sha256": batch.proposals[0].source.image_sha256,
            "model_id": batch.proposals[0].source.model_id,
            "manifest_id": context.snapshot.manifest_id,
            "manifest_sha256": context.snapshot.manifest_sha256,
            "build_snapshot_sha256": context.snapshot.snapshot_hash,
            "active_build_id": context.snapshot.active_build_id,
            "target_catalog_sha256": context.targets.content_sha256,
        },
        "ordered_target_ids": list(proposed_targets),
        "ordered_candidate_sha256": [item["candidate_sha256"] for item in candidates],
        "candidates": candidates,
        "next_required_stage": "EVALUATE_EACH_ACTION_WITH_FRESH_STATE_AND_CALIBRATED_PLANNER",
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {
        **report,
        "ingress_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }


__all__ = ["SCHEMA", "ModelMotionIngressError", "ingest_model_motion_batch"]
