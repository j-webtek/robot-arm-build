"""Hash-bound per-waypoint full-body collision evaluation.

This boundary closes the gap between a measured trajectory-screening report and
the primitive collision kernel.  Every accepted planner waypoint must have one
explicit :class:`CollisionPose`, including configuration-specific geometry for
every deformable body (for example the moving camera cable).  The evaluator is
bounded, deterministic, and deliberately makes no continuous-sweep claim.

No transform or cable shape is inferred here.  Producers must derive rigid
transforms from the exact waypoint joint solution and supply independently
qualified deformable geometry.  Clear discrete samples remain blocked from
physical release until a continuous/conservative segment proof exists.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from rocell.simulation.collision import (
    CollisionEvaluationPolicy,
    CollisionEvaluationStatus,
    CollisionPose,
    audit_collision_geometry,
    evaluate_collision_pose,
)

from .installed_collision_geometry import InstalledCollisionGeometryProfile
from .measured_trajectory_screening import SCHEMA as TRAJECTORY_SCREENING_SCHEMA


SCHEMA = "rocell.measured_waypoint_collision_sequence.v1"
MAX_WAYPOINT_COLLISION_SAMPLES = 256


class MeasuredWaypointCollisionSequenceError(ValueError):
    """Trajectory, profile, or sampled-pose evidence does not bind exactly."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class MeasuredWaypointCollisionSample:
    """One collision pose bound to one exact planner waypoint and IK result."""

    waypoint_sequence: int
    source_waypoint_sha256: str
    source_joint_result_sha256: str
    pose: CollisionPose

    def __post_init__(self) -> None:
        if (
            isinstance(self.waypoint_sequence, bool)
            or not isinstance(self.waypoint_sequence, int)
            or self.waypoint_sequence < 0
        ):
            raise MeasuredWaypointCollisionSequenceError(
                "waypoint_sequence must be a non-negative integer"
            )
        for value, label in (
            (self.source_waypoint_sha256, "source_waypoint_sha256"),
            (self.source_joint_result_sha256, "source_joint_result_sha256"),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise MeasuredWaypointCollisionSequenceError(
                    f"{label} must be a lowercase SHA-256 digest"
                )
        if not isinstance(self.pose, CollisionPose):
            raise TypeError("pose must be a CollisionPose")

    @property
    def content_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "waypoint_sequence": self.waypoint_sequence,
            "source_waypoint_sha256": self.source_waypoint_sha256,
            "source_joint_result_sha256": self.source_joint_result_sha256,
            "pose_sha256": self.pose.content_hash,
            "pose": self.pose.to_dict(),
        }


def _validated_trajectory(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MeasuredWaypointCollisionSequenceError(
            "trajectory_screening must be an object"
        )
    document = dict(value)
    digest = document.pop("trajectory_screening_sha256", None)
    if document.get("schema") != TRAJECTORY_SCREENING_SCHEMA:
        raise MeasuredWaypointCollisionSequenceError(
            "trajectory screening schema is not the measured v2 boundary"
        )
    if not isinstance(digest, str) or digest != _sha256(document):
        raise MeasuredWaypointCollisionSequenceError(
            "trajectory screening hash is invalid"
        )
    return dict(value)


def evaluate_measured_waypoint_collision_sequence(
    installed_profile: InstalledCollisionGeometryProfile,
    trajectory_screening: Mapping[str, Any],
    samples: Sequence[MeasuredWaypointCollisionSample],
    *,
    policy: CollisionEvaluationPolicy | None = None,
) -> dict[str, Any]:
    """Evaluate every planner waypoint while retaining the continuous-proof gate."""

    if not isinstance(installed_profile, InstalledCollisionGeometryProfile):
        raise TypeError("installed_profile must be InstalledCollisionGeometryProfile")
    trajectory = _validated_trajectory(trajectory_screening)
    if (
        trajectory.get("installed_collision_profile_sha256")
        != installed_profile.content_sha256
        or trajectory.get("collision_contract_sha256")
        != installed_profile.contract.content_hash
    ):
        raise MeasuredWaypointCollisionSequenceError(
            "trajectory collision lineage differs from installed profile"
        )
    if not trajectory.get("ik_all_waypoints_accepted"):
        raise MeasuredWaypointCollisionSequenceError(
            "collision sequence requires an all-accepted measured IK route"
        )
    waypoints = trajectory.get("waypoints")
    joint_results = trajectory.get("joint_results")
    if not isinstance(waypoints, list) or not isinstance(joint_results, list):
        raise MeasuredWaypointCollisionSequenceError(
            "trajectory waypoint or joint-result collection is invalid"
        )
    if len(waypoints) != len(joint_results):
        raise MeasuredWaypointCollisionSequenceError(
            "trajectory waypoint and joint-result counts differ"
        )
    try:
        iterator = iter(samples)
    except TypeError as exc:
        raise TypeError("samples must be a finite sequence") from exc
    bounded: list[MeasuredWaypointCollisionSample] = []
    for _ in range(MAX_WAYPOINT_COLLISION_SAMPLES + 1):
        try:
            bounded.append(next(iterator))
        except StopIteration:
            break
    if len(bounded) > MAX_WAYPOINT_COLLISION_SAMPLES:
        raise MeasuredWaypointCollisionSequenceError(
            "collision sample count exceeds the hard maximum"
        )
    supplied = tuple(bounded)
    if len(supplied) != len(waypoints) or not supplied:
        raise MeasuredWaypointCollisionSequenceError(
            "exactly one collision sample is required for every waypoint"
        )

    selected_policy = policy or CollisionEvaluationPolicy(
        clearance_policy=installed_profile.clearance_policy
    )
    if not isinstance(selected_policy, CollisionEvaluationPolicy):
        raise TypeError("policy must be CollisionEvaluationPolicy")
    if selected_policy.clearance_policy != installed_profile.clearance_policy:
        raise MeasuredWaypointCollisionSequenceError(
            "collision policy must use the installed profile clearance policy"
        )

    pose_reports: list[dict[str, Any]] = []
    blockers: list[str] = []
    all_clear = True
    for index, sample in enumerate(supplied):
        if not isinstance(sample, MeasuredWaypointCollisionSample):
            raise TypeError("samples must contain MeasuredWaypointCollisionSample values")
        waypoint = waypoints[index]
        joint_result = joint_results[index]
        if sample.waypoint_sequence != index:
            raise MeasuredWaypointCollisionSequenceError(
                "collision samples must be complete and ordered by waypoint sequence"
            )
        if (
            not isinstance(waypoint, Mapping)
            or waypoint.get("sequence") != index
            or sample.source_waypoint_sha256 != _sha256(waypoint)
            or sample.source_joint_result_sha256 != _sha256(joint_result)
        ):
            raise MeasuredWaypointCollisionSequenceError(
                f"collision sample {index} does not bind the exact planner waypoint"
            )
        if sample.pose.pose_id != f"waypoint-{index:04d}":
            raise MeasuredWaypointCollisionSequenceError(
                f"collision sample {index} pose_id is not canonical"
            )
        evaluation = evaluate_collision_pose(
            installed_profile.contract, sample.pose, selected_policy
        )
        pose_reports.append(
            {
                "sample": sample.to_dict(),
                "collision_report_sha256": evaluation.report_hash,
                "status": evaluation.status.value,
                "collision_free_diagnostic": evaluation.collision_free_diagnostic,
                "collisions": [item.to_dict() for item in evaluation.collisions],
                "pose_blockers": [item.to_dict() for item in evaluation.pose_blockers],
            }
        )
        if not evaluation.collision_free_diagnostic:
            all_clear = False
            blockers.append(
                f"WAYPOINT_{index:04d}_{evaluation.status.value}"
            )

    if all_clear:
        status = "DISCRETE_WAYPOINTS_CLEAR_CONTINUOUS_PROOF_REQUIRED"
        blockers.append("CONTINUOUS_FULL_BODY_COLLISION_SWEEP_REQUIRED")
        next_stage = "SUPPLY_CONSERVATIVE_INTER_WAYPOINT_SWEEP_PROOF"
    elif any(item["status"] == CollisionEvaluationStatus.COLLISION_DETECTED.value for item in pose_reports):
        status = "BLOCKED_COLLISION_DETECTED"
        next_stage = "CORRECT_ROUTE_OR_INSTALLED_GEOMETRY"
    else:
        status = "BLOCKED_INCOMPLETE_WAYPOINT_COLLISION_EVIDENCE"
        next_stage = "SUPPLY_COMPLETE_RIGID_TRANSFORMS_AND_DEFORMABLE_GEOMETRY"

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "trajectory_screening_sha256": trajectory["trajectory_screening_sha256"],
        "installed_collision_profile_sha256": installed_profile.content_sha256,
        "collision_contract_sha256": installed_profile.contract.content_hash,
        "collision_policy_sha256": selected_policy.content_hash,
        "sample_count": len(supplied),
        "configuration_sampled_body_ids": list(
            audit_collision_geometry(
                installed_profile.contract
            ).configuration_sampled_body_ids
        ),
        "pose_reports": pose_reports,
        "full_body_waypoint_screen_executed": True,
        "all_waypoints_collision_free_at_supplied_samples": all_clear,
        "continuous_collision_proven": False,
        "blockers": blockers,
        "next_required_stage": next_stage,
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {**report, "waypoint_collision_sequence_sha256": _sha256(report)}
