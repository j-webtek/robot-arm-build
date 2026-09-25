"""Dense full-mission collision bindings for the static B0477 workcell.

The target-route diagnostic in :mod:`rocell.simulation.static_route_collision`
screens one seven-pose, park-to-target-to-park route.  This additive service
instead consumes the *final accepted dense waypoint sequence* produced by the
trajectory simulator.  It evaluates every dense endpoint and one explicitly
supplied joint-interpolated midpoint for every incoming segment.  The caller
must supply complete rigid-body transforms and a freshly sampled arm-harness
envelope at both kinds of sample.

The separation between ``route_waypoint_ordinal`` and
``global_authorization_command_ordinal`` is deliberate.  The first accepted
park pose is a known initial condition and has no command; every later route
waypoint has exactly one mission-global command ordinal.  This module binds
that mapping but neither creates command bytes nor authorizes execution.

Only an endpoint which is both CONTACT and the final endpoint of that phase
may tolerate the exact ``robot:tool_tip``/designated-device overlap.  Dense
CONTACT intermediates and all joint midpoints are evaluated without an
exclusion.  Global exclusions are forbidden by the underlying static route
contract and checked again here.

This remains a bounded, discrete, simulation-only diagnostic.  It does not
derive collision poses from FK, validate physical geometry, prove continuous
clearance, access hardware, emit T=104, or produce physical authorization
evidence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any

from rocell.application.trajectory_simulation import (
    CartesianRouteWaypoint,
    JointTrajectoryWaypointResult,
    TrajectorySearchRound,
    TrajectorySimulationReport,
)
from rocell.geometry import Vec3
from rocell.kinematics import ARM_JOINT_NAMES
from rocell.models.units import finite_real
from rocell.motion import MotionPhase

from .collision import (
    CollisionBindingMode,
    CollisionContractError,
    CollisionEvaluationPolicy,
    CollisionGeometryContract,
    CollisionPair,
    CollisionPose,
    CollisionPoseEvaluation,
    evaluate_collision_pose,
)
from .static_route_collision import (
    REQUIRED_STATIC_ROUTE_SOURCE_KEYS,
    STATIC_ROUTE_BODY_REQUIREMENTS,
    StaticB0477RouteCollisionContract,
    StaticRouteCollisionPolicy,
    StaticRoutePoseResult,
    StaticRouteSampleDisposition,
    StaticRouteTargetBinding,
)


STATIC_B0477_MISSION_ROUTE_REPORT_SCHEMA = (
    "rocell.static_b0477_dense_mission_collision_report.v1"
)
STATIC_B0477_MISSION_ENDPOINT_SCHEMA = (
    "rocell.static_b0477_dense_mission_endpoint_input.v1"
)
STATIC_B0477_MISSION_MIDPOINT_SCHEMA = (
    "rocell.static_b0477_dense_mission_joint_midpoint_input.v1"
)
STATIC_B0477_MISSION_COMMAND_BINDING_SCHEMA = (
    "rocell.static_b0477_dense_mission_command_collision_binding.v1"
)

MAX_STATIC_MISSION_WAYPOINTS = 512
MAX_STATIC_MISSION_INCOMING_MIDPOINTS = MAX_STATIC_MISSION_WAYPOINTS - 1
_SHA256_HEX_LENGTH = 64
_JOINT_MIDPOINT_ABSOLUTE_TOLERANCE_RAD = 1e-12
_TRAJECTORY_POSE_ABSOLUTE_TOLERANCE = 1e-9
MAX_STATIC_MISSION_CONTACT_PENETRATION_MM = 10.0


class StaticMissionRouteError(ValueError):
    """A dense mission/collision binding is malformed or inconsistent."""


class StaticMissionRouteStatus(str, Enum):
    """Outcome of the bounded dense collision diagnostic."""

    PASS_DIAGNOSTIC_ONLY = "PASS_DIAGNOSTIC_ONLY"
    COLLISION_DETECTED = "COLLISION_DETECTED"
    CONTACT_OVERLAP_MISSING = "CONTACT_OVERLAP_MISSING"
    BLOCKED_POSE_INPUT = "BLOCKED_POSE_INPUT"


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise StaticMissionRouteError(f"{label} must be lowercase SHA-256")
    if (
        len(value) != _SHA256_HEX_LENGTH
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StaticMissionRouteError(f"{label} must be lowercase SHA-256")
    return value


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StaticMissionRouteError(f"{label} must be a non-negative integer")
    return value


def _optional_non_negative_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, label)


def _bounded_tuple(
    values: Iterable[Any], maximum: int, label: str
) -> tuple[Any, ...]:
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise TypeError(f"{label} must be iterable") from exc
    result: list[Any] = []
    for _ in range(maximum + 1):
        try:
            result.append(next(iterator))
        except StopIteration:
            return tuple(result)
    raise StaticMissionRouteError(f"{label} exceeds hard maximum {maximum}")


def _joint_vector(
    value: object, label: str
) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, tuple):
        raise StaticMissionRouteError(f"{label} must be an immutable tuple")
    if len(value) != len(ARM_JOINT_NAMES):
        raise StaticMissionRouteError(
            f"{label} must contain exactly {len(ARM_JOINT_NAMES)} arm joints"
        )
    parsed: list[tuple[str, float]] = []
    for index, item in enumerate(value):
        if not isinstance(item, tuple) or len(item) != 2:
            raise StaticMissionRouteError(
                f"{label}[{index}] must be an immutable (name, radians) pair"
            )
        name, raw_position = item
        if name != ARM_JOINT_NAMES[index]:
            raise StaticMissionRouteError(
                f"{label} joint names/order must exactly equal ARM_JOINT_NAMES"
            )
        try:
            position = finite_real(raw_position, name=f"{label}[{name!r}]")
        except (TypeError, ValueError) as exc:
            raise StaticMissionRouteError(
                f"{label}[{name!r}] must be finite radians"
            ) from exc
        parsed.append((name, position))
    return tuple(parsed)


def _zero_authority() -> dict[str, Any]:
    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_messages_generated": 0,
        "can_release_physical_gates": False,
        "can_authorize_motion": False,
        "can_authorize_contact": False,
        "physical_release_effect": "NONE",
    }


@dataclass(frozen=True, slots=True)
class StaticMissionEndpointPose:
    """Complete collision input for one accepted dense route waypoint."""

    route_waypoint_ordinal: int
    global_authorization_command_ordinal: int | None
    joint_positions_rad: tuple[tuple[str, float], ...]
    pose: CollisionPose

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "route_waypoint_ordinal",
            _non_negative_int(
                self.route_waypoint_ordinal, "route_waypoint_ordinal"
            ),
        )
        object.__setattr__(
            self,
            "global_authorization_command_ordinal",
            _optional_non_negative_int(
                self.global_authorization_command_ordinal,
                "global_authorization_command_ordinal",
            ),
        )
        object.__setattr__(
            self,
            "joint_positions_rad",
            _joint_vector(self.joint_positions_rad, "joint_positions_rad"),
        )
        if not isinstance(self.pose, CollisionPose):
            raise TypeError("pose must be CollisionPose")

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": STATIC_B0477_MISSION_ENDPOINT_SCHEMA,
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "global_authorization_command_ordinal": (
                self.global_authorization_command_ordinal
            ),
            "joint_positions_rad": dict(self.joint_positions_rad),
            "pose": self.pose.to_dict(),
            "authority": _zero_authority(),
        }


@dataclass(frozen=True, slots=True)
class StaticMissionIncomingMidpointPose:
    """Complete collision input at the 0.5 joint midpoint of one command."""

    start_route_waypoint_ordinal: int
    end_route_waypoint_ordinal: int
    global_authorization_command_ordinal: int
    interpolation_fraction: float
    joint_positions_rad: tuple[tuple[str, float], ...]
    pose: CollisionPose

    def __post_init__(self) -> None:
        start = _non_negative_int(
            self.start_route_waypoint_ordinal,
            "start_route_waypoint_ordinal",
        )
        end = _non_negative_int(
            self.end_route_waypoint_ordinal,
            "end_route_waypoint_ordinal",
        )
        if end != start + 1:
            raise StaticMissionRouteError(
                "incoming midpoint must bind adjacent route waypoints"
            )
        command = _non_negative_int(
            self.global_authorization_command_ordinal,
            "global_authorization_command_ordinal",
        )
        try:
            fraction = finite_real(
                self.interpolation_fraction, name="interpolation_fraction"
            )
        except (TypeError, ValueError) as exc:
            raise StaticMissionRouteError(
                "interpolation_fraction must be finite"
            ) from exc
        if not math.isclose(fraction, 0.5, rel_tol=0.0, abs_tol=1e-15):
            raise StaticMissionRouteError(
                "incoming collision sample must be the exact 0.5 joint midpoint"
            )
        object.__setattr__(self, "start_route_waypoint_ordinal", start)
        object.__setattr__(self, "end_route_waypoint_ordinal", end)
        object.__setattr__(self, "global_authorization_command_ordinal", command)
        object.__setattr__(self, "interpolation_fraction", 0.5)
        object.__setattr__(
            self,
            "joint_positions_rad",
            _joint_vector(self.joint_positions_rad, "joint_positions_rad"),
        )
        if not isinstance(self.pose, CollisionPose):
            raise TypeError("pose must be CollisionPose")

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": STATIC_B0477_MISSION_MIDPOINT_SCHEMA,
            "start_route_waypoint_ordinal": self.start_route_waypoint_ordinal,
            "end_route_waypoint_ordinal": self.end_route_waypoint_ordinal,
            "global_authorization_command_ordinal": (
                self.global_authorization_command_ordinal
            ),
            "interpolation_fraction": self.interpolation_fraction,
            "joint_positions_rad": dict(self.joint_positions_rad),
            "pose": self.pose.to_dict(),
            "authority": _zero_authority(),
        }


@dataclass(frozen=True, slots=True)
class StaticMissionEndpointResult:
    """Collision result and trajectory identity for one dense endpoint."""

    endpoint: StaticMissionEndpointPose
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    phase_endpoint: bool
    waypoint_sha256: str
    joint_result_sha256: str
    designated_contact_overlap_allowed: bool
    target_binding_sha256: str | None
    pose_result: StaticRoutePoseResult

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, StaticMissionEndpointPose):
            raise TypeError("endpoint must be StaticMissionEndpointPose")
        if not isinstance(self.phase, MotionPhase):
            raise TypeError("phase must be MotionPhase")
        object.__setattr__(
            self, "waypoint_sha256", _sha256(self.waypoint_sha256, "waypoint_sha256")
        )
        object.__setattr__(
            self,
            "joint_result_sha256",
            _sha256(self.joint_result_sha256, "joint_result_sha256"),
        )
        if self.target_binding_sha256 is not None:
            object.__setattr__(
                self,
                "target_binding_sha256",
                _sha256(
                    self.target_binding_sha256, "target_binding_sha256"
                ),
            )
        if not isinstance(self.designated_contact_overlap_allowed, bool):
            raise TypeError("designated_contact_overlap_allowed must be bool")
        if not isinstance(self.phase_endpoint, bool):
            raise TypeError("phase_endpoint must be bool")
        if not isinstance(self.pose_result, StaticRoutePoseResult):
            raise TypeError("pose_result must be StaticRoutePoseResult")

    @property
    def accepted(self) -> bool:
        return self.pose_result.accepted

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_input": {
                "sha256": self.endpoint.content_hash,
                "content": self.endpoint.to_dict(),
            },
            "phase": self.phase.value,
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "phase_endpoint": self.phase_endpoint,
            "waypoint_sha256": self.waypoint_sha256,
            "joint_result_sha256": self.joint_result_sha256,
            "designated_contact_overlap_allowed": (
                self.designated_contact_overlap_allowed
            ),
            "target_binding_sha256": self.target_binding_sha256,
            "accepted": self.accepted,
            "pose_result": self.pose_result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class StaticMissionMidpointResult:
    """Collision result for one command's incoming joint midpoint."""

    midpoint: StaticMissionIncomingMidpointPose
    incoming_phase: MotionPhase
    incoming_action_index: int | None
    incoming_semantic_target: str | None
    pose_result: StaticRoutePoseResult

    def __post_init__(self) -> None:
        if not isinstance(self.midpoint, StaticMissionIncomingMidpointPose):
            raise TypeError("midpoint must be StaticMissionIncomingMidpointPose")
        if not isinstance(self.incoming_phase, MotionPhase):
            raise TypeError("incoming_phase must be MotionPhase")
        if not isinstance(self.pose_result, StaticRoutePoseResult):
            raise TypeError("pose_result must be StaticRoutePoseResult")

    @property
    def accepted(self) -> bool:
        return self.pose_result.accepted

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "midpoint_input": {
                "sha256": self.midpoint.content_hash,
                "content": self.midpoint.to_dict(),
            },
            "incoming_phase": self.incoming_phase.value,
            "incoming_action_index": self.incoming_action_index,
            "incoming_semantic_target": self.incoming_semantic_target,
            "designated_contact_overlap_allowed": False,
            "accepted": self.accepted,
            "pose_result": self.pose_result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class StaticMissionCommandCollisionBinding:
    """Canonical mapping from one mission-global command to collision evidence."""

    global_authorization_command_ordinal: int
    route_waypoint_ordinal: int
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    phase_endpoint: bool
    waypoint_sha256: str
    joint_result_sha256: str
    endpoint_input_sha256: str
    endpoint_result_sha256: str
    incoming_midpoint_input_sha256: str
    incoming_midpoint_result_sha256: str
    target_binding_sha256: str | None
    designated_contact_overlap_allowed: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "global_authorization_command_ordinal",
            _non_negative_int(
                self.global_authorization_command_ordinal,
                "global_authorization_command_ordinal",
            ),
        )
        object.__setattr__(
            self,
            "route_waypoint_ordinal",
            _non_negative_int(
                self.route_waypoint_ordinal, "route_waypoint_ordinal"
            ),
        )
        if not isinstance(self.phase, MotionPhase):
            raise TypeError("phase must be MotionPhase")
        for name in (
            "waypoint_sha256",
            "joint_result_sha256",
            "endpoint_input_sha256",
            "endpoint_result_sha256",
            "incoming_midpoint_input_sha256",
            "incoming_midpoint_result_sha256",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        if self.target_binding_sha256 is not None:
            object.__setattr__(
                self,
                "target_binding_sha256",
                _sha256(
                    self.target_binding_sha256, "target_binding_sha256"
                ),
            )
        if not isinstance(self.phase_endpoint, bool):
            raise TypeError("phase_endpoint must be bool")
        if not isinstance(self.designated_contact_overlap_allowed, bool):
            raise TypeError("designated_contact_overlap_allowed must be bool")

    @property
    def trajectory_command_binding_sha256(self) -> str:
        """Hash the command precursor without claiming wire-command creation."""

        return _canonical_hash(
            {
                "global_authorization_command_ordinal": (
                    self.global_authorization_command_ordinal
                ),
                "route_waypoint_ordinal": self.route_waypoint_ordinal,
                "phase": self.phase.value,
                "action_index": self.action_index,
                "semantic_target": self.semantic_target,
                "phase_endpoint": self.phase_endpoint,
                "waypoint_sha256": self.waypoint_sha256,
                "joint_result_sha256": self.joint_result_sha256,
                "wire_command_present": False,
            }
        )

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": STATIC_B0477_MISSION_COMMAND_BINDING_SCHEMA,
            "global_authorization_command_ordinal": (
                self.global_authorization_command_ordinal
            ),
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "phase": self.phase.value,
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "phase_endpoint": self.phase_endpoint,
            "waypoint_sha256": self.waypoint_sha256,
            "joint_result_sha256": self.joint_result_sha256,
            "trajectory_command_binding_sha256": (
                self.trajectory_command_binding_sha256
            ),
            "endpoint_input_sha256": self.endpoint_input_sha256,
            "endpoint_result_sha256": self.endpoint_result_sha256,
            "incoming_midpoint_input_sha256": (
                self.incoming_midpoint_input_sha256
            ),
            "incoming_midpoint_result_sha256": (
                self.incoming_midpoint_result_sha256
            ),
            "target_binding_sha256": self.target_binding_sha256,
            "designated_contact_overlap_allowed": (
                self.designated_contact_overlap_allowed
            ),
            "authority": _zero_authority(),
        }


@dataclass(frozen=True, slots=True)
class StaticMissionRouteCollisionReport:
    """Self-contained dense-route collision report with permanent zero authority."""

    status: StaticMissionRouteStatus
    device: str
    route_target_ids: tuple[str, ...]
    trajectory_report_sha256: str
    final_round_sha256: str
    plan_sha256: str
    target_profile_sha256: str
    robot_model_sha256: str
    contract: StaticB0477RouteCollisionContract
    policy: StaticRouteCollisionPolicy
    target_bindings: tuple[StaticRouteTargetBinding, ...]
    endpoint_results: tuple[StaticMissionEndpointResult, ...]
    midpoint_results: tuple[StaticMissionMidpointResult, ...]
    command_bindings: tuple[StaticMissionCommandCollisionBinding, ...]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, StaticMissionRouteStatus):
            raise TypeError("status must be StaticMissionRouteStatus")
        if self.device not in {"keyboard", "phone"}:
            raise StaticMissionRouteError("device must be keyboard or phone")
        for name in (
            "route_target_ids",
            "target_bindings",
            "endpoint_results",
            "midpoint_results",
            "command_bindings",
            "blockers",
        ):
            if type(getattr(self, name)) is not tuple:
                raise TypeError(f"{name} must be exactly tuple")
        for name in (
            "trajectory_report_sha256",
            "final_round_sha256",
            "plan_sha256",
            "target_profile_sha256",
            "robot_model_sha256",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        if not isinstance(self.contract, StaticB0477RouteCollisionContract):
            raise TypeError("contract must be StaticB0477RouteCollisionContract")
        if not isinstance(self.policy, StaticRouteCollisionPolicy):
            raise TypeError("policy must be StaticRouteCollisionPolicy")
        self._validate_internal_coverage()

    def _validate_internal_coverage(self) -> None:
        """Reject hollow or cross-wired reports even when status says PASS."""

        targets = tuple(self.target_bindings)
        endpoints = tuple(self.endpoint_results)
        midpoints = tuple(self.midpoint_results)
        commands = tuple(self.command_bindings)
        blockers = tuple(self.blockers)
        if not self.route_target_ids or len(targets) != len(self.route_target_ids):
            raise StaticMissionRouteError(
                "report target bindings do not cover every route target"
            )
        if any(type(item) is not StaticRouteTargetBinding for item in targets):
            raise TypeError("target_bindings must contain StaticRouteTargetBinding")
        for target_id, binding in zip(self.route_target_ids, targets):
            if (
                binding.device != self.device
                or binding.target_id != target_id
                or binding.target_profile_sha256 != self.target_profile_sha256
            ):
                raise StaticMissionRouteError(
                    "report target binding differs from route identity"
                )
        if (
            self.contract.sources.source_hashes.get("target_profile")
            != self.target_profile_sha256
            or self.contract.sources.source_hashes.get("robot_model")
            != self.robot_model_sha256
        ):
            raise StaticMissionRouteError(
                "report contract source hashes differ from trajectory identity"
            )
        if not 2 <= len(endpoints) <= MAX_STATIC_MISSION_WAYPOINTS:
            raise StaticMissionRouteError(
                "report endpoint coverage is outside the dense-route bound"
            )
        if len(midpoints) != len(endpoints) - 1 or len(commands) != len(midpoints):
            raise StaticMissionRouteError(
                "report must contain one midpoint and command binding per incoming endpoint"
            )
        if any(type(item) is not StaticMissionEndpointResult for item in endpoints):
            raise TypeError("endpoint_results must contain StaticMissionEndpointResult")
        if any(type(item) is not StaticMissionMidpointResult for item in midpoints):
            raise TypeError("midpoint_results must contain StaticMissionMidpointResult")
        if any(
            type(item) is not StaticMissionCommandCollisionBinding
            for item in commands
        ):
            raise TypeError(
                "command_bindings must contain StaticMissionCommandCollisionBinding"
            )
        contact_endpoints = tuple(
            item
            for item in endpoints
            if item.phase is MotionPhase.CONTACT and item.phase_endpoint
        )
        if len(contact_endpoints) != len(targets):
            raise StaticMissionRouteError(
                "report final CONTACT endpoints do not cover target occurrences"
        )
        target_hash_by_action: dict[int, str] = {}
        target_semantic_by_action: dict[int, str] = {}
        for contact, target in zip(contact_endpoints, targets):
            if (
                contact.action_index is None
                or contact.action_index in target_hash_by_action
                or contact.semantic_target != f"{self.device}:{target.target_id}"
            ):
                raise StaticMissionRouteError(
                    "report CONTACT action/target occurrence mapping is inconsistent"
                )
            target_hash_by_action[contact.action_index] = target.content_hash
            target_semantic_by_action[contact.action_index] = contact.semantic_target
        for ordinal, endpoint in enumerate(endpoints):
            expected_command = None if ordinal == 0 else ordinal - 1
            if (
                endpoint.endpoint.route_waypoint_ordinal != ordinal
                or endpoint.endpoint.global_authorization_command_ordinal
                != expected_command
            ):
                raise StaticMissionRouteError(
                    "report endpoint ordinals do not preserve park/command mapping"
                )
            if endpoint.action_index is None:
                if endpoint.semantic_target is not None:
                    raise StaticMissionRouteError(
                        "report endpoint target exists without an action"
                    )
                expected_target_hash = None
            else:
                _non_negative_int(endpoint.action_index, "endpoint action_index")
                if endpoint.action_index not in target_hash_by_action:
                    raise StaticMissionRouteError(
                        "report endpoint action is not contact-bound"
                    )
                if (
                    endpoint.semantic_target
                    != target_semantic_by_action[endpoint.action_index]
                ):
                    raise StaticMissionRouteError(
                        "report endpoint semantic target changed within one action"
                    )
                expected_target_hash = target_hash_by_action[endpoint.action_index]
            expected_allowance = (
                endpoint.phase is MotionPhase.CONTACT and endpoint.phase_endpoint
            )
            if (
                endpoint.target_binding_sha256 != expected_target_hash
                or endpoint.designated_contact_overlap_allowed
                is not expected_allowance
            ):
                raise StaticMissionRouteError(
                    "report endpoint target/contact allowance is inconsistent"
                )
        for ordinal, (midpoint, command, incoming) in enumerate(
            zip(midpoints, commands, endpoints[1:])
        ):
            if (
                midpoint.midpoint.start_route_waypoint_ordinal != ordinal
                or midpoint.midpoint.end_route_waypoint_ordinal != ordinal + 1
                or midpoint.midpoint.global_authorization_command_ordinal
                != ordinal
                or midpoint.incoming_phase is not incoming.phase
                or midpoint.incoming_action_index != incoming.action_index
                or midpoint.incoming_semantic_target != incoming.semantic_target
            ):
                raise StaticMissionRouteError(
                    "report midpoint differs from its incoming endpoint"
                )
            if (
                command.global_authorization_command_ordinal != ordinal
                or command.route_waypoint_ordinal != ordinal + 1
                or command.phase is not incoming.phase
                or command.action_index != incoming.action_index
                or command.semantic_target != incoming.semantic_target
                or command.phase_endpoint is not incoming.phase_endpoint
                or command.waypoint_sha256 != incoming.waypoint_sha256
                or command.joint_result_sha256 != incoming.joint_result_sha256
                or command.endpoint_input_sha256 != incoming.endpoint.content_hash
                or command.endpoint_result_sha256 != incoming.content_hash
                or command.incoming_midpoint_input_sha256
                != midpoint.midpoint.content_hash
                or command.incoming_midpoint_result_sha256
                != midpoint.content_hash
                or command.target_binding_sha256
                != incoming.target_binding_sha256
                or command.designated_contact_overlap_allowed
                is not incoming.designated_contact_overlap_allowed
            ):
                raise StaticMissionRouteError(
                    "report command binding differs from endpoint/midpoint evidence"
                )
        expected_blockers = tuple(
            item.pose_result.blocker
            for item in endpoints
            if item.pose_result.blocker is not None
        ) + tuple(
            item.pose_result.blocker
            for item in midpoints
            if item.pose_result.blocker is not None
        )
        if blockers != expected_blockers:
            raise StaticMissionRouteError(
                "report blockers differ from endpoint/midpoint results"
            )
        if self.status is not _status_for_results(endpoints, midpoints):
            raise StaticMissionRouteError(
                "report status differs from endpoint/midpoint results"
            )

    def assert_matches_trajectory(
        self,
        trajectory: TrajectorySimulationReport,
        *,
        recompute_collision: bool = False,
    ) -> None:
        """Bind coverage to an exact route and optionally rerun every query."""

        if type(trajectory) is not TrajectorySimulationReport:
            raise TypeError("trajectory must be exactly TrajectorySimulationReport")
        self.__post_init__()
        _, plan_hash, target_profile, model_hash = _validate_contract_and_sources(
            trajectory,
            self.contract,
            self.policy,
        )
        final_round, waypoints, joint_results, action_to_occurrence = (
            _validate_trajectory(trajectory)
        )
        if (
            self.device != trajectory.device
            or self.route_target_ids != trajectory.route_target_ids
            or self.trajectory_report_sha256 != _canonical_hash(trajectory.to_dict())
            or self.final_round_sha256 != _canonical_hash(final_round.to_dict())
            or self.plan_sha256 != plan_hash
            or self.target_profile_sha256 != target_profile
            or self.robot_model_sha256 != model_hash
        ):
            raise StaticMissionRouteError(
                "collision report does not bind the exact trajectory identity"
            )
        _validate_target_bindings(trajectory, self.contract, self.target_bindings)
        _validate_pose_inputs(
            self.contract,
            waypoints,
            joint_results,
            tuple(item.endpoint for item in self.endpoint_results),
            tuple(item.midpoint for item in self.midpoint_results),
        )
        for ordinal, (waypoint, joint_result, endpoint) in enumerate(
            zip(waypoints, joint_results, self.endpoint_results)
        ):
            occurrence = (
                None
                if waypoint.action_index is None
                else action_to_occurrence[waypoint.action_index]
            )
            target = None if occurrence is None else self.target_bindings[occurrence]
            if (
                endpoint.phase is not waypoint.phase
                or endpoint.action_index != waypoint.action_index
                or endpoint.semantic_target != waypoint.semantic_target
                or endpoint.phase_endpoint is not waypoint.phase_endpoint
                or endpoint.waypoint_sha256 != _waypoint_hash(waypoint)
                or endpoint.joint_result_sha256 != _joint_result_hash(joint_result)
                or endpoint.target_binding_sha256
                != (None if target is None else target.content_hash)
            ):
                raise StaticMissionRouteError(
                    f"collision endpoint {ordinal} differs from its trajectory row"
                )
        for ordinal, (midpoint, incoming) in enumerate(
            zip(self.midpoint_results, waypoints[1:])
        ):
            if (
                midpoint.incoming_phase is not incoming.phase
                or midpoint.incoming_action_index != incoming.action_index
                or midpoint.incoming_semantic_target != incoming.semantic_target
            ):
                raise StaticMissionRouteError(
                    f"collision midpoint {ordinal} differs from its incoming route row"
                )
        if recompute_collision:
            recomputed = evaluate_static_b0477_mission_route(
                trajectory,
                self.contract,
                self.policy,
                self.target_bindings,
                tuple(item.endpoint for item in self.endpoint_results),
                tuple(item.midpoint for item in self.midpoint_results),
            )
            if recomputed.to_dict() != self.to_dict():
                raise StaticMissionRouteError(
                    "collision report differs from an independent recomputation"
                )

    @property
    def passed_diagnostic(self) -> bool:
        return self.status is StaticMissionRouteStatus.PASS_DIAGNOSTIC_ONLY

    @property
    def can_produce_authorization_v2_physical_evidence(self) -> bool:
        return False

    def as_authorization_v2_physical_evidence(self) -> None:
        raise StaticMissionRouteError(
            "dense static mission collision reports are diagnostic-only and "
            "cannot produce authorization_v2 physical evidence"
        )

    @property
    def endpoint_result_sequence_sha256(self) -> str:
        return _canonical_hash([item.content_hash for item in self.endpoint_results])

    @property
    def midpoint_result_sequence_sha256(self) -> str:
        return _canonical_hash([item.content_hash for item in self.midpoint_results])

    @property
    def command_binding_sequence_sha256(self) -> str:
        return _canonical_hash([item.content_hash for item in self.command_bindings])

    @property
    def report_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": STATIC_B0477_MISSION_ROUTE_REPORT_SCHEMA,
            "status": self.status.value,
            "passed_diagnostic": self.passed_diagnostic,
            "device": self.device,
            "route_target_ids": list(self.route_target_ids),
            "trajectory": {
                "report_sha256": self.trajectory_report_sha256,
                "final_round_sha256": self.final_round_sha256,
                "plan_sha256": self.plan_sha256,
                "target_profile_sha256": self.target_profile_sha256,
                "robot_model_sha256": self.robot_model_sha256,
            },
            "contract": {
                "sha256": self.contract.content_hash,
                "content": self.contract.to_dict(),
            },
            "policy": {
                "sha256": self.policy.content_hash,
                "content": self.policy.to_dict(),
            },
            "target_bindings": [
                {"sha256": item.content_hash, "content": item.to_dict()}
                for item in self.target_bindings
            ],
            "coverage": {
                "endpoint_count": len(self.endpoint_results),
                "incoming_joint_midpoint_count": len(self.midpoint_results),
                "command_binding_count": len(self.command_bindings),
                "endpoint_result_sequence_sha256": (
                    self.endpoint_result_sequence_sha256
                ),
                "midpoint_result_sequence_sha256": (
                    self.midpoint_result_sequence_sha256
                ),
                "command_binding_sequence_sha256": (
                    self.command_binding_sequence_sha256
                ),
                "all_endpoints_accepted": bool(self.endpoint_results)
                and all(item.accepted for item in self.endpoint_results),
                "all_incoming_midpoints_accepted": bool(self.midpoint_results)
                and all(item.accepted for item in self.midpoint_results),
                "separate_ordinal_domains": True,
                "initial_known_pose_has_no_command": True,
            },
            "blockers": list(self.blockers),
            "endpoint_results": [item.to_dict() for item in self.endpoint_results],
            "midpoint_results": [item.to_dict() for item in self.midpoint_results],
            "command_bindings": [item.to_dict() for item in self.command_bindings],
            "limitations": [
                "Endpoint and joint-midpoint collision poses are caller-supplied and hash-bound; this service does not recompute full-link FK.",
                "Only supplied endpoints and 0.5 joint midpoints are sampled; this is not a continuous collision proof.",
                "Synthetic or measured provenance labels do not authenticate geometry or installed transforms.",
                "Dynamics, deflection, payload, force, vibration, and unmodelled cable motion are excluded.",
                "No controller payload or wire-format T=104 command is created here.",
            ],
            "authorization_v2": {
                "eligible_as_physical_evidence": False,
                "reason": "zero-authority discrete simulation diagnostic",
            },
            "authority": _zero_authority(),
        }


def _provenance_mapping(report: TrajectorySimulationReport) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in report.source_provenance:
        if not isinstance(item, tuple) or len(item) != 2:
            raise StaticMissionRouteError(
                "trajectory source_provenance must contain key/value pairs"
            )
        key, value = item
        if not isinstance(key, str) or not key:
            raise StaticMissionRouteError(
                "trajectory source_provenance keys must be non-empty strings"
            )
        if key in result:
            raise StaticMissionRouteError(
                f"trajectory source_provenance duplicates {key!r}"
            )
        result[key] = value
    return result


def _validate_contract_and_sources(
    trajectory: TrajectorySimulationReport,
    contract: StaticB0477RouteCollisionContract,
    policy: StaticRouteCollisionPolicy,
) -> tuple[dict[str, Any], str, str, str]:
    if len(contract.sources.source_hashes) != len(REQUIRED_STATIC_ROUTE_SOURCE_KEYS):
        raise StaticMissionRouteError(
            "static B0477 mission contract must contain exactly nine source hashes"
        )
    if set(contract.sources.source_hashes) != set(REQUIRED_STATIC_ROUTE_SOURCE_KEYS):
        raise StaticMissionRouteError(
            "static B0477 mission contract source keys are not the exact frozen set"
        )
    required_body_ids = tuple(item.body_id for item in STATIC_ROUTE_BODY_REQUIREMENTS)
    if len(required_body_ids) != 26:
        raise StaticMissionRouteError("frozen static route body inventory is not 26")
    if len(contract.bodies) != 26 or {item.body_id for item in contract.bodies} != set(
        required_body_ids
    ):
        raise StaticMissionRouteError(
            "static B0477 mission contract must bind the exact 26-body inventory"
        )
    if contract.global_pair_exclusions:
        raise StaticMissionRouteError(
            "dense static mission collision does not permit global exclusions"
        )
    if policy.collision_policy.clearance_policy is None:
        raise StaticMissionRouteError(
            "an explicit collision clearance policy is required"
        )
    provenance = _provenance_mapping(trajectory)
    plan_hash = _sha256(provenance.get("plan_hash"), "trajectory plan_hash")
    target_profile = _sha256(
        provenance.get("target_profile_sha256"),
        "trajectory target_profile_sha256",
    )
    model_hash = _sha256(
        provenance.get("model_sha256"), "trajectory model_sha256"
    )
    loaded_model_hash = _sha256(
        provenance.get("loaded_model_sha256"),
        "trajectory loaded_model_sha256",
    )
    if model_hash != loaded_model_hash:
        raise StaticMissionRouteError(
            "trajectory model_sha256 differs from loaded_model_sha256"
        )
    if target_profile != contract.sources.source_hashes["target_profile"]:
        raise StaticMissionRouteError(
            "trajectory target profile differs from collision-contract source closure"
        )
    if model_hash != contract.sources.source_hashes["robot_model"]:
        raise StaticMissionRouteError(
            "trajectory robot model differs from collision-contract source closure"
        )
    return provenance, plan_hash, target_profile, model_hash


def _validate_joint_result(
    waypoint: CartesianRouteWaypoint,
    result: JointTrajectoryWaypointResult,
    ordinal: int,
) -> tuple[tuple[str, float], ...]:
    if result.waypoint_sequence != ordinal:
        raise StaticMissionRouteError(
            f"joint result {ordinal} has the wrong waypoint sequence"
        )
    if (
        result.phase is not waypoint.phase
        or result.action_index != waypoint.action_index
        or result.semantic_target != waypoint.semantic_target
    ):
        raise StaticMissionRouteError(
            f"joint result {ordinal} does not preserve waypoint phase/action/target"
        )
    if (
        result.ik_status != "CONVERGED"
        or not result.accepted
        or not result.controller_intersection_passed
        or not result.arm_margin_passed
        or result.solver_weighted_task_jacobian_numerical_rank_passed is not True
        or not result.adjacent_joint_delta_passed
        or result.failure_reason is not None
    ):
        raise StaticMissionRouteError(
            f"joint result {ordinal} is not an independently accepted IK result"
        )
    return _joint_vector(
        result.solution_arm_joint_positions_rad,
        f"joint result {ordinal} solution_arm_joint_positions_rad",
    )


def _validate_trajectory(
    trajectory: TrajectorySimulationReport,
) -> tuple[
    TrajectorySearchRound,
    tuple[CartesianRouteWaypoint, ...],
    tuple[JointTrajectoryWaypointResult, ...],
    dict[int, int],
]:
    if trajectory.device not in {"keyboard", "phone"}:
        raise StaticMissionRouteError("trajectory device must be keyboard or phone")
    if not trajectory.geometry_all_checks_passed:
        raise StaticMissionRouteError(
            "trajectory nominal geometry checks did not all pass"
        )
    final_round = trajectory.final_round
    if final_round is None or not final_round.all_waypoints_accepted:
        raise StaticMissionRouteError(
            "trajectory must contain a final accepted dense waypoint round"
        )
    waypoints = final_round.waypoints
    joint_results = final_round.joint_results
    if not 2 <= len(waypoints) <= MAX_STATIC_MISSION_WAYPOINTS:
        raise StaticMissionRouteError(
            "final dense trajectory waypoint count is outside [2, 512]"
        )
    if len(joint_results) != len(waypoints):
        raise StaticMissionRouteError(
            "final dense trajectory lacks exact 1:1 waypoint/IK-result coverage"
        )
    if (
        waypoints[0].phase is not MotionPhase.PARK
        or not waypoints[0].phase_endpoint
        or waypoints[0].action_index is not None
        or waypoints[0].semantic_target is not None
    ):
        raise StaticMissionRouteError(
            "final dense trajectory must begin at an endpoint PARK condition"
        )
    if (
        waypoints[-1].phase is not MotionPhase.PARK
        or not waypoints[-1].phase_endpoint
        or waypoints[-1].action_index is not None
        or waypoints[-1].semantic_target is not None
    ):
        raise StaticMissionRouteError(
            "final dense trajectory must end at an endpoint PARK condition"
        )

    contact_action_to_occurrence: dict[int, int] = {}
    contact_targets: list[str] = []
    previous_action: int | None = None
    for ordinal, (waypoint, result) in enumerate(zip(waypoints, joint_results)):
        if waypoint.sequence != ordinal:
            raise StaticMissionRouteError(
                "final dense waypoint sequences must be unique, increasing, and zero-based"
            )
        if not isinstance(waypoint.phase, MotionPhase):
            raise StaticMissionRouteError(f"waypoint {ordinal} phase is invalid")
        if not isinstance(waypoint.phase_endpoint, bool):
            raise StaticMissionRouteError(
                f"waypoint {ordinal} phase_endpoint must be bool"
            )
        if waypoint.point_board.frame != "board":
            raise StaticMissionRouteError(
                f"waypoint {ordinal} is not expressed in board coordinates"
            )
        if not waypoint.source_path_check_passed:
            raise StaticMissionRouteError(
                f"waypoint {ordinal} inherited a failed geometric path check"
            )
        action_index = waypoint.action_index
        if action_index is not None:
            action_index = _non_negative_int(
                action_index, f"waypoint {ordinal} action_index"
            )
            if previous_action is not None and action_index < previous_action:
                raise StaticMissionRouteError(
                    "trajectory action indices must be monotonically increasing"
                )
            previous_action = action_index
            if waypoint.semantic_target is None:
                raise StaticMissionRouteError(
                    f"waypoint {ordinal} has an action without a semantic target"
                )
        elif waypoint.semantic_target is not None:
            raise StaticMissionRouteError(
                f"waypoint {ordinal} has a semantic target without an action"
            )
        _validate_joint_result(waypoint, result, ordinal)
        if waypoint.phase is MotionPhase.CONTACT:
            if action_index is None or waypoint.semantic_target is None:
                raise StaticMissionRouteError(
                    "CONTACT waypoints must bind an action and semantic target"
                )
            if waypoint.phase_endpoint:
                if action_index in contact_action_to_occurrence:
                    raise StaticMissionRouteError(
                        f"action {action_index} has more than one final CONTACT endpoint"
                    )
                occurrence = len(contact_targets)
                contact_action_to_occurrence[action_index] = occurrence
                contact_targets.append(waypoint.semantic_target)

    if len(contact_targets) != len(trajectory.route_target_ids) or not contact_targets:
        raise StaticMissionRouteError(
            "CONTACT endpoint count does not exactly cover route_target_ids"
        )
    expected_semantic_targets = tuple(
        f"{trajectory.device}:{target_id}" for target_id in trajectory.route_target_ids
    )
    if tuple(contact_targets) != expected_semantic_targets:
        raise StaticMissionRouteError(
            "CONTACT endpoint targets/order differ from route_target_ids"
        )
    for ordinal, waypoint in enumerate(waypoints):
        if waypoint.action_index is None:
            continue
        bound_occurrence = contact_action_to_occurrence.get(waypoint.action_index)
        if bound_occurrence is None:
            raise StaticMissionRouteError(
                f"waypoint {ordinal} action has no final CONTACT endpoint"
            )
        if waypoint.semantic_target != expected_semantic_targets[bound_occurrence]:
            raise StaticMissionRouteError(
                f"waypoint {ordinal} target differs within one action route"
            )
    return final_round, waypoints, joint_results, contact_action_to_occurrence


def _validate_target_bindings(
    trajectory: TrajectorySimulationReport,
    contract: StaticB0477RouteCollisionContract,
    target_bindings: tuple[StaticRouteTargetBinding, ...],
) -> None:
    if len(target_bindings) != len(trajectory.route_target_ids):
        raise StaticMissionRouteError(
            "target bindings must cover every physical target occurrence exactly once"
        )
    for occurrence, (target_id, binding) in enumerate(
        zip(trajectory.route_target_ids, target_bindings)
    ):
        if not isinstance(binding, StaticRouteTargetBinding):
            raise TypeError("target_bindings must contain StaticRouteTargetBinding")
        if binding.device != trajectory.device or binding.target_id != target_id:
            raise StaticMissionRouteError(
                f"target binding {occurrence} differs from the trajectory occurrence"
            )
        if (
            binding.target_profile_sha256
            != contract.sources.source_hashes["target_profile"]
        ):
            raise StaticMissionRouteError(
                f"target binding {occurrence} profile differs from source closure"
            )


def _validate_complete_pose(
    pose: CollisionPose,
    contract: StaticB0477RouteCollisionContract,
    label: str,
) -> None:
    if pose.root_frame != contract.root_frame:
        raise StaticMissionRouteError(
            f"{label} collision pose root differs from the contract"
        )
    # CONFIGURATION_SAMPLED geometry supplies fresh primitives *and* still
    # requires its parent-frame transform in the primitive evaluator.
    pose_frames = {
        item.parent_frame
        for item in STATIC_ROUTE_BODY_REQUIREMENTS
        if item.binding_mode is not CollisionBindingMode.STATIC_ROOT
    }
    if set(pose.root_t_parent) != pose_frames:
        missing = sorted(pose_frames - set(pose.root_t_parent))
        extra = sorted(set(pose.root_t_parent) - pose_frames)
        raise StaticMissionRouteError(
            f"{label} must bind the exact rigid transform set; "
            f"missing={missing}, extra={extra}"
        )
    for frame, transform in pose.root_t_parent.items():
        if transform.parent_frame != contract.root_frame or transform.child_frame != frame:
            raise StaticMissionRouteError(
                f"{label} contains a mismatched {frame!r} transform"
            )
    sampled_body_ids = {
        item.body_id
        for item in STATIC_ROUTE_BODY_REQUIREMENTS
        if item.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED
    }
    if set(pose.configuration_primitives) != sampled_body_ids:
        missing = sorted(sampled_body_ids - set(pose.configuration_primitives))
        extra = sorted(set(pose.configuration_primitives) - sampled_body_ids)
        raise StaticMissionRouteError(
            f"{label} must contain the exact per-pose arm-harness geometry; "
            f"missing={missing}, extra={extra}"
        )
    for body_id, geometry in pose.configuration_primitives.items():
        if not geometry.evidence_state.supports_diagnostic:
            raise StaticMissionRouteError(
                f"{label} sampled geometry {body_id!r} is not diagnostic-ready"
            )


def _validate_pose_inputs(
    contract: StaticB0477RouteCollisionContract,
    waypoints: tuple[CartesianRouteWaypoint, ...],
    joint_results: tuple[JointTrajectoryWaypointResult, ...],
    endpoint_poses: tuple[StaticMissionEndpointPose, ...],
    midpoint_poses: tuple[StaticMissionIncomingMidpointPose, ...],
) -> None:
    if len(endpoint_poses) != len(waypoints):
        raise StaticMissionRouteError(
            "endpoint poses must cover final dense waypoints exactly 1:1"
        )
    if len(midpoint_poses) != len(waypoints) - 1:
        raise StaticMissionRouteError(
            "incoming joint-midpoint poses must cover every command exactly 1:1"
        )
    all_pose_ids = [item.pose.pose_id for item in endpoint_poses]
    all_pose_ids.extend(item.pose.pose_id for item in midpoint_poses)
    if len(all_pose_ids) != len(set(all_pose_ids)):
        raise StaticMissionRouteError(
            "every endpoint and incoming midpoint pose_id must be globally unique"
        )

    for ordinal, (waypoint, result, endpoint) in enumerate(
        zip(waypoints, joint_results, endpoint_poses)
    ):
        expected_command = None if ordinal == 0 else ordinal - 1
        if endpoint.route_waypoint_ordinal != ordinal:
            raise StaticMissionRouteError(
                "endpoint route waypoint ordinals must be increasing and zero-based"
            )
        if endpoint.global_authorization_command_ordinal != expected_command:
            raise StaticMissionRouteError(
                "endpoint global authorization ordinals must be None, then zero-based"
            )
        expected_joints = _joint_vector(
            result.solution_arm_joint_positions_rad,
            f"joint result {ordinal} solution_arm_joint_positions_rad",
        )
        if endpoint.joint_positions_rad != expected_joints:
            raise StaticMissionRouteError(
                f"endpoint {ordinal} joint vector differs from its accepted IK result"
            )
        _validate_complete_pose(endpoint.pose, contract, f"endpoint {ordinal}")
        tool_transform = endpoint.pose.root_t_parent["tool_tip"]
        achieved_tip = Vec3.from_iterable(result.achieved_tip_position_board_mm)
        if not tool_transform.translation_mm.almost_equal(
            achieved_tip,
            absolute_tolerance=_TRAJECTORY_POSE_ABSOLUTE_TOLERANCE,
        ):
            raise StaticMissionRouteError(
                f"endpoint {ordinal} tool-tip transform differs from achieved IK position"
            )
        achieved_axis = Vec3.from_iterable(result.achieved_hand_tcp_z_axis_board)
        supplied_axis = tool_transform.rotation.apply(Vec3(0.0, 0.0, 1.0))
        if not supplied_axis.almost_equal(
            achieved_axis,
            absolute_tolerance=_TRAJECTORY_POSE_ABSOLUTE_TOLERANCE,
        ):
            raise StaticMissionRouteError(
                f"endpoint {ordinal} tool-tip orientation differs from achieved IK axis"
            )
        # Keep the source waypoint's board identity visible in this binding.
        if waypoint.sequence != endpoint.route_waypoint_ordinal:
            raise StaticMissionRouteError(
                f"endpoint {ordinal} does not bind its source waypoint"
            )

    for command_ordinal, midpoint in enumerate(midpoint_poses):
        start = command_ordinal
        end = command_ordinal + 1
        if (
            midpoint.start_route_waypoint_ordinal != start
            or midpoint.end_route_waypoint_ordinal != end
            or midpoint.global_authorization_command_ordinal != command_ordinal
        ):
            raise StaticMissionRouteError(
                "midpoint coverage/order differs from the incoming command sequence"
            )
        start_joints = endpoint_poses[start].joint_positions_rad
        end_joints = endpoint_poses[end].joint_positions_rad
        for (start_name, start_value), (end_name, end_value), (
            midpoint_name,
            midpoint_value,
        ) in zip(start_joints, end_joints, midpoint.joint_positions_rad):
            if start_name != end_name or start_name != midpoint_name:
                raise StaticMissionRouteError(
                    f"midpoint {command_ordinal} joint names are inconsistent"
                )
            expected = (start_value + end_value) * 0.5
            if not math.isclose(
                midpoint_value,
                expected,
                rel_tol=0.0,
                abs_tol=_JOINT_MIDPOINT_ABSOLUTE_TOLERANCE_RAD,
            ):
                raise StaticMissionRouteError(
                    f"midpoint {command_ordinal} is not the exact joint midpoint"
                )
        _validate_complete_pose(
            midpoint.pose, contract, f"midpoint {command_ordinal}"
        )


def _normalized_pair(pair: CollisionPair) -> tuple[str, str]:
    first, second = sorted((pair.first_body_id, pair.second_body_id))
    return first, second


def _evaluate_pose(
    collision_contract: CollisionGeometryContract,
    pose: CollisionPose,
    collision_policy: CollisionEvaluationPolicy,
    *,
    allowed_contact_pair: tuple[str, str] | None,
    require_contact: bool,
) -> StaticRoutePoseResult:
    try:
        evaluation = evaluate_collision_pose(
            collision_contract, pose, collision_policy
        )
    except (CollisionContractError, TypeError, ValueError) as exc:
        return StaticRoutePoseResult(
            pose.pose_id,
            StaticRouteSampleDisposition.BLOCKED,
            None,
            str(exc),
        )
    if not isinstance(evaluation, CollisionPoseEvaluation):
        return StaticRoutePoseResult(
            pose.pose_id,
            StaticRouteSampleDisposition.BLOCKED,
            None,
            "collision evaluator returned an unsupported result",
        )
    if not evaluation.evaluation_complete:
        blockers = evaluation.pose_blockers or evaluation.geometry_audit.diagnostic_blockers
        detail = "; ".join(
            f"{item.code.value}:{item.body_id}" for item in blockers
        ) or evaluation.status.value
        return StaticRoutePoseResult(
            pose.pose_id,
            StaticRouteSampleDisposition.BLOCKED,
            evaluation,
            detail,
        )
    collision_pairs = tuple(
        _normalized_pair(item) for item in evaluation.collisions
    )
    if allowed_contact_pair is None:
        if collision_pairs:
            return StaticRoutePoseResult(
                pose.pose_id,
                StaticRouteSampleDisposition.COLLISION,
                evaluation,
                "collision is not allowed at this dense mission sample",
            )
        return StaticRoutePoseResult(
            pose.pose_id, StaticRouteSampleDisposition.CLEAR, evaluation
        )
    disallowed = tuple(
        pair for pair in collision_pairs if pair != allowed_contact_pair
    )
    if disallowed:
        return StaticRoutePoseResult(
            pose.pose_id,
            StaticRouteSampleDisposition.COLLISION,
            evaluation,
            f"CONTACT contains collisions other than {allowed_contact_pair!r}",
        )
    if allowed_contact_pair in collision_pairs:
        return StaticRoutePoseResult(
            pose.pose_id,
            StaticRouteSampleDisposition.ALLOWED_DESIGNATED_CONTACT,
            evaluation,
        )
    if require_contact:
        return StaticRoutePoseResult(
            pose.pose_id,
            StaticRouteSampleDisposition.REQUIRED_CONTACT_MISSING,
            evaluation,
            "designated tool-tip/target overlap is absent at final CONTACT endpoint",
        )
    return StaticRoutePoseResult(
        pose.pose_id, StaticRouteSampleDisposition.CLEAR, evaluation
    )


def _waypoint_hash(waypoint: CartesianRouteWaypoint) -> str:
    return _canonical_hash(waypoint.to_dict())


def _joint_result_hash(result: JointTrajectoryWaypointResult) -> str:
    return _canonical_hash(result.to_dict())


def _status_for_results(
    endpoints: tuple[StaticMissionEndpointResult, ...],
    midpoints: tuple[StaticMissionMidpointResult, ...],
) -> StaticMissionRouteStatus:
    results = tuple(item.pose_result for item in endpoints) + tuple(
        item.pose_result for item in midpoints
    )
    if any(
        item.disposition is StaticRouteSampleDisposition.BLOCKED
        for item in results
    ):
        return StaticMissionRouteStatus.BLOCKED_POSE_INPUT
    if any(
        item.disposition is StaticRouteSampleDisposition.COLLISION
        for item in results
    ):
        return StaticMissionRouteStatus.COLLISION_DETECTED
    if any(
        item.disposition is StaticRouteSampleDisposition.REQUIRED_CONTACT_MISSING
        for item in results
    ):
        return StaticMissionRouteStatus.CONTACT_OVERLAP_MISSING
    return StaticMissionRouteStatus.PASS_DIAGNOSTIC_ONLY


def evaluate_static_b0477_mission_route(
    trajectory: TrajectorySimulationReport,
    contract: StaticB0477RouteCollisionContract,
    policy: StaticRouteCollisionPolicy,
    target_bindings: Iterable[StaticRouteTargetBinding],
    endpoint_poses: Iterable[StaticMissionEndpointPose],
    incoming_midpoint_poses: Iterable[StaticMissionIncomingMidpointPose],
) -> StaticMissionRouteCollisionReport:
    """Evaluate every accepted dense endpoint and incoming joint midpoint.

    The initial route waypoint is a known PARK pose and therefore has no global
    authorization command.  Route waypoint ``n`` (for ``n > 0``), incoming
    midpoint ``n-1 -> n``, and authorization command ``n-1`` are bound exactly.
    No live controller or wire-command API is reachable from this service.
    """

    if not isinstance(trajectory, TrajectorySimulationReport):
        raise TypeError("trajectory must be TrajectorySimulationReport")
    if not isinstance(contract, StaticB0477RouteCollisionContract):
        raise TypeError("contract must be StaticB0477RouteCollisionContract")
    if not isinstance(policy, StaticRouteCollisionPolicy):
        raise TypeError("policy must be StaticRouteCollisionPolicy")

    _, plan_hash, target_profile, model_hash = _validate_contract_and_sources(
        trajectory, contract, policy
    )
    final_round, waypoints, joint_results, action_to_occurrence = (
        _validate_trajectory(trajectory)
    )
    bound_targets = _bounded_tuple(
        target_bindings,
        len(trajectory.route_target_ids),
        "target_bindings",
    )
    endpoints = _bounded_tuple(
        endpoint_poses, MAX_STATIC_MISSION_WAYPOINTS, "endpoint_poses"
    )
    midpoints = _bounded_tuple(
        incoming_midpoint_poses,
        MAX_STATIC_MISSION_INCOMING_MIDPOINTS,
        "incoming_midpoint_poses",
    )
    if any(not isinstance(item, StaticRouteTargetBinding) for item in bound_targets):
        raise TypeError("target_bindings must contain StaticRouteTargetBinding")
    if any(not isinstance(item, StaticMissionEndpointPose) for item in endpoints):
        raise TypeError("endpoint_poses must contain StaticMissionEndpointPose")
    if any(
        not isinstance(item, StaticMissionIncomingMidpointPose)
        for item in midpoints
    ):
        raise TypeError(
            "incoming_midpoint_poses must contain StaticMissionIncomingMidpointPose"
        )
    typed_targets = tuple(bound_targets)
    typed_endpoints = tuple(endpoints)
    typed_midpoints = tuple(midpoints)
    _validate_target_bindings(trajectory, contract, typed_targets)
    _validate_pose_inputs(
        contract,
        waypoints,
        joint_results,
        typed_endpoints,
        typed_midpoints,
    )
    # The static wrapper materializes the primitive contract.  Build it once
    # for the complete mission rather than once for every endpoint/midpoint.
    collision_contract = contract.collision_contract

    endpoint_results: list[StaticMissionEndpointResult] = []
    for ordinal, (waypoint, joint_result, endpoint) in enumerate(
        zip(waypoints, joint_results, typed_endpoints)
    ):
        occurrence = (
            None
            if waypoint.action_index is None
            else action_to_occurrence[waypoint.action_index]
        )
        target = None if occurrence is None else typed_targets[occurrence]
        allow_contact = (
            waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint
        )
        allowed_pair = (
            None
            if not allow_contact or target is None
            else tuple(sorted(("robot:tool_tip", target.target_body_id)))
        )
        pose_result = _evaluate_pose(
            collision_contract,
            endpoint.pose,
            policy.collision_policy,
            allowed_contact_pair=allowed_pair,
            require_contact=(allow_contact and policy.require_designated_contact_overlap),
        )
        if allow_contact and target is not None:
            tool_tip = endpoint.pose.root_t_parent["tool_tip"].translation_mm
            lateral_offset = math.hypot(
                tool_tip.x - target.center_board_mm.x,
                tool_tip.y - target.center_board_mm.y,
            )
            penetration = target.center_board_mm.z - tool_tip.z
            if lateral_offset > policy.maximum_contact_target_offset_mm:
                pose_result = StaticRoutePoseResult(
                    endpoint.pose.pose_id,
                    StaticRouteSampleDisposition.BLOCKED,
                    pose_result.evaluation,
                    "final CONTACT tool-tip lateral origin is "
                    f"{lateral_offset:.9g} mm from bound target center",
                )
            elif not 0.0 <= penetration <= MAX_STATIC_MISSION_CONTACT_PENETRATION_MM:
                pose_result = StaticRoutePoseResult(
                    endpoint.pose.pose_id,
                    StaticRouteSampleDisposition.BLOCKED,
                    pose_result.evaluation,
                    "final CONTACT tool-tip penetration relative to the target "
                    f"surface is {penetration:.9g} mm, outside [0, "
                    f"{MAX_STATIC_MISSION_CONTACT_PENETRATION_MM:g}] mm",
                )
        endpoint_results.append(
            StaticMissionEndpointResult(
                endpoint=endpoint,
                phase=waypoint.phase,
                action_index=waypoint.action_index,
                semantic_target=waypoint.semantic_target,
                phase_endpoint=waypoint.phase_endpoint,
                waypoint_sha256=_waypoint_hash(waypoint),
                joint_result_sha256=_joint_result_hash(joint_result),
                designated_contact_overlap_allowed=allow_contact,
                target_binding_sha256=(
                    None if target is None else target.content_hash
                ),
                pose_result=pose_result,
            )
        )

    midpoint_results: list[StaticMissionMidpointResult] = []
    for command_ordinal, midpoint in enumerate(typed_midpoints):
        incoming = waypoints[command_ordinal + 1]
        midpoint_results.append(
            StaticMissionMidpointResult(
                midpoint=midpoint,
                incoming_phase=incoming.phase,
                incoming_action_index=incoming.action_index,
                incoming_semantic_target=incoming.semantic_target,
                pose_result=_evaluate_pose(
                    collision_contract,
                    midpoint.pose,
                    policy.collision_policy,
                    allowed_contact_pair=None,
                    require_contact=False,
                ),
            )
        )

    endpoint_result_tuple = tuple(endpoint_results)
    midpoint_result_tuple = tuple(midpoint_results)
    command_bindings = tuple(
        StaticMissionCommandCollisionBinding(
            global_authorization_command_ordinal=command_ordinal,
            route_waypoint_ordinal=command_ordinal + 1,
            phase=endpoint_result_tuple[command_ordinal + 1].phase,
            action_index=endpoint_result_tuple[command_ordinal + 1].action_index,
            semantic_target=(
                endpoint_result_tuple[command_ordinal + 1].semantic_target
            ),
            phase_endpoint=endpoint_result_tuple[command_ordinal + 1].phase_endpoint,
            waypoint_sha256=(
                endpoint_result_tuple[command_ordinal + 1].waypoint_sha256
            ),
            joint_result_sha256=(
                endpoint_result_tuple[command_ordinal + 1].joint_result_sha256
            ),
            endpoint_input_sha256=(
                endpoint_result_tuple[command_ordinal + 1].endpoint.content_hash
            ),
            endpoint_result_sha256=(
                endpoint_result_tuple[command_ordinal + 1].content_hash
            ),
            incoming_midpoint_input_sha256=(
                midpoint_result_tuple[command_ordinal].midpoint.content_hash
            ),
            incoming_midpoint_result_sha256=(
                midpoint_result_tuple[command_ordinal].content_hash
            ),
            target_binding_sha256=(
                endpoint_result_tuple[command_ordinal + 1].target_binding_sha256
            ),
            designated_contact_overlap_allowed=(
                endpoint_result_tuple[
                    command_ordinal + 1
                ].designated_contact_overlap_allowed
            ),
        )
        for command_ordinal in range(len(midpoint_result_tuple))
    )
    blockers = tuple(
        item.pose_result.blocker
        for item in endpoint_result_tuple
        if item.pose_result.blocker is not None
    ) + tuple(
        item.pose_result.blocker
        for item in midpoint_result_tuple
        if item.pose_result.blocker is not None
    )
    report = StaticMissionRouteCollisionReport(
        status=_status_for_results(endpoint_result_tuple, midpoint_result_tuple),
        device=trajectory.device,
        route_target_ids=trajectory.route_target_ids,
        trajectory_report_sha256=_canonical_hash(trajectory.to_dict()),
        final_round_sha256=_canonical_hash(final_round.to_dict()),
        plan_sha256=plan_hash,
        target_profile_sha256=target_profile,
        robot_model_sha256=model_hash,
        contract=contract,
        policy=policy,
        target_bindings=typed_targets,
        endpoint_results=endpoint_result_tuple,
        midpoint_results=midpoint_result_tuple,
        command_bindings=command_bindings,
        blockers=blockers,
    )
    # Re-evaluate the structural inputs after collision evaluation.  The public
    # values are frozen, but this catches hostile/mutable typed test doubles at
    # the boundary rather than silently reporting a mixed snapshot.
    _validate_contract_and_sources(trajectory, contract, policy)
    _validate_trajectory(trajectory)
    _validate_target_bindings(trajectory, contract, typed_targets)
    _validate_pose_inputs(
        contract,
        waypoints,
        joint_results,
        typed_endpoints,
        typed_midpoints,
    )
    return report


__all__ = [
    "MAX_STATIC_MISSION_CONTACT_PENETRATION_MM",
    "MAX_STATIC_MISSION_INCOMING_MIDPOINTS",
    "MAX_STATIC_MISSION_WAYPOINTS",
    "STATIC_B0477_MISSION_COMMAND_BINDING_SCHEMA",
    "STATIC_B0477_MISSION_ENDPOINT_SCHEMA",
    "STATIC_B0477_MISSION_MIDPOINT_SCHEMA",
    "STATIC_B0477_MISSION_ROUTE_REPORT_SCHEMA",
    "StaticMissionCommandCollisionBinding",
    "StaticMissionEndpointPose",
    "StaticMissionEndpointResult",
    "StaticMissionIncomingMidpointPose",
    "StaticMissionMidpointResult",
    "StaticMissionRouteCollisionReport",
    "StaticMissionRouteError",
    "StaticMissionRouteStatus",
    "evaluate_static_b0477_mission_route",
]
