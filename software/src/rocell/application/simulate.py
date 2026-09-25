"""Typed end-to-end simulation service for keyboard and Android actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.geometry import JointPosition, Point3Mm
from rocell.kinematics import BoardToolTipTarget, IkOptions, RoArmM3NumericalIk
from rocell.models.actions import ActionPlan, VerifyPhoneState
from rocell.motion import (
    GeometricDryRunEngine,
    GeometricPathStep,
    GeometricSimulationReport,
    GeometricSimulationSettings,
    MotionPhase,
)
from rocell.rc03 import Capability, CapabilityAssessment, assess_capability
from rocell.simulation import FiducialObservation, SyntheticFiducialObserver

from .context import SimulationContext, revalidate_simulation_context
from ._pinned_model import (
    MAX_PINNED_URDF_BYTES,
    PinnedModelLoadError,
    load_pinned_urdf,
)


class SimulationRunStatus(str, Enum):
    FAIL = "FAIL_SIMULATION_ONLY"
    PASS = "PASS_SIMULATION_ONLY_WITH_PHYSICAL_HOLDS"
    PASS_WITH_IK_GAPS = (
        "PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS"
    )


class SimulationRunError(RuntimeError):
    """A run cannot start because its immutable preflight is denied."""


def _freeze_json_value(value: Any) -> Any:
    """Recursively remove mutable containers from retained report evidence."""

    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JSON evidence mapping keys must be strings")
        return MappingProxyType(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unsupported JSON evidence value {type(value).__name__}")


def _thaw_json_value(value: Any) -> Any:
    """Return a detached JSON-ready copy of recursively frozen evidence."""

    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class IkPathSample:
    path_sequence: int
    phase: MotionPhase
    semantic_target: str | None
    target_tip_position_board_mm: Point3Mm
    status: str
    converged: bool
    urdf_converged: bool
    controller_intersection_pass: bool
    solution_arm_joint_positions_rad: tuple[tuple[str, float], ...]
    position_error_mm: float
    alignment_error_rad: float
    attempt_count: int
    continuation_seed_used: bool

    def to_dict(self) -> dict[str, Any]:
        point = self.target_tip_position_board_mm
        return {
            "path_sequence": self.path_sequence,
            "phase": self.phase.value,
            "semantic_target": self.semantic_target,
            "target_tip_position_board_mm": {
                "frame": point.frame,
                "x": point.x,
                "y": point.y,
                "z": point.z,
            },
            "status": self.status,
            "converged": self.converged,
            "urdf_converged": self.urdf_converged,
            "controller_intersection_pass": self.controller_intersection_pass,
            "solution_arm_joint_positions_rad": dict(
                self.solution_arm_joint_positions_rad
            ),
            "position_error_mm": self.position_error_mm,
            "alignment_error_rad": self.alignment_error_rad,
            "attempt_count": self.attempt_count,
            "continuation_seed_used": self.continuation_seed_used,
            "hardware_commands_generated": 0,
        }


@dataclass(frozen=True, slots=True)
class IkFeasibilityReport:
    unique_tip_point_count: int
    samples: tuple[IkPathSample, ...]
    maximum_samples: int
    sampling_policy: str
    tool_case_id: str
    board_to_robot_world_state: str
    ready_arm_joint_positions_rad: tuple[tuple[str, float], ...]
    fixed_gripper_position_rad: float
    controller_gripper_intersection_rad: tuple[float, float]
    kinematic_model_expected_sha256: str
    loaded_kinematic_model_sha256: str
    loaded_kinematic_model_bytes: int

    @property
    def converged_count(self) -> int:
        return sum(sample.converged for sample in self.samples)

    @property
    def all_sampled_converged(self) -> bool:
        return bool(self.samples) and self.converged_count == len(self.samples)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.simulation.ik_summary.v1",
            "status": (
                "ALL_SAMPLED_CONVERGED"
                if self.all_sampled_converged
                else "PROVISIONAL_FEASIBILITY_GAPS_REPORTED"
            ),
            "simulation_only": True,
            "required_for_simulation_pass": False,
            "live_motion_authorized": False,
            "hardware_commands_generated": 0,
            "sampling_policy": self.sampling_policy,
            "unique_tip_point_count": self.unique_tip_point_count,
            "sampled_tip_point_count": len(self.samples),
            "omitted_unique_tip_point_count": self.unique_tip_point_count - len(self.samples),
            "converged_count": self.converged_count,
            "all_sampled_converged": self.all_sampled_converged,
            "tool_case_id": self.tool_case_id,
            "board_to_robot_world_state": self.board_to_robot_world_state,
            "ready_arm_joint_positions_rad": dict(self.ready_arm_joint_positions_rad),
            "fixed_gripper_position_rad": self.fixed_gripper_position_rad,
            "controller_gripper_intersection_rad": list(
                self.controller_gripper_intersection_rad
            ),
            "kinematic_model": {
                "expected_sha256": self.kinematic_model_expected_sha256,
                "loaded_sha256": self.loaded_kinematic_model_sha256,
                "loaded_byte_count": self.loaded_kinematic_model_bytes,
                "maximum_bytes": MAX_PINNED_URDF_BYTES,
                "exact_captured_bytes_verified": (
                    self.kinematic_model_expected_sha256
                    == self.loaded_kinematic_model_sha256
                ),
            },
            "results": [sample.to_dict() for sample in self.samples],
            "interpretation": (
                "Diagnostic path-point reachability only. Samples always include park, then "
                "prioritize contact points, and use the prior converged solution as a "
                "deterministic continuation seed. The "
                "provisional controller/URDF joint intersection is enforced. The board "
                "transform and TCP are nominal; solutions are not controller commands."
            ),
        }


@dataclass(frozen=True, slots=True)
class SyntheticVisionReport:
    scenario_id: str
    camera_model: Mapping[str, Any]
    observations: tuple[FiducialObservation, ...]

    def __post_init__(self) -> None:
        frozen = _freeze_json_value(self.camera_model)
        if not isinstance(frozen, Mapping):
            raise TypeError("camera_model must be a mapping")
        object.__setattr__(self, "camera_model", frozen)
        object.__setattr__(self, "observations", tuple(self.observations))

    @property
    def visible_count(self) -> int:
        return sum(observation.visible for observation in self.observations)

    @property
    def all_visible(self) -> bool:
        return bool(self.observations) and self.visible_count == len(self.observations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.simulation.synthetic_vision_check.v1",
            "status": "PASS" if self.all_visible else "FAIL",
            "simulation_only": True,
            "required_for_simulation_pass": True,
            "required_scope": "SYNTHETIC_OVERVIEW_FIXTURE_HEALTH_ONLY",
            "physical_camera_accessed": False,
            "scenario_id": self.scenario_id,
            "scenario_is_arm_mounted_camera": False,
            "camera_model": _thaw_json_value(self.camera_model),
            "tag_count": len(self.observations),
            "visible_tag_count": self.visible_count,
            "all_tags_visible": self.all_visible,
            "observations": [observation.to_dict() for observation in self.observations],
            "eye_on_arm_coverage": {
                "status": "NOT_RUN_INSTALL_TRANSFORMS_MISSING",
                "required_before_physical_motion": True,
                "carrier_frame": "E",
                "vendor_carrier_link": "link2",
                "missing": ["link2_T_holder", "holder_T_C_arm", "camera_intrinsics"],
                "trajectory_synchronized_frames_tested": 0,
            },
        }


@dataclass(frozen=True, slots=True)
class VerificationCoverage:
    explicit_phone_state_requirements: int
    planned_vision_corrections: int
    planned_outcome_verifications: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "NOT_PERFORMED_OBSERVERS_NOT_IMPLEMENTED",
            "required_for_current_simulation_pass": False,
            "required_before_physical_contact": True,
            "phone_ui_state_observation_performed": False,
            "keypress_outcome_observation_performed": False,
            "tap_outcome_observation_performed": False,
            "vision_correction_applied": False,
            "explicit_phone_state_requirements": self.explicit_phone_state_requirements,
            "planned_vision_corrections": self.planned_vision_corrections,
            "planned_outcome_verifications": self.planned_outcome_verifications,
            "interpretation": (
                "VERIFY and VISION_CORRECT path phases are requirements/placeholders, not "
                "evidence that Android UI state or typed output was observed."
            ),
        }


@dataclass(frozen=True, slots=True)
class SimulationRunReport:
    """Complete zero-authority report for one semantic plan and locked context."""

    context: SimulationContext
    capability: CapabilityAssessment
    plan: ActionPlan
    geometry: GeometricSimulationReport
    ik: IkFeasibilityReport
    vision: SyntheticVisionReport
    verification: VerificationCoverage

    @property
    def required_simulation_checks_pass(self) -> bool:
        return (
            self.context.alignment.all_checks_pass
            and self.geometry.all_checks_pass
            and self.vision.all_visible
        )

    @property
    def status(self) -> SimulationRunStatus:
        if not self.required_simulation_checks_pass:
            return SimulationRunStatus.FAIL
        if not self.ik.all_sampled_converged:
            return SimulationRunStatus.PASS_WITH_IK_GAPS
        return SimulationRunStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        snapshot = self.context.snapshot
        profile = self.context.hardware_profile
        targets = self.context.targets
        scene = self.context.scene
        return {
            "schema": "rocell.simulation_run.v1",
            "status": self.status.value,
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "required_simulation_checks_pass": self.required_simulation_checks_pass,
            "all_sampled_ik_converged": self.ik.all_sampled_converged,
            "snapshot": {
                "manifest_id": snapshot.manifest_id,
                "manifest_sha256": snapshot.manifest_sha256,
                "snapshot_hash": snapshot.snapshot_hash,
                "integrity_verified": snapshot.integrity_verified,
                "capability": {
                    "allowed": self.capability.allowed,
                    "reasons": list(self.capability.reasons),
                    "snapshot_hash": self.capability.snapshot_hash,
                },
            },
            "plan": {
                "plan_hash": self.plan.plan_hash,
                "device": self.plan.device.value,
                "profile_id": self.plan.profile_id,
                "action_count": len(self.plan.actions),
                "requested_text_sha256": self.plan.requested_text_sha256,
                "required_calibrations": list(self.plan.required_calibrations),
            },
            "sources": {
                "simulation_bundle": {
                    "bundle_id": self.context.bundle_lock.bundle_id,
                    "lock_sha256": self.context.bundle_lock.source_lock_sha256,
                    "artifacts": {
                        artifact_id: artifact.sha256
                        for artifact_id, artifact in sorted(
                            self.context.bundle_lock.artifacts.items()
                        )
                    },
                    "physical_release_effect": "NONE",
                },
                "hardware_profile_id": profile.profile_id,
                "hardware_profile_hash": profile.profile_hash,
                "simulation_profile_sha256": self.context.scenario.source_profile_sha256,
                "target_profile_sha256": targets.content_sha256,
                "scene_source_hashes": dict(sorted(scene.source_hashes.items())),
                "kinematic_model": self.ik.to_dict()["kinematic_model"],
            },
            "placemat_alignment": {
                **self.context.alignment.to_dict(),
                "report_hash": self.context.alignment.report_hash,
            },
            "geometry": {
                **self.geometry.to_dict(),
                "report_hash": self.geometry.report_hash,
                "required_for_simulation_pass": True,
            },
            "ik": self.ik.to_dict(),
            "vision": self.vision.to_dict(),
            "verification": self.verification.to_dict(),
            "controller_bridge": {
                "status": "NOT_RUN_R_CTRL_CORRELATION_MISSING",
                "controller_cartesian_frame": "R_ctrl",
                "urdf_frames": ["world", "base_link", "hand_tcp"],
                "frame_equivalence_assumed": False,
                "t104_commands_generated": 0,
                "t1041_enabled": False,
            },
            "physical_readiness": {
                "status": snapshot.physical_release_status,
                "safe_to_power_robot": snapshot.safe_to_power_robot,
                "contact_enabled": snapshot.contact_enabled,
                "changed_by_run": False,
                "unresolved_plan_calibrations": list(self.plan.required_calibrations),
            },
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


def _unique_tip_steps(
    steps: Sequence[GeometricPathStep],
) -> tuple[GeometricPathStep, ...]:
    unique: list[GeometricPathStep] = []
    seen: set[tuple[float, float, float]] = set()
    for step in steps:
        point = step.tip_point_board
        if point is None:
            continue
        key = (point.x, point.y, point.z)
        if key in seen:
            continue
        seen.add(key)
        unique.append(step)
    return tuple(unique)


def _stratified(items: Sequence[GeometricPathStep], count: int) -> tuple[GeometricPathStep, ...]:
    if count <= 0 or not items:
        return ()
    if count >= len(items):
        return tuple(items)
    if count == 1:
        return (items[len(items) // 2],)
    indices = tuple(
        (index * (len(items) - 1)) // (count - 1)
        for index in range(count)
    )
    return tuple(items[index] for index in indices)


def sample_ik_steps(
    steps: Sequence[GeometricPathStep],
    maximum: int,
) -> tuple[GeometricPathStep, ...]:
    """Select unique points with required park and contact coverage first."""

    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise ValueError("maximum must be a positive integer")
    unique = _unique_tip_steps(steps)
    parks = tuple(step for step in unique if step.phase is MotionPhase.PARK)
    if maximum == 1:
        return parks[:1] or _stratified(unique, 1)
    selected = list(parks[:1])
    selected_sequences = {step.sequence for step in selected}
    contacts = tuple(step for step in unique if step.phase is MotionPhase.CONTACT)
    contact_capacity = maximum - len(selected)
    selected.extend(_stratified(contacts, contact_capacity))
    selected_sequences.update(step.sequence for step in selected)
    if len(selected) == maximum:
        return tuple(sorted(selected, key=lambda step: step.sequence))
    remaining = tuple(step for step in unique if step.sequence not in selected_sequences)
    selected.extend(_stratified(remaining, maximum - len(selected)))
    return tuple(sorted(selected, key=lambda step: step.sequence))


def _run_ik(context: SimulationContext, geometry: GeometricSimulationReport) -> IkFeasibilityReport:
    return run_scenario_ik(context.scenario, geometry)


def run_scenario_ik(scenario, geometry: GeometricSimulationReport) -> IkFeasibilityReport:
    """Shared numerical sampler; caller must validate its architecture's inputs.

    This routine does not establish a context, calibration or motion authority.
    Legacy and static contexts keep distinct entry points and source checks.
    """
    policy = scenario.ik_policy
    try:
        loaded_model = load_pinned_urdf(
            scenario.model_path,
            scenario.model_sha256,
        )
    except PinnedModelLoadError as exc:
        raise SimulationRunError(
            f"Could not load pinned IK model: {exc}"
        ) from exc
    solver = RoArmM3NumericalIk(
        model=loaded_model.model,
        board_T_world=scenario.board_T_world,
        hand_tcp_to_tip_z_mm=scenario.hand_tcp_to_tip_z_mm,
        fixed_gripper_position=scenario.fixed_gripper_position,
        ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
        gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
        options=IkOptions(
            max_attempts=policy.max_attempts,
            max_iterations_per_attempt=policy.max_iterations_per_attempt,
        ),
        joint_bounds_rad=scenario.controller_joint_intersection_rad,
    )
    unique = _unique_tip_steps(geometry.steps)
    sampled = sample_ik_steps(geometry.steps, policy.maximum_samples)
    continuation_seed: Mapping[str, JointPosition] | None = None
    samples: list[IkPathSample] = []
    for step in sampled:
        point = step.tip_point_board
        assert point is not None
        seed_used = continuation_seed is not None
        result = solver.solve(
            BoardToolTipTarget(Point3Mm("board", point.x, point.y, point.z)),
            seed_joint_positions=(() if continuation_seed is None else (continuation_seed,)),
        )
        solution_values = {
            position.name: position.position.value
            for position in result.solution_arm_joint_positions
        }
        # The solver already searches inside the controller/URDF intersection;
        # retain this check as report-level defense against a solver regression.
        controller_intersection_pass = result.converged and all(
            lower <= solution_values[name] <= upper
            for name, (lower, upper) in scenario.controller_joint_intersection_rad.items()
        )
        accepted = result.converged and controller_intersection_pass
        if accepted:
            continuation_seed = {
                position.name: position.position
                for position in result.solution_arm_joint_positions
            }
        samples.append(
            IkPathSample(
                path_sequence=step.sequence,
                phase=step.phase,
                semantic_target=step.semantic_target,
                target_tip_position_board_mm=point,
                status=(
                    result.status.value
                    if controller_intersection_pass or not result.converged
                    else "CONTROLLER_INTERSECTION_REJECTED"
                ),
                converged=accepted,
                urdf_converged=result.converged,
                controller_intersection_pass=controller_intersection_pass,
                solution_arm_joint_positions_rad=tuple(
                    (position.name, position.position.value)
                    for position in result.solution_arm_joint_positions
                ),
                position_error_mm=result.residual.position_error_mm,
                alignment_error_rad=result.residual.alignment_error_rad,
                attempt_count=len(result.attempts),
                continuation_seed_used=seed_used,
            )
        )
    return IkFeasibilityReport(
        unique_tip_point_count=len(unique),
        samples=tuple(samples),
        maximum_samples=policy.maximum_samples,
        sampling_policy=policy.sampling_policy,
        tool_case_id=scenario.tool_case_id,
        board_to_robot_world_state=scenario.board_T_world_state,
        ready_arm_joint_positions_rad=tuple(
            (name, position.value)
            for name, position in scenario.ready_arm_joint_positions_rad.items()
        ),
        fixed_gripper_position_rad=scenario.fixed_gripper_position.value,
        controller_gripper_intersection_rad=scenario.controller_gripper_intersection_rad,
        kinematic_model_expected_sha256=scenario.model_sha256,
        loaded_kinematic_model_sha256=loaded_model.sha256,
        loaded_kinematic_model_bytes=loaded_model.byte_count,
    )


def _run_vision(context: SimulationContext) -> SyntheticVisionReport:
    fixture = context.scenario.overview
    observations = SyntheticFiducialObserver(
        fixture.camera,
        fixture.camera_T_board,
    ).observe_scene(context.scene)
    return SyntheticVisionReport(
        scenario_id=fixture.scenario_id,
        camera_model=fixture.camera.to_dict(),
        observations=observations,
    )


def run_simulation(context: SimulationContext, plan: ActionPlan) -> SimulationRunReport:
    """Run the complete deterministic pipeline without importing hardware adapters."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    if not isinstance(plan, ActionPlan):
        raise TypeError("plan must be an ActionPlan")
    revalidate_simulation_context(context)
    capability = assess_capability(context.snapshot, Capability.SIMULATED_DRY_RUN)
    if not capability.allowed:
        raise SimulationRunError("Simulation preflight denied: " + "; ".join(capability.reasons))
    policy = context.scenario.path_policy
    settings = GeometricSimulationSettings(
        clearance_above_highest_obstacle_mm=policy.clearance_above_highest_obstacle_mm,
        segment_clearance_mm=policy.segment_clearance_mm,
        hover_height_mm=policy.hover_height_mm,
        approach_height_mm=policy.approach_height_mm,
        contact_overtravel_mm=policy.contact_overtravel_mm,
        park_xy_board_mm=policy.park_xy_board_mm,
    )
    geometry = GeometricDryRunEngine(settings).run(
        plan,
        context.snapshot,
        context.hardware_profile,
        context.scene,
        context.targets,
    )
    ik = _run_ik(context, geometry)
    vision = _run_vision(context)
    verification = VerificationCoverage(
        explicit_phone_state_requirements=sum(
            isinstance(action, VerifyPhoneState) for action in plan.actions
        ),
        planned_vision_corrections=sum(
            step.phase is MotionPhase.VISION_CORRECT for step in geometry.steps
        ),
        planned_outcome_verifications=sum(
            step.phase is MotionPhase.VERIFY for step in geometry.steps
        ),
    )
    return SimulationRunReport(
        context=context,
        capability=capability,
        plan=plan,
        geometry=geometry,
        ik=ik,
        vision=vision,
        verification=verification,
    )
