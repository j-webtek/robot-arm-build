"""Bounded Freeze005 park-pose optimization with zero hardware authority.

The optimizer derives XY hypotheses from the revalidated RC03 board envelope,
station/device keepout projections, and physical AprilTag tile projections.
Every eligible point uses the one controlled transit-plane Z and is screened
for both selected route tool lengths through canonical numerical IK.  Results
are independent park-pose diagnostics: no path, swept robot volume, collision,
singularity, dynamics, controller command, or hardware access is provided.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from rocell import __version__
from rocell.geometry import Point3Mm, UrdfModel
from rocell.kinematics import BoardToolTipTarget, IkOptions, RoArmM3NumericalIk
from rocell.models.units import finite_real
from rocell.motion import GeometricDryRunEngine

from ._pinned_model import (
    MAX_PINNED_URDF_BYTES,
    PinnedModelLoadError,
    load_pinned_urdf,
)
from .context import SimulationContext, revalidate_simulation_context
from .reach_optimizer import (
    PoseFeasibility,
    ReachStudyInput,
    _default_reach_study_inputs_from_model,
)
from .trajectory_simulation import _hash_file_bounded, _implementation_hashes


FREEZE005_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-005"
FREEZE005_SELECTED_STUDY_INPUT_ID = "reach-00ed8c5820df03c7"
FREEZE005_REACH_REPORT_SHA256 = (
    "335275e2a68aa2cda82163fedfe93c17daccdd65d87e07ab03359fafc738fc00"
)

# Freezes 006 through 011 retain the Freeze-005 reach-study selection and report
# hash.  Freeze 010 changed production-fit/build records, while Freeze 011 was
# workflow-only; neither changed the selected placement/tool inputs or pinned
# model.  Park candidate geometry is still regenerated from the revalidated
# active scene and its hashes are recorded in each report.  The allowlist is
# deliberately explicit so an unknown future freeze still fails closed instead
# of silently inheriting this historical source.
_FREEZE006_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-006"
_FREEZE007_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-007"
_FREEZE008_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-008"
_FREEZE009_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-009"
_FREEZE010_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-010"
_FREEZE011_MANIFEST_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-011"
_COMPATIBLE_MANIFEST_IDS = frozenset(
    (
        FREEZE005_MANIFEST_ID,
        _FREEZE006_MANIFEST_ID,
        _FREEZE007_MANIFEST_ID,
        _FREEZE008_MANIFEST_ID,
        _FREEZE009_MANIFEST_ID,
        _FREEZE010_MANIFEST_ID,
        _FREEZE011_MANIFEST_ID,
    )
)

_ROUTES = ("keyboard", "phone")
_FINE_OFFSETS = (
    (-1.0, -1.0),
    (0.0, -1.0),
    (1.0, -1.0),
    (-1.0, 0.0),
    (1.0, 0.0),
    (-1.0, 1.0),
    (0.0, 1.0),
    (1.0, 1.0),
)
_MAX_COARSE_RAW_CANDIDATES = 128
_MAX_COARSE_ELIGIBLE_CANDIDATES = 64
_MAX_REFINEMENT_ANCHORS = 8
_MAX_REFINEMENT_RAW_CANDIDATES = 64
_MAX_REFINEMENT_ELIGIBLE_CANDIDATES = 32
_MAX_TOTAL_IK_SOLVES = 192
_MAX_CANONICAL_IK_ATTEMPTS = 8
_MAX_CANONICAL_IK_ITERATIONS = 200
_CANONICAL_IK_SOLVER = RoArmM3NumericalIk


class ParkOptimizationError(ValueError):
    """A park study violates its frozen selection or bounded-search contract."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ParkOptimizationPolicy:
    """Geometry, margin, refinement, and resource controls for one study."""

    board_edge_inset_mm: float = 10.0
    planar_keepout_clearance_mm: float = 5.0
    coarse_maximum_spacing_mm: float = 60.0
    refinement_step_mm: float = 15.0
    refinement_anchor_count: int = 4
    minimum_normalized_arm_joint_margin: float = 0.01
    maximum_coarse_raw_candidates: int = 128
    maximum_coarse_eligible_candidates: int = 64
    maximum_refinement_raw_candidates: int = 32
    maximum_refinement_eligible_candidates: int = 32
    maximum_total_ik_solves: int = 192

    def __post_init__(self) -> None:
        for name, lower, upper in (
            ("board_edge_inset_mm", 1.0, 100.0),
            ("planar_keepout_clearance_mm", 1.0, 50.0),
            ("coarse_maximum_spacing_mm", 20.0, 200.0),
            ("refinement_step_mm", 2.0, 50.0),
            ("minimum_normalized_arm_joint_margin", 1e-6, 0.49),
        ):
            value = finite_real(getattr(self, name), name=name)
            if not lower <= value <= upper:
                raise ParkOptimizationError(f"{name} must be in [{lower}, {upper}]")
            object.__setattr__(self, name, value)
        if self.refinement_step_mm >= self.coarse_maximum_spacing_mm:
            raise ParkOptimizationError(
                "refinement_step_mm must be below coarse_maximum_spacing_mm"
            )
        for name, lower, upper in (
            ("refinement_anchor_count", 1, _MAX_REFINEMENT_ANCHORS),
            (
                "maximum_coarse_raw_candidates",
                1,
                _MAX_COARSE_RAW_CANDIDATES,
            ),
            (
                "maximum_coarse_eligible_candidates",
                1,
                _MAX_COARSE_ELIGIBLE_CANDIDATES,
            ),
            (
                "maximum_refinement_raw_candidates",
                1,
                _MAX_REFINEMENT_RAW_CANDIDATES,
            ),
            (
                "maximum_refinement_eligible_candidates",
                1,
                _MAX_REFINEMENT_ELIGIBLE_CANDIDATES,
            ),
            ("maximum_total_ik_solves", 2, _MAX_TOTAL_IK_SOLVES),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise ParkOptimizationError(
                    f"{name} must be an integer in [{lower}, {upper}]"
                )
        if self.refinement_anchor_count * len(_FINE_OFFSETS) > (
            self.maximum_refinement_raw_candidates
        ):
            raise ParkOptimizationError(
                "refinement anchors exceed the refinement raw-candidate budget"
            )
        planned_solve_bound = 2 * (
            self.maximum_coarse_eligible_candidates
            + self.maximum_refinement_eligible_candidates
        )
        if planned_solve_bound > self.maximum_total_ik_solves:
            raise ParkOptimizationError(
                "candidate ceilings exceed maximum_total_ik_solves"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": "FREEZE005_GEOMETRY_DERIVED_COARSE_FINE_PARK_V1",
            "board_edge_inset_mm": self.board_edge_inset_mm,
            "planar_keepout_clearance_mm": self.planar_keepout_clearance_mm,
            "coarse_maximum_spacing_mm": self.coarse_maximum_spacing_mm,
            "refinement_step_mm": self.refinement_step_mm,
            "refinement_anchor_count": self.refinement_anchor_count,
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "maximum_coarse_raw_candidates": self.maximum_coarse_raw_candidates,
            "maximum_coarse_eligible_candidates": (
                self.maximum_coarse_eligible_candidates
            ),
            "maximum_refinement_raw_candidates": (
                self.maximum_refinement_raw_candidates
            ),
            "maximum_refinement_eligible_candidates": (
                self.maximum_refinement_eligible_candidates
            ),
            "maximum_total_ik_solves": self.maximum_total_ik_solves,
            "hard_implementation_caps": {
                "coarse_raw_candidates": _MAX_COARSE_RAW_CANDIDATES,
                "coarse_eligible_candidates": _MAX_COARSE_ELIGIBLE_CANDIDATES,
                "refinement_anchors": _MAX_REFINEMENT_ANCHORS,
                "refinement_raw_candidates": _MAX_REFINEMENT_RAW_CANDIDATES,
                "refinement_eligible_candidates": (
                    _MAX_REFINEMENT_ELIGIBLE_CANDIDATES
                ),
                "total_ik_solves": _MAX_TOTAL_IK_SOLVES,
                "ik_attempts_per_solve": _MAX_CANONICAL_IK_ATTEMPTS,
                "ik_iterations_per_attempt": _MAX_CANONICAL_IK_ITERATIONS,
                "captured_urdf_bytes": MAX_PINNED_URDF_BYTES,
            },
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ParkGeometryProposal:
    proposal_id: str
    candidate_id: str
    stage: str
    anchor_candidate_id: str | None
    point_board: Point3Mm
    eligible_for_ik: bool
    rejection_reasons: tuple[str, ...]
    board_edge_clearance_mm: float
    nearest_keepout_id: str
    nearest_keepout_clearance_mm: float
    nearest_tag_name: str
    nearest_tag_clearance_mm: float
    minimum_planar_clearance_mm: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "candidate_id": self.candidate_id,
            "stage": self.stage,
            "anchor_candidate_id": self.anchor_candidate_id,
            "point_board_mm": [
                self.point_board.x,
                self.point_board.y,
                self.point_board.z,
            ],
            "eligible_for_ik": self.eligible_for_ik,
            "rejection_reasons": list(self.rejection_reasons),
            "board_edge_clearance_mm": self.board_edge_clearance_mm,
            "nearest_keepout": {
                "id": self.nearest_keepout_id,
                "clearance_mm": self.nearest_keepout_clearance_mm,
            },
            "nearest_tag_tile": {
                "name": self.nearest_tag_name,
                "clearance_mm": self.nearest_tag_clearance_mm,
            },
            "minimum_planar_clearance_mm": self.minimum_planar_clearance_mm,
        }


@dataclass(frozen=True, slots=True)
class ParkRouteResult:
    route: str
    tool_length_mm: float
    feasibility: PoseFeasibility
    reused_identical_tool_solution: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "tool_length_mm": self.tool_length_mm,
            "reused_identical_tool_solution": self.reused_identical_tool_solution,
            **self.feasibility.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ParkCandidateEvaluation:
    geometry: ParkGeometryProposal
    route_results: tuple[ParkRouteResult, ...]
    ranking_key: tuple[Any, ...]

    @property
    def accepted_route_count(self) -> int:
        return sum(row.feasibility.accepted for row in self.route_results)

    @property
    def all_routes_accepted(self) -> bool:
        return (
            len(self.route_results) == len(_ROUTES)
            and self.accepted_route_count == len(_ROUTES)
        )

    @property
    def minimum_normalized_arm_joint_margin(self) -> float | None:
        margins = tuple(
            row.feasibility.minimum_normalized_arm_joint_margin
            for row in self.route_results
            if row.feasibility.accepted
            and row.feasibility.minimum_normalized_arm_joint_margin is not None
        )
        return min(margins) if margins else None

    def to_dict(self, *, rank: int | None = None) -> dict[str, Any]:
        value = {
            "geometry": self.geometry.to_dict(),
            "accepted_route_count": self.accepted_route_count,
            "all_required_route_parks_accepted": self.all_routes_accepted,
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "ranking_key": list(self.ranking_key),
            "route_results": [row.to_dict() for row in self.route_results],
        }
        if rank is not None:
            value["rank"] = rank
        return value


@dataclass(frozen=True, slots=True)
class ParkOptimizationReport:
    source_provenance: tuple[tuple[str, Any], ...]
    policy: ParkOptimizationPolicy
    selected_study_input: ReachStudyInput
    transit_plane_z_mm: float
    frozen_baseline_candidate_id: str
    frozen_baseline_was_injected: bool
    coarse_proposals: tuple[ParkGeometryProposal, ...]
    fine_proposals: tuple[ParkGeometryProposal, ...]
    coarse_evaluations: tuple[ParkCandidateEvaluation, ...]
    fine_evaluations: tuple[ParkCandidateEvaluation, ...]
    ranked_candidates: tuple[ParkCandidateEvaluation, ...]
    actual_ik_solve_count: int
    unique_route_tool_length_count: int
    planned_ik_solve_upper_bound: int

    @property
    def best_candidate(self) -> ParkCandidateEvaluation | None:
        """Return the typed best park candidate without reparsing report JSON."""

        return self.ranked_candidates[0] if self.ranked_candidates else None

    @property
    def status(self) -> str:
        if self.best_candidate is not None and self.best_candidate.all_routes_accepted:
            return "PARK_POSE_DIAGNOSTIC_COMPLETE_CANDIDATE_FOUND"
        return "PARK_POSE_DIAGNOSTIC_NO_COMPLETE_CANDIDATE"

    def to_dict(self) -> dict[str, Any]:
        provenance = dict(self.source_provenance)
        provenance["ik_options"] = dict(provenance["ik_options"])
        best = self.best_candidate
        baseline = next(
            (
                proposal
                for proposal in self.coarse_proposals
                if proposal.candidate_id == self.frozen_baseline_candidate_id
            ),
            None,
        )
        if baseline is None:
            raise ParkOptimizationError(
                "frozen baseline candidate is absent from coarse proposal evidence"
            )
        baseline_is_injected = baseline.proposal_id == "coarse-baseline"
        if baseline_is_injected != self.frozen_baseline_was_injected:
            raise ParkOptimizationError(
                "frozen baseline injection evidence is internally inconsistent"
            )
        return {
            "schema": "rocell.freeze005_park_pose_optimization.v1",
            "status": self.status,
            "scope": "INDEPENDENT_GEOMETRY_FILTERED_PARK_POSE_IK_ONLY",
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
            "canonical_context_modified": False,
            "source_provenance": provenance,
            "policy": {**self.policy.to_dict(), "policy_hash": self.policy.policy_hash},
            "selected_reach_study_input": self.selected_study_input.to_dict(),
            "transit_plane": {
                "z_board_mm": self.transit_plane_z_mm,
                "derivation": (
                    "maximum RC03 obstacle Z plus controlled path clearance"
                ),
                "candidate_z_axis_searched": False,
            },
            "geometry_generation": {
                "method": (
                    "board-inset uniform coarse lattice plus local eight-neighbor "
                    "refinement, with the frozen park retained as a baseline; "
                    "conservative XY AABB clearance against every non-board "
                    "obstacle and physical tag tile"
                ),
                "frozen_baseline_candidate_id": (
                    self.frozen_baseline_candidate_id
                ),
                "frozen_baseline_proposal_id": baseline.proposal_id,
                "frozen_baseline_was_injected": self.frozen_baseline_was_injected,
                "frozen_baseline_was_coincident_with_lattice": (
                    not self.frozen_baseline_was_injected
                ),
                "coarse_raw_count": len(self.coarse_proposals),
                "coarse_eligible_count": sum(
                    row.eligible_for_ik for row in self.coarse_proposals
                ),
                "fine_raw_count": len(self.fine_proposals),
                "fine_eligible_count": sum(
                    row.eligible_for_ik for row in self.fine_proposals
                ),
                "coarse_proposals": [row.to_dict() for row in self.coarse_proposals],
                "fine_proposals": [row.to_dict() for row in self.fine_proposals],
            },
            "search": {
                "actual_ik_solve_count": self.actual_ik_solve_count,
                "unique_route_tool_length_count": self.unique_route_tool_length_count,
                "planned_ik_solve_upper_bound": self.planned_ik_solve_upper_bound,
                "coarse_evaluations": [
                    row.to_dict() for row in self.coarse_evaluations
                ],
                "fine_evaluations": [row.to_dict() for row in self.fine_evaluations],
                "ranked_candidates": [
                    row.to_dict(rank=index)
                    for index, row in enumerate(self.ranked_candidates, start=1)
                ],
            },
            "best_candidate": None if best is None else best.to_dict(rank=1),
            "ranking_order": [
                "both selected route tools accepted",
                "accepted route-tool count",
                "maximum worst accepted normalized arm-joint margin",
                "maximum minimum planar geometry clearance",
                "minimum worst IK position residual",
                "minimum displacement from the frozen canonical park",
                "stable coordinates and candidate ID",
            ],
            "unsupported_diagnostics": [
                "motion from an installed measured start state to park",
                "park-to-target transit, approach, contact, and return paths",
                "robot-link, self, tool, camera-holder, and cable collision",
                "Jacobian singularity and manipulability",
                "timing, velocity, acceleration, dynamics, payload, and force",
                "controller-frame correlation and T=104 execution",
                "vision correction and keyboard/Android outcome observation",
            ],
            "limitations": [
                "Candidate clearance is a conservative planar tool-tip projection, not a swept robot-volume proof.",
                "Every IK result is an independent park pose; branch/path continuity is not evaluated.",
                "The selected base placement and equal 100 mm route tools remain unmeasured Freeze005 study hypotheses.",
                "The five-arm-joint margin gate excludes the fixed gripper, which remains separately unqualified.",
                "A complete diagnostic candidate cannot authorize physical motion or contact.",
            ],
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class _PlanarRect:
    identifier: str
    minimum_x: float
    maximum_x: float
    minimum_y: float
    maximum_y: float


def _rect_distance(x: float, y: float, rectangle: _PlanarRect) -> float:
    delta_x = max(rectangle.minimum_x - x, 0.0, x - rectangle.maximum_x)
    delta_y = max(rectangle.minimum_y - y, 0.0, y - rectangle.maximum_y)
    return math.hypot(delta_x, delta_y)


def _scene_rectangles(
    context: SimulationContext,
) -> tuple[tuple[_PlanarRect, ...], tuple[_PlanarRect, ...]]:
    keepouts = tuple(
        _PlanarRect(
            obstacle.obstacle_id,
            obstacle.minimum.x,
            obstacle.maximum.x,
            obstacle.minimum.y,
            obstacle.maximum.y,
        )
        for obstacle in context.scene.obstacles
        if obstacle.obstacle_id != "board_solid"
    )
    tags: list[_PlanarRect] = []
    for tag in context.scene.fiducials:
        corners = tag.tile_corners()
        tags.append(
            _PlanarRect(
                tag.name,
                min(point.x for point in corners),
                max(point.x for point in corners),
                min(point.y for point in corners),
                max(point.y for point in corners),
            )
        )
    if not keepouts or not tags:
        raise ParkOptimizationError(
            "Freeze005 park derivation requires obstacle and tag geometry"
        )
    return keepouts, tuple(tags)


def _candidate_id(point: Point3Mm) -> str:
    return "park-" + _stable_hash(
        {"x": point.x, "y": point.y, "z": point.z}
    )[:16]


def _geometry_proposal(
    context: SimulationContext,
    policy: ParkOptimizationPolicy,
    keepouts: tuple[_PlanarRect, ...],
    tags: tuple[_PlanarRect, ...],
    *,
    proposal_id: str,
    stage: str,
    anchor_candidate_id: str | None,
    x: float,
    y: float,
    transit_z_mm: float,
    duplicate: bool,
) -> ParkGeometryProposal:
    point = Point3Mm("board", round(x, 9), round(y, 9), transit_z_mm)
    board = context.scene.board
    board_clearance = min(
        point.x - board.minimum.x,
        board.maximum.x - point.x,
        point.y - board.minimum.y,
        board.maximum.y - point.y,
    )
    keepout_distance, nearest_keepout = min(
        (_rect_distance(point.x, point.y, rectangle), rectangle.identifier)
        for rectangle in keepouts
    )
    tag_distance, nearest_tag = min(
        (_rect_distance(point.x, point.y, rectangle), rectangle.identifier)
        for rectangle in tags
    )
    reasons: list[str] = []
    if board_clearance + 1e-9 < policy.board_edge_inset_mm:
        reasons.append("BOARD_EDGE_INSET_REJECTED")
    if keepout_distance + 1e-9 < policy.planar_keepout_clearance_mm:
        reasons.append(f"KEEPOUT_CLEARANCE_REJECTED:{nearest_keepout}")
    if tag_distance + 1e-9 < policy.planar_keepout_clearance_mm:
        reasons.append(f"TAG_CLEARANCE_REJECTED:{nearest_tag}")
    if duplicate:
        reasons.append("DUPLICATE_CANDIDATE_REJECTED")
    return ParkGeometryProposal(
        proposal_id=proposal_id,
        candidate_id=_candidate_id(point),
        stage=stage,
        anchor_candidate_id=anchor_candidate_id,
        point_board=point,
        eligible_for_ik=not reasons,
        rejection_reasons=tuple(reasons),
        board_edge_clearance_mm=board_clearance,
        nearest_keepout_id=nearest_keepout,
        nearest_keepout_clearance_mm=keepout_distance,
        nearest_tag_name=nearest_tag,
        nearest_tag_clearance_mm=tag_distance,
        minimum_planar_clearance_mm=min(
            board_clearance, keepout_distance, tag_distance
        ),
    )


def _uniform_axis(lower: float, upper: float, maximum_spacing: float) -> tuple[float, ...]:
    if lower >= upper:
        raise ParkOptimizationError("board inset leaves no candidate interval")
    segment_count = max(1, math.ceil((upper - lower) / maximum_spacing))
    return tuple(
        lower + (upper - lower) * index / segment_count
        for index in range(segment_count + 1)
    )


class _ParkIkEvaluator:
    def __init__(
        self,
        context: SimulationContext,
        model: UrdfModel,
        study: ReachStudyInput,
        options: IkOptions,
        minimum_margin: float,
        solver_class: type[Any],
        maximum_solves: int,
    ) -> None:
        self._context = context
        self._study = study
        self._options = options
        self._minimum_margin = minimum_margin
        self._solver_class = solver_class
        self._maximum_solves = maximum_solves
        self._model = model
        self._solvers: dict[float, Any] = {}
        self._cache: dict[tuple[float, float, float, float], PoseFeasibility] = {}

    @property
    def solve_count(self) -> int:
        return len(self._cache)

    def _solver(self, tool_length_mm: float) -> Any:
        if tool_length_mm not in self._solvers:
            scenario = self._context.scenario
            self._solvers[tool_length_mm] = self._solver_class(
                model=self._model,
                board_T_world=self._study.board_T_vendor_world,
                hand_tcp_to_tip_z_mm=-tool_length_mm,
                fixed_gripper_position=scenario.fixed_gripper_position,
                ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
                gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
                options=self._options,
                joint_bounds_rad=scenario.controller_joint_intersection_rad,
            )
        return self._solvers[tool_length_mm]

    def screen(
        self, tool_length_mm: float, point: Point3Mm
    ) -> tuple[PoseFeasibility, bool]:
        key = (tool_length_mm, point.x, point.y, point.z)
        if key in self._cache:
            return self._cache[key], True
        if self.solve_count >= self._maximum_solves:
            raise ParkOptimizationError("maximum_total_ik_solves exhausted")
        solved = self._solver(tool_length_mm).solve(BoardToolTipTarget(point))
        bounds = self._context.scenario.controller_joint_intersection_rad
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
            and normalized_margin >= self._minimum_margin
        )
        feasibility = PoseFeasibility(
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
        self._cache[key] = feasibility
        return feasibility, False


def _rank_key(
    geometry: ParkGeometryProposal,
    route_results: tuple[ParkRouteResult, ...],
    canonical_park_xy: tuple[float, float],
) -> tuple[Any, ...]:
    accepted = tuple(row for row in route_results if row.feasibility.accepted)
    minimum_margin = min(
        (
            row.feasibility.minimum_normalized_arm_joint_margin
            for row in accepted
            if row.feasibility.minimum_normalized_arm_joint_margin is not None
        ),
        default=-1.0,
    )
    worst_residual = max(
        (row.feasibility.position_error_mm for row in route_results),
        default=math.inf,
    )
    canonical_distance = math.hypot(
        geometry.point_board.x - canonical_park_xy[0],
        geometry.point_board.y - canonical_park_xy[1],
    )
    return (
        0 if len(accepted) == len(_ROUTES) else 1,
        -len(accepted),
        -minimum_margin,
        -geometry.minimum_planar_clearance_mm,
        worst_residual,
        canonical_distance,
        geometry.point_board.y,
        geometry.point_board.x,
        geometry.candidate_id,
    )


def _evaluate_candidate(
    proposal: ParkGeometryProposal,
    evaluator: _ParkIkEvaluator,
    study: ReachStudyInput,
    canonical_park_xy: tuple[float, float],
) -> ParkCandidateEvaluation:
    tool_lengths = {
        "keyboard": study.keyboard_tool_length_mm,
        "phone": study.phone_tool_length_mm,
    }
    route_results: list[ParkRouteResult] = []
    for route in _ROUTES:
        feasibility, reused = evaluator.screen(
            tool_lengths[route], proposal.point_board
        )
        route_results.append(
            ParkRouteResult(route, tool_lengths[route], feasibility, reused)
        )
    rows = tuple(route_results)
    return ParkCandidateEvaluation(
        geometry=proposal,
        route_results=rows,
        ranking_key=_rank_key(proposal, rows, canonical_park_xy),
    )


def _ik_options_dict(options: IkOptions) -> dict[str, int | float]:
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


def _selected_study(
    context: SimulationContext, captured_model: UrdfModel
) -> ReachStudyInput:
    if context.snapshot.manifest_id not in _COMPATIBLE_MANIFEST_IDS:
        raise ParkOptimizationError(
            "park optimization has no documented source binding for manifest "
            f"{context.snapshot.manifest_id!r}; compatible manifests are "
            f"{sorted(_COMPATIBLE_MANIFEST_IDS)!r}"
        )
    matches = tuple(
        study
        for study in _default_reach_study_inputs_from_model(context, captured_model)
        if study.study_input_id == FREEZE005_SELECTED_STUDY_INPUT_ID
    )
    if len(matches) != 1:
        raise ParkOptimizationError(
            "Freeze005 selected reach study input does not resolve exactly once"
        )
    return matches[0]


def _implementation_provenance(
    solver_class: type[Any], solver_mode: str
) -> tuple[tuple[str, str], ...]:
    bound = dict(
        _implementation_hashes(
            solver_class,
            GeometricDryRunEngine,
            solver_mode=solver_mode,
        )
    )
    park_hash, _ = _hash_file_bounded(Path(__file__).resolve(), 5_000_000)
    values = {
        "park_optimizer_module_sha256": park_hash,
        "ik_module_sha256": bound["ik_module_sha256"],
        "active_ik_solver_source_sha256": bound[
            "active_ik_solver_source_sha256"
        ],
        "rocell_source_tree_sha256": bound["rocell_source_tree_sha256"],
        "ik_solver_identity": bound["ik_solver_identity"],
        "solver_mode": solver_mode,
    }
    values["park_implementation_bundle_sha256"] = _stable_hash(values)
    return tuple(sorted(values.items()))


def _run_park_optimization_with_solver(
    context: SimulationContext,
    policy: ParkOptimizationPolicy | None,
    *,
    solver_class: type[Any],
    solver_mode: str,
) -> ParkOptimizationReport:
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    if not context.alignment.all_checks_pass:
        raise ParkOptimizationError("canonical placemat alignment must pass")
    selected_policy = policy or ParkOptimizationPolicy()
    if not isinstance(selected_policy, ParkOptimizationPolicy):
        raise TypeError("policy must be a ParkOptimizationPolicy")
    scenario = context.scenario
    if (
        scenario.ik_policy.max_attempts > _MAX_CANONICAL_IK_ATTEMPTS
        or scenario.ik_policy.max_iterations_per_attempt
        > _MAX_CANONICAL_IK_ITERATIONS
    ):
        raise ParkOptimizationError("canonical IK effort exceeds park-study caps")
    try:
        loaded_model = load_pinned_urdf(
            scenario.model_path,
            scenario.model_sha256,
        )
    except PinnedModelLoadError as exc:
        raise ParkOptimizationError(f"pinned URDF capture failed: {exc}") from exc
    captured_model = loaded_model.model
    captured_model_sha256 = loaded_model.sha256
    captured_model_byte_count = loaded_model.byte_count
    study = _selected_study(context, captured_model)
    keepouts, tags = _scene_rectangles(context)
    transit_z = max(
        obstacle.maximum.z for obstacle in context.scene.obstacles
    ) + scenario.path_policy.clearance_above_highest_obstacle_mm
    board = context.scene.board
    x_axis = _uniform_axis(
        board.minimum.x + selected_policy.board_edge_inset_mm,
        board.maximum.x - selected_policy.board_edge_inset_mm,
        selected_policy.coarse_maximum_spacing_mm,
    )
    y_axis = _uniform_axis(
        board.minimum.y + selected_policy.board_edge_inset_mm,
        board.maximum.y - selected_policy.board_edge_inset_mm,
        selected_policy.coarse_maximum_spacing_mm,
    )
    lattice_coordinates = tuple((x, y) for y in y_axis for x in x_axis)
    canonical_park = scenario.path_policy.park_xy_board_mm
    baseline_coordinate = (canonical_park[0], canonical_park[1])
    include_baseline = baseline_coordinate not in lattice_coordinates
    raw_count = len(lattice_coordinates) + int(include_baseline)
    if raw_count > selected_policy.maximum_coarse_raw_candidates:
        raise ParkOptimizationError(
            f"coarse lattice has {raw_count} raw candidates; maximum is "
            f"{selected_policy.maximum_coarse_raw_candidates}"
        )
    coarse_rows = [
        _geometry_proposal(
            context,
            selected_policy,
            keepouts,
            tags,
            proposal_id=f"coarse-{row_index:03d}-{column_index:03d}",
            stage="COARSE",
            anchor_candidate_id=None,
            x=x,
            y=y,
            transit_z_mm=transit_z,
            duplicate=False,
        )
        for row_index, y in enumerate(y_axis)
        for column_index, x in enumerate(x_axis)
    ]
    if include_baseline:
        coarse_rows.append(
            _geometry_proposal(
                context,
                selected_policy,
                keepouts,
                tags,
                proposal_id="coarse-baseline",
                stage="COARSE",
                anchor_candidate_id=None,
                x=baseline_coordinate[0],
                y=baseline_coordinate[1],
                transit_z_mm=transit_z,
                duplicate=False,
            )
        )
    coarse_proposals = tuple(coarse_rows)
    eligible_coarse = tuple(
        row for row in coarse_proposals if row.eligible_for_ik
    )
    if len(eligible_coarse) > selected_policy.maximum_coarse_eligible_candidates:
        raise ParkOptimizationError(
            f"coarse lattice has {len(eligible_coarse)} eligible candidates; "
            f"maximum is {selected_policy.maximum_coarse_eligible_candidates}"
        )
    implementation = _implementation_provenance(solver_class, solver_mode)
    options = IkOptions(
        max_attempts=scenario.ik_policy.max_attempts,
        max_iterations_per_attempt=scenario.ik_policy.max_iterations_per_attempt,
    )
    evaluator = _ParkIkEvaluator(
        context,
        captured_model,
        study,
        options,
        selected_policy.minimum_normalized_arm_joint_margin,
        solver_class,
        selected_policy.maximum_total_ik_solves,
    )
    coarse_evaluations = tuple(
        _evaluate_candidate(row, evaluator, study, canonical_park)
        for row in eligible_coarse
    )
    anchors = tuple(sorted(coarse_evaluations, key=lambda row: row.ranking_key))[
        : selected_policy.refinement_anchor_count
    ]
    seen_coordinates = {
        (row.point_board.x, row.point_board.y, row.point_board.z)
        for row in coarse_proposals
    }
    fine_rows: list[ParkGeometryProposal] = []
    for anchor_index, anchor in enumerate(anchors):
        for offset_index, (offset_x, offset_y) in enumerate(_FINE_OFFSETS):
            x = round(
                anchor.geometry.point_board.x
                + offset_x * selected_policy.refinement_step_mm,
                9,
            )
            y = round(
                anchor.geometry.point_board.y
                + offset_y * selected_policy.refinement_step_mm,
                9,
            )
            coordinate = (x, y, transit_z)
            duplicate = coordinate in seen_coordinates
            fine_rows.append(
                _geometry_proposal(
                    context,
                    selected_policy,
                    keepouts,
                    tags,
                    proposal_id=f"fine-{anchor_index:02d}-{offset_index:02d}",
                    stage="FINE",
                    anchor_candidate_id=anchor.geometry.candidate_id,
                    x=x,
                    y=y,
                    transit_z_mm=transit_z,
                    duplicate=duplicate,
                )
            )
            seen_coordinates.add(coordinate)
    if len(fine_rows) > selected_policy.maximum_refinement_raw_candidates:
        raise ParkOptimizationError("refinement exceeded its raw-candidate budget")
    fine_proposals = tuple(fine_rows)
    eligible_fine = tuple(row for row in fine_proposals if row.eligible_for_ik)
    if len(eligible_fine) > (
        selected_policy.maximum_refinement_eligible_candidates
    ):
        raise ParkOptimizationError(
            "refinement exceeded its eligible-candidate budget"
        )
    fine_evaluations = tuple(
        _evaluate_candidate(row, evaluator, study, canonical_park)
        for row in eligible_fine
    )
    ranked = tuple(
        sorted(
            (*coarse_evaluations, *fine_evaluations),
            key=lambda row: row.ranking_key,
        )
    )
    unique_tool_lengths = len(
        {study.keyboard_tool_length_mm, study.phone_tool_length_mm}
    )
    planned_solve_upper_bound = 2 * (
        selected_policy.maximum_coarse_eligible_candidates
        + selected_policy.maximum_refinement_eligible_candidates
    )
    gripper_lower, gripper_upper = scenario.controller_gripper_intersection_rad
    gripper_value = scenario.fixed_gripper_position.value
    provenance: tuple[tuple[str, Any], ...] = (
        ("snapshot_hash", context.snapshot.snapshot_hash),
        ("manifest_id", context.snapshot.manifest_id),
        ("simulation_bundle_id", context.bundle_lock.bundle_id),
        ("simulation_bundle_sha256", context.bundle_lock.source_lock_sha256),
        ("hardware_profile_hash", context.hardware_profile.profile_hash),
        ("scenario_profile_sha256", scenario.source_profile_sha256),
        ("target_profile_sha256", context.targets.content_sha256),
        ("model_sha256", scenario.model_sha256),
        ("alignment_report_hash", context.alignment.report_hash),
        ("scene_source_hashes", tuple(sorted(context.scene.source_hashes.items()))),
        (
            "documented_selection_reach_report_sha256",
            FREEZE005_REACH_REPORT_SHA256,
        ),
        ("reach_report_artifact_verified", False),
        (
            "reach_selection_binding",
            "DOCUMENTED_REPORT_HASH_PLUS_REVALIDATED_DEFAULT_STUDY_ID_REPLAY",
        ),
        ("selected_study_input_id", study.study_input_id),
        (
            "ik_solver_algorithm_version",
            (
                "DETERMINISTIC_BOUNDED_DLS_V1"
                if solver_class is _CANONICAL_IK_SOLVER
                else "EXPLICIT_TEST_DOUBLE"
            ),
        ),
        ("ik_options", tuple(sorted(_ik_options_dict(options).items()))),
        ("rocell_runtime_version", __version__),
        (
            "controller_joint_intersection_rad",
            tuple(
                (name, tuple(bounds))
                for name, bounds in scenario.controller_joint_intersection_rad.items()
            ),
        ),
        ("fixed_gripper_position_rad", gripper_value),
        ("fixed_gripper_intersection_rad", (gripper_lower, gripper_upper)),
        ("fixed_gripper_in_arm_margin_gate", False),
        ("captured_model_sha256", captured_model_sha256),
        ("captured_model_byte_count", captured_model_byte_count),
        ("captured_model_maximum_bytes", MAX_PINNED_URDF_BYTES),
        ("captured_model_matches_pinned_sha256", True),
        *implementation,
    )
    return ParkOptimizationReport(
        source_provenance=provenance,
        policy=selected_policy,
        selected_study_input=study,
        transit_plane_z_mm=transit_z,
        frozen_baseline_candidate_id=_candidate_id(
            Point3Mm(
                "board",
                baseline_coordinate[0],
                baseline_coordinate[1],
                transit_z,
            )
        ),
        frozen_baseline_was_injected=include_baseline,
        coarse_proposals=coarse_proposals,
        fine_proposals=fine_proposals,
        coarse_evaluations=coarse_evaluations,
        fine_evaluations=fine_evaluations,
        ranked_candidates=ranked,
        actual_ik_solve_count=evaluator.solve_count,
        unique_route_tool_length_count=unique_tool_lengths,
        planned_ik_solve_upper_bound=planned_solve_upper_bound,
    )


def run_park_optimization(
    context: SimulationContext,
    policy: ParkOptimizationPolicy | None = None,
) -> ParkOptimizationReport:
    """Optimize Freeze005 park XY with canonical, simulation-only IK."""

    return _run_park_optimization_with_solver(
        context,
        policy,
        solver_class=_CANONICAL_IK_SOLVER,
        solver_mode="CANONICAL_IN_PACKAGE_IMPLEMENTATION",
    )


__all__ = [
    "FREEZE005_MANIFEST_ID",
    "FREEZE005_REACH_REPORT_SHA256",
    "FREEZE005_SELECTED_STUDY_INPUT_ID",
    "ParkOptimizationError",
    "ParkCandidateEvaluation",
    "ParkOptimizationPolicy",
    "ParkOptimizationReport",
    "run_park_optimization",
]
