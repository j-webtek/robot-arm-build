"""Bounded full-catalog mission-route coverage diagnostics.

This service evaluates every target in the locked RC03 catalog through the
canonical discrete trajectory service.  Every target is deliberately an
*independent* park-to-target-to-park route.  Consequently, an early failure
for one target cannot hide later catalog gaps, and the result cannot be
misread as evidence that an arbitrary multi-key sequence is feasible.

Chunks bound orchestration and report structure only.  They are never joined
into a continuous trajectory.  The service has no hardware, camera, serial,
contact-release, or controller-command authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from rocell.kinematics import MAX_TASK_JACOBIAN_FK_EVALUATIONS
from rocell.models.actions import ActionPlan, PressKey, TapPhoneTarget
from rocell.models.units import finite_real
from rocell.motion import MotionPhase
from rocell.typing import (
    compile_development_text,
    development_keyboard_profile,
    development_phone_profile,
)

from .context import SimulationContext, revalidate_simulation_context
from .reach_optimizer import ReachStudyInput
from .trajectory_simulation import (
    JointTrajectoryWaypointResult,
    TrajectorySimulationError,
    TrajectorySimulationPolicy,
    TrajectorySimulationReport,
    run_trajectory_simulation,
)


EXPECTED_KEYBOARD_TARGET_COUNT = 46
EXPECTED_PHONE_TARGET_COUNT = 29
EXPECTED_MISSION_TARGET_COUNT = (
    EXPECTED_KEYBOARD_TARGET_COUNT + EXPECTED_PHONE_TARGET_COUNT
)

_MAX_CHUNK_SIZE = 16
_MAX_CHUNK_COUNT = EXPECTED_MISSION_TARGET_COUNT
_MAX_REFINEMENT_ROUNDS = 1
_MAX_WAYPOINTS_PER_ROUND = 64
_MAX_IK_SOLVES_PER_ROUTE = 128
_MAX_MISSION_WAYPOINT_RECORDS = (
    EXPECTED_MISSION_TARGET_COUNT
    * (_MAX_REFINEMENT_ROUNDS + 1)
    * _MAX_WAYPOINTS_PER_ROUND
)
_MAX_MISSION_IK_SOLVES = (
    EXPECTED_MISSION_TARGET_COUNT * _MAX_IK_SOLVES_PER_ROUTE
)
_MAX_MISSION_TASK_JACOBIAN_FK_EVALUATIONS = (
    _MAX_MISSION_IK_SOLVES * MAX_TASK_JACOBIAN_FK_EVALUATIONS
)
_ORDERED_SINGLE_TARGET_ENDPOINT_PHASES = (
    MotionPhase.PARK,
    MotionPhase.TRANSIT,
    MotionPhase.HOVER,
    MotionPhase.APPROACH,
    MotionPhase.CONTACT,
    MotionPhase.RETRACT,
    MotionPhase.TRANSIT,
    MotionPhase.PARK,
)
_COMMON_ROUTE_PROVENANCE_KEYS = (
    "snapshot_hash",
    "simulation_bundle_id",
    "simulation_bundle_sha256",
    "hardware_profile_hash",
    "target_profile_sha256",
    "model_sha256",
    "loaded_model_sha256",
    "loaded_model_bytes",
    "alignment_report_hash",
    "study_input_id",
    "ik_solver_implementation",
    "ik_solver_algorithm_version",
    "task_jacobian_conditioning_implementation",
    "task_jacobian_conditioning_algorithm_version",
    "task_jacobian_conditioning_solver_mode",
    "task_jacobian_numerical_rank_gate",
    "normalized_task_jacobian_conditioning_gate_enabled",
    "implementation_bundle_sha256",
    "rocell_source_tree_sha256",
    "rocell_runtime_version",
    "ik_options",
)


class MissionRouteCoverageError(ValueError):
    """The complete mission-coverage diagnostic cannot be produced safely."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class MissionRouteCoveragePolicy:
    """Resource limits for 75 independent single-target trajectory studies."""

    orchestration_chunk_size: int = 8
    maximum_cartesian_step_mm: float = 30.0
    maximum_joint_step_rad: float = 0.35
    minimum_normalized_arm_joint_margin: float = 0.01
    maximum_refinement_rounds: int = 1
    maximum_waypoints_per_round: int = 64
    maximum_total_ik_solves_per_route: int = 128

    def __post_init__(self) -> None:
        for name, lower, upper in (
            ("maximum_cartesian_step_mm", 1.0, 100.0),
            ("maximum_joint_step_rad", 0.01, 1.0),
            ("minimum_normalized_arm_joint_margin", 1e-6, 0.49),
        ):
            value = finite_real(getattr(self, name), name=name)
            if not lower <= value <= upper:
                raise MissionRouteCoverageError(
                    f"{name} must be in [{lower}, {upper}]"
                )
            object.__setattr__(self, name, value)
        for name, lower, upper in (
            ("orchestration_chunk_size", 1, _MAX_CHUNK_SIZE),
            ("maximum_refinement_rounds", 0, _MAX_REFINEMENT_ROUNDS),
            ("maximum_waypoints_per_round", 8, _MAX_WAYPOINTS_PER_ROUND),
            (
                "maximum_total_ik_solves_per_route",
                8,
                _MAX_IK_SOLVES_PER_ROUTE,
            ),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise MissionRouteCoverageError(
                    f"{name} must be an integer in [{lower}, {upper}]"
                )

    @property
    def planned_maximum_waypoint_records(self) -> int:
        return (
            EXPECTED_MISSION_TARGET_COUNT
            * (self.maximum_refinement_rounds + 1)
            * self.maximum_waypoints_per_round
        )

    @property
    def planned_maximum_ik_solves(self) -> int:
        return (
            EXPECTED_MISSION_TARGET_COUNT
            * self.maximum_total_ik_solves_per_route
        )

    @property
    def planned_maximum_task_jacobian_fk_evaluations(self) -> int:
        return (
            self.planned_maximum_ik_solves
            * MAX_TASK_JACOBIAN_FK_EVALUATIONS
        )

    def trajectory_policy(
        self, park_xy_board_mm: tuple[float, float]
    ) -> TrajectorySimulationPolicy:
        """Build the exact downstream policy for one independent target."""

        return TrajectorySimulationPolicy(
            maximum_cartesian_step_mm=self.maximum_cartesian_step_mm,
            maximum_joint_step_rad=self.maximum_joint_step_rad,
            minimum_normalized_arm_joint_margin=(
                self.minimum_normalized_arm_joint_margin
            ),
            maximum_refinement_rounds=self.maximum_refinement_rounds,
            maximum_waypoints_per_round=self.maximum_waypoints_per_round,
            maximum_total_ik_solves=self.maximum_total_ik_solves_per_route,
            maximum_route_targets=1,
            park_xy_board_mm=park_xy_board_mm,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": "INDEPENDENT_FULL_CATALOG_ROUTE_COVERAGE_V1",
            "orchestration_chunk_size": self.orchestration_chunk_size,
            "route_semantics": "ONE_TARGET_PER_INDEPENDENT_PARK_TO_PARK_ROUTE",
            "maximum_cartesian_step_mm": self.maximum_cartesian_step_mm,
            "maximum_joint_step_rad": self.maximum_joint_step_rad,
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "maximum_refinement_rounds": self.maximum_refinement_rounds,
            "maximum_waypoints_per_round": self.maximum_waypoints_per_round,
            "maximum_total_ik_solves_per_route": (
                self.maximum_total_ik_solves_per_route
            ),
            "maximum_targets_per_route": 1,
            "expected_catalog": {
                "keyboard": EXPECTED_KEYBOARD_TARGET_COUNT,
                "phone": EXPECTED_PHONE_TARGET_COUNT,
                "total": EXPECTED_MISSION_TARGET_COUNT,
            },
            "planned_resource_upper_bounds": {
                "waypoint_records": self.planned_maximum_waypoint_records,
                "ik_solves": self.planned_maximum_ik_solves,
                "task_jacobian_fk_evaluations": (
                    self.planned_maximum_task_jacobian_fk_evaluations
                ),
            },
            "hard_implementation_caps": {
                "orchestration_chunk_size": _MAX_CHUNK_SIZE,
                "orchestration_chunks": _MAX_CHUNK_COUNT,
                "target_routes": EXPECTED_MISSION_TARGET_COUNT,
                "refinement_rounds_per_route": _MAX_REFINEMENT_ROUNDS,
                "waypoints_per_round": _MAX_WAYPOINTS_PER_ROUND,
                "ik_solves_per_route": _MAX_IK_SOLVES_PER_ROUTE,
                "mission_waypoint_records": _MAX_MISSION_WAYPOINT_RECORDS,
                "mission_ik_solves": _MAX_MISSION_IK_SOLVES,
                "task_jacobian_fk_evaluations_per_evaluated_waypoint": (
                    MAX_TASK_JACOBIAN_FK_EVALUATIONS
                ),
                "mission_task_jacobian_fk_evaluations": (
                    _MAX_MISSION_TASK_JACOBIAN_FK_EVALUATIONS
                ),
            },
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class MissionRouteFailureEvidence:
    """Compact first-failure evidence for an independent target route."""

    reason: str
    phase: str | None
    waypoint_sequence: int | None
    semantic_target: str | None
    position_error_mm: float | None
    alignment_error_rad: float | None
    minimum_normalized_arm_joint_margin: float | None
    task_jacobian_numerical_rank: int | None
    normalized_minimum_task_jacobian_singular_value: float | None
    task_jacobian_condition_number: float | None
    source_check_id: str | None
    inherited_collision_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "phase": self.phase,
            "waypoint_sequence": self.waypoint_sequence,
            "semantic_target": self.semantic_target,
            "position_error_mm": self.position_error_mm,
            "alignment_error_rad": self.alignment_error_rad,
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "solver_weighted_task_jacobian": {
                "numerical_rank": self.task_jacobian_numerical_rank,
                "normalized_minimum_singular_value": (
                    self.normalized_minimum_task_jacobian_singular_value
                ),
                "condition_number": self.task_jacobian_condition_number,
            },
            "source_check_id": self.source_check_id,
            "inherited_collision_ids": list(self.inherited_collision_ids),
        }


@dataclass(frozen=True, slots=True)
class MissionTargetRouteEvidence:
    """Compact evidence retained from one canonical trajectory report."""

    route_ordinal: int
    chunk_id: str
    device: str
    target_id: str
    semantic_character_sha256: str
    action_plan_hash: str
    trajectory_report_hash: str
    trajectory_status: str
    termination_reason: str
    geometry_all_checks_passed: bool
    ordered_single_target_route_planned: bool
    contact_endpoint_planned: bool
    contact_endpoint_evaluated: bool
    contact_endpoint_accepted: bool
    all_waypoints_accepted: bool
    round_count: int
    planned_waypoint_count: int
    evaluated_waypoint_count: int
    total_ik_solves: int
    task_jacobian_evaluated_waypoint_count: int
    task_jacobian_fk_evaluations: int
    minimum_normalized_arm_joint_margin: float | None
    minimum_task_jacobian_numerical_rank: int | None
    minimum_normalized_task_jacobian_singular_value: float | None
    maximum_task_jacobian_condition_number: float | None
    maximum_adjacent_joint_delta_rad: float | None
    first_failure: MissionRouteFailureEvidence | None

    @property
    def accepted(self) -> bool:
        return (
            self.geometry_all_checks_passed
            and self.ordered_single_target_route_planned
            and self.contact_endpoint_planned
            and self.contact_endpoint_evaluated
            and self.contact_endpoint_accepted
            and self.all_waypoints_accepted
            and self.first_failure is None
        )

    @property
    def failure_reason(self) -> str | None:
        if self.accepted:
            return None
        if self.first_failure is not None:
            return self.first_failure.reason
        return self.termination_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_ordinal": self.route_ordinal,
            "chunk_id": self.chunk_id,
            "device": self.device,
            "target_id": self.target_id,
            "semantic_character_sha256": self.semantic_character_sha256,
            "action_plan_hash": self.action_plan_hash,
            "trajectory_report_hash": self.trajectory_report_hash,
            "trajectory_status": self.trajectory_status,
            "termination_reason": self.termination_reason,
            "accepted": self.accepted,
            "geometry_all_checks_passed": self.geometry_all_checks_passed,
            "ordered_single_target_route_planned": (
                self.ordered_single_target_route_planned
            ),
            "contact_endpoint": {
                "planned": self.contact_endpoint_planned,
                "evaluated": self.contact_endpoint_evaluated,
                "accepted": self.contact_endpoint_accepted,
            },
            "all_waypoints_accepted": self.all_waypoints_accepted,
            "round_count": self.round_count,
            "planned_waypoint_count": self.planned_waypoint_count,
            "evaluated_waypoint_count": self.evaluated_waypoint_count,
            "total_ik_solves": self.total_ik_solves,
            "task_jacobian_evaluated_waypoint_count": (
                self.task_jacobian_evaluated_waypoint_count
            ),
            "task_jacobian_fk_evaluations": (
                self.task_jacobian_fk_evaluations
            ),
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "minimum_task_jacobian_numerical_rank": (
                self.minimum_task_jacobian_numerical_rank
            ),
            "minimum_normalized_task_jacobian_singular_value": (
                self.minimum_normalized_task_jacobian_singular_value
            ),
            "maximum_task_jacobian_condition_number": (
                self.maximum_task_jacobian_condition_number
            ),
            "maximum_adjacent_joint_delta_rad": (
                self.maximum_adjacent_joint_delta_rad
            ),
            "first_failure": (
                None if self.first_failure is None else self.first_failure.to_dict()
            ),
            "hardware_commands_generated": 0,
        }


@dataclass(frozen=True, slots=True)
class MissionRouteCoverageChunk:
    """A bounded orchestration group, never a joined motion sequence."""

    chunk_id: str
    chunk_index: int
    device: str
    routes: tuple[MissionTargetRouteEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "device": self.device,
            "orchestration_only": True,
            "continuous_route": False,
            "target_ids": [route.target_id for route in self.routes],
            "route_count": len(self.routes),
            "accepted_route_count": sum(route.accepted for route in self.routes),
            "routes": [route.to_dict() for route in self.routes],
        }


@dataclass(frozen=True, slots=True)
class MissionRouteCoverageReport:
    """Complete compact evidence for the locked 75-target mission catalog."""

    source_provenance: tuple[tuple[str, Any], ...]
    policy: MissionRouteCoveragePolicy
    study_input: ReachStudyInput
    park_xy_board_mm: tuple[float, float]
    keyboard_target_ids: tuple[str, ...]
    phone_target_ids: tuple[str, ...]
    chunks: tuple[MissionRouteCoverageChunk, ...]

    @property
    def routes(self) -> tuple[MissionTargetRouteEvidence, ...]:
        return tuple(route for chunk in self.chunks for route in chunk.routes)

    @property
    def complete_catalog_evidence(self) -> bool:
        routes = self.routes
        keyboard = tuple(
            route.target_id for route in routes if route.device == "keyboard"
        )
        phone = tuple(
            route.target_id for route in routes if route.device == "phone"
        )
        return (
            len(routes) == EXPECTED_MISSION_TARGET_COUNT
            and keyboard == self.keyboard_target_ids
            and phone == self.phone_target_ids
            and len(set((route.device, route.target_id) for route in routes))
            == EXPECTED_MISSION_TARGET_COUNT
            and "key_a" in phone
        )

    @property
    def all_routes_accepted(self) -> bool:
        return self.complete_catalog_evidence and all(
            route.accepted for route in self.routes
        )

    @property
    def status(self) -> str:
        if not self.complete_catalog_evidence:
            return "MISSION_ROUTE_COVERAGE_INCOMPLETE_FAIL_CLOSED"
        if self.all_routes_accepted:
            return (
                "MISSION_ROUTE_COVERAGE_DIAGNOSTIC_PASS_"
                "WITH_UNSUPPORTED_CHECKS"
            )
        return "MISSION_ROUTE_COVERAGE_DIAGNOSTIC_GAPS_REPORTED"

    @property
    def total_ik_solves(self) -> int:
        return sum(route.total_ik_solves for route in self.routes)

    @property
    def total_waypoint_records(self) -> int:
        return sum(route.planned_waypoint_count for route in self.routes)

    @property
    def total_task_jacobian_fk_evaluations(self) -> int:
        return sum(
            route.task_jacobian_fk_evaluations for route in self.routes
        )

    def _device_summary(self, device: str) -> dict[str, Any]:
        routes = tuple(route for route in self.routes if route.device == device)
        failure_counts: dict[str, int] = {}
        phase_failure_counts: dict[str, int] = {}
        for route in routes:
            reason = route.failure_reason
            if reason is not None:
                failure_counts[reason] = failure_counts.get(reason, 0) + 1
            if route.first_failure is not None:
                phase = route.first_failure.phase or "NOT_REACHED"
                phase_failure_counts[phase] = phase_failure_counts.get(phase, 0) + 1
        margins = tuple(
            route.minimum_normalized_arm_joint_margin
            for route in routes
            if route.minimum_normalized_arm_joint_margin is not None
        )
        normalized_jacobian = tuple(
            route.minimum_normalized_task_jacobian_singular_value
            for route in routes
            if route.minimum_normalized_task_jacobian_singular_value is not None
        )
        ranks = tuple(
            route.minimum_task_jacobian_numerical_rank
            for route in routes
            if route.minimum_task_jacobian_numerical_rank is not None
        )
        return {
            "route_count": len(routes),
            "accepted_route_count": sum(route.accepted for route in routes),
            "geometry_passed_route_count": sum(
                route.geometry_all_checks_passed for route in routes
            ),
            "ordered_route_planned_count": sum(
                route.ordered_single_target_route_planned for route in routes
            ),
            "contact_endpoint_evaluated_count": sum(
                route.contact_endpoint_evaluated for route in routes
            ),
            "contact_endpoint_accepted_count": sum(
                route.contact_endpoint_accepted for route in routes
            ),
            "minimum_normalized_arm_joint_margin": (
                min(margins) if margins else None
            ),
            "minimum_task_jacobian_numerical_rank": (
                min(ranks) if ranks else None
            ),
            "minimum_normalized_task_jacobian_singular_value": (
                min(normalized_jacobian) if normalized_jacobian else None
            ),
            "failure_reason_counts": dict(sorted(failure_counts.items())),
            "first_failure_phase_counts": dict(
                sorted(phase_failure_counts.items())
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.independent_mission_route_coverage.v1",
            "status": self.status,
            "scope": (
                "LOCKED_46_KEYBOARD_PLUS_29_PHONE_INDEPENDENT_"
                "PARK_TO_TARGET_TO_PARK_ROUTES"
            ),
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "contact_authorized": False,
            "physical_release_effect": "NONE",
            "sequence_claim": (
                "NONE_EACH_TARGET_ROUTE_IS_INDEPENDENT_AND_CHUNKS_ARE_"
                "ORCHESTRATION_ONLY"
            ),
            "source_provenance": dict(self.source_provenance),
            "policy": {
                **self.policy.to_dict(),
                "policy_hash": self.policy.policy_hash,
            },
            "study_input": self.study_input.to_dict(),
            "effective_park_xy_board_mm": list(self.park_xy_board_mm),
            "catalog": {
                "keyboard_target_count": len(self.keyboard_target_ids),
                "phone_target_count": len(self.phone_target_ids),
                "total_target_count": (
                    len(self.keyboard_target_ids) + len(self.phone_target_ids)
                ),
                "phone_key_a_present": "key_a" in self.phone_target_ids,
                "keyboard_target_ids": list(self.keyboard_target_ids),
                "phone_target_ids": list(self.phone_target_ids),
                "complete_catalog_evidence": self.complete_catalog_evidence,
            },
            "resource_usage": {
                "chunk_count": len(self.chunks),
                "route_count": len(self.routes),
                "total_waypoint_records": self.total_waypoint_records,
                "total_ik_solves": self.total_ik_solves,
                "total_task_jacobian_fk_evaluations": (
                    self.total_task_jacobian_fk_evaluations
                ),
            },
            "all_routes_accepted": self.all_routes_accepted,
            "device_summary": {
                "keyboard": self._device_summary("keyboard"),
                "phone": self._device_summary("phone"),
            },
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "unsupported_diagnostics": [
                "robot-link, self, holder, camera, cable, and tool-volume collision",
                "full 6D physical singularity/manipulability and force capability",
                "timing, velocity, acceleration, dynamics, payload, and contact force",
                "controller correlation, measured initial-state-to-park motion, and T=104 execution",
                "vision correction, device UI state observation, and action outcome observation",
                "arbitrary multi-target sequence feasibility",
            ],
            "limitations": [
                "Each target starts from and returns to the same nominal Cartesian park pose; initial/final joint-state equality is not claimed and no inter-target joint state is carried.",
                "Chunk order is deterministic bookkeeping and is not a motion plan or arbitrary typing-sequence proof.",
                "Every independent route deliberately crosses the canonical public trajectory boundary and repeats its source, context, and model validation; eliminating that cost requires a future immutable shared-run capture contract.",
                "A target failure does not stop later independent routes, but a source or contract failure aborts the complete report.",
                "Nominal target, device, base, tool, and obstacle inputs remain unmeasured simulation assumptions.",
                "Even a complete PASS is diagnostic evidence only and cannot authorize motion or contact.",
            ],
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class MissionSemanticRoute:
    """One canonical character that exercises exactly one catalog target.

    Keeping this binding public lets independent diagnostic services reuse the
    same 46-key/29-phone accounting without duplicating semantic-profile logic.
    It carries no geometry and grants no execution authority.
    """

    device: str
    target_id: str
    semantic_character: str

    def __post_init__(self) -> None:
        if self.device not in {"keyboard", "phone"}:
            raise MissionRouteCoverageError("semantic route device is invalid")
        if (
            not isinstance(self.target_id, str)
            or not self.target_id
            or self.target_id.strip() != self.target_id
            or len(self.target_id) > 128
            or any(ord(character) < 32 for character in self.target_id)
        ):
            raise MissionRouteCoverageError("semantic route target_id is invalid")
        # Newline and tab are legitimate semantic inputs even though target
        # identifiers themselves may never contain control characters.
        if (
            not isinstance(self.semantic_character, str)
            or len(self.semantic_character) != 1
        ):
            raise MissionRouteCoverageError(
                "semantic route must bind exactly one Unicode character"
            )


def mission_semantic_routes(
    context: SimulationContext,
) -> tuple[MissionSemanticRoute, ...]:
    """Bind every catalog target to exactly one canonical semantic character."""

    keyboard_profile = development_keyboard_profile()
    phone_profile = development_phone_profile()
    keyboard: dict[str, str] = {}
    for character, key_sequence in keyboard_profile.character_keys.items():
        if len(key_sequence) != 1:
            raise MissionRouteCoverageError(
                "locked keyboard coverage requires one physical key per character"
            )
        target_id = key_sequence[0]
        if target_id in keyboard:
            raise MissionRouteCoverageError(
                f"keyboard target {target_id!r} has multiple semantic characters"
            )
        keyboard[target_id] = character
    phone: dict[str, str] = {}
    for character, spec in phone_profile.character_targets.items():
        if spec.target_id in phone:
            raise MissionRouteCoverageError(
                f"phone target {spec.target_id!r} has multiple semantic characters"
            )
        phone[spec.target_id] = character

    keyboard_ids = tuple(sorted(context.targets.keyboard_targets))
    phone_ids = tuple(sorted(context.targets.phone_targets))
    if (
        len(keyboard_ids) != EXPECTED_KEYBOARD_TARGET_COUNT
        or len(phone_ids) != EXPECTED_PHONE_TARGET_COUNT
        or len(keyboard_ids) + len(phone_ids) != EXPECTED_MISSION_TARGET_COUNT
        or "key_a" not in phone_ids
    ):
        raise MissionRouteCoverageError(
            "mission coverage requires the locked 46-key + 29-phone = 75 "
            "target catalog including phone key_a"
        )
    if set(keyboard) != set(keyboard_ids):
        raise MissionRouteCoverageError(
            "keyboard semantic profile is not a one-to-one match for the catalog"
        )
    if set(phone) != set(phone_ids):
        raise MissionRouteCoverageError(
            "phone semantic profile is not a one-to-one match for the catalog"
        )
    return (
        *(
            MissionSemanticRoute("keyboard", target_id, keyboard[target_id])
            for target_id in keyboard_ids
        ),
        *(
            MissionSemanticRoute("phone", target_id, phone[target_id])
            for target_id in phone_ids
        ),
    )


def _physical_target_ids(plan: ActionPlan) -> tuple[str, ...]:
    return tuple(
        action.key_id if isinstance(action, PressKey) else action.target_id
        for action in plan.actions
        if isinstance(action, (PressKey, TapPhoneTarget))
    )


def _common_route_provenance(
    report: TrajectorySimulationReport,
) -> tuple[tuple[str, Any], ...]:
    provenance = dict(report.source_provenance)
    missing = tuple(
        key for key in _COMMON_ROUTE_PROVENANCE_KEYS if key not in provenance
    )
    if missing:
        raise MissionRouteCoverageError(
            f"trajectory report lacks common provenance keys: {missing}"
        )
    return tuple((key, provenance[key]) for key in _COMMON_ROUTE_PROVENANCE_KEYS)


def _first_failure(
    report: TrajectorySimulationReport,
) -> MissionRouteFailureEvidence | None:
    final = report.final_round
    if final is not None:
        waypoints = {
            waypoint.sequence: waypoint for waypoint in final.waypoints
        }
        failed = next(
            (result for result in final.joint_results if not result.accepted),
            None,
        )
        if failed is not None:
            waypoint = waypoints.get(failed.waypoint_sequence)
            conditioning = failed.solver_weighted_task_jacobian
            return MissionRouteFailureEvidence(
                reason=failed.failure_reason or "UNCLASSIFIED_WAYPOINT_REJECTION",
                phase=failed.phase.value,
                waypoint_sequence=failed.waypoint_sequence,
                semantic_target=failed.semantic_target,
                position_error_mm=failed.position_error_mm,
                alignment_error_rad=failed.alignment_error_rad,
                minimum_normalized_arm_joint_margin=(
                    failed.minimum_normalized_arm_joint_margin
                ),
                task_jacobian_numerical_rank=(
                    None if conditioning is None else conditioning.numerical_rank
                ),
                normalized_minimum_task_jacobian_singular_value=(
                    None
                    if conditioning is None
                    else conditioning.normalized_minimum_singular_value
                ),
                task_jacobian_condition_number=(
                    None if conditioning is None else conditioning.condition_number
                ),
                source_check_id=(
                    None if waypoint is None else waypoint.source_check_id
                ),
                inherited_collision_ids=(
                    () if waypoint is None else waypoint.inherited_collision_ids
                ),
            )
    if report.status != (
        "DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS"
    ):
        return MissionRouteFailureEvidence(
            reason=report.termination_reason,
            phase=None,
            waypoint_sequence=None,
            semantic_target=None,
            position_error_mm=None,
            alignment_error_rad=None,
            minimum_normalized_arm_joint_margin=None,
            task_jacobian_numerical_rank=None,
            normalized_minimum_task_jacobian_singular_value=None,
            task_jacobian_condition_number=None,
            source_check_id=None,
            inherited_collision_ids=(),
        )
    return None


def _route_evidence(
    report: TrajectorySimulationReport,
    *,
    plan: ActionPlan,
    request: MissionSemanticRoute,
    route_ordinal: int,
    chunk_id: str,
) -> MissionTargetRouteEvidence:
    if report.device != request.device or report.route_target_ids != (
        request.target_id,
    ):
        raise MissionRouteCoverageError(
            f"trajectory report identity drifted for {request.device}:{request.target_id}"
        )
    final = report.final_round
    final_waypoints = () if final is None else final.waypoints
    endpoint_phases = tuple(
        waypoint.phase for waypoint in final_waypoints if waypoint.phase_endpoint
    )
    ordered_route = endpoint_phases == _ORDERED_SINGLE_TARGET_ENDPOINT_PHASES
    contact_endpoints = tuple(
        waypoint
        for waypoint in final_waypoints
        if waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint
    )
    final_results: Mapping[int, JointTrajectoryWaypointResult] = (
        {}
        if final is None
        else {
            result.waypoint_sequence: result for result in final.joint_results
        }
    )
    contact_result = (
        None
        if len(contact_endpoints) != 1
        else final_results.get(contact_endpoints[0].sequence)
    )
    all_results = tuple(
        result for round_ in report.rounds for result in round_.joint_results
    )
    margins = tuple(
        result.minimum_normalized_arm_joint_margin
        for result in all_results
        if result.minimum_normalized_arm_joint_margin is not None
    )
    conditioning = tuple(
        result.solver_weighted_task_jacobian
        for result in all_results
        if result.solver_weighted_task_jacobian is not None
    )
    condition_numbers = tuple(
        item.condition_number
        for item in conditioning
        if item.condition_number is not None
    )
    joint_deltas = tuple(
        result.maximum_joint_delta_rad
        for result in all_results
        if result.maximum_joint_delta_rad is not None
    )
    return MissionTargetRouteEvidence(
        route_ordinal=route_ordinal,
        chunk_id=chunk_id,
        device=request.device,
        target_id=request.target_id,
        semantic_character_sha256=hashlib.sha256(
            request.semantic_character.encode("utf-8")
        ).hexdigest(),
        action_plan_hash=plan.plan_hash,
        trajectory_report_hash=report.report_hash,
        trajectory_status=report.status,
        termination_reason=report.termination_reason,
        geometry_all_checks_passed=report.geometry_all_checks_passed,
        ordered_single_target_route_planned=ordered_route,
        contact_endpoint_planned=len(contact_endpoints) == 1,
        contact_endpoint_evaluated=contact_result is not None,
        contact_endpoint_accepted=(
            contact_result is not None and contact_result.accepted
        ),
        all_waypoints_accepted=(
            final is not None and final.all_waypoints_accepted
        ),
        round_count=len(report.rounds),
        planned_waypoint_count=sum(
            len(round_.waypoints) for round_ in report.rounds
        ),
        evaluated_waypoint_count=len(all_results),
        total_ik_solves=report.total_ik_solves,
        task_jacobian_evaluated_waypoint_count=(
            report.task_jacobian_evaluated_waypoint_count
        ),
        task_jacobian_fk_evaluations=(
            report.total_task_jacobian_fk_evaluations
        ),
        minimum_normalized_arm_joint_margin=(
            min(margins) if margins else None
        ),
        minimum_task_jacobian_numerical_rank=(
            min(item.numerical_rank for item in conditioning)
            if conditioning
            else None
        ),
        minimum_normalized_task_jacobian_singular_value=(
            min(item.normalized_minimum_singular_value for item in conditioning)
            if conditioning
            else None
        ),
        maximum_task_jacobian_condition_number=(
            max(condition_numbers) if condition_numbers else None
        ),
        maximum_adjacent_joint_delta_rad=(
            max(joint_deltas) if joint_deltas else None
        ),
        first_failure=_first_failure(report),
    )


def _validate_route_budget(
    evidence: MissionTargetRouteEvidence,
    policy: MissionRouteCoveragePolicy,
) -> None:
    maximum_waypoints = (
        (policy.maximum_refinement_rounds + 1)
        * policy.maximum_waypoints_per_round
    )
    if evidence.planned_waypoint_count > maximum_waypoints:
        raise MissionRouteCoverageError(
            f"route {evidence.device}:{evidence.target_id} exceeded its waypoint cap"
        )
    if evidence.total_ik_solves > policy.maximum_total_ik_solves_per_route:
        raise MissionRouteCoverageError(
            f"route {evidence.device}:{evidence.target_id} exceeded its IK cap"
        )
    if evidence.task_jacobian_fk_evaluations > (
        evidence.total_ik_solves * MAX_TASK_JACOBIAN_FK_EVALUATIONS
    ):
        raise MissionRouteCoverageError(
            f"route {evidence.device}:{evidence.target_id} exceeded its Jacobian FK cap"
        )


def run_mission_route_coverage(
    context: SimulationContext,
    study_input: ReachStudyInput,
    park_xy_board_mm: tuple[float, float],
    policy: MissionRouteCoveragePolicy | None = None,
) -> MissionRouteCoverageReport:
    """Evaluate all 75 locked targets as independent bounded routes.

    Individual route rejections are retained and do not stop later targets.
    Invalid source, placement, park, provenance, or resource contracts abort
    the complete report rather than returning partial evidence as a success.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    if not isinstance(study_input, ReachStudyInput):
        raise TypeError("study_input must be a ReachStudyInput")
    revalidate_simulation_context(context)
    selected_policy = policy or MissionRouteCoveragePolicy()
    if not isinstance(selected_policy, MissionRouteCoveragePolicy):
        raise TypeError("policy must be a MissionRouteCoveragePolicy")
    try:
        raw_park = tuple(park_xy_board_mm)
    except TypeError as exc:
        raise MissionRouteCoverageError(
            "park_xy_board_mm must contain explicit x and y"
        ) from exc
    if len(raw_park) != 2:
        raise MissionRouteCoverageError(
            "park_xy_board_mm must contain explicit x and y"
        )
    park_xy = tuple(
        finite_real(value, name="park coordinate") for value in raw_park
    )
    assert len(park_xy) == 2
    typed_park = (park_xy[0], park_xy[1])

    requests = mission_semantic_routes(context)
    if len(requests) != EXPECTED_MISSION_TARGET_COUNT:
        raise MissionRouteCoverageError(
            "mission route materialization did not produce exactly 75 targets"
        )
    if (
        selected_policy.planned_maximum_waypoint_records
        > _MAX_MISSION_WAYPOINT_RECORDS
        or selected_policy.planned_maximum_ik_solves > _MAX_MISSION_IK_SOLVES
        or selected_policy.planned_maximum_task_jacobian_fk_evaluations
        > _MAX_MISSION_TASK_JACOBIAN_FK_EVALUATIONS
    ):
        raise MissionRouteCoverageError(
            "planned mission route coverage exceeds hard resource caps"
        )
    trajectory_policy = selected_policy.trajectory_policy(typed_park)

    # Device-separated chunks bound orchestration only.  Every invocation
    # below still contains exactly one physical target and starts from park.
    request_chunks: list[tuple[str, tuple[MissionSemanticRoute, ...]]] = []
    for device in ("keyboard", "phone"):
        device_requests = tuple(
            request for request in requests if request.device == device
        )
        for offset in range(0, len(device_requests), selected_policy.orchestration_chunk_size):
            request_chunks.append(
                (
                    device,
                    device_requests[
                        offset : offset + selected_policy.orchestration_chunk_size
                    ],
                )
            )
    if not request_chunks or len(request_chunks) > _MAX_CHUNK_COUNT:
        raise MissionRouteCoverageError(
            "orchestration chunk plan exceeds its hard bound"
        )

    chunks: list[MissionRouteCoverageChunk] = []
    expected_provenance: tuple[tuple[str, Any], ...] | None = None
    route_ordinal = 0
    for chunk_index, (device, chunk_requests) in enumerate(request_chunks):
        chunk_id = f"{device}-mission-coverage-{chunk_index:03d}"
        chunk_routes: list[MissionTargetRouteEvidence] = []
        for request in chunk_requests:
            plan = compile_development_text(
                request.device, request.semantic_character
            )
            if _physical_target_ids(plan) != (request.target_id,):
                raise MissionRouteCoverageError(
                    f"semantic compilation did not isolate {request.device}:"
                    f"{request.target_id}"
                )
            try:
                route_report = run_trajectory_simulation(
                    context,
                    plan,
                    study_input,
                    trajectory_policy,
                )
            except TrajectorySimulationError as exc:
                raise MissionRouteCoverageError(
                    "canonical trajectory contract failed for "
                    f"{request.device}:{request.target_id}: {exc}"
                ) from exc
            if route_report.study_input != study_input:
                raise MissionRouteCoverageError(
                    "trajectory report study-input content drifted"
                )
            if route_report.park_xy_board_mm != typed_park:
                raise MissionRouteCoverageError(
                    "trajectory report did not retain the explicit park XY"
                )
            if route_report.policy != trajectory_policy:
                raise MissionRouteCoverageError(
                    "trajectory report did not retain the exact mission route policy"
                )
            route_provenance = dict(route_report.source_provenance)
            if route_provenance.get("plan_hash") != plan.plan_hash:
                raise MissionRouteCoverageError(
                    "trajectory report plan hash differs from the locally compiled plan"
                )
            if route_provenance.get("plan_profile_id") != plan.profile_id:
                raise MissionRouteCoverageError(
                    "trajectory report semantic profile differs from the locally compiled plan"
                )
            expected_tool_length = (
                study_input.keyboard_tool_length_mm
                if request.device == "keyboard"
                else study_input.phone_tool_length_mm
            )
            if route_report.tool_length_mm != expected_tool_length:
                raise MissionRouteCoverageError(
                    "trajectory report route tool differs from the selected layout input"
                )
            common_provenance = _common_route_provenance(route_report)
            if expected_provenance is None:
                expected_provenance = common_provenance
            elif common_provenance != expected_provenance:
                raise MissionRouteCoverageError(
                    "trajectory source provenance changed during mission coverage"
                )
            evidence = _route_evidence(
                route_report,
                plan=plan,
                request=request,
                route_ordinal=route_ordinal,
                chunk_id=chunk_id,
            )
            _validate_route_budget(evidence, selected_policy)
            chunk_routes.append(evidence)
            route_ordinal += 1
        chunks.append(
            MissionRouteCoverageChunk(
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                device=device,
                routes=tuple(chunk_routes),
            )
        )

    if expected_provenance is None:
        raise MissionRouteCoverageError("no route provenance was produced")
    report = MissionRouteCoverageReport(
        source_provenance=expected_provenance,
        policy=selected_policy,
        study_input=study_input,
        park_xy_board_mm=typed_park,
        keyboard_target_ids=tuple(sorted(context.targets.keyboard_targets)),
        phone_target_ids=tuple(sorted(context.targets.phone_targets)),
        chunks=tuple(chunks),
    )
    if not report.complete_catalog_evidence:
        raise MissionRouteCoverageError(
            "complete 46-key + 29-phone route evidence was not produced"
        )
    if (
        report.total_waypoint_records > _MAX_MISSION_WAYPOINT_RECORDS
        or report.total_ik_solves > _MAX_MISSION_IK_SOLVES
        or report.total_task_jacobian_fk_evaluations
        > _MAX_MISSION_TASK_JACOBIAN_FK_EVALUATIONS
    ):
        raise MissionRouteCoverageError(
            "actual mission route coverage exceeded hard resource caps"
        )
    return report


__all__ = [
    "EXPECTED_KEYBOARD_TARGET_COUNT",
    "EXPECTED_MISSION_TARGET_COUNT",
    "EXPECTED_PHONE_TARGET_COUNT",
    "MissionRouteCoverageChunk",
    "MissionRouteCoverageError",
    "MissionRouteCoveragePolicy",
    "MissionRouteCoverageReport",
    "MissionRouteFailureEvidence",
    "MissionSemanticRoute",
    "MissionTargetRouteEvidence",
    "mission_semantic_routes",
    "run_mission_route_coverage",
]
