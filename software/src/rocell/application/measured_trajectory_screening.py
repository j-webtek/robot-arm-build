"""Deterministic measured-waypoint IK screening with no execution authority.

This boundary consumes the output of measured target reprojection.  It requires
an independently observed current arm state before constructing a route, then
uses the pinned numerical IK implementation and its canonical joint-margin,
task-Jacobian-rank, and adjacent-joint-delta gates.  Current collision readiness
is attached explicitly; incomplete geometry always blocks physical release.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from rocell.calibration import PlannerCalibrationSnapshot
from rocell.geometry import JointPosition, Point3Mm, RigidTransform, Rotation3, Vec3
from rocell.kinematics import (
    ARM_JOINT_NAMES,
    BoardToolTipTarget,
    IkOptions,
    RoArmM3NumericalIk,
)
from rocell.models import ModelMotionProposal
from rocell.motion import MotionPhase
from rocell.targets import NominalTargetCatalog

from ._pinned_model import load_pinned_urdf
from .collision_readiness import assess_current_collision_readiness
from .context import SimulationContext, revalidate_simulation_context
from .measured_target_reprojection import reproject_measured_target
from .observed_planner_start_state import (
    ObservedPlannerStartState,
    ObservedPlannerStartStateError,
)
from .trajectory_simulation import (
    CartesianRouteWaypoint,
    TrajectorySimulationPolicy,
    evaluate_joint_trajectory_solution,
)


SCHEMA = "rocell.measured_trajectory_screening.v1"
_REFERENCE_TO_URDF = dict(
    zip(
        ("b_base", "s_shoulder", "e_elbow", "t_wrist_pitch", "r_wrist_roll"),
        ARM_JOINT_NAMES,
    )
)
_PHASES = {
    "HOVER_DESTINATION": MotionPhase.HOVER,
    "APPROACH": MotionPhase.APPROACH,
    "CONTACT_CANDIDATE": MotionPhase.CONTACT,
    "RETRACT": MotionPhase.RETRACT,
}


class MeasuredTrajectoryScreeningError(ValueError):
    """Inputs cannot form one deterministic, bounded route-screening attempt."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _verify_reprojection(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MeasuredTrajectoryScreeningError("reprojection must be an object")
    document = dict(value)
    digest = document.pop("reprojection_sha256", None)
    if (
        not isinstance(digest, str)
        or digest != hashlib.sha256(_canonical(document)).hexdigest()
    ):
        raise MeasuredTrajectoryScreeningError("reprojection hash is invalid")
    return dict(value)


def _point_from_document(value: object) -> Point3Mm:
    if not isinstance(value, Mapping) or set(value) != {"frame", "x", "y", "z"}:
        raise MeasuredTrajectoryScreeningError("waypoint point schema is invalid")
    try:
        point = Point3Mm(value["frame"], value["x"], value["y"], value["z"])
    except (TypeError, ValueError) as exc:
        raise MeasuredTrajectoryScreeningError("waypoint point is invalid") from exc
    if point.frame != "B":
        raise MeasuredTrajectoryScreeningError("measured waypoint must use frame B")
    return Point3Mm("board", point.x, point.y, point.z)


def _observed_state(
    value: ObservedPlannerStartState | None,
    snapshot: PlannerCalibrationSnapshot,
    evaluation_monotonic_ns: int | None,
    bounds: Mapping[str, tuple[float, float]],
) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, ObservedPlannerStartState):
        raise MeasuredTrajectoryScreeningError(
            "observed start state must be authenticated feedback evidence"
        )
    if evaluation_monotonic_ns is None:
        raise MeasuredTrajectoryScreeningError(
            "evaluation_monotonic_ns is required with observed start state"
        )
    try:
        qualified = value.require_fresh_for(snapshot, evaluation_monotonic_ns)
    except ObservedPlannerStartStateError as exc:
        raise MeasuredTrajectoryScreeningError(str(exc)) from exc
    result: dict[str, float] = {}
    for name in ARM_JOINT_NAMES:
        raw = qualified[name]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise MeasuredTrajectoryScreeningError(
                f"observed start {name} is not numeric"
            )
        number = float(raw)
        lower, upper = bounds[name]
        if not math.isfinite(number) or not lower <= number <= upper:
            raise MeasuredTrajectoryScreeningError(
                f"observed start {name} leaves calibrated planner bounds"
            )
        result[name] = number
    return result


def _planner_bounds(
    context: SimulationContext, snapshot: PlannerCalibrationSnapshot
) -> dict[str, tuple[float, float]]:
    result: dict[str, tuple[float, float]] = {}
    for index, reference_name in enumerate(_REFERENCE_TO_URDF):
        urdf_name = _REFERENCE_TO_URDF[reference_name]
        scenario_lower, scenario_upper = (
            context.scenario.controller_joint_intersection_rad[urdf_name]
        )
        lower = max(scenario_lower, snapshot.joint_lower_rad[index])
        upper = min(scenario_upper, snapshot.joint_upper_rad[index])
        if lower >= upper:
            raise MeasuredTrajectoryScreeningError(
                f"calibrated and pinned bounds do not overlap for {reference_name}"
            )
        result[urdf_name] = (lower, upper)
    gripper = context.scenario.fixed_gripper_position.value
    if not snapshot.joint_lower_rad[5] <= gripper <= snapshot.joint_upper_rad[5]:
        raise MeasuredTrajectoryScreeningError(
            "fixed planner gripper position leaves calibrated gripper bounds"
        )
    return result


def _compatibility_blockers(snapshot: PlannerCalibrationSnapshot) -> list[str]:
    blockers: list[str] = []
    tool = snapshot.hand_T_tool
    if (
        not tool.rotation.almost_equal(Rotation3.identity(), absolute_tolerance=1e-6)
        or abs(tool.translation_mm.x) > 1e-6
        or abs(tool.translation_mm.y) > 1e-6
        or tool.translation_mm.z > 0.0
    ):
        blockers.append("GENERAL_G_T_T_NOT_SUPPORTED_BY_AXIAL_TCP_IK")
    normal = snapshot.board_T_device.rotation.apply(Vec3(0.0, 0.0, 1.0))
    alignment = max(-1.0, min(1.0, normal.dot(Vec3(0.0, 0.0, 1.0))))
    if math.acos(alignment) > 0.003:
        blockers.append("MEASURED_DEVICE_NORMAL_NOT_SUPPORTED_BY_BOARD_NORMAL_IK")
    return blockers


def _densify(
    start: Point3Mm,
    requested: list[tuple[MotionPhase, Point3Mm]],
    maximum_step_mm: float,
    maximum_waypoints: int,
    target_id: str,
) -> tuple[CartesianRouteWaypoint, ...]:
    result: list[CartesianRouteWaypoint] = []
    previous = start
    for requested_index, (phase, destination) in enumerate(requested):
        delta = (
            destination.x - previous.x,
            destination.y - previous.y,
            destination.z - previous.z,
        )
        distance = math.sqrt(sum(component * component for component in delta))
        subdivisions = max(1, math.ceil(distance / maximum_step_mm))
        for subdivision in range(1, subdivisions + 1):
            ratio = subdivision / subdivisions
            point = Point3Mm(
                "board",
                previous.x + ratio * delta[0],
                previous.y + ratio * delta[1],
                previous.z + ratio * delta[2],
            )
            prior = start if not result else result[-1].point_board
            local_distance = math.sqrt(
                (point.x - prior.x) ** 2
                + (point.y - prior.y) ** 2
                + (point.z - prior.z) ** 2
            )
            result.append(
                CartesianRouteWaypoint(
                    sequence=len(result),
                    phase=(
                        MotionPhase.TRANSIT
                        if requested_index == 0 and subdivision < subdivisions
                        else phase
                    ),
                    action_index=0,
                    semantic_target=target_id,
                    point_board=point,
                    distance_from_previous_mm=local_distance,
                    source_geometric_sequence=requested_index,
                    source_check_id=None,
                    source_path_check_passed=True,
                    inherited_collision_ids=(),
                    phase_endpoint=subdivision == subdivisions,
                )
            )
            if len(result) > maximum_waypoints:
                raise MeasuredTrajectoryScreeningError(
                    "densified route exceeds waypoint cap"
                )
        previous = destination
    return tuple(result)


def screen_measured_trajectory(
    proposal: ModelMotionProposal,
    context: SimulationContext,
    snapshot: PlannerCalibrationSnapshot,
    reprojection: Mapping[str, Any],
    *,
    observed_start_state: ObservedPlannerStartState | None = None,
    evaluation_monotonic_ns: int | None = None,
    policy: TrajectorySimulationPolicy | None = None,
) -> dict[str, Any]:
    """Screen one measured route, retaining every blocker and generating no commands."""

    if not isinstance(proposal, ModelMotionProposal):
        raise TypeError("proposal must be a ModelMotionProposal")
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    if not isinstance(snapshot, PlannerCalibrationSnapshot):
        raise TypeError("snapshot must be a PlannerCalibrationSnapshot")
    revalidate_simulation_context(context)
    if (
        snapshot.manifest_id != context.snapshot.manifest_id
        or snapshot.active_build_id != context.snapshot.active_build_id
    ):
        raise MeasuredTrajectoryScreeningError(
            "calibration snapshot build identity does not match the active context"
        )
    document = _verify_reprojection(reprojection)
    if (
        document.get("proposal_sha256") != proposal.proposal_sha256
        or document.get("calibration_snapshot_sha256") != snapshot.snapshot_sha256
        or document.get("target_catalog_sha256") != context.targets.content_sha256
    ):
        raise MeasuredTrajectoryScreeningError(
            "reprojection lineage does not match inputs"
        )
    expected = reproject_measured_target(
        proposal,
        context.targets,
        snapshot,
        model_motion_candidate_sha256=document["model_motion_candidate_sha256"],
    )
    if expected != document:
        raise MeasuredTrajectoryScreeningError(
            "reprojection does not replay deterministically"
        )

    selected_policy = policy or TrajectorySimulationPolicy(
        maximum_cartesian_step_mm=15.0,
        maximum_refinement_rounds=0,
        maximum_total_ik_solves=256,
    )
    if not isinstance(selected_policy, TrajectorySimulationPolicy):
        raise TypeError("policy must be a TrajectorySimulationPolicy")
    collision = assess_current_collision_readiness(context)
    blockers = _compatibility_blockers(snapshot)
    if not collision.geometry_audit.diagnostic_ready:
        blockers.append("FULL_COLLISION_GEOMETRY_INCOMPLETE")
    else:
        blockers.append("CONTINUOUS_FULL_BODY_COLLISION_SWEEP_NOT_IMPLEMENTED")

    bounds = _planner_bounds(context, snapshot)
    observed = _observed_state(
        observed_start_state, snapshot, evaluation_monotonic_ns, bounds
    )
    if observed is None:
        blockers.append("FRESH_OBSERVED_START_JOINT_STATE_REQUIRED")

    waypoints: tuple[CartesianRouteWaypoint, ...] = ()
    results: list[dict[str, Any]] = []
    ik_executed = False
    ik_all_accepted = False
    if observed is not None and not any(
        item.endswith("NOT_SUPPORTED_BY_AXIAL_TCP_IK")
        or item.endswith("NOT_SUPPORTED_BY_BOARD_NORMAL_IK")
        for item in blockers
    ):
        model = load_pinned_urdf(
            context.scenario.model_path, context.scenario.model_sha256
        ).model
        board_T_world = RigidTransform(
            "board",
            "world",
            snapshot.board_T_vendor_world.rotation,
            snapshot.board_T_vendor_world.translation_mm,
        )
        options = IkOptions(
            max_attempts=context.scenario.ik_policy.max_attempts,
            max_iterations_per_attempt=(
                context.scenario.ik_policy.max_iterations_per_attempt
            ),
        )
        solver = RoArmM3NumericalIk(
            model=model,
            board_T_world=board_T_world,
            hand_tcp_to_tip_z_mm=snapshot.hand_T_tool.translation_mm.z,
            fixed_gripper_position=context.scenario.fixed_gripper_position,
            ready_arm_joint_positions={
                name: JointPosition.radians(value) for name, value in observed.items()
            },
            gripper_bounds_rad=context.scenario.controller_gripper_intersection_rad,
            options=options,
            joint_bounds_rad=bounds,
        )
        requested: list[tuple[MotionPhase, Point3Mm]] = []
        for item in document["requested_waypoints"]:
            if not isinstance(item, Mapping) or set(item) != {"phase", "point_mm"}:
                raise MeasuredTrajectoryScreeningError("waypoint schema is invalid")
            try:
                phase = _PHASES[item["phase"]]
            except (KeyError, TypeError) as exc:
                raise MeasuredTrajectoryScreeningError(
                    "waypoint phase is invalid"
                ) from exc
            requested.append((phase, _point_from_document(item["point_mm"])))
        first_target = BoardToolTipTarget(requested[0][1])
        typed_observed = {
            name: JointPosition.radians(value) for name, value in observed.items()
        }
        start = solver.evaluate(first_target, typed_observed).tip_position_board_mm
        waypoints = _densify(
            start,
            requested,
            selected_policy.maximum_cartesian_step_mm,
            selected_policy.maximum_waypoints_per_round,
            proposal.target_id,
        )
        previous = dict(observed)
        ik_executed = True
        for waypoint in waypoints:
            solved = solver.solve(
                BoardToolTipTarget(waypoint.point_board),
                seed_joint_positions=(
                    {
                        name: JointPosition.radians(value)
                        for name, value in previous.items()
                    },
                ),
            )
            evaluated = evaluate_joint_trajectory_solution(
                waypoint, solved, solver, bounds, previous, selected_policy
            )
            results.append(evaluated.to_dict())
            if not evaluated.accepted:
                blockers.append(f"IK_ROUTE_REJECTED:{evaluated.failure_reason}")
                break
            previous = dict(evaluated.solution_arm_joint_positions_rad)
        ik_all_accepted = len(results) == len(waypoints) and all(
            item["accepted"] for item in results
        )

    if observed is None:
        status = "BLOCKED_OBSERVED_START_STATE_REQUIRED"
        next_stage = "CAPTURE_FRESH_OBSERVED_START_JOINT_STATE"
    elif not ik_all_accepted:
        status = "BLOCKED_DETERMINISTIC_IK_OR_CONTINUITY"
        next_stage = "CORRECT_IK_OR_ROUTE_CONTINUITY"
    else:
        status = "BLOCKED_FULL_ROUTE_COLLISION_SCREENING_REQUIRED"
        next_stage = "COMPLETE_COLLISION_GEOMETRY_AND_CONTINUOUS_SWEEP"

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "proposal_sha256": proposal.proposal_sha256,
        "reprojection_sha256": document["reprojection_sha256"],
        "calibration_snapshot_sha256": snapshot.snapshot_sha256,
        "build_snapshot_sha256": context.snapshot.snapshot_hash,
        "kinematic_model_sha256": context.scenario.model_sha256,
        "policy": {
            **selected_policy.to_dict(),
            "policy_hash": selected_policy.policy_hash,
        },
        "observed_start_state_sha256": (
            None
            if observed_start_state is None
            else observed_start_state.observed_start_state_sha256
        ),
        "observed_start_joint_positions_rad": observed,
        "waypoints": [item.to_dict() for item in waypoints],
        "joint_results": results,
        "ik_executed": ik_executed,
        "ik_all_waypoints_accepted": ik_all_accepted,
        "sampled_joint_continuity_checked": ik_executed,
        "collision_readiness_sha256": collision.report_hash,
        "collision_readiness_status": collision.status,
        "full_collision_screen_executed": False,
        "continuous_collision_proven": False,
        "blockers": list(dict.fromkeys(blockers)),
        "next_required_stage": next_stage,
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {
        **report,
        "trajectory_screening_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }
