"""Bounded, deterministic reach-layout studies with zero hardware authority.

This module deliberately treats every candidate as a *study overlay* on a
freshly revalidated :class:`SimulationContext`.  It never replaces fields in
the canonical scenario.  Physical arm placement is entered as ``B_T_Ru``
(``Ru`` is the URDF ``base_link``); the solver transform is then derived as::

    B_T_Wv = B_T_Ru * inverse(Wv_T_Ru)

where ``Wv_T_Ru`` is read from the pinned URDF fixed joint.  This distinction
matters because the current model places ``base_link`` 70.1 mm above its
vendor-world root.

The optimizer is diagnostic only.  It evaluates independent contact and park
poses through the existing bounded IK solver and controller/URDF joint
intersection.  It performs no trajectory, collision-volume, payload,
singularity, camera, serial, or controller-command work.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import json
import math
from typing import Any, Iterable

from rocell import __version__
from rocell.geometry import (
    Point3Mm,
    RigidTransform,
    Rotation3,
    UrdfModel,
    Vec3,
)
from rocell.kinematics import BoardToolTipTarget, IkOptions, RoArmM3NumericalIk
from rocell.models.units import finite_real
from rocell.targets import TargetRegion

from ._pinned_model import PinnedModelLoadError, load_pinned_urdf
from .context import SimulationContext, revalidate_simulation_context


_MAX_STUDY_INPUTS = 25
_MAX_FINALISTS = 5
_MAX_PARK_POINTS = 16
_MAX_FULL_TARGETS = 75
_MAX_IK_ATTEMPTS = 8
_MAX_IK_ITERATIONS_PER_ATTEMPT = 200
_MAX_PLANNED_IK_SOLVES = 2_000
_MAX_PARK_Z_ABOVE_REQUIRED_MM = 300.0
_DEFAULT_YAW_DELTA_RAD = math.radians(8.0)


class ReachOptimizationError(ValueError):
    """A reach study request or canonical source contract is invalid."""


def _stable_hash(document: object) -> str:
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _axis(values: Iterable[object], label: str) -> tuple[float, ...]:
    result = tuple(
        sorted({finite_real(value, name=label) for value in values})
    )
    if not result:
        raise ReachOptimizationError(f"{label} cannot be empty")
    return result


@dataclass(frozen=True, slots=True)
class ReachStudyPolicy:
    """Explicit bounded search axes and numerical effort.

    ``rear_edge_to_base_axis_y_mm`` is the physical board-rear-edge to arm
    axis offset.  RC03 records that offset and yaw as unknown, so values here
    are hypotheses, not released mounting dimensions.
    """

    rear_clamp_contact_x_board_mm: tuple[float, ...]
    clamp_to_base_axis_x_mm: tuple[float, ...]
    rear_edge_to_base_axis_y_mm: tuple[float, ...]
    base_yaw_board_rad: tuple[float, ...]
    keyboard_tool_length_mm: tuple[float, ...]
    phone_tool_length_mm: tuple[float, ...]
    park_points_board_mm: tuple[tuple[float, float, float], ...]
    finalist_count: int = 2
    coarse_targets_per_device: int = 3
    minimum_normalized_arm_joint_margin: float = 0.01

    def __post_init__(self) -> None:
        for name in (
            "rear_clamp_contact_x_board_mm",
            "clamp_to_base_axis_x_mm",
            "rear_edge_to_base_axis_y_mm",
            "base_yaw_board_rad",
            "keyboard_tool_length_mm",
            "phone_tool_length_mm",
        ):
            object.__setattr__(self, name, _axis(getattr(self, name), name))
        parks: list[tuple[float, float, float]] = []
        for index, raw in enumerate(self.park_points_board_mm):
            if not isinstance(raw, (tuple, list)) or len(raw) != 3:
                raise ReachOptimizationError(
                    f"park_points_board_mm[{index}] must contain x, y, z"
                )
            parks.append(
                tuple(
                    finite_real(value, name=f"park_points_board_mm[{index}]")
                    for value in raw
                )  # type: ignore[arg-type]
            )
        canonical_parks = tuple(sorted(set(parks)))
        if not canonical_parks or len(canonical_parks) > _MAX_PARK_POINTS:
            raise ReachOptimizationError(
                f"park point count must be between 1 and {_MAX_PARK_POINTS}"
            )
        object.__setattr__(self, "park_points_board_mm", canonical_parks)
        for name, upper in (
            ("finalist_count", _MAX_FINALISTS),
            ("coarse_targets_per_device", 8),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= upper:
                raise ReachOptimizationError(f"{name} must be an integer in [1, {upper}]")
        minimum_margin = finite_real(
            self.minimum_normalized_arm_joint_margin,
            name="minimum_normalized_arm_joint_margin",
        )
        if not 0.0 < minimum_margin < 0.5:
            raise ReachOptimizationError(
                "minimum_normalized_arm_joint_margin must be in (0, 0.5)"
            )
        object.__setattr__(self, "minimum_normalized_arm_joint_margin", minimum_margin)
        if any(length < 0.0 or length > 150.0 for length in self.keyboard_tool_length_mm):
            raise ReachOptimizationError("keyboard tool lengths must be in [0, 150] mm")
        if any(length < 0.0 or length > 150.0 for length in self.phone_tool_length_mm):
            raise ReachOptimizationError("phone tool lengths must be in [0, 150] mm")
        count = (
            len(self.rear_clamp_contact_x_board_mm)
            * len(self.clamp_to_base_axis_x_mm)
            * len(self.rear_edge_to_base_axis_y_mm)
            * len(self.base_yaw_board_rad)
            * len(self.keyboard_tool_length_mm)
            * len(self.phone_tool_length_mm)
        )
        if count > _MAX_STUDY_INPUTS:
            raise ReachOptimizationError(
                f"study grid has {count} inputs; maximum is {_MAX_STUDY_INPUTS}"
            )

    @property
    def study_input_count(self) -> int:
        return (
            len(self.rear_clamp_contact_x_board_mm)
            * len(self.clamp_to_base_axis_x_mm)
            * len(self.rear_edge_to_base_axis_y_mm)
            * len(self.base_yaw_board_rad)
            * len(self.keyboard_tool_length_mm)
            * len(self.phone_tool_length_mm)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": "BOUNDED_COARSE_THEN_FULL_FINALISTS_V1",
            "fixed_planar_assumptions": {
                "base_link_z": "canonical B_T_Ru Z derived from the pinned scenario and Wv_T_Ru",
                "base_roll_rad": 0.0,
                "base_pitch_rad": 0.0,
                "physical_status": "UNMEASURED_STUDY_ASSUMPTIONS",
            },
            "rear_clamp_contact_x_board_mm": list(
                self.rear_clamp_contact_x_board_mm
            ),
            "clamp_to_base_axis_x_mm": list(self.clamp_to_base_axis_x_mm),
            "rear_edge_to_base_axis_y_mm": list(
                self.rear_edge_to_base_axis_y_mm
            ),
            "base_yaw_board_rad": list(self.base_yaw_board_rad),
            "keyboard_tool_length_mm": list(self.keyboard_tool_length_mm),
            "phone_tool_length_mm": list(self.phone_tool_length_mm),
            "park_points_board_mm": [list(point) for point in self.park_points_board_mm],
            "finalist_count": self.finalist_count,
            "coarse_targets_per_device": self.coarse_targets_per_device,
            "minimum_normalized_arm_joint_margin": self.minimum_normalized_arm_joint_margin,
            "margin_scope": {
                "gated_joints": "five IK arm joints",
                "fixed_gripper_excluded": True,
                "reason": "gripper is fixed and does not affect hand_tcp reach kinematics",
            },
            "maximum_study_inputs": _MAX_STUDY_INPUTS,
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReachStudyInput:
    """One physical placement/tool hypothesis and its derived solver frame."""

    rear_clamp_contact_x_board_mm: float
    clamp_to_base_axis_x_mm: float
    base_axis_x_board_mm: float
    rear_edge_to_base_axis_y_mm: float
    base_link_z_board_mm: float
    base_yaw_board_rad: float
    keyboard_tool_length_mm: float
    phone_tool_length_mm: float
    board_T_base_link: RigidTransform
    board_T_vendor_world: RigidTransform

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_input_id": self.study_input_id,
            "physical_placement_input": {
                "transform": "B_T_Ru",
                "ru_frame": "base_link",
                "rear_clamp_contact_x_board_mm": self.rear_clamp_contact_x_board_mm,
                "clamp_to_base_axis_x_mm": self.clamp_to_base_axis_x_mm,
                "base_axis_x_board_mm": self.base_axis_x_board_mm,
                "rear_edge_to_base_axis_y_mm": self.rear_edge_to_base_axis_y_mm,
                "base_link_z_board_mm": self.base_link_z_board_mm,
                "base_yaw_board_rad": self.base_yaw_board_rad,
                "matrix_row_major": list(self.board_T_base_link.to_transform().matrix),
            },
            "derived_solver_transform": {
                "transform": "B_T_Wv",
                "wv_frame": "world",
                "derivation": "B_T_Ru * inverse(Wv_T_Ru)",
                "matrix_row_major": list(
                    self.board_T_vendor_world.to_transform().matrix
                ),
            },
            "route_tool_lengths_mm": {
                "keyboard": self.keyboard_tool_length_mm,
                "phone": self.phone_tool_length_mm,
            },
            "canonical_context_modified": False,
            "physical_release_effect": "NONE",
        }

    @property
    def study_input_id(self) -> str:
        identity = {
            "clamp_x": self.rear_clamp_contact_x_board_mm,
            "clamp_to_axis_x": self.clamp_to_base_axis_x_mm,
            "x": self.base_axis_x_board_mm,
            "rear_y": self.rear_edge_to_base_axis_y_mm,
            "z": self.base_link_z_board_mm,
            "yaw": self.base_yaw_board_rad,
            "keyboard_tool": self.keyboard_tool_length_mm,
            "phone_tool": self.phone_tool_length_mm,
        }
        return f"reach-{_stable_hash(identity)[:16]}"


@dataclass(frozen=True, slots=True)
class PoseFeasibility:
    status: str
    accepted: bool
    position_error_mm: float
    alignment_error_rad: float
    minimum_arm_joint_margin_rad: float | None
    minimum_normalized_arm_joint_margin: float | None
    attempt_count: int
    selected_attempt_index: int
    solution_arm_joint_positions_rad: tuple[tuple[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "accepted": self.accepted,
            "position_error_mm": self.position_error_mm,
            "alignment_error_rad": self.alignment_error_rad,
            "minimum_arm_joint_margin_rad": self.minimum_arm_joint_margin_rad,
            "minimum_normalized_arm_joint_margin": self.minimum_normalized_arm_joint_margin,
            "attempt_count": self.attempt_count,
            "selected_attempt_index": self.selected_attempt_index,
            "solution_arm_joint_positions_rad": dict(
                self.solution_arm_joint_positions_rad
            ),
            "hardware_commands_generated": 0,
        }


@dataclass(frozen=True, slots=True)
class ContactPoseResult:
    device: str
    target_id: str
    tip_position_board: Point3Mm
    feasibility: PoseFeasibility

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "target_id": self.target_id,
            "tip_position_board_mm": [
                self.tip_position_board.x,
                self.tip_position_board.y,
                self.tip_position_board.z,
            ],
            **self.feasibility.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class FullContactEvaluation:
    study_input: ReachStudyInput
    outcomes: tuple[ContactPoseResult, ...]
    ik_solve_count: int

    def _device(self, device: str) -> tuple[ContactPoseResult, ...]:
        return tuple(row for row in self.outcomes if row.device == device)

    def accepted_count(self, device: str) -> int:
        return sum(row.feasibility.accepted for row in self._device(device))

    def total_count(self, device: str) -> int:
        return len(self._device(device))

    @property
    def all_contacts_accepted(self) -> bool:
        return bool(self.outcomes) and all(row.feasibility.accepted for row in self.outcomes)

    @property
    def minimum_normalized_arm_margin(self) -> float | None:
        margins = tuple(
            row.feasibility.minimum_normalized_arm_joint_margin
            for row in self.outcomes
            if row.feasibility.accepted
            and row.feasibility.minimum_normalized_arm_joint_margin is not None
        )
        return min(margins) if margins else None

    def to_dict(self) -> dict[str, Any]:
        coverage = {}
        for device in ("keyboard", "phone"):
            selected = self._device(device)
            accepted = self.accepted_count(device)
            coverage[device] = {
                "accepted": accepted,
                "total": len(selected),
                "fraction": accepted / len(selected),
                "rejected_target_ids": [
                    row.target_id for row in selected if not row.feasibility.accepted
                ],
            }
        return {
            "study_input_id": self.study_input.study_input_id,
            "coverage": coverage,
            "all_mandatory_contacts_accepted": self.all_contacts_accepted,
            "minimum_normalized_arm_joint_margin": self.minimum_normalized_arm_margin,
            "ik_solve_count": self.ik_solve_count,
            "outcomes": [row.to_dict() for row in self.outcomes],
        }


@dataclass(frozen=True, slots=True)
class CoarseReachEvaluation:
    """Auditable reduced-coverage evidence used only to select finalists."""

    study_input: ReachStudyInput
    keyboard_accepted: int
    keyboard_total: int
    phone_accepted: int
    phone_total: int
    rejected_target_ids: tuple[str, ...]
    evaluated_parks: tuple[ParkEvaluation, ...]
    park: ParkEvaluation
    minimum_normalized_arm_joint_margin: float | None
    ranking_key: tuple[Any, ...]
    ik_solve_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_input": self.study_input.to_dict(),
            "coverage": {
                "keyboard": {
                    "accepted": self.keyboard_accepted,
                    "total": self.keyboard_total,
                    "fraction": self.keyboard_accepted / self.keyboard_total,
                },
                "phone": {
                    "accepted": self.phone_accepted,
                    "total": self.phone_total,
                    "fraction": self.phone_accepted / self.phone_total,
                },
                "rejected_target_ids": list(self.rejected_target_ids),
            },
            "selected_park_id": self.park.park_id,
            "evaluated_parks": [park.to_dict() for park in self.evaluated_parks],
            "minimum_normalized_arm_joint_margin": self.minimum_normalized_arm_joint_margin,
            "ranking_key": list(self.ranking_key),
            "ik_solve_count": self.ik_solve_count,
            "finalist_selection_evidence_only": True,
        }


@dataclass(frozen=True, slots=True)
class ParkEvaluation:
    park_id: str
    point_board: Point3Mm
    geometry_valid: bool
    keyboard: PoseFeasibility | None
    phone: PoseFeasibility | None

    @property
    def accepted_route_count(self) -> int:
        return sum(
            result is not None and result.accepted
            for result in (self.keyboard, self.phone)
        )

    @property
    def all_routes_accepted(self) -> bool:
        return self.geometry_valid and self.accepted_route_count == 2

    @property
    def minimum_normalized_arm_margin(self) -> float | None:
        margins = tuple(
            result.minimum_normalized_arm_joint_margin
            for result in (self.keyboard, self.phone)
            if result is not None
            and result.accepted
            and result.minimum_normalized_arm_joint_margin is not None
        )
        return min(margins) if margins else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "park_id": self.park_id,
            "point_board_mm": [
                self.point_board.x,
                self.point_board.y,
                self.point_board.z,
            ],
            "geometry_valid": self.geometry_valid,
            "required_route_results": {
                "keyboard": None if self.keyboard is None else self.keyboard.to_dict(),
                "phone": None if self.phone is None else self.phone.to_dict(),
            },
            "accepted_route_count": self.accepted_route_count,
            "all_required_route_parks_accepted": self.all_routes_accepted,
        }


@dataclass(frozen=True, slots=True)
class RankedReachCandidate:
    rank: int
    study_input_id: str
    park_id: str
    keyboard_accepted: int
    keyboard_total: int
    phone_accepted: int
    phone_total: int
    park_routes_accepted: int
    mission_complete: bool
    minimum_normalized_arm_joint_margin: float | None
    normalized_deviation_from_nominal: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "study_input_id": self.study_input_id,
            "park_id": self.park_id,
            "hard_gates": {
                "keyboard_contacts": f"{self.keyboard_accepted}/{self.keyboard_total}",
                "phone_contacts": f"{self.phone_accepted}/{self.phone_total}",
                "route_parks": f"{self.park_routes_accepted}/2",
                "contact_and_park_diagnostic_complete": self.mission_complete,
            },
            "minimum_normalized_arm_joint_margin": self.minimum_normalized_arm_joint_margin,
            "normalized_deviation_from_nominal": self.normalized_deviation_from_nominal,
            "ranking_order": [
                "contact_and_park_diagnostic_complete",
                "accepted_route_parks",
                "minimum_device_coverage_fraction",
                "total_contacts_accepted",
                "minimum_normalized_arm_joint_margin",
                "minimum_nominal_deviation",
                "stable_study_ids",
            ],
            "execution_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class ReachOptimizationReport:
    source_provenance: tuple[tuple[str, Any], ...]
    policy: ReachStudyPolicy
    vendor_world_T_base_link: RigidTransform
    canonical_board_T_base_link: RigidTransform
    coarse_target_ids: tuple[str, ...]
    coarse_evaluations: tuple[CoarseReachEvaluation, ...]
    coarse_candidate_count: int
    coarse_ik_solve_count: int
    finalist_ids: tuple[str, ...]
    full_evaluations: tuple[FullContactEvaluation, ...]
    park_evaluations: tuple[tuple[str, ParkEvaluation], ...]
    ranked_candidates: tuple[RankedReachCandidate, ...]
    full_ik_solve_count: int
    planned_ik_solve_upper_bound: int

    @property
    def status(self) -> str:
        if self.ranked_candidates and self.ranked_candidates[0].mission_complete:
            return "CONTACT_AND_PARK_DIAGNOSTIC_COMPLETE_FINALIST_FOUND"
        return "CONTACT_AND_PARK_DIAGNOSTIC_NO_COMPLETE_FINALIST"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.reach_layout_optimization.v1",
            "status": self.status,
            "scope": "INDEPENDENT_CONTACT_AND_PARK_IK_DIAGNOSTIC_ONLY",
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
            "canonical_context_modified": False,
            "full_catalog_exhaustive_over_study_grid": False,
            "resource_bounds": {
                "maximum_study_inputs": _MAX_STUDY_INPUTS,
                "maximum_finalists": _MAX_FINALISTS,
                "maximum_park_points": _MAX_PARK_POINTS,
                "required_full_target_count": _MAX_FULL_TARGETS,
                "maximum_ik_attempts": _MAX_IK_ATTEMPTS,
                "maximum_iterations_per_attempt": _MAX_IK_ITERATIONS_PER_ATTEMPT,
                "maximum_planned_ik_solves": _MAX_PLANNED_IK_SOLVES,
                "planned_ik_solve_upper_bound": self.planned_ik_solve_upper_bound,
                "maximum_park_z_above_required_mm": _MAX_PARK_Z_ABOVE_REQUIRED_MM,
            },
            "source_provenance": dict(self.source_provenance),
            "policy": {**self.policy.to_dict(), "policy_hash": self.policy.policy_hash},
            "frame_derivation": {
                "formula": "B_T_Wv = B_T_Ru * inverse(Wv_T_Ru)",
                "vendor_world_T_base_link_row_major": list(
                    self.vendor_world_T_base_link.to_transform().matrix
                ),
                "canonical_board_T_base_link_row_major": list(
                    self.canonical_board_T_base_link.to_transform().matrix
                ),
            },
            "stages": {
                "coarse": {
                    "coverage_target_ids": list(self.coarse_target_ids),
                    "candidate_count": self.coarse_candidate_count,
                    "ik_solve_count": self.coarse_ik_solve_count,
                    "purpose": "bounded finalist selection only",
                    "evaluations": [
                        evaluation.to_dict()
                        for evaluation in self.coarse_evaluations
                    ],
                },
                "full": {
                    "finalist_ids": list(self.finalist_ids),
                    "full_catalog_contact_count": sum(
                        evaluation.total_count(device)
                        for device in ("keyboard", "phone")
                        for evaluation in self.full_evaluations[:1]
                    ),
                    "ik_solve_count": self.full_ik_solve_count,
                },
            },
            "study_inputs": [
                evaluation.study_input.to_dict()
                for evaluation in self.full_evaluations
            ],
            "full_contact_evaluations": [
                evaluation.to_dict() for evaluation in self.full_evaluations
            ],
            "park_evaluations": [
                {"study_input_id": study_id, **park.to_dict()}
                for study_id, park in self.park_evaluations
            ],
            "ranked_candidates": [row.to_dict() for row in self.ranked_candidates],
            "limitations": [
                "Every target and park is independent-pose IK screening; path continuity is not tested.",
                "No robot-link, camera-holder, cable, tool-volume, self-collision, payload, or force model is evaluated.",
                "Base-axis offset/yaw and tool lengths are hypothetical study inputs, not measured installation data.",
                "The rear clamp zone constrains contact X only; clamp-to-base-axis X/Y offsets remain unmeasured hypotheses.",
                "Base-link Z is fixed to canonical 70.1 mm and base roll/pitch are fixed to zero for this planar study.",
                "The normalized margin gate covers the five IK arm joints only; the fixed gripper is separately reported at its provisional lower bound and requires installed-tool/grip qualification.",
                "Coarse screening can omit a globally better candidate; only listed finalists receive the full catalog.",
                "No result authorizes physical motion or contact.",
            ],
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self.to_dict())


def default_reach_study_policy(context: SimulationContext) -> ReachStudyPolicy:
    """Return a small (18-input) reproducible coarse/finalist study policy."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    scenario = context.scenario
    nominal_x = scenario.board_T_world.translation_mm.x
    clamp_lower, clamp_upper = context.scene.arm_clamp_rear_edge_x_range_mm
    nominal_yaw = math.atan2(
        scenario.board_T_world.rotation.matrix[3],
        scenario.board_T_world.rotation.matrix[0],
    )
    nominal_tool = -scenario.hand_tcp_to_tip_z_mm
    highest_z = max(obstacle.maximum.z for obstacle in context.scene.obstacles)
    park_z = highest_z + scenario.path_policy.clearance_above_highest_obstacle_mm
    park_x, park_y = scenario.path_policy.park_xy_board_mm
    # Paired route axes make 3 x 3 x 2 = 18 inputs, below the hard cap.
    return ReachStudyPolicy(
        rear_clamp_contact_x_board_mm=(clamp_lower, nominal_x, clamp_upper),
        clamp_to_base_axis_x_mm=(0.0,),
        rear_edge_to_base_axis_y_mm=(0.0,),
        base_yaw_board_rad=(
            nominal_yaw - _DEFAULT_YAW_DELTA_RAD,
            nominal_yaw,
            nominal_yaw + _DEFAULT_YAW_DELTA_RAD,
        ),
        keyboard_tool_length_mm=(nominal_tool - 20.0, nominal_tool),
        phone_tool_length_mm=(nominal_tool,),
        park_points_board_mm=((park_x, park_y, park_z),),
        finalist_count=2,
        coarse_targets_per_device=3,
    )


def default_reach_study_inputs(
    context: SimulationContext,
) -> tuple[ReachStudyInput, ...]:
    """Enumerate the locked default placement grid without running any IK.

    This is useful for replaying a previously reported candidate by its
    content-derived ``study_input_id``. It revalidates the complete canonical
    context and the audited vendor-world/base-link offset, but it does not
    assert that any returned input remains highly ranked or feasible.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    if not context.alignment.all_checks_pass:
        raise ReachOptimizationError(
            "canonical placemat alignment must pass before enumerating reach inputs"
        )
    try:
        loaded_model = load_pinned_urdf(
            context.scenario.model_path,
            context.scenario.model_sha256,
        )
    except PinnedModelLoadError as exc:
        raise ReachOptimizationError(f"pinned URDF capture failed: {exc}") from exc
    return _default_reach_study_inputs_from_model(context, loaded_model.model)


def _default_reach_study_inputs_from_model(
    context: SimulationContext,
    model: UrdfModel,
) -> tuple[ReachStudyInput, ...]:
    """Enumerate the default grid from an already captured, verified model.

    This internal seam lets evidence-sensitive callers parse one bounded byte
    capture and reuse that exact :class:`UrdfModel`, instead of reopening a
    mutable path after canonical-context validation.  The public helper above
    retains its existing path-based API and validation behavior.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    if not isinstance(model, UrdfModel):
        raise TypeError("model must be an UrdfModel")
    if not context.alignment.all_checks_pass:
        raise ReachOptimizationError(
            "canonical placemat alignment must pass before enumerating reach inputs"
        )
    fixed = model.joint("world_to_base_link")
    if (
        fixed.joint_type != "fixed"
        or fixed.parent_link != "world"
        or fixed.child_link != "base_link"
    ):
        raise ReachOptimizationError("pinned URDF lost Wv_T_Ru fixed-joint contract")
    vendor_world_T_base_link = fixed.transform_at(None)
    if not math.isclose(
        vendor_world_T_base_link.translation_mm.z, 70.1, abs_tol=1e-9
    ):
        raise ReachOptimizationError("pinned Wv_T_Ru Z offset is not 70.1 mm")
    canonical_board_T_base_link = context.scenario.board_T_world.compose(
        vendor_world_T_base_link
    )
    return _study_inputs(
        context,
        default_reach_study_policy(context),
        vendor_world_T_base_link,
        canonical_board_T_base_link,
    )


def _target_catalog(context: SimulationContext) -> tuple[TargetRegion, ...]:
    return tuple(
        sorted(
            (
                *context.targets.keyboard_targets.values(),
                *context.targets.phone_targets.values(),
            ),
            key=lambda target: (target.device, target.target_id),
        )
    )


def _spatial_subset(
    targets: tuple[TargetRegion, ...], per_device: int
) -> tuple[TargetRegion, ...]:
    """Select spatially spread targets without relying on semantic names."""

    selected_all: list[TargetRegion] = []
    for device in ("keyboard", "phone"):
        available = tuple(target for target in targets if target.device == device)
        if not available:
            raise ReachOptimizationError(f"full target catalog has no {device} targets")
        selected = [min(available, key=lambda target: (target.center.x, target.center.y, target.target_id))]
        while len(selected) < min(per_device, len(available)):
            remaining = tuple(target for target in available if target not in selected)
            selected.append(
                max(
                    remaining,
                    key=lambda target: (
                        min(
                            (target.center.x - prior.center.x) ** 2
                            + (target.center.y - prior.center.y) ** 2
                            for prior in selected
                        ),
                        -target.center.x,
                        -target.center.y,
                        target.target_id,
                    ),
                )
            )
        selected_all.extend(selected)
    return tuple(sorted(selected_all, key=lambda target: (target.device, target.target_id)))


def _study_inputs(
    context: SimulationContext,
    policy: ReachStudyPolicy,
    vendor_world_T_base_link: RigidTransform,
    canonical_board_T_base_link: RigidTransform,
) -> tuple[ReachStudyInput, ...]:
    clamp_lower, clamp_upper = context.scene.arm_clamp_rear_edge_x_range_mm
    board_rear_y = context.scene.board.maximum.y
    nominal_yaw = math.atan2(
        canonical_board_T_base_link.rotation.matrix[3],
        canonical_board_T_base_link.rotation.matrix[0],
    )
    inputs: list[ReachStudyInput] = []
    for clamp_x, clamp_to_axis_x, rear_offset, yaw, keyboard_tool, phone_tool in product(
        policy.rear_clamp_contact_x_board_mm,
        policy.clamp_to_base_axis_x_mm,
        policy.rear_edge_to_base_axis_y_mm,
        policy.base_yaw_board_rad,
        policy.keyboard_tool_length_mm,
        policy.phone_tool_length_mm,
    ):
        if not clamp_lower <= clamp_x <= clamp_upper:
            raise ReachOptimizationError(
                f"rear clamp contact X {clamp_x:g} mm leaves RC03 zone [{clamp_lower:g}, {clamp_upper:g}]"
            )
        if not -100.0 <= clamp_to_axis_x <= 100.0:
            raise ReachOptimizationError(
                "clamp-to-base-axis X offset must remain in the unmeasured -100..100 mm study envelope"
            )
        if not 0.0 <= rear_offset <= 100.0:
            raise ReachOptimizationError(
                "rear-edge-to-base-axis offset must remain in the controlled 0..100 mm study envelope"
            )
        if abs(yaw - nominal_yaw) > math.radians(15.0) + 1e-12:
            raise ReachOptimizationError(
                "base yaw must remain within +/-15 degrees of the nominal study orientation"
            )
        base_axis_x = clamp_x + clamp_to_axis_x
        board_T_base_link = RigidTransform(
            "board",
            "base_link",
            Rotation3.from_rpy(0.0, 0.0, yaw),
            Vec3(
                base_axis_x,
                board_rear_y + rear_offset,
                canonical_board_T_base_link.translation_mm.z,
            ),
        )
        board_T_vendor_world = board_T_base_link.compose(
            vendor_world_T_base_link.inverse()
        )
        inputs.append(
            ReachStudyInput(
                rear_clamp_contact_x_board_mm=clamp_x,
                clamp_to_base_axis_x_mm=clamp_to_axis_x,
                base_axis_x_board_mm=base_axis_x,
                rear_edge_to_base_axis_y_mm=rear_offset,
                base_link_z_board_mm=board_T_base_link.translation_mm.z,
                base_yaw_board_rad=yaw,
                keyboard_tool_length_mm=keyboard_tool,
                phone_tool_length_mm=phone_tool,
                board_T_base_link=board_T_base_link,
                board_T_vendor_world=board_T_vendor_world,
            )
        )
    return tuple(sorted(inputs, key=lambda item: item.study_input_id))


class _CandidateEvaluator:
    """Cache repeated route/tool/point solves for one candidate and IK policy."""

    def __init__(
        self,
        context: SimulationContext,
        model: Any,
        study: ReachStudyInput,
        options: IkOptions,
        minimum_normalized_arm_joint_margin: float,
    ) -> None:
        self.context = context
        self.study = study
        self._model = model
        self._options = options
        self._minimum_normalized_arm_joint_margin = minimum_normalized_arm_joint_margin
        self._solvers: dict[float, RoArmM3NumericalIk] = {}
        self._cache: dict[tuple[float, float, float, float], PoseFeasibility] = {}

    @property
    def solve_count(self) -> int:
        return len(self._cache)

    def _solver(self, tool_length_mm: float) -> RoArmM3NumericalIk:
        if tool_length_mm not in self._solvers:
            scenario = self.context.scenario
            self._solvers[tool_length_mm] = RoArmM3NumericalIk(
                model=self._model,
                board_T_world=self.study.board_T_vendor_world,
                hand_tcp_to_tip_z_mm=-tool_length_mm,
                fixed_gripper_position=scenario.fixed_gripper_position,
                ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
                gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
                options=self._options,
                joint_bounds_rad=scenario.controller_joint_intersection_rad,
            )
        return self._solvers[tool_length_mm]

    def screen(self, tool_length_mm: float, point: Point3Mm) -> PoseFeasibility:
        key = (tool_length_mm, point.x, point.y, point.z)
        if key in self._cache:
            return self._cache[key]
        solved = self._solver(tool_length_mm).solve(BoardToolTipTarget(point))
        bounds = self.context.scenario.controller_joint_intersection_rad
        solution = {
            item.name: item.position.value
            for item in solved.solution_arm_joint_positions
        }
        controller_ok = solved.converged and set(solution) == set(bounds) and all(
            lower <= solution[name] <= upper
            for name, (lower, upper) in bounds.items()
        )
        raw_margin = None
        normalized_margin = None
        if controller_ok:
            raw_margin = min(
                min(value - bounds[name][0], bounds[name][1] - value)
                for name, value in solution.items()
            )
            normalized_margin = min(
                min(value - bounds[name][0], bounds[name][1] - value)
                / (bounds[name][1] - bounds[name][0])
                for name, value in solution.items()
            )
        margin_ok = (
            controller_ok
            and normalized_margin is not None
            and normalized_margin >= self._minimum_normalized_arm_joint_margin
        )
        result = PoseFeasibility(
            status=(
                solved.status.value
                if margin_ok or not solved.converged
                else "MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED"
                if controller_ok
                else "INTERNAL_CONTROLLER_INTERSECTION_REJECTED"
            ),
            accepted=bool(margin_ok),
            position_error_mm=solved.residual.position_error_mm,
            alignment_error_rad=solved.residual.alignment_error_rad,
            minimum_arm_joint_margin_rad=raw_margin,
            minimum_normalized_arm_joint_margin=normalized_margin,
            attempt_count=len(solved.attempts),
            selected_attempt_index=solved.selected_attempt_index,
            solution_arm_joint_positions_rad=tuple(solution.items()),
        )
        self._cache[key] = result
        return result


def _contact_point(context: SimulationContext, target: TargetRegion) -> Point3Mm:
    return Point3Mm(
        "board",
        target.center.x,
        target.center.y,
        target.center.z - context.scenario.path_policy.contact_overtravel_mm,
    )


def _tool_length(study: ReachStudyInput, device: str) -> float:
    return (
        study.keyboard_tool_length_mm
        if device == "keyboard"
        else study.phone_tool_length_mm
    )


def _evaluate_contacts(
    context: SimulationContext,
    evaluator: _CandidateEvaluator,
    targets: tuple[TargetRegion, ...],
) -> tuple[ContactPoseResult, ...]:
    return tuple(
        ContactPoseResult(
            device=target.device,
            target_id=target.target_id,
            tip_position_board=_contact_point(context, target),
            feasibility=evaluator.screen(
                _tool_length(evaluator.study, target.device),
                _contact_point(context, target),
            ),
        )
        for target in targets
    )


def _park_geometry_valid(context: SimulationContext, point: Point3Mm) -> bool:
    board = context.scene.board
    if not (
        board.minimum.x <= point.x <= board.maximum.x
        and board.minimum.y <= point.y <= board.maximum.y
    ):
        return False
    required_z = max(obstacle.maximum.z for obstacle in context.scene.obstacles) + (
        context.scenario.path_policy.clearance_above_highest_obstacle_mm
    )
    if point.z < required_z:
        return False
    # Retain the conservative RC03 rule that park XY may not alias any device,
    # station, or physical tag tile even when its point Z is above the proxy.
    for obstacle in context.scene.obstacles:
        if obstacle.obstacle_id == "board_solid":
            continue
        if (
            obstacle.minimum.x <= point.x <= obstacle.maximum.x
            and obstacle.minimum.y <= point.y <= obstacle.maximum.y
        ):
            return False
    for tag in context.scene.fiducials:
        half = tag.tile_edge_mm / 2.0
        if (
            tag.center.x - half <= point.x <= tag.center.x + half
            and tag.center.y - half <= point.y <= tag.center.y + half
        ):
            return False
    return True


def _evaluate_park(
    context: SimulationContext,
    evaluator: _CandidateEvaluator,
    index: int,
    raw: tuple[float, float, float],
) -> ParkEvaluation:
    point = Point3Mm("board", *raw)
    valid = _park_geometry_valid(context, point)
    if not valid:
        return ParkEvaluation(f"park-{index:02d}", point, False, None, None)
    return ParkEvaluation(
        f"park-{index:02d}",
        point,
        True,
        evaluator.screen(evaluator.study.keyboard_tool_length_mm, point),
        evaluator.screen(evaluator.study.phone_tool_length_mm, point),
    )


def _coverage(outcomes: tuple[ContactPoseResult, ...], device: str) -> tuple[int, int]:
    selected = tuple(row for row in outcomes if row.device == device)
    return sum(row.feasibility.accepted for row in selected), len(selected)


def _minimum_margin(
    contacts: FullContactEvaluation,
    park: ParkEvaluation,
) -> float | None:
    values = tuple(
        value
        for value in (
            contacts.minimum_normalized_arm_margin,
            park.minimum_normalized_arm_margin,
        )
        if value is not None
    )
    return min(values) if values else None


def _deviation(
    study: ReachStudyInput,
    park: ParkEvaluation,
    canonical_board_T_base_link: RigidTransform,
    context: SimulationContext,
) -> float:
    canonical_yaw = math.atan2(
        canonical_board_T_base_link.rotation.matrix[3],
        canonical_board_T_base_link.rotation.matrix[0],
    )
    nominal_tool = -context.scenario.hand_tcp_to_tip_z_mm
    nominal_park_x, nominal_park_y = context.scenario.path_policy.park_xy_board_mm
    nominal_park_z = max(obstacle.maximum.z for obstacle in context.scene.obstacles) + (
        context.scenario.path_policy.clearance_above_highest_obstacle_mm
    )
    return (
        abs(
            study.rear_clamp_contact_x_board_mm
            - canonical_board_T_base_link.translation_mm.x
        )
        / 160.0
        + abs(study.clamp_to_base_axis_x_mm) / 100.0
        + abs(study.rear_edge_to_base_axis_y_mm) / 100.0
        + abs(study.base_yaw_board_rad - canonical_yaw) / math.radians(30.0)
        + abs(study.keyboard_tool_length_mm - nominal_tool) / 150.0
        + abs(study.phone_tool_length_mm - nominal_tool) / 150.0
        + abs(park.point_board.x - nominal_park_x) / 610.0
        + abs(park.point_board.y - nominal_park_y) / 457.0
        + abs(park.point_board.z - nominal_park_z) / 100.0
    )


def _rank_key(
    contacts: FullContactEvaluation,
    park: ParkEvaluation,
    deviation: float,
) -> tuple[Any, ...]:
    keyboard = (contacts.accepted_count("keyboard"), contacts.total_count("keyboard"))
    phone = (contacts.accepted_count("phone"), contacts.total_count("phone"))
    balanced = min(keyboard[0] / keyboard[1], phone[0] / phone[1])
    total_accepted = keyboard[0] + phone[0]
    margin = _minimum_margin(contacts, park)
    mission_complete = contacts.all_contacts_accepted and park.all_routes_accepted
    # Hard mission completion first, then both route parks.  Device-balanced
    # coverage intentionally precedes the raw total so the smaller phone map
    # cannot mask poor keyboard feasibility.
    return (
        0 if mission_complete else 1,
        -park.accepted_route_count,
        -balanced,
        -total_accepted,
        -(margin if margin is not None else -1.0),
        deviation,
        contacts.study_input.study_input_id,
        park.park_id,
    )


def _ik_options_dict(options: IkOptions) -> dict[str, Any]:
    return {
        name: getattr(options, name)
        for name in (
            "max_attempts",
            "max_iterations_per_attempt",
            "position_tolerance_mm",
            "alignment_tolerance_rad",
            "orientation_weight_mm_per_rad",
            "finite_difference_step_rad",
            "initial_damping",
            "minimum_damping",
            "maximum_damping",
            "max_joint_step_rad",
            "line_search_steps",
        )
    }


def run_reach_optimization(
    context: SimulationContext,
    policy: ReachStudyPolicy | None = None,
) -> ReachOptimizationReport:
    """Run a bounded coarse screen and full-catalog finalist evaluation.

    The canonical context is reconstructed and compared before any candidate
    is created.  Candidate transforms live only in local study objects.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    if not context.alignment.all_checks_pass:
        raise ReachOptimizationError(
            "canonical placemat alignment must pass before a reach study"
        )
    selected_policy = policy or default_reach_study_policy(context)
    if not isinstance(selected_policy, ReachStudyPolicy):
        raise TypeError("policy must be a ReachStudyPolicy")

    scenario = context.scenario
    try:
        loaded_model = load_pinned_urdf(
            scenario.model_path,
            scenario.model_sha256,
        )
    except PinnedModelLoadError as exc:
        raise ReachOptimizationError(f"pinned URDF capture failed: {exc}") from exc
    model = loaded_model.model
    fixed = model.joint("world_to_base_link")
    if (
        fixed.joint_type != "fixed"
        or fixed.parent_link != "world"
        or fixed.child_link != "base_link"
    ):
        raise ReachOptimizationError("pinned URDF lost Wv_T_Ru fixed-joint contract")
    vendor_world_T_base_link = fixed.transform_at(None)
    canonical_board_T_base_link = scenario.board_T_world.compose(
        vendor_world_T_base_link
    )
    # The current pinned model is expected to carry the audited +70.1 mm
    # offset.  Failing closed avoids silently returning to direct Wv placement.
    if not math.isclose(
        vendor_world_T_base_link.translation_mm.z, 70.1, abs_tol=1e-9
    ):
        raise ReachOptimizationError("pinned Wv_T_Ru Z offset is not 70.1 mm")

    inputs = _study_inputs(
        context,
        selected_policy,
        vendor_world_T_base_link,
        canonical_board_T_base_link,
    )
    full_targets = _target_catalog(context)
    keyboard_target_count = sum(target.device == "keyboard" for target in full_targets)
    phone_target_count = sum(target.device == "phone" for target in full_targets)
    if (
        len(full_targets) != _MAX_FULL_TARGETS
        or keyboard_target_count != 46
        or phone_target_count != 29
    ):
        raise ReachOptimizationError(
            "optimizer requires the locked 46-key + 29-phone = 75 target catalog"
        )
    if (
        scenario.ik_policy.max_attempts > _MAX_IK_ATTEMPTS
        or scenario.ik_policy.max_iterations_per_attempt
        > _MAX_IK_ITERATIONS_PER_ATTEMPT
    ):
        raise ReachOptimizationError("canonical IK effort exceeds optimizer resource caps")
    required_park_z = max(
        obstacle.maximum.z for obstacle in context.scene.obstacles
    ) + scenario.path_policy.clearance_above_highest_obstacle_mm
    if any(
        point[2] < 0.0
        or point[2] > required_park_z + _MAX_PARK_Z_ABOVE_REQUIRED_MM
        for point in selected_policy.park_points_board_mm
    ):
        raise ReachOptimizationError(
            "park Z must stay between board top and the bounded required+300 mm study ceiling"
        )
    coarse_targets = _spatial_subset(
        full_targets, selected_policy.coarse_targets_per_device
    )
    coarse_options = IkOptions(
        max_attempts=2,
        max_iterations_per_attempt=min(
            18, scenario.ik_policy.max_iterations_per_attempt
        ),
    )
    canonical_options = IkOptions(
        max_attempts=scenario.ik_policy.max_attempts,
        max_iterations_per_attempt=scenario.ik_policy.max_iterations_per_attempt,
    )
    planned_solve_upper_bound = (
        len(inputs)
        * (len(coarse_targets) + 2 * len(selected_policy.park_points_board_mm))
        + min(selected_policy.finalist_count, len(inputs))
        * (len(full_targets) + 2 * len(selected_policy.park_points_board_mm))
    )
    if planned_solve_upper_bound > _MAX_PLANNED_IK_SOLVES:
        raise ReachOptimizationError(
            f"planned IK solve upper bound {planned_solve_upper_bound} exceeds "
            f"{_MAX_PLANNED_IK_SOLVES}"
        )

    coarse_rows: list[tuple[tuple[Any, ...], ReachStudyInput]] = []
    coarse_evaluations: list[CoarseReachEvaluation] = []
    coarse_solves = 0
    for study in inputs:
        evaluator = _CandidateEvaluator(
            context,
            model,
            study,
            coarse_options,
            selected_policy.minimum_normalized_arm_joint_margin,
        )
        outcomes = _evaluate_contacts(context, evaluator, coarse_targets)
        evaluated_parks = tuple(
            _evaluate_park(context, evaluator, index, park_point)
            for index, park_point in enumerate(selected_policy.park_points_board_mm)
        )
        keyboard = _coverage(outcomes, "keyboard")
        phone = _coverage(outcomes, "phone")
        balanced = min(keyboard[0] / keyboard[1], phone[0] / phone[1])
        margins = tuple(
            row.feasibility.minimum_normalized_arm_joint_margin
            for row in outcomes
            if row.feasibility.accepted
            and row.feasibility.minimum_normalized_arm_joint_margin is not None
        )
        park_choices: list[tuple[tuple[Any, ...], ParkEvaluation, float | None]] = []
        for candidate_park in evaluated_parks:
            park_margin = candidate_park.minimum_normalized_arm_margin
            all_margins = margins + (() if park_margin is None else (park_margin,))
            minimum_margin = min(all_margins) if all_margins else None
            candidate_key = (
                -candidate_park.accepted_route_count,
                -balanced,
                -(keyboard[0] + phone[0]),
                -(minimum_margin if minimum_margin is not None else -1.0),
                _deviation(
                    study,
                    candidate_park,
                    canonical_board_T_base_link,
                    context,
                ),
                study.study_input_id,
                candidate_park.park_id,
            )
            park_choices.append((candidate_key, candidate_park, minimum_margin))
        rank_key, park, minimum_margin = min(park_choices, key=lambda row: row[0])
        coarse_rows.append((rank_key, study))
        coarse_evaluations.append(
            CoarseReachEvaluation(
                study_input=study,
                keyboard_accepted=keyboard[0],
                keyboard_total=keyboard[1],
                phone_accepted=phone[0],
                phone_total=phone[1],
                rejected_target_ids=tuple(
                    f"{row.device}:{row.target_id}"
                    for row in outcomes
                    if not row.feasibility.accepted
                ),
                evaluated_parks=evaluated_parks,
                park=park,
                minimum_normalized_arm_joint_margin=minimum_margin,
                ranking_key=rank_key,
                ik_solve_count=evaluator.solve_count,
            )
        )
        coarse_solves += evaluator.solve_count
    finalists = tuple(
        row[1]
        for row in sorted(coarse_rows)
        [: min(selected_policy.finalist_count, len(inputs))]
    )

    full_evaluations: list[FullContactEvaluation] = []
    park_rows: list[tuple[str, ParkEvaluation]] = []
    full_evaluators: dict[str, _CandidateEvaluator] = {}
    for study in finalists:
        evaluator = _CandidateEvaluator(
            context,
            model,
            study,
            canonical_options,
            selected_policy.minimum_normalized_arm_joint_margin,
        )
        full_evaluators[study.study_input_id] = evaluator
        outcomes = _evaluate_contacts(context, evaluator, full_targets)
        full_evaluations.append(
            FullContactEvaluation(
                study_input=study,
                outcomes=outcomes,
                ik_solve_count=0,  # finalized after shared park evaluations
            )
        )
        for park_index, park_point in enumerate(selected_policy.park_points_board_mm):
            park_rows.append(
                (
                    study.study_input_id,
                    _evaluate_park(context, evaluator, park_index, park_point),
                )
            )

    # Replace the provisional counts without mutating canonical or candidate
    # inputs.  The frozen result captures contact+park cache reuse exactly.
    finalized_evaluations = tuple(
        FullContactEvaluation(
            evaluation.study_input,
            evaluation.outcomes,
            full_evaluators[evaluation.study_input.study_input_id].solve_count,
        )
        for evaluation in full_evaluations
    )
    evaluation_by_id = {
        evaluation.study_input.study_input_id: evaluation
        for evaluation in finalized_evaluations
    }
    ranked_source: list[
        tuple[tuple[Any, ...], FullContactEvaluation, ParkEvaluation, float]
    ] = []
    for study_id, park in park_rows:
        contacts = evaluation_by_id[study_id]
        deviation = _deviation(
            contacts.study_input, park, canonical_board_T_base_link, context
        )
        ranked_source.append(
            (_rank_key(contacts, park, deviation), contacts, park, deviation)
        )
    ranked: list[RankedReachCandidate] = []
    for rank, (_, contacts, park, deviation) in enumerate(
        sorted(ranked_source), start=1
    ):
        keyboard = (
            contacts.accepted_count("keyboard"),
            contacts.total_count("keyboard"),
        )
        phone = (
            contacts.accepted_count("phone"),
            contacts.total_count("phone"),
        )
        ranked.append(
            RankedReachCandidate(
                rank=rank,
                study_input_id=contacts.study_input.study_input_id,
                park_id=park.park_id,
                keyboard_accepted=keyboard[0],
                keyboard_total=keyboard[1],
                phone_accepted=phone[0],
                phone_total=phone[1],
                park_routes_accepted=park.accepted_route_count,
                mission_complete=(
                    contacts.all_contacts_accepted and park.all_routes_accepted
                ),
                minimum_normalized_arm_joint_margin=_minimum_margin(contacts, park),
                normalized_deviation_from_nominal=deviation,
            )
        )

    gripper_lower, gripper_upper = scenario.controller_gripper_intersection_rad
    gripper_value = scenario.fixed_gripper_position.value
    fixed_gripper_normalized_margin = min(
        gripper_value - gripper_lower,
        gripper_upper - gripper_value,
    ) / (gripper_upper - gripper_lower)
    provenance = (
        ("snapshot_hash", context.snapshot.snapshot_hash),
        ("simulation_bundle_id", context.bundle_lock.bundle_id),
        ("simulation_bundle_sha256", context.bundle_lock.source_lock_sha256),
        ("hardware_profile_hash", context.hardware_profile.profile_hash),
        ("scenario_profile_sha256", scenario.source_profile_sha256),
        ("target_profile_sha256", context.targets.content_sha256),
        ("model_sha256", scenario.model_sha256),
        ("alignment_report_hash", context.alignment.report_hash),
        ("scene_source_hashes", tuple(sorted(context.scene.source_hashes.items()))),
        ("fixed_gripper_position_rad", gripper_value),
        ("gripper_controller_urdf_intersection_rad", (gripper_lower, gripper_upper)),
        ("fixed_gripper_normalized_margin", fixed_gripper_normalized_margin),
        ("fixed_gripper_in_arm_margin_gate", False),
        ("ik_solver_implementation", "RoArmM3NumericalIk"),
        ("ik_solver_algorithm_version", "DETERMINISTIC_BOUNDED_DLS_V1"),
        ("rocell_runtime_version", __version__),
        ("coarse_ik_options", tuple(sorted(_ik_options_dict(coarse_options).items()))),
        ("full_ik_options", tuple(sorted(_ik_options_dict(canonical_options).items()))),
        (
            "controller_joint_intersection_rad",
            tuple(
                (name, tuple(bounds))
                for name, bounds in scenario.controller_joint_intersection_rad.items()
            ),
        ),
    )
    return ReachOptimizationReport(
        source_provenance=provenance,
        policy=selected_policy,
        vendor_world_T_base_link=vendor_world_T_base_link,
        canonical_board_T_base_link=canonical_board_T_base_link,
        coarse_target_ids=tuple(
            f"{target.device}:{target.target_id}" for target in coarse_targets
        ),
        coarse_evaluations=tuple(
            sorted(
                coarse_evaluations,
                key=lambda evaluation: evaluation.ranking_key,
            )
        ),
        coarse_candidate_count=len(inputs),
        coarse_ik_solve_count=coarse_solves,
        finalist_ids=tuple(study.study_input_id for study in finalists),
        full_evaluations=finalized_evaluations,
        park_evaluations=tuple(park_rows),
        ranked_candidates=tuple(ranked),
        full_ik_solve_count=sum(
            evaluator.solve_count for evaluator in full_evaluators.values()
        ),
        planned_ik_solve_upper_bound=planned_solve_upper_bound,
    )


__all__ = [
    "ReachOptimizationError",
    "ReachOptimizationReport",
    "ReachStudyInput",
    "ReachStudyPolicy",
    "default_reach_study_policy",
    "default_reach_study_inputs",
    "run_reach_optimization",
]
