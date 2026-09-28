"""Golden zero-I/O composition of the optimized typing planning boundaries."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from rocell.calibration import PlannerCalibrationSnapshot
from rocell.models import ActionPlan, decode_model_motion_batch_v2_json

from .bounded_segment_collision_qualification import BoundedSegmentSamplingPolicy
from .context import SimulationContext
from .installed_collision_geometry import InstalledCollisionGeometryProfile
from .model_motion_registry_v2 import (
    TrustedMotionRegistryV2,
    ingest_with_trusted_registry_v2,
    revalidate_with_trusted_registry_v2,
)
from .typing_collision_intake_v1 import prepare_typing_collision_intake_v1
from .typing_execution_plan_v1 import (
    TypingExecutionConfigV1,
    compile_typing_execution_plan_v1,
)
from .typing_joint_schedule_v1 import (
    TypingJointDynamicsProfileV1,
    compile_typing_joint_schedule_v1,
)
from .typing_trajectory_ik_screen_v1 import (
    READY_STATUS as IK_READY_STATUS,
    TypingTrajectoryIkSeedV1,
    screen_typing_trajectory_ik_v1,
)
from .typing_trajectory_plan_v1 import (
    TypingTrajectoryPolicyV1,
    compile_typing_trajectory_plan_v1,
)
from .trajectory_simulation import TrajectorySimulationPolicy


SCHEMA = "rocell.typing_shadow_pipeline.v1"
STATUS = "BLOCKED_AT_HONEST_COLLISION_EVIDENCE_BOUNDARY"


class TypingShadowPipelineV1Error(ValueError):
    """A stage failed before the golden zero-I/O receipt could be composed."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypingShadowPipelineV1Error("stage output is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def run_typing_shadow_pipeline_v1(
    payload: bytes,
    intent_plan: ActionPlan,
    context: SimulationContext,
    *,
    registry: TrustedMotionRegistryV2,
    current_time_epoch_ms: int,
    ingress_monotonic_ns: int,
    preplanner_monotonic_ns: int,
    execution_config: TypingExecutionConfigV1,
    trajectory_policy: TypingTrajectoryPolicyV1,
    calibration_snapshot: PlannerCalibrationSnapshot,
    ik_seed: TypingTrajectoryIkSeedV1,
    joint_dynamics_profile: TypingJointDynamicsProfileV1,
    ik_policy: TrajectorySimulationPolicy | None = None,
    installed_collision_profile: InstalledCollisionGeometryProfile | None = None,
    collision_sampling_policy: BoundedSegmentSamplingPolicy | None = None,
) -> dict[str, Any]:
    """Run exact production boundaries through their honest offline blocker.

    The function has no transport dependency and exposes no callback capable of
    writing to hardware.  A successful receipt means composition succeeded; it
    does not mean collision evidence, fresh state, or physical authority exists.
    """

    batch = decode_model_motion_batch_v2_json(payload)
    ingress = ingest_with_trusted_registry_v2(
        batch,
        intent_plan,
        context,
        registry=registry,
        current_time_epoch_ms=current_time_epoch_ms,
        current_monotonic_ns=ingress_monotonic_ns,
    )
    freshness = revalidate_with_trusted_registry_v2(
        ingress,
        registry=registry,
        current_monotonic_ns=preplanner_monotonic_ns,
    )
    execution = compile_typing_execution_plan_v1(
        batch,
        ingress,
        config=execution_config,
    )
    trajectory = compile_typing_trajectory_plan_v1(
        execution,
        policy=trajectory_policy,
    )
    ik = screen_typing_trajectory_ik_v1(
        execution,
        trajectory,
        context,
        calibration_snapshot,
        ik_seed,
        policy=ik_policy,
    )
    if ik.get("status") != IK_READY_STATUS:
        raise TypingShadowPipelineV1Error(
            "golden shadow route did not reach the accepted offline IK boundary"
        )
    schedule = compile_typing_joint_schedule_v1(
        trajectory,
        ik,
        joint_dynamics_profile,
    )
    collision = prepare_typing_collision_intake_v1(
        execution,
        trajectory,
        ik,
        context,
        calibration_snapshot,
        installed_collision_profile,
        sampling_policy=collision_sampling_policy,
    )
    ordered_targets = [action.target_id for action in execution.actions]
    if ordered_targets != [proposal.target_id for proposal in batch.proposals]:
        raise TypingShadowPipelineV1Error("action order changed during composition")
    stage_hashes: Mapping[str, str] = {
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "batch_sha256": batch.batch_sha256,
        "ingress_sha256": ingress["ingress_sha256"],
        "freshness_sha256": _sha256(freshness),
        "typing_execution_plan_sha256": execution.plan_sha256,
        "typing_trajectory_plan_sha256": trajectory.trajectory_plan_sha256,
        "typing_trajectory_ik_screen_sha256": ik[
            "typing_trajectory_ik_screen_sha256"
        ],
        "typing_joint_schedule_sha256": schedule.schedule_sha256,
        "typing_collision_intake_sha256": collision[
            "typing_collision_intake_sha256"
        ],
    }
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "request_id": batch.request_id,
        "ordered_target_ids": ordered_targets,
        "action_count": len(ordered_targets),
        "stage_hashes": dict(stage_hashes),
        "terminal_stage": "COLLISION_EVIDENCE_INTAKE",
        "terminal_stage_status": collision["status"],
        "terminal_blockers": collision["blockers"],
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {**receipt, "typing_shadow_pipeline_sha256": _sha256(receipt)}


__all__ = [
    "SCHEMA",
    "STATUS",
    "TypingShadowPipelineV1Error",
    "run_typing_shadow_pipeline_v1",
]
