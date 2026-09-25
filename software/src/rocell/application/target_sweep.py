"""Exhaustive nominal target/phase/tool IK screening.

Unlike the path sampler used for quick per-text simulation, this service can
evaluate every mapped keyboard and phone target.  Results remain screening
evidence: each point is solved independently, so no branch-continuous path,
collision-free robot-link sweep, or controller command is implied.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Iterable

from rocell.geometry import Point3Mm
from rocell.kinematics import BoardToolTipTarget, IkOptions, RoArmM3NumericalIk
from rocell.simulation import VirtualToolCase
from rocell.targets import TargetRegion

from .context import SimulationContext, revalidate_simulation_context
from ._pinned_model import (
    MAX_PINNED_URDF_BYTES,
    PinnedModelLoadError,
    load_pinned_urdf,
)


class SweepPhase(str, Enum):
    CONTACT = "contact"
    APPROACH = "approach"
    HOVER = "hover"
    TRANSIT = "transit"


@dataclass(frozen=True, slots=True)
class TargetSweepResult:
    device: str
    target_id: str
    phase: SweepPhase
    tool_case_id: str
    tip_position_board: Point3Mm
    status: str
    accepted: bool
    urdf_converged: bool
    controller_intersection_pass: bool
    position_error_mm: float
    alignment_error_rad: float
    attempt_count: int
    selected_attempt_index: int
    solution_arm_joint_positions_rad: tuple[tuple[str, float], ...]
    minimum_effective_joint_margin_rad: float | None

    def to_dict(self) -> dict[str, Any]:
        point = self.tip_position_board
        return {
            "device": self.device,
            "target_id": self.target_id,
            "phase": self.phase.value,
            "tool_case_id": self.tool_case_id,
            "tip_position_board_mm": {
                "frame": point.frame,
                "x": point.x,
                "y": point.y,
                "z": point.z,
            },
            "status": self.status,
            "accepted": self.accepted,
            "urdf_converged": self.urdf_converged,
            "controller_intersection_pass": self.controller_intersection_pass,
            "position_error_mm": self.position_error_mm,
            "alignment_error_rad": self.alignment_error_rad,
            "attempt_count": self.attempt_count,
            "selected_attempt_index": self.selected_attempt_index,
            "solution_arm_joint_positions_rad": dict(
                self.solution_arm_joint_positions_rad
            ),
            "minimum_effective_joint_margin_rad": self.minimum_effective_joint_margin_rad,
            "hardware_commands_generated": 0,
        }


@dataclass(frozen=True, slots=True)
class ParkSweepResult:
    """Initial/final Cartesian park reachability for one virtual tool case."""

    tool_case_id: str
    tip_position_board: Point3Mm
    status: str
    accepted: bool
    position_error_mm: float
    alignment_error_rad: float
    attempt_count: int
    selected_attempt_index: int
    solution_arm_joint_positions_rad: tuple[tuple[str, float], ...]
    minimum_effective_joint_margin_rad: float | None

    def to_dict(self) -> dict[str, Any]:
        point = self.tip_position_board
        return {
            "phase": "park",
            "role": "REQUIRED_INITIAL_AND_FINAL_ROUTE_POSE",
            "tool_case_id": self.tool_case_id,
            "tip_position_board_mm": {
                "frame": point.frame,
                "x": point.x,
                "y": point.y,
                "z": point.z,
            },
            "status": self.status,
            "accepted": self.accepted,
            "position_error_mm": self.position_error_mm,
            "alignment_error_rad": self.alignment_error_rad,
            "attempt_count": self.attempt_count,
            "selected_attempt_index": self.selected_attempt_index,
            "solution_arm_joint_positions_rad": dict(
                self.solution_arm_joint_positions_rad
            ),
            "minimum_effective_joint_margin_rad": self.minimum_effective_joint_margin_rad,
            "hardware_commands_generated": 0,
        }


@dataclass(frozen=True, slots=True)
class TargetSweepReport:
    """Deterministic independent-pose IK screen across targets, phases, and tools."""

    snapshot_hash: str
    simulation_bundle_id: str
    simulation_bundle_sha256: str
    hardware_profile_hash: str
    target_profile_sha256: str
    model_sha256: str
    loaded_model_sha256: str | None
    loaded_model_bytes: int | None
    alignment_status: str
    alignment_report_hash: str
    alignment_passed: bool
    scene_source_hashes: tuple[tuple[str, str], ...]
    board_transform_state: str
    board_transform_row_major: tuple[float, ...]
    path_policy: tuple[tuple[str, Any], ...]
    ik_policy: tuple[tuple[str, Any], ...]
    tool_cases: tuple[str, ...]
    phases: tuple[SweepPhase, ...]
    devices: tuple[str, ...]
    catalog_target_count: int
    selected_target_count: int
    complete_matrix: bool
    results: tuple[TargetSweepResult, ...]
    park_results: tuple[ParkSweepResult, ...]

    @property
    def accepted_count(self) -> int:
        return sum(result.accepted for result in self.results)

    @property
    def all_targets_accepted(self) -> bool:
        return bool(self.results) and self.accepted_count == len(self.results)

    @property
    def all_park_accepted(self) -> bool:
        return bool(self.park_results) and all(result.accepted for result in self.park_results)

    @property
    def all_accepted(self) -> bool:
        return self.alignment_passed and self.all_targets_accepted and self.all_park_accepted

    @property
    def status(self) -> str:
        if not self.alignment_passed:
            return "BLOCKED_PLACEMAT_ALIGNMENT"
        if not self.all_accepted:
            return "FEASIBILITY_GAPS_REPORTED"
        return "PASS_COMPLETE_MATRIX" if self.complete_matrix else "PASS_SELECTED_MATRIX"

    def _group_summary(self) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for tool_case in self.tool_cases:
            for device in self.devices:
                for phase in self.phases:
                    selected = tuple(
                        result
                        for result in self.results
                        if result.tool_case_id == tool_case
                        and result.device == device
                        and result.phase is phase
                    )
                    groups.append(
                        {
                            "tool_case_id": tool_case,
                            "device": device,
                            "phase": phase.value,
                            "accepted": sum(result.accepted for result in selected),
                            "total": len(selected),
                        }
                    )
        return groups

    def to_dict(self) -> dict[str, Any]:
        # Policy values are stored as recursively immutable tuples.  Build
        # fresh lists/dicts for JSON so callers cannot mutate report evidence
        # through a previously returned document.
        path_policy_document = dict(self.path_policy)
        park_xy = path_policy_document.get("park_xy_board_mm")
        if isinstance(park_xy, tuple):
            path_policy_document["park_xy_board_mm"] = list(park_xy)
        ik_policy_document = dict(self.ik_policy)
        joint_bounds = ik_policy_document.get("joint_bounds")
        if isinstance(joint_bounds, tuple):
            ik_policy_document["joint_bounds"] = {
                name: list(bounds) for name, bounds in joint_bounds
            }
        ready_arm = ik_policy_document.get("ready_arm_joint_positions_rad")
        if isinstance(ready_arm, tuple):
            ik_policy_document["ready_arm_joint_positions_rad"] = dict(ready_arm)
        gripper_bounds = ik_policy_document.get("gripper_model_bounds_rad")
        if isinstance(gripper_bounds, tuple):
            ik_policy_document["gripper_model_bounds_rad"] = list(gripper_bounds)
        return {
            "schema": "rocell.target_feasibility_sweep.v2",
            "status": self.status,
            "simulation_only": True,
            "required_for_physical_release": False,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "snapshot_hash": self.snapshot_hash,
            "simulation_bundle_id": self.simulation_bundle_id,
            "simulation_bundle_sha256": self.simulation_bundle_sha256,
            "hardware_profile_hash": self.hardware_profile_hash,
            "target_profile_sha256": self.target_profile_sha256,
            "model_sha256": self.model_sha256,
            "loaded_model": {
                "used": self.loaded_model_sha256 is not None,
                "sha256": self.loaded_model_sha256,
                "byte_count": self.loaded_model_bytes,
                "maximum_bytes": MAX_PINNED_URDF_BYTES,
            },
            "placemat_alignment": {
                "status": self.alignment_status,
                "report_hash": self.alignment_report_hash,
                "passed": self.alignment_passed,
            },
            "scene_source_hashes": dict(self.scene_source_hashes),
            "effective_scenario": {
                "board_transform_state": self.board_transform_state,
                "board_transform_row_major": list(self.board_transform_row_major),
                "path_policy": path_policy_document,
                "ik_policy": ik_policy_document,
            },
            "tool_cases": list(self.tool_cases),
            "phases": [phase.value for phase in self.phases],
            "devices": list(self.devices),
            "catalog_target_count": self.catalog_target_count,
            "selected_target_count": self.selected_target_count,
            "complete_matrix": self.complete_matrix,
            "accepted_count": self.accepted_count,
            "total_count": len(self.results),
            "all_targets_accepted": self.all_targets_accepted,
            "park_accepted_count": sum(result.accepted for result in self.park_results),
            "park_total_count": len(self.park_results),
            "all_park_accepted": self.all_park_accepted,
            "all_accepted": self.all_accepted,
            "summary": self._group_summary(),
            "results": [result.to_dict() for result in self.results],
            "park_results": [result.to_dict() for result in self.park_results],
            "limitations": [
                "Targets and device surfaces are synthetic nominal seeds, not measured calibration.",
                "Each point is solved independently; joint-branch continuity and swept-link collision are not tested.",
                "The board-to-vendor-world transform and tool offsets are scenario assumptions.",
                "Accepted solutions satisfy the URDF solver and provisional controller/URDF joint intersection only.",
                "Robot-link, holder, arm-mounted camera, moving cable, tool-volume, fixture-aperture, and self-collision sweeps are not modeled.",
            ],
        }

    @property
    def report_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _tip_point(
    target: TargetRegion,
    phase: SweepPhase,
    *,
    transit_z_mm: float,
    approach_height_mm: float,
    hover_height_mm: float,
    contact_overtravel_mm: float,
) -> Point3Mm:
    offsets = {
        SweepPhase.CONTACT: -contact_overtravel_mm,
        SweepPhase.APPROACH: approach_height_mm,
        SweepPhase.HOVER: hover_height_mm,
    }
    z = transit_z_mm if phase is SweepPhase.TRANSIT else target.center.z + offsets[phase]
    return Point3Mm("board", target.center.x, target.center.y, z)


def _selected_targets(
    context: SimulationContext,
    devices: tuple[str, ...],
    target_ids: tuple[str, ...] | None,
) -> tuple[TargetRegion, ...]:
    result: list[TargetRegion] = []
    if "keyboard" in devices:
        result.extend(context.targets.keyboard_targets.values())
    if "phone" in devices:
        result.extend(context.targets.phone_targets.values())
    available = tuple(sorted(result, key=lambda target: (target.device, target.target_id)))
    if target_ids is None:
        return available
    if not target_ids:
        raise ValueError("target_ids cannot be empty when supplied")
    available_ids = {target.target_id for target in available}
    unknown = tuple(target_id for target_id in target_ids if target_id not in available_ids)
    if unknown:
        raise ValueError(f"Unknown targets for selected devices: {unknown}")
    selected_ids = set(target_ids)
    return tuple(target for target in available if target.target_id in selected_ids)


def _selected_tool_cases(
    context: SimulationContext,
    case_ids: tuple[str, ...],
) -> tuple[VirtualToolCase, ...]:
    by_id = {case.case_id: case for case in context.scenario.tool_cases}
    missing = tuple(case_id for case_id in case_ids if case_id not in by_id)
    if missing:
        raise ValueError(f"Unknown tool cases: {missing}")
    return tuple(by_id[case_id] for case_id in case_ids)


def _complete_matrix_requested(
    *,
    selected_devices: tuple[str, ...],
    selected_case_ids: tuple[str, ...],
    all_case_ids: tuple[str, ...],
    selected_phases: tuple[SweepPhase, ...],
    selected_target_count: int,
    catalog_target_count: int,
) -> bool:
    """Return true only when no device, tool, phase, or target was omitted."""

    return (
        set(selected_devices) == {"keyboard", "phone"}
        and set(selected_case_ids) == set(all_case_ids)
        and set(selected_phases) == set(SweepPhase)
        and selected_target_count == catalog_target_count
    )


def run_target_sweep(
    context: SimulationContext,
    *,
    devices: Iterable[str],
    tool_case_ids: Iterable[str],
    phases: Iterable[SweepPhase],
    target_ids: Iterable[str] | None = None,
) -> TargetSweepReport:
    """Run independent target-point IK for the requested locked-catalog subset."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    selected_devices = tuple(dict.fromkeys(devices))
    if not selected_devices or any(device not in {"keyboard", "phone"} for device in selected_devices):
        raise ValueError("devices must contain keyboard and/or phone")
    selected_phases = tuple(dict.fromkeys(SweepPhase(phase) for phase in phases))
    if not selected_phases:
        raise ValueError("at least one sweep phase is required")
    selected_case_ids = tuple(dict.fromkeys(tool_case_ids))
    if not selected_case_ids:
        raise ValueError("at least one tool case is required")
    selected_target_ids = (
        None if target_ids is None else tuple(dict.fromkeys(target_ids))
    )
    tool_cases = _selected_tool_cases(context, selected_case_ids)
    targets = _selected_targets(context, selected_devices, selected_target_ids)
    scenario = context.scenario
    highest_obstacle_z = max(obstacle.maximum.z for obstacle in context.scene.obstacles)
    transit_z = (
        highest_obstacle_z
        + scenario.path_policy.clearance_above_highest_obstacle_mm
    )
    options = IkOptions(
        max_attempts=scenario.ik_policy.max_attempts,
        max_iterations_per_attempt=scenario.ik_policy.max_iterations_per_attempt,
    )
    results: list[TargetSweepResult] = []
    park_results: list[ParkSweepResult] = []
    loaded_model_sha256: str | None = None
    loaded_model_bytes: int | None = None
    if context.alignment.all_checks_pass:
        try:
            loaded_model = load_pinned_urdf(
                scenario.model_path,
                scenario.model_sha256,
            )
        except PinnedModelLoadError as exc:
            raise ValueError(f"Could not load pinned sweep model: {exc}") from exc
        model = loaded_model.model
        loaded_model_sha256 = loaded_model.sha256
        loaded_model_bytes = loaded_model.byte_count
        for tool_case in tool_cases:
            solver = RoArmM3NumericalIk(
                model=model,
                board_T_world=scenario.board_T_world,
                hand_tcp_to_tip_z_mm=tool_case.hand_tcp_to_tip_z_mm,
                fixed_gripper_position=scenario.fixed_gripper_position,
                ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
                gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
                options=options,
                joint_bounds_rad=scenario.controller_joint_intersection_rad,
            )

            park_x, park_y = scenario.path_policy.park_xy_board_mm
            park_point = Point3Mm("board", park_x, park_y, transit_z)
            park_solved = solver.solve(BoardToolTipTarget(park_point))
            park_solution = {
                position.name: position.position.value
                for position in park_solved.solution_arm_joint_positions
            }
            park_controller_ok = park_solved.converged and all(
                lower <= park_solution[name] <= upper
                for name, (lower, upper) in scenario.controller_joint_intersection_rad.items()
            )
            park_margin = (
                min(
                    min(value - scenario.controller_joint_intersection_rad[name][0],
                        scenario.controller_joint_intersection_rad[name][1] - value)
                    for name, value in park_solution.items()
                )
                if park_solution
                else None
            )
            park_results.append(
                ParkSweepResult(
                    tool_case_id=tool_case.case_id,
                    tip_position_board=park_point,
                    status=(
                        park_solved.status.value
                        if park_controller_ok or not park_solved.converged
                        else "INTERNAL_CONTROLLER_INTERSECTION_REJECTED"
                    ),
                    accepted=park_solved.converged and park_controller_ok,
                    position_error_mm=park_solved.residual.position_error_mm,
                    alignment_error_rad=park_solved.residual.alignment_error_rad,
                    attempt_count=len(park_solved.attempts),
                    selected_attempt_index=park_solved.selected_attempt_index,
                    solution_arm_joint_positions_rad=tuple(park_solution.items()),
                    minimum_effective_joint_margin_rad=park_margin,
                )
            )

            for target in targets:
                for phase in selected_phases:
                    point = _tip_point(
                        target,
                        phase,
                        transit_z_mm=transit_z,
                        approach_height_mm=scenario.path_policy.approach_height_mm,
                        hover_height_mm=scenario.path_policy.hover_height_mm,
                        contact_overtravel_mm=scenario.path_policy.contact_overtravel_mm,
                    )
                    solved = solver.solve(BoardToolTipTarget(point))
                    solution = {
                        position.name: position.position.value
                        for position in solved.solution_arm_joint_positions
                    }
                    controller_ok = solved.converged and all(
                        lower <= solution[name] <= upper
                        for name, (lower, upper) in scenario.controller_joint_intersection_rad.items()
                    )
                    accepted = solved.converged and controller_ok
                    minimum_margin = (
                        min(
                            min(
                                value - scenario.controller_joint_intersection_rad[name][0],
                                scenario.controller_joint_intersection_rad[name][1] - value,
                            )
                            for name, value in solution.items()
                        )
                        if solution
                        else None
                    )
                    results.append(
                        TargetSweepResult(
                            device=target.device,
                            target_id=target.target_id,
                            phase=phase,
                            tool_case_id=tool_case.case_id,
                            tip_position_board=point,
                            status=(
                                solved.status.value
                                if controller_ok or not solved.converged
                                else "INTERNAL_CONTROLLER_INTERSECTION_REJECTED"
                            ),
                            accepted=accepted,
                            urdf_converged=solved.converged,
                            controller_intersection_pass=controller_ok,
                            position_error_mm=solved.residual.position_error_mm,
                            alignment_error_rad=solved.residual.alignment_error_rad,
                            attempt_count=len(solved.attempts),
                            selected_attempt_index=solved.selected_attempt_index,
                            solution_arm_joint_positions_rad=tuple(solution.items()),
                            minimum_effective_joint_margin_rad=minimum_margin,
                        )
                    )
    catalog_target_count = (
        len(context.targets.keyboard_targets) + len(context.targets.phone_targets)
    )
    complete_matrix = _complete_matrix_requested(
        selected_devices=selected_devices,
        selected_case_ids=selected_case_ids,
        all_case_ids=tuple(case.case_id for case in scenario.tool_cases),
        selected_phases=selected_phases,
        selected_target_count=len(targets),
        catalog_target_count=catalog_target_count,
    )
    transform = scenario.board_T_world.to_transform()
    path_policy = scenario.path_policy
    ik_policy = scenario.ik_policy
    return TargetSweepReport(
        snapshot_hash=context.snapshot.snapshot_hash,
        simulation_bundle_id=context.bundle_lock.bundle_id,
        simulation_bundle_sha256=context.bundle_lock.source_lock_sha256,
        hardware_profile_hash=context.hardware_profile.profile_hash,
        target_profile_sha256=context.targets.content_sha256,
        model_sha256=scenario.model_sha256,
        loaded_model_sha256=loaded_model_sha256,
        loaded_model_bytes=loaded_model_bytes,
        alignment_status=context.alignment.status,
        alignment_report_hash=context.alignment.report_hash,
        alignment_passed=context.alignment.all_checks_pass,
        scene_source_hashes=tuple(sorted(context.scene.source_hashes.items())),
        board_transform_state=scenario.board_T_world_state,
        board_transform_row_major=transform.matrix,
        path_policy=(
            ("clearance_above_highest_obstacle_mm", path_policy.clearance_above_highest_obstacle_mm),
            ("segment_clearance_mm", path_policy.segment_clearance_mm),
            ("hover_height_mm", path_policy.hover_height_mm),
            ("approach_height_mm", path_policy.approach_height_mm),
            ("contact_overtravel_mm", path_policy.contact_overtravel_mm),
            ("park_xy_board_mm", tuple(path_policy.park_xy_board_mm)),
            ("transit_z_board_mm", transit_z),
        ),
        ik_policy=(
            ("sampling_policy", ik_policy.sampling_policy),
            ("maximum_samples", ik_policy.maximum_samples),
            ("max_attempts", ik_policy.max_attempts),
            ("max_iterations_per_attempt", ik_policy.max_iterations_per_attempt),
            (
                "joint_bounds",
                tuple(
                    (name, tuple(bounds))
                    for name, bounds in scenario.controller_joint_intersection_rad.items()
                ),
            ),
            (
                "ready_arm_joint_positions_rad",
                tuple(
                    (name, position.value)
                    for name, position in scenario.ready_arm_joint_positions_rad.items()
                ),
            ),
            ("fixed_gripper_position_rad", scenario.fixed_gripper_position.value),
            (
                "gripper_model_bounds_rad",
                tuple(scenario.controller_gripper_intersection_rad),
            ),
        ),
        tool_cases=selected_case_ids,
        phases=selected_phases,
        devices=selected_devices,
        catalog_target_count=catalog_target_count,
        selected_target_count=len(targets),
        complete_matrix=complete_matrix,
        results=tuple(results),
        park_results=tuple(park_results),
    )
