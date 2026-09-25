"""Bounded replanning of an unexecuted trajectory suffix after arm-camera vision.

The nominal route is useful until a settled hover observation proves that the
board registration should change.  At that point its *Cartesian intent* is
still valid, but every unexecuted joint solution was computed in the old board
registration and must be discarded.  This module performs that replacement.

The service deliberately has no executor or transport dependency.  It accepts
only an issued :class:`BoardPoseCorrectionDecision` whose status is ``APPLY``;
reconstructs the current tool tip from achieved model-space joints; inserts a
vertical/lateral/vertical correction maneuver at the existing transit plane;
checks that maneuver against the nominal board-frame obstacle proxies; and
re-solves the entire remaining Cartesian suffix under the candidate
``Wv_T_board`` registration.

Three identities remain separate throughout:

* ``source_waypoint_sequence`` identifies retained nominal Cartesian intent;
* ``execution_sequence`` is a fresh, strictly increasing virtual command ID;
* ``trajectory_revision`` identifies the installed registration revision.

This is simulation evidence only.  It cannot install a physical calibration,
emit a controller command, authorize contact, or release any safety gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from rocell.geometry import JointPosition, Point3Mm, RigidTransform, Rotation3, Vec3
from rocell.kinematics import (
    ARM_JOINT_NAMES,
    GRIPPER_JOINT_NAME,
    HAND_TCP_LINK_NAME,
    BoardToolTipTarget,
    IkOptions,
    RoArmM3NumericalIk,
)
from rocell.motion import MotionPhase

from ._pinned_model import PinnedModelLoadError, load_pinned_urdf
from .arm_camera_pose import (
    AchievedJointStateSource,
    AchievedModelJointPositions,
    achieved_joint_sample_sha256,
)
from .board_pose_correction import (
    BoardPoseCorrectionDecision,
    BoardPoseCorrectionStatus,
    BoardRegistration,
)
from .context import SimulationContext, revalidate_simulation_context
from .runtime_ports import (
    ArmFeedbackSample,
    RuntimeAuthority,
    RuntimeExecutionMode,
)
from .trajectory_simulation import (
    CartesianRouteWaypoint,
    JointTrajectoryWaypointResult,
    TrajectorySimulationReport,
    evaluate_joint_trajectory_solution,
)


CORRECTED_TRAJECTORY_SUFFIX_SCHEMA = "rocell.corrected_trajectory_suffix.v1"
MAX_CORRECTED_SUFFIX_WAYPOINTS = 512
MAX_EXECUTION_SEQUENCE = 1_000_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_IMPLEMENTATION_BYTES = 2 * 1024 * 1024
_IMPLEMENTATION_DEPENDENCIES = (
    "application/corrected_trajectory_suffix.py",
    "application/trajectory_simulation.py",
    "application/board_pose_correction.py",
    "application/_pinned_model.py",
    "geometry/transforms.py",
    "geometry/urdf.py",
    "kinematics/ik.py",
    "simulation/scene.py",
)


class CorrectedTrajectorySuffixError(ValueError):
    """A correction replan input violates the fail-closed suffix contract."""


class CorrectionPathRole(str, Enum):
    """Why a waypoint exists in the replacement suffix."""

    ASCEND_TO_CORRECTION_PLANE = "ASCEND_TO_CORRECTION_PLANE"
    LATERAL_ON_CORRECTION_PLANE = "LATERAL_ON_CORRECTION_PLANE"
    DESCEND_TO_CORRECTED_HOVER = "DESCEND_TO_CORRECTED_HOVER"
    RETAINED_CARTESIAN_INTENT = "RETAINED_CARTESIAN_INTENT"


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _authority() -> RuntimeAuthority:
    return RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL)


def _authority_dict() -> dict[str, object]:
    value = _authority()
    return {
        "execution_mode": value.execution_mode.value,
        "hardware_accessed": value.hardware_accessed,
        "hardware_commands_generated": value.hardware_commands_generated,
        "live_motion_authorized": value.live_motion_authorized,
        "physical_contact_authorized": value.physical_contact_authorized,
        "physical_release_effect": value.physical_release_effect,
    }


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CorrectedTrajectorySuffixError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _implementation_hash() -> str:
    """Bind replanning to every source that defines its geometry and gates."""

    rocell_root = Path(__file__).resolve(strict=True).parents[1]
    hashes: dict[str, str] = {}
    for relative in _IMPLEMENTATION_DEPENDENCIES:
        path = rocell_root / relative
        try:
            with path.open("rb") as stream:
                payload = stream.read(_MAX_IMPLEMENTATION_BYTES + 1)
        except OSError as exc:
            raise CorrectedTrajectorySuffixError(
                f"cannot read correction implementation dependency {relative}"
            ) from exc
        if len(payload) > _MAX_IMPLEMENTATION_BYTES:
            raise CorrectedTrajectorySuffixError(
                f"correction implementation dependency {relative} is too large"
            )
        hashes[relative] = hashlib.sha256(payload).hexdigest()
    return _stable_hash(
        {
            "schema": "rocell.corrected_suffix_implementation_bundle.v1",
            "sources": hashes,
        }
    )


def _point_dict(point: Point3Mm) -> dict[str, object]:
    return {"frame": point.frame, "xyz_mm": [point.x, point.y, point.z]}


def _bounded_sequence(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorrectedTrajectorySuffixError(f"{label} must be an integer")
    if not 0 <= value <= MAX_EXECUTION_SEQUENCE:
        raise CorrectedTrajectorySuffixError(
            f"{label} must be within [0, {MAX_EXECUTION_SEQUENCE}]"
        )
    return value


def _distance(left: Point3Mm, right: Point3Mm) -> float:
    if left.frame != right.frame:
        raise CorrectedTrajectorySuffixError("cannot measure points in different frames")
    return math.sqrt(
        (left.x - right.x) ** 2
        + (left.y - right.y) ** 2
        + (left.z - right.z) ** 2
    )


def _ignored_obstacles_for_semantic_target(semantic_target: str) -> tuple[str, ...]:
    if semantic_target.startswith("keyboard:"):
        return ("keyboard", "station:keyboard_left", "station:keyboard_right")
    if semantic_target.startswith("phone:"):
        return ("phone", "station:phone_tcp")
    raise CorrectedTrajectorySuffixError(
        f"unsupported correction semantic target {semantic_target!r}"
    )


def _board_T_world(registration: BoardRegistration) -> RigidTransform:
    """Convert selected ``Wv_T_board`` to the IK solver's ``board_T_world``."""

    board_T_Wv = registration.Wv_T_board.inverse()
    return RigidTransform(
        "board",
        "world",
        board_T_Wv.rotation,
        board_T_Wv.translation_mm,
    )


def _nominal_Wv_T_board(trajectory: TrajectorySimulationReport) -> RigidTransform:
    nominal = trajectory.study_input.board_T_vendor_world
    if nominal.parent_frame != "board" or nominal.child_frame != "world":
        raise CorrectedTrajectorySuffixError(
            "trajectory study input must contain board_T_world"
        )
    board_T_Wv = RigidTransform(
        "board", "Wv", nominal.rotation, nominal.translation_mm
    )
    return board_T_Wv.inverse()


def _validate_achieved_feedback_sample(
    context: SimulationContext,
    sample: ArmFeedbackSample[AchievedModelJointPositions],
    *,
    expected_execution_sequence: int,
) -> tuple[dict[str, float], str]:
    """Validate the achieved-state envelope used as the replan boundary.

    A naked joint mapping is deliberately insufficient here: the replacement
    must be correlated to the command that actually reached the virtual plant.
    The runtime-port sample binds source kind, command sequence, timestamp,
    stale flag, the complete six-joint vector, and the source-state digest.
    """

    if not isinstance(sample, ArmFeedbackSample):
        raise TypeError("achieved_feedback_sample must be an ArmFeedbackSample")
    if not isinstance(sample.feedback, AchievedModelJointPositions):
        raise TypeError(
            "achieved_feedback_sample.feedback must be AchievedModelJointPositions"
        )
    if sample.stale:
        raise CorrectedTrajectorySuffixError("achieved feedback sample is stale")
    if sample.sequence != expected_execution_sequence:
        raise CorrectedTrajectorySuffixError(
            "achieved feedback sequence differs from the executed hover command"
        )
    if sample.feedback.source_kind is not AchievedJointStateSource.VIRTUAL_PLANT:
        raise CorrectedTrajectorySuffixError(
            "correction replanning requires VIRTUAL_PLANT achieved feedback"
        )
    values = sample.feedback.positions_by_name
    parsed: dict[str, float] = {}
    bounds = context.scenario.controller_joint_intersection_rad
    for name in ARM_JOINT_NAMES:
        number = values[name].value
        if not math.isfinite(number):
            raise CorrectedTrajectorySuffixError(
                f"achieved joint {name!r} must be finite"
            )
        lower, upper = bounds[name]
        if not lower <= number <= upper:
            raise CorrectedTrajectorySuffixError(
                f"achieved joint {name!r} leaves the controller/URDF intersection"
            )
        parsed[name] = number
    gripper = values[GRIPPER_JOINT_NAME].value
    gripper_lower, gripper_upper = context.scenario.controller_gripper_intersection_rad
    if not gripper_lower <= gripper <= gripper_upper:
        raise CorrectedTrajectorySuffixError(
            "achieved gripper leaves the controller/URDF intersection"
        )
    if gripper != context.scenario.fixed_gripper_position.value:
        raise CorrectedTrajectorySuffixError(
            "achieved gripper differs from the fixed scenario gripper position"
        )
    return parsed, achieved_joint_sample_sha256(sample)


def _current_tip_in_selected_board(
    *,
    model: Any,
    selected_registration: BoardRegistration,
    arm_positions_rad: Mapping[str, float],
    fixed_gripper_position: JointPosition,
    tool_length_mm: float,
) -> Point3Mm:
    state = {
        name: JointPosition.radians(arm_positions_rad[name])
        for name in ARM_JOINT_NAMES
    }
    state[GRIPPER_JOINT_NAME] = fixed_gripper_position
    world_T_hand = model.forward_kinematics(state)[HAND_TCP_LINK_NAME]
    hand_T_tip = RigidTransform(
        HAND_TCP_LINK_NAME,
        "tool_tip",
        Rotation3.identity(),
        Vec3(0.0, 0.0, -tool_length_mm),
    )
    world_T_tip = world_T_hand.compose(hand_T_tip)
    Wv_T_tip = RigidTransform(
        "Wv",
        "tool_tip",
        world_T_tip.rotation,
        world_T_tip.translation_mm,
    )
    board_T_Wv = selected_registration.Wv_T_board.inverse()
    point_Wv = Point3Mm(
        "Wv",
        Wv_T_tip.translation_mm.x,
        Wv_T_tip.translation_mm.y,
        Wv_T_tip.translation_mm.z,
    )
    return board_T_Wv.transform_point(point_Wv)


@dataclass(frozen=True, slots=True)
class CorrectionSegmentCheck:
    """One full correction-leg clearance result before densification."""

    check_id: str
    role: CorrectionPathRole
    start_board: Point3Mm
    end_board: Point3Mm
    clearance_mm: float
    ignored_obstacle_ids: tuple[str, ...]
    checked_obstacle_ids: tuple[str, ...]
    colliding_obstacle_ids: tuple[str, ...]
    method: str

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or not self.check_id:
            raise CorrectedTrajectorySuffixError("correction check ID is invalid")
        if not isinstance(self.role, CorrectionPathRole):
            raise TypeError("correction check role must be CorrectionPathRole")
        for name in ("start_board", "end_board"):
            point = getattr(self, name)
            if not isinstance(point, Point3Mm) or point.frame != "board":
                raise CorrectedTrajectorySuffixError(
                    f"{name} must be a board-frame Point3Mm"
                )
        if (
            isinstance(self.clearance_mm, bool)
            or not isinstance(self.clearance_mm, (int, float))
            or not math.isfinite(float(self.clearance_mm))
            or self.clearance_mm < 0.0
        ):
            raise CorrectedTrajectorySuffixError(
                "correction clearance must be finite and non-negative"
            )
        object.__setattr__(self, "clearance_mm", float(self.clearance_mm))
        for name in (
            "ignored_obstacle_ids",
            "checked_obstacle_ids",
            "colliding_obstacle_ids",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) or not item for item in value
            ):
                raise CorrectedTrajectorySuffixError(
                    f"{name} must be an immutable tuple of IDs"
                )
            if len(value) != len(set(value)):
                raise CorrectedTrajectorySuffixError(f"{name} contains duplicates")
        if not set(self.colliding_obstacle_ids).issubset(
            self.checked_obstacle_ids
        ):
            raise CorrectedTrajectorySuffixError(
                "colliding obstacles must be a checked subset"
            )
        if not isinstance(self.method, str) or not self.method:
            raise CorrectedTrajectorySuffixError("correction check method is invalid")

    @property
    def passed(self) -> bool:
        return not self.colliding_obstacle_ids

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "role": self.role.value,
            "start_board": _point_dict(self.start_board),
            "end_board": _point_dict(self.end_board),
            "clearance_mm": self.clearance_mm,
            "ignored_obstacle_ids": list(self.ignored_obstacle_ids),
            "checked_obstacle_ids": list(self.checked_obstacle_ids),
            "colliding_obstacle_ids": list(self.colliding_obstacle_ids),
            "method": self.method,
            "passed": self.passed,
            "full_body_collision_evaluated": False,
        }


@dataclass(frozen=True, slots=True)
class CorrectedSuffixWaypoint:
    """One Cartesian replacement waypoint and its two independent identities."""

    execution_sequence: int
    trajectory_revision: int
    source_waypoint_sequence: int | None
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    point_board: Point3Mm
    distance_from_previous_mm: float
    path_role: CorrectionPathRole
    source_check_id: str | None
    source_path_check_passed: bool
    inherited_collision_ids: tuple[str, ...]
    phase_endpoint: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "execution_sequence",
            _bounded_sequence(self.execution_sequence, "execution_sequence"),
        )
        object.__setattr__(
            self,
            "trajectory_revision",
            _bounded_sequence(self.trajectory_revision, "trajectory_revision"),
        )
        if self.source_waypoint_sequence is not None:
            object.__setattr__(
                self,
                "source_waypoint_sequence",
                _bounded_sequence(
                    self.source_waypoint_sequence, "source_waypoint_sequence"
                ),
            )
        if not isinstance(self.phase, MotionPhase):
            raise TypeError("phase must be MotionPhase")
        if not isinstance(self.path_role, CorrectionPathRole):
            raise TypeError("path_role must be CorrectionPathRole")
        if not isinstance(self.point_board, Point3Mm) or self.point_board.frame != "board":
            raise CorrectedTrajectorySuffixError("waypoint point must be in board")
        if (
            isinstance(self.distance_from_previous_mm, bool)
            or not isinstance(self.distance_from_previous_mm, (int, float))
            or not math.isfinite(float(self.distance_from_previous_mm))
            or self.distance_from_previous_mm < 0.0
        ):
            raise CorrectedTrajectorySuffixError(
                "distance_from_previous_mm must be finite and non-negative"
            )
        object.__setattr__(
            self, "distance_from_previous_mm", float(self.distance_from_previous_mm)
        )
        object.__setattr__(
            self, "inherited_collision_ids", tuple(self.inherited_collision_ids)
        )
        if self.action_index is not None:
            _bounded_sequence(self.action_index, "action_index")
        if self.semantic_target is not None and (
            not isinstance(self.semantic_target, str) or not self.semantic_target
        ):
            raise CorrectedTrajectorySuffixError("semantic_target is invalid")
        if self.source_check_id is not None and (
            not isinstance(self.source_check_id, str) or not self.source_check_id
        ):
            raise CorrectedTrajectorySuffixError("source_check_id is invalid")
        if not isinstance(self.source_path_check_passed, bool):
            raise CorrectedTrajectorySuffixError(
                "source_path_check_passed must be boolean"
            )
        if not isinstance(self.phase_endpoint, bool):
            raise CorrectedTrajectorySuffixError("phase_endpoint must be boolean")

    def as_solver_waypoint(self) -> CartesianRouteWaypoint:
        """Present this point to the shared canonical IK acceptance evaluator."""

        return CartesianRouteWaypoint(
            sequence=self.execution_sequence,
            phase=self.phase,
            action_index=self.action_index,
            semantic_target=self.semantic_target,
            point_board=self.point_board,
            distance_from_previous_mm=self.distance_from_previous_mm,
            source_geometric_sequence=(
                -1
                if self.source_waypoint_sequence is None
                else self.source_waypoint_sequence
            ),
            source_check_id=self.source_check_id,
            source_path_check_passed=self.source_path_check_passed,
            inherited_collision_ids=self.inherited_collision_ids,
            phase_endpoint=self.phase_endpoint,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_sequence": self.execution_sequence,
            "trajectory_revision": self.trajectory_revision,
            "source_waypoint_sequence": self.source_waypoint_sequence,
            "phase": self.phase.value,
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "point_board": _point_dict(self.point_board),
            "distance_from_previous_mm": self.distance_from_previous_mm,
            "path_role": self.path_role.value,
            "source_check_id": self.source_check_id,
            "source_path_check_passed": self.source_path_check_passed,
            "inherited_collision_ids": list(self.inherited_collision_ids),
            "phase_endpoint": self.phase_endpoint,
        }


@dataclass(frozen=True, slots=True)
class CorrectedTrajectorySuffix:
    """Immutable evidence for one attempted replacement suffix."""

    source_trajectory_sha256: str
    correction_decision: BoardPoseCorrectionDecision
    replaced_after_source_hover_sequence: int
    previous_execution_sequence: int
    achieved_joint_state_sha256: str
    achieved_maximum_tracking_error_rad: float
    maximum_allowed_tracking_error_rad: float
    correction_plane_z_board_mm: float
    segment_checks: tuple[CorrectionSegmentCheck, ...]
    waypoints: tuple[CorrectedSuffixWaypoint, ...]
    joint_results: tuple[JointTrajectoryWaypointResult, ...]
    total_ik_solves: int
    termination_reason: str
    implementation_sha256: str

    def __post_init__(self) -> None:
        if self.correction_decision.status is not BoardPoseCorrectionStatus.APPLY:
            raise CorrectedTrajectorySuffixError(
                "a replacement suffix requires an APPLY correction decision"
            )
        object.__setattr__(
            self,
            "source_trajectory_sha256",
            _digest(self.source_trajectory_sha256, "source_trajectory_sha256"),
        )
        for name in ("achieved_joint_state_sha256", "implementation_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        for name in (
            "achieved_maximum_tracking_error_rad",
            "maximum_allowed_tracking_error_rad",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0.0
            ):
                raise CorrectedTrajectorySuffixError(
                    f"{name} must be finite and non-negative"
                )
            object.__setattr__(self, name, float(value))
        if (
            self.achieved_maximum_tracking_error_rad
            > self.maximum_allowed_tracking_error_rad + 1e-12
        ):
            raise CorrectedTrajectorySuffixError(
                "achieved hover tracking error exceeds its declared limit"
            )
        _bounded_sequence(
            self.replaced_after_source_hover_sequence,
            "replaced_after_source_hover_sequence",
        )
        _bounded_sequence(self.previous_execution_sequence, "previous_execution_sequence")
        if not isinstance(self.segment_checks, tuple):
            raise CorrectedTrajectorySuffixError("segment_checks must be a tuple")
        if tuple(item.role for item in self.segment_checks) != tuple(
            role
            for role in CorrectionPathRole
            if role is not CorrectionPathRole.RETAINED_CARTESIAN_INTENT
        ):
            raise CorrectedTrajectorySuffixError(
                "segment_checks must contain the three correction legs in order"
            )
        if len({item.check_id for item in self.segment_checks}) != len(
            self.segment_checks
        ):
            raise CorrectedTrajectorySuffixError("correction check IDs must be unique")
        if not isinstance(self.waypoints, tuple) or not (
            1 <= len(self.waypoints) <= MAX_CORRECTED_SUFFIX_WAYPOINTS
        ):
            raise CorrectedTrajectorySuffixError(
                "waypoints must be a bounded immutable tuple"
            )
        if not isinstance(self.joint_results, tuple):
            raise CorrectedTrajectorySuffixError("joint_results must be a tuple")
        expected_sequences = tuple(
            range(
                self.previous_execution_sequence + 1,
                self.previous_execution_sequence + 1 + len(self.waypoints),
            )
        )
        if tuple(item.execution_sequence for item in self.waypoints) != expected_sequences:
            raise CorrectedTrajectorySuffixError(
                "replacement execution sequences must be contiguous and strictly increasing"
            )
        revision = self.correction_decision.candidate_registration.revision
        if any(item.trajectory_revision != revision for item in self.waypoints):
            raise CorrectedTrajectorySuffixError(
                "every replacement waypoint must use the candidate revision"
            )
        if len(self.joint_results) > len(self.waypoints):
            raise CorrectedTrajectorySuffixError("too many joint results")
        for waypoint, result in zip(self.waypoints, self.joint_results):
            if (
                result.waypoint_sequence != waypoint.execution_sequence
                or result.phase is not waypoint.phase
                or result.action_index != waypoint.action_index
                or result.semantic_target != waypoint.semantic_target
            ):
                raise CorrectedTrajectorySuffixError(
                    "replacement waypoint/result correlation changed"
                )
        if self.total_ik_solves != len(self.joint_results):
            raise CorrectedTrajectorySuffixError(
                "total_ik_solves must equal the evaluated result count"
            )
        if not isinstance(self.termination_reason, str) or not self.termination_reason:
            raise CorrectedTrajectorySuffixError("termination_reason is invalid")
        if self.passed and (
            not self.waypoints
            or not all(check.passed for check in self.segment_checks)
            or not all(result.accepted for result in self.joint_results)
            or len(self.joint_results) != len(self.waypoints)
        ):
            raise CorrectedTrajectorySuffixError(
                "a passing replacement must accept every checked waypoint"
            )

    @property
    def passed(self) -> bool:
        return self.termination_reason == "ALL_REPLACEMENT_WAYPOINTS_ACCEPTED"

    @property
    def trajectory_revision(self) -> int:
        return self.correction_decision.candidate_registration.revision

    @property
    def suffix_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": CORRECTED_TRAJECTORY_SUFFIX_SCHEMA,
            "status": "PASS" if self.passed else "FAIL",
            "simulation_only": True,
            "source_trajectory_sha256": self.source_trajectory_sha256,
            "correction_decision_sha256": self.correction_decision.decision_hash,
            "selected_registration_sha256": (
                self.correction_decision.candidate_registration.registration_hash
            ),
            "trajectory_revision": self.trajectory_revision,
            "replacement_boundary": {
                "after_source_hover_sequence": (
                    self.replaced_after_source_hover_sequence
                ),
                "previous_execution_sequence": self.previous_execution_sequence,
                "caller_must_discard_all_old_joint_results_after_boundary": True,
                "atomic_queue_replacement_verified_here": False,
            },
            "achieved_joint_state_sha256": self.achieved_joint_state_sha256,
            "achieved_hover_tracking": {
                "maximum_error_rad": self.achieved_maximum_tracking_error_rad,
                "maximum_allowed_rad": self.maximum_allowed_tracking_error_rad,
                "passed": True,
            },
            "correction_plane_z_board_mm": self.correction_plane_z_board_mm,
            "segment_checks": [item.to_dict() for item in self.segment_checks],
            "waypoints": [item.to_dict() for item in self.waypoints],
            "joint_results": [item.to_dict() for item in self.joint_results],
            "total_ik_solves": self.total_ik_solves,
            "termination_reason": self.termination_reason,
            "implementation_sha256": self.implementation_sha256,
            "unsupported_physical_checks": [
                "ROBOT_LINK_AND_SELF_COLLISION",
                "CAMERA_HOLDER_AND_CABLE_SWEEP",
                "CONTINUOUS_JOINT_PATH",
                "DYNAMICS_AND_CONTACT_FORCE",
            ],
            "authority": _authority_dict(),
        }


@dataclass(frozen=True, slots=True)
class _DraftWaypoint:
    source_waypoint_sequence: int | None
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    point_board: Point3Mm
    path_role: CorrectionPathRole
    source_check_id: str | None
    source_path_check_passed: bool
    inherited_collision_ids: tuple[str, ...]
    phase_endpoint: bool


def _append_densified_leg(
    drafts: list[_DraftWaypoint],
    *,
    start: Point3Mm,
    end: Point3Mm,
    maximum_step_mm: float,
    phase: MotionPhase,
    action_index: int,
    semantic_target: str,
    role: CorrectionPathRole,
    check: CorrectionSegmentCheck,
    endpoint: bool,
    maximum_waypoints: int,
) -> Point3Mm:
    distance = _distance(start, end)
    if distance <= 1e-12:
        return start
    subdivisions = max(1, math.ceil(distance / maximum_step_mm))
    if len(drafts) + subdivisions > maximum_waypoints:
        raise CorrectedTrajectorySuffixError(
            "replacement suffix exceeds the source trajectory resource policy"
        )
    for index in range(1, subdivisions + 1):
        ratio = index / subdivisions
        drafts.append(
            _DraftWaypoint(
                source_waypoint_sequence=None,
                phase=phase,
                action_index=action_index,
                semantic_target=semantic_target,
                point_board=Point3Mm(
                    "board",
                    start.x + ratio * (end.x - start.x),
                    start.y + ratio * (end.y - start.y),
                    start.z + ratio * (end.z - start.z),
                ),
                path_role=role,
                source_check_id=check.check_id,
                source_path_check_passed=check.passed,
                inherited_collision_ids=check.colliding_obstacle_ids,
                phase_endpoint=endpoint and index == subdivisions,
            )
        )
    return end


def replan_corrected_trajectory_suffix(
    context: SimulationContext,
    trajectory: TrajectorySimulationReport,
    correction_decision: BoardPoseCorrectionDecision,
    *,
    hover_waypoint_sequence: int,
    previous_execution_sequence: int,
    achieved_feedback_sample: ArmFeedbackSample[AchievedModelJointPositions],
) -> CorrectedTrajectorySuffix:
    """Replace every unexecuted joint solution after one observed hover.

    The caller remains responsible for atomically selecting this suffix in its
    virtual execution queue.  A failed report must never be executed.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be SimulationContext")
    if not isinstance(trajectory, TrajectorySimulationReport):
        raise TypeError("trajectory must be TrajectorySimulationReport")
    if not isinstance(correction_decision, BoardPoseCorrectionDecision):
        raise TypeError("correction_decision must be BoardPoseCorrectionDecision")
    revalidate_simulation_context(context)
    if correction_decision.status is not BoardPoseCorrectionStatus.APPLY:
        raise CorrectedTrajectorySuffixError(
            "only an APPLY correction decision can replace a trajectory suffix"
        )
    hover_sequence = _bounded_sequence(
        hover_waypoint_sequence, "hover_waypoint_sequence"
    )
    prior_execution = _bounded_sequence(
        previous_execution_sequence, "previous_execution_sequence"
    )
    if prior_execution >= MAX_EXECUTION_SEQUENCE:
        raise CorrectedTrajectorySuffixError("execution sequence budget is exhausted")
    final = trajectory.final_round
    if final is None or not final.all_waypoints_accepted:
        raise CorrectedTrajectorySuffixError(
            "source trajectory must have a fully accepted final round"
        )
    indices = [
        index
        for index, waypoint in enumerate(final.waypoints)
        if waypoint.sequence == hover_sequence
    ]
    if len(indices) != 1:
        raise CorrectedTrajectorySuffixError(
            "hover sequence must identify exactly one source waypoint"
        )
    hover_index = indices[0]
    hover = final.waypoints[hover_index]
    hover_result = final.joint_results[hover_index]
    if (
        hover.phase is not MotionPhase.HOVER
        or not hover.phase_endpoint
        or hover.action_index is None
        or hover.semantic_target is None
    ):
        raise CorrectedTrajectorySuffixError(
            "replacement boundary must be a physical-action HOVER endpoint"
        )
    if prior_execution != hover.sequence:
        raise CorrectedTrajectorySuffixError(
            "first-revision execution sequence must equal the executed source hover"
        )
    if hover_index + 1 >= len(final.waypoints):
        raise CorrectedTrajectorySuffixError("hover has no unexecuted suffix")
    if hover_result.waypoint_sequence != hover.sequence or not hover_result.accepted:
        raise CorrectedTrajectorySuffixError("source hover result is not accepted")

    active_nominal = _nominal_Wv_T_board(trajectory)
    expected_active = BoardRegistration(
        revision=0,
        Wv_T_board=active_nominal,
        source_hashes=(
            (
                "reach_study_input",
                _stable_hash(trajectory.study_input.to_dict()),
            ),
        ),
    )
    if (
        correction_decision.active_registration.revision != 0
        or correction_decision.candidate_registration.revision != 1
        or correction_decision.active_registration.registration_hash
        != expected_active.registration_hash
    ):
        raise CorrectedTrajectorySuffixError(
            "first correction lineage differs from the source trajectory registration"
        )
    achieved, achieved_hash = _validate_achieved_feedback_sample(
        context,
        achieved_feedback_sample,
        expected_execution_sequence=prior_execution,
    )
    source_hover_solution = dict(hover_result.solution_arm_joint_positions_rad)
    maximum_tracking_error = max(
        abs(achieved[name] - source_hover_solution[name])
        for name in ARM_JOINT_NAMES
    )
    maximum_allowed_tracking_error = trajectory.policy.maximum_joint_step_rad
    if maximum_tracking_error > maximum_allowed_tracking_error + 1e-12:
        raise CorrectedTrajectorySuffixError(
            "achieved hover tracking error exceeds the source trajectory joint-step policy"
        )

    try:
        loaded = load_pinned_urdf(
            context.scenario.model_path, context.scenario.model_sha256
        )
    except PinnedModelLoadError as exc:
        raise CorrectedTrajectorySuffixError(
            f"could not load the pinned kinematic model: {exc}"
        ) from exc
    selected = correction_decision.candidate_registration
    current = _current_tip_in_selected_board(
        model=loaded.model,
        selected_registration=selected,
        arm_positions_rad=achieved,
        fixed_gripper_position=context.scenario.fixed_gripper_position,
        tool_length_mm=trajectory.tool_length_mm,
    )
    correction_plane_z = max(
        current.z, hover.point_board.z, trajectory.transit_plane_z_mm
    )
    target_device, target_id = hover.semantic_target.split(":", 1)
    try:
        target = context.targets.resolve(target_device, target_id)
    except (KeyError, ValueError) as exc:
        raise CorrectedTrajectorySuffixError(
            "hover semantic target is absent from the locked target catalog"
        ) from exc
    minimum_safe_start_z = (
        target.center.z + context.scenario.path_policy.approach_height_mm
    )
    ignored = _ignored_obstacles_for_semantic_target(hover.semantic_target)
    start_clearance = context.scene.check_point_clearance(
        current,
        clearance_mm=context.scenario.path_policy.segment_clearance_mm,
        ignored_obstacle_ids=ignored,
    )
    if current.z < minimum_safe_start_z or not start_clearance.clear:
        raise CorrectedTrajectorySuffixError(
            "achieved hover is not safely above the newly selected target geometry"
        )
    ascent = Point3Mm("board", current.x, current.y, correction_plane_z)
    lateral = Point3Mm(
        "board", hover.point_board.x, hover.point_board.y, correction_plane_z
    )
    corrected_hover = hover.point_board
    clearance = context.scenario.path_policy.segment_clearance_mm
    leg_specs = (
        (
            "correction-ascent",
            CorrectionPathRole.ASCEND_TO_CORRECTION_PLANE,
            current,
            ascent,
            ignored,
        ),
        (
            "correction-lateral",
            CorrectionPathRole.LATERAL_ON_CORRECTION_PLANE,
            ascent,
            lateral,
            (),
        ),
        (
            "correction-descent",
            CorrectionPathRole.DESCEND_TO_CORRECTED_HOVER,
            lateral,
            corrected_hover,
            ignored,
        ),
    )
    segment_checks: list[CorrectionSegmentCheck] = []
    for check_id, role, start, end, ignored_ids in leg_specs:
        observed = context.scene.check_segment_clearance(
            start,
            end,
            clearance_mm=clearance,
            ignored_obstacle_ids=ignored_ids,
        )
        segment_checks.append(
            CorrectionSegmentCheck(
                check_id=f"revision-{selected.revision}:{check_id}",
                role=role,
                start_board=start,
                end_board=end,
                clearance_mm=clearance,
                ignored_obstacle_ids=tuple(ignored_ids),
                checked_obstacle_ids=observed.checked_obstacle_ids,
                colliding_obstacle_ids=observed.colliding_obstacle_ids,
                method=observed.method,
            )
        )

    # A correction can move the solver onto a different valid IK branch.  Use
    # the source policy's finest already-bounded refinement resolution from the
    # outset, then perform one deterministic solve pass.  This avoids executing
    # a coarse failed attempt and remains within the same declared policy.
    maximum_step = min(
        final.maximum_cartesian_step_mm,
        trajectory.policy.maximum_cartesian_step_mm
        / (2**trajectory.policy.maximum_refinement_rounds),
    )
    replacement_waypoint_cap = min(
        MAX_CORRECTED_SUFFIX_WAYPOINTS,
        trajectory.policy.maximum_waypoints_per_round,
        trajectory.policy.maximum_total_ik_solves,
    )
    drafts: list[_DraftWaypoint] = []
    cursor = current
    cursor = _append_densified_leg(
        drafts,
        start=cursor,
        end=ascent,
        maximum_step_mm=maximum_step,
        phase=MotionPhase.VISION_CORRECT,
        action_index=hover.action_index,
        semantic_target=hover.semantic_target,
        role=CorrectionPathRole.ASCEND_TO_CORRECTION_PLANE,
        check=segment_checks[0],
        endpoint=False,
        maximum_waypoints=replacement_waypoint_cap,
    )
    cursor = _append_densified_leg(
        drafts,
        start=cursor,
        end=lateral,
        maximum_step_mm=maximum_step,
        phase=MotionPhase.VISION_CORRECT,
        action_index=hover.action_index,
        semantic_target=hover.semantic_target,
        role=CorrectionPathRole.LATERAL_ON_CORRECTION_PLANE,
        check=segment_checks[1],
        endpoint=False,
        maximum_waypoints=replacement_waypoint_cap,
    )
    cursor = _append_densified_leg(
        drafts,
        start=cursor,
        end=corrected_hover,
        maximum_step_mm=maximum_step,
        phase=MotionPhase.HOVER,
        action_index=hover.action_index,
        semantic_target=hover.semantic_target,
        role=CorrectionPathRole.DESCEND_TO_CORRECTED_HOVER,
        check=segment_checks[2],
        endpoint=True,
        maximum_waypoints=replacement_waypoint_cap,
    )
    # Even a correction that needs no translational leg can require an
    # orientation update.  Preserve an explicit revalidated hover target.
    if not drafts or drafts[-1].point_board != corrected_hover:
        if len(drafts) >= replacement_waypoint_cap:
            raise CorrectedTrajectorySuffixError(
                "replacement suffix exceeds the source trajectory resource policy"
            )
        drafts.append(
            _DraftWaypoint(
                source_waypoint_sequence=None,
                phase=MotionPhase.HOVER,
                action_index=hover.action_index,
                semantic_target=hover.semantic_target,
                point_board=corrected_hover,
                path_role=CorrectionPathRole.DESCEND_TO_CORRECTED_HOVER,
                source_check_id=segment_checks[2].check_id,
                source_path_check_passed=segment_checks[2].passed,
                inherited_collision_ids=segment_checks[2].colliding_obstacle_ids,
                phase_endpoint=True,
            )
        )

    for source in final.waypoints[hover_index + 1 :]:
        distance = _distance(cursor, source.point_board)
        subdivisions = max(1, math.ceil(distance / maximum_step))
        if len(drafts) + subdivisions > replacement_waypoint_cap:
            raise CorrectedTrajectorySuffixError(
                "replacement suffix exceeds the source trajectory resource policy"
            )
        for subdivision in range(1, subdivisions + 1):
            ratio = subdivision / subdivisions
            drafts.append(
                _DraftWaypoint(
                    # Multiple refined points may inherit one nominal segment
                    # endpoint.  Execution identity remains independent.
                    source_waypoint_sequence=source.sequence,
                    phase=source.phase,
                    action_index=source.action_index,
                    semantic_target=source.semantic_target,
                    point_board=Point3Mm(
                        "board",
                        cursor.x + ratio * (source.point_board.x - cursor.x),
                        cursor.y + ratio * (source.point_board.y - cursor.y),
                        cursor.z + ratio * (source.point_board.z - cursor.z),
                    ),
                    path_role=CorrectionPathRole.RETAINED_CARTESIAN_INTENT,
                    source_check_id=source.source_check_id,
                    source_path_check_passed=source.source_path_check_passed,
                    inherited_collision_ids=source.inherited_collision_ids,
                    phase_endpoint=(
                        source.phase_endpoint and subdivision == subdivisions
                    ),
                )
            )
        cursor = source.point_board
    if not drafts or len(drafts) > replacement_waypoint_cap:
        raise CorrectedTrajectorySuffixError(
            "replacement suffix is empty or exceeds its effective waypoint cap"
        )
    if prior_execution + len(drafts) > MAX_EXECUTION_SEQUENCE:
        raise CorrectedTrajectorySuffixError("replacement exceeds execution sequence cap")

    waypoints: list[CorrectedSuffixWaypoint] = []
    previous_point = current
    for offset, draft in enumerate(drafts, start=1):
        distance = _distance(previous_point, draft.point_board)
        if distance > maximum_step + 1e-9:
            raise CorrectedTrajectorySuffixError(
                "replacement Cartesian waypoint exceeds the source densification bound"
            )
        waypoints.append(
            CorrectedSuffixWaypoint(
                execution_sequence=prior_execution + offset,
                trajectory_revision=selected.revision,
                source_waypoint_sequence=draft.source_waypoint_sequence,
                phase=draft.phase,
                action_index=draft.action_index,
                semantic_target=draft.semantic_target,
                point_board=draft.point_board,
                distance_from_previous_mm=distance,
                path_role=draft.path_role,
                source_check_id=draft.source_check_id,
                source_path_check_passed=draft.source_path_check_passed,
                inherited_collision_ids=draft.inherited_collision_ids,
                phase_endpoint=draft.phase_endpoint,
            )
        )
        previous_point = draft.point_board

    scenario = context.scenario
    options = IkOptions(
        max_attempts=scenario.ik_policy.max_attempts,
        max_iterations_per_attempt=scenario.ik_policy.max_iterations_per_attempt,
    )
    solver = RoArmM3NumericalIk(
        model=loaded.model,
        board_T_world=_board_T_world(selected),
        hand_tcp_to_tip_z_mm=-trajectory.tool_length_mm,
        fixed_gripper_position=scenario.fixed_gripper_position,
        ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
        gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
        options=options,
        joint_bounds_rad=scenario.controller_joint_intersection_rad,
    )
    results: list[JointTrajectoryWaypointResult] = []
    previous_solution = achieved
    termination = "CORRECTION_SEGMENT_CLEARANCE_FAILED"
    if all(check.passed for check in segment_checks):
        termination = "ALL_REPLACEMENT_WAYPOINTS_ACCEPTED"
        for waypoint in waypoints:
            seeds = (
                {
                    name: JointPosition.radians(previous_solution[name])
                    for name in ARM_JOINT_NAMES
                },
            )
            solved = solver.solve(
                BoardToolTipTarget(waypoint.point_board),
                seed_joint_positions=seeds,
            )
            result = evaluate_joint_trajectory_solution(
                waypoint.as_solver_waypoint(),
                solved,
                solver,
                scenario.controller_joint_intersection_rad,
                previous_solution,
                trajectory.policy,
            )
            results.append(result)
            if not result.accepted:
                termination = f"REPLACEMENT_WAYPOINT_REJECTED:{result.failure_reason}"
                break
            previous_solution = dict(result.solution_arm_joint_positions_rad)

    implementation_hash = _implementation_hash()
    return CorrectedTrajectorySuffix(
        source_trajectory_sha256=trajectory.report_hash,
        correction_decision=correction_decision,
        replaced_after_source_hover_sequence=hover.sequence,
        previous_execution_sequence=prior_execution,
        achieved_joint_state_sha256=achieved_hash,
        achieved_maximum_tracking_error_rad=maximum_tracking_error,
        maximum_allowed_tracking_error_rad=maximum_allowed_tracking_error,
        correction_plane_z_board_mm=correction_plane_z,
        segment_checks=tuple(segment_checks),
        waypoints=tuple(waypoints),
        joint_results=tuple(results),
        total_ik_solves=len(results),
        termination_reason=termination,
        implementation_sha256=implementation_hash,
    )


__all__ = [
    "CORRECTED_TRAJECTORY_SUFFIX_SCHEMA",
    "MAX_CORRECTED_SUFFIX_WAYPOINTS",
    "CorrectionPathRole",
    "CorrectionSegmentCheck",
    "CorrectedSuffixWaypoint",
    "CorrectedTrajectorySuffix",
    "CorrectedTrajectorySuffixError",
    "replan_corrected_trajectory_suffix",
]
