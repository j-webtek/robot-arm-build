"""Bind every accepted trajectory waypoint to one non-wire controller target.

The historical virtual-session executor consumes joint waypoints directly.  A
real RoArm integration will instead need a controller-facing command at every
dense waypoint, without losing the semantic action, collision sample, or
authorization ordinal that justified it.  This module establishes that join
table now, while hardware is unavailable.

The result is deliberately *not* a RoArm command program.  It uses the strict
in-memory :mod:`rocell.simulation.t104_runtime` document, which has no encoder,
transport, or live permit API.  The controller pose is computed by applying the
audited firmware equations to the accepted logical joint values.  Equality of
that controller frame and the physical arm/board frames remains explicitly
uncommissioned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from rocell.motion import MotionPhase
from rocell.simulation.controller import (
    ControllerJointState,
    ControllerPose,
    controller_forward_kinematics,
    model_gripper_to_controller_raw,
    validate_provisional_simulation_intersection,
)
from rocell.simulation.t104_runtime import (
    MAX_RUNTIME_COMMANDS,
    NonWireT104Command,
    NonWireT104Target,
    T104FaultInjection,
    T104RuntimeConfig,
    controller_pose_sha256,
)
from rocell.simulation.virtual_workcell import VIRTUAL_ARM_JOINT_NAMES

from .semantic_step_schedule import (
    ContactSemanticStep,
    SemanticStepSchedule,
)
from .trajectory_simulation import (
    CartesianRouteWaypoint,
    JointTrajectoryWaypointResult,
    TrajectorySimulationReport,
)


DENSE_ROUTE_COMMAND_SCHEMA = "rocell.zero_authority.dense_route_command.v1"
DENSE_ROUTE_SCHEDULE_SCHEMA = "rocell.zero_authority.dense_route_schedule.v1"
CONTROLLER_JOINT_INTERPRETATION = (
    "LOGICAL_JOINT_NAME_PARITY_WITH_UNCOMMISSIONED_R_CTRL_FRAME_CORRELATION"
)
MAX_DENSE_SCHEDULE_BYTES = 32 * 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SUPPORTED_PHASES = frozenset(
    {
        MotionPhase.PARK,
        MotionPhase.TRANSIT,
        MotionPhase.HOVER,
        MotionPhase.APPROACH,
        MotionPhase.CONTACT,
        MotionPhase.RETRACT,
    }
)


class DenseRouteScheduleError(ValueError):
    """The trajectory cannot be represented by an exact non-wire schedule."""


def _canonical_bytes(value: object, *, maximum: int = MAX_DENSE_SCHEDULE_BYTES) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DenseRouteScheduleError("value is not bounded canonical JSON") from exc
    if len(encoded) > maximum:
        raise DenseRouteScheduleError("canonical route schedule exceeds its byte limit")
    return encoded


def _hash(value: object, *, maximum: int = MAX_DENSE_SCHEDULE_BYTES) -> str:
    return hashlib.sha256(_canonical_bytes(value, maximum=maximum)).hexdigest()


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise DenseRouteScheduleError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise DenseRouteScheduleError(f"{label} must be a bounded identifier")
    return value


def _ordinal(value: object, label: str, *, maximum: int = MAX_RUNTIME_COMMANDS) -> int:
    if isinstance(value, bool) or type(value) is not int or not 0 <= value < maximum:
        raise DenseRouteScheduleError(f"{label} must be a bounded nonnegative integer")
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "physical_authority": "ZERO",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_message_present": False,
        "physical_release_effect": "NONE",
    }


def _joint_result_hash(result: JointTrajectoryWaypointResult) -> str:
    return _hash(result.to_dict(), maximum=1024 * 1024)


def _waypoint_hash(waypoint: CartesianRouteWaypoint) -> str:
    return _hash(waypoint.to_dict(), maximum=64 * 1024)


def _controller_pose(result: JointTrajectoryWaypointResult) -> ControllerPose:
    """Project accepted logical model joints through the audited controller FK.

    This does not assert a measured transform between ``R_ctrl`` and the URDF or
    board frame.  The explicit interpretation string on the parent schedule
    prevents the projection from being mistaken for commissioned correlation.
    """

    if not result.accepted or not result.controller_intersection_passed:
        raise DenseRouteScheduleError(
            "every scheduled waypoint needs accepted controller-intersection IK"
        )
    joints = dict(result.solution_arm_joint_positions_rad)
    if set(joints) != set(VIRTUAL_ARM_JOINT_NAMES) or len(joints) != len(
        VIRTUAL_ARM_JOINT_NAMES
    ):
        raise DenseRouteScheduleError(
            "joint result must contain the exact five logical RoArm joints"
        )
    state = ControllerJointState(
        base_rad=joints[VIRTUAL_ARM_JOINT_NAMES[0]],
        shoulder_rad=joints[VIRTUAL_ARM_JOINT_NAMES[1]],
        elbow_rad=joints[VIRTUAL_ARM_JOINT_NAMES[2]],
        wrist_pitch_rad=joints[VIRTUAL_ARM_JOINT_NAMES[3]],
        wrist_roll_rad=joints[VIRTUAL_ARM_JOINT_NAMES[4]],
        gripper_raw_rad=model_gripper_to_controller_raw(0.0),
    )
    validate_provisional_simulation_intersection(state)
    return controller_forward_kinematics(state)


def _primitive_for_phase(phase: MotionPhase):
    # Local import keeps the type source beside the mapping and avoids implying
    # that a motion phase itself is an authorization.
    from rocell.safety.authorization_v2 import SimulationPrimitive

    return {
        MotionPhase.TRANSIT: SimulationPrimitive.TRANSIT,
        MotionPhase.HOVER: SimulationPrimitive.MOVE_ABOVE,
        MotionPhase.APPROACH: SimulationPrimitive.DESCEND_PRECONTACT,
        MotionPhase.CONTACT: SimulationPrimitive.CONTACT_INTENT,
        MotionPhase.RETRACT: SimulationPrimitive.RETRACT,
        MotionPhase.PARK: SimulationPrimitive.PARK,
    }[phase]


@dataclass(frozen=True, slots=True)
class DenseRouteCommandBinding:
    """One exact row joining all four mission ordering domains."""

    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    route_waypoint_ordinal: int
    authorization_command_ordinal: int
    phase: MotionPhase
    semantic_target: str | None
    phase_endpoint: bool
    mission_tail: bool
    waypoint_sha256: str
    joint_result_sha256: str
    command: NonWireT104Command
    schema: str = DENSE_ROUTE_COMMAND_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _hash(self._document()))

    @property
    def primitive(self):
        return _primitive_for_phase(self.phase)

    @property
    def command_sha256(self) -> str:
        return self.command.canonical_sha256

    @property
    def binding_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        if self.schema != DENSE_ROUTE_COMMAND_SCHEMA:
            raise DenseRouteScheduleError("unsupported dense-route command schema")
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=512)
        _ordinal(self.contact_occurrence_ordinal, "contact_occurrence_ordinal", maximum=512)
        route = _ordinal(self.route_waypoint_ordinal, "route_waypoint_ordinal")
        authorization = _ordinal(
            self.authorization_command_ordinal,
            "authorization_command_ordinal",
        )
        if route == 0 or authorization != route - 1:
            raise DenseRouteScheduleError(
                "authorization ordinal must explicitly bind route waypoint ordinal minus one"
            )
        if type(self.phase) is not MotionPhase or self.phase not in _SUPPORTED_PHASES:
            raise DenseRouteScheduleError("unsupported dense route motion phase")
        if self.semantic_target is not None:
            _identifier(self.semantic_target, "semantic_target")
        if type(self.phase_endpoint) is not bool or type(self.mission_tail) is not bool:
            raise TypeError("phase_endpoint and mission_tail must be bool")
        if self.mission_tail:
            if self.semantic_target is not None or self.phase not in {
                MotionPhase.TRANSIT,
                MotionPhase.PARK,
            }:
                raise DenseRouteScheduleError(
                    "mission tail may contain only unowned TRANSIT/PARK waypoints"
                )
        elif self.semantic_target is None:
            raise DenseRouteScheduleError("non-tail command needs a semantic target")
        _digest(self.waypoint_sha256, "waypoint_sha256")
        _digest(self.joint_result_sha256, "joint_result_sha256")
        if type(self.command) is not NonWireT104Command:
            raise TypeError("command must be exactly NonWireT104Command")
        # Round-trip revalidation also rejects constructor-bypass mutation.
        command = NonWireT104Command.from_dict(self.command.to_dict())
        if command.sequence_ordinal != authorization:
            raise DenseRouteScheduleError("non-wire command ordinal differs from binding")
        if command.joint_result_sha256 != self.joint_result_sha256:
            raise DenseRouteScheduleError("non-wire command has the wrong joint-result hash")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "authorization_command_ordinal": self.authorization_command_ordinal,
            "phase": self.phase.value,
            "authorization_primitive": self.primitive.value,
            "semantic_target": self.semantic_target,
            "phase_endpoint": self.phase_endpoint,
            "mission_tail": self.mission_tail,
            "waypoint_sha256": self.waypoint_sha256,
            "joint_result_sha256": self.joint_result_sha256,
            "non_wire_command": self.command.to_dict(),
            "non_wire_command_sha256": self.command.canonical_sha256,
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document()) != self._sealed_sha256:
            raise DenseRouteScheduleError("dense route command changed after construction")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


@dataclass(frozen=True, slots=True)
class DenseContactRouteSlice:
    """Contiguous command span owned by one physical contact occurrence."""

    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    target_id: str
    first_authorization_command_ordinal: int
    last_authorization_command_ordinal: int
    final_hover_route_waypoint_ordinal: int
    contact_route_waypoint_ordinal: int
    final_retract_route_waypoint_ordinal: int
    includes_mission_tail: bool

    def __post_init__(self) -> None:
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=512)
        _ordinal(self.contact_occurrence_ordinal, "contact_occurrence_ordinal", maximum=512)
        _identifier(self.target_id, "target_id")
        first = _ordinal(
            self.first_authorization_command_ordinal,
            "first_authorization_command_ordinal",
        )
        last = _ordinal(
            self.last_authorization_command_ordinal,
            "last_authorization_command_ordinal",
        )
        if last < first:
            raise DenseRouteScheduleError("contact command span is reversed")
        for name in (
            "final_hover_route_waypoint_ordinal",
            "contact_route_waypoint_ordinal",
            "final_retract_route_waypoint_ordinal",
        ):
            route = _ordinal(getattr(self, name), name)
            if not first <= route - 1 <= last:
                raise DenseRouteScheduleError(f"{name} lies outside the contact command span")
        if not (
            self.final_hover_route_waypoint_ordinal
            < self.contact_route_waypoint_ordinal
            < self.final_retract_route_waypoint_ordinal
        ):
            raise DenseRouteScheduleError("hover/contact/retract endpoints are out of order")
        if type(self.includes_mission_tail) is not bool:
            raise TypeError("includes_mission_tail must be bool")

    def to_dict(self) -> dict[str, object]:
        return {
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "target_id": self.target_id,
            "first_authorization_command_ordinal": (
                self.first_authorization_command_ordinal
            ),
            "last_authorization_command_ordinal": self.last_authorization_command_ordinal,
            "final_hover_route_waypoint_ordinal": (
                self.final_hover_route_waypoint_ordinal
            ),
            "contact_route_waypoint_ordinal": self.contact_route_waypoint_ordinal,
            "final_retract_route_waypoint_ordinal": (
                self.final_retract_route_waypoint_ordinal
            ),
            "includes_mission_tail": self.includes_mission_tail,
        }


@dataclass(frozen=True, slots=True)
class DenseRouteSchedule:
    """Immutable non-wire program for every waypoint after known initial park."""

    mission_id: str
    controller_session_id: str
    source_plan_sha256: str
    semantic_schedule_sha256: str
    trajectory_report_sha256: str
    initial_route_waypoint_sha256: str
    initial_joint_result_sha256: str
    initial_controller_pose: ControllerPose
    commands: tuple[DenseRouteCommandBinding, ...]
    contact_slices: tuple[DenseContactRouteSlice, ...]
    runtime_config: T104RuntimeConfig
    controller_joint_interpretation: str = CONTROLLER_JOINT_INTERPRETATION
    schema: str = DENSE_ROUTE_SCHEDULE_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _hash(self._document()))

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def route_waypoint_count(self) -> int:
        return self.command_count + 1

    @property
    def canonical_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        if self.schema != DENSE_ROUTE_SCHEDULE_SCHEMA:
            raise DenseRouteScheduleError("unsupported dense route schedule schema")
        _identifier(self.mission_id, "mission_id")
        _identifier(self.controller_session_id, "controller_session_id")
        for name in (
            "source_plan_sha256",
            "semantic_schedule_sha256",
            "trajectory_report_sha256",
            "initial_route_waypoint_sha256",
            "initial_joint_result_sha256",
        ):
            _digest(getattr(self, name), name)
        if self.controller_joint_interpretation != CONTROLLER_JOINT_INTERPRETATION:
            raise DenseRouteScheduleError("controller joint interpretation was promoted")
        if type(self.initial_controller_pose) is not ControllerPose:
            raise TypeError("initial_controller_pose must be ControllerPose")
        if type(self.commands) is not tuple:
            raise TypeError("commands must be an immutable tuple")
        commands = self.commands
        if not 1 <= len(commands) <= MAX_RUNTIME_COMMANDS:
            raise DenseRouteScheduleError("dense route command count is outside bounds")
        if any(type(item) is not DenseRouteCommandBinding for item in commands):
            raise TypeError("commands must contain DenseRouteCommandBinding")
        for item in commands:
            item.validate()
        if tuple(item.authorization_command_ordinal for item in commands) != tuple(
            range(len(commands))
        ):
            raise DenseRouteScheduleError("authorization command ordinals must be dense")
        if tuple(item.route_waypoint_ordinal for item in commands) != tuple(
            range(1, len(commands) + 1)
        ):
            raise DenseRouteScheduleError("route waypoint ordinals must be dense from one")
        if tuple(item.command.sequence_ordinal for item in commands) != tuple(
            range(len(commands))
        ):
            raise DenseRouteScheduleError("non-wire command ordinals must be dense")
        action_groups: list[int] = []
        for item in commands:
            if not action_groups or action_groups[-1] != item.contact_occurrence_ordinal:
                if item.contact_occurrence_ordinal in action_groups:
                    raise DenseRouteScheduleError("contact command groups must be contiguous")
                action_groups.append(item.contact_occurrence_ordinal)
        if action_groups != list(range(len(self.contact_slices))):
            raise DenseRouteScheduleError("command contact groups must be dense and complete")
        tails = tuple(index for index, item in enumerate(commands) if item.mission_tail)
        if tails and tails != tuple(range(tails[0], len(commands))):
            raise DenseRouteScheduleError("mission tail commands must be one final suffix")
        if type(self.contact_slices) is not tuple:
            raise TypeError("contact_slices must be an immutable tuple")
        slices = self.contact_slices
        if not slices or any(type(item) is not DenseContactRouteSlice for item in slices):
            raise DenseRouteScheduleError("contact_slices must be non-empty typed values")
        if tuple(item.contact_occurrence_ordinal for item in slices) != tuple(
            range(len(slices))
        ):
            raise DenseRouteScheduleError("contact slice ordinals must be dense")
        for index, slice_ in enumerate(slices):
            owned = tuple(
                item
                for item in commands
                if item.contact_occurrence_ordinal == index
            )
            if (
                not owned
                or owned[0].authorization_command_ordinal
                != slice_.first_authorization_command_ordinal
                or owned[-1].authorization_command_ordinal
                != slice_.last_authorization_command_ordinal
                or slice_.semantic_step_ordinal != owned[0].semantic_step_ordinal
                or owned[0].semantic_target is None
                or owned[0].semantic_target.partition(":")[2] != slice_.target_id
                or slice_.includes_mission_tail != any(item.mission_tail for item in owned)
            ):
                raise DenseRouteScheduleError("contact slice differs from its command group")
        if type(self.runtime_config) is not T104RuntimeConfig:
            raise TypeError("runtime_config must be exactly T104RuntimeConfig")
        round_trip = T104RuntimeConfig.from_dict(self.runtime_config.to_dict())
        if (
            round_trip.session_id != self.controller_session_id
            or round_trip.initial_pose != self.initial_controller_pose
            or tuple(entry.command_sha256 for entry in round_trip.schedule)
            != tuple(item.command_sha256 for item in commands)
        ):
            raise DenseRouteScheduleError("runtime configuration differs from dense commands")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "mission_id": self.mission_id,
            "controller_session_id": self.controller_session_id,
            "source_plan_sha256": self.source_plan_sha256,
            "semantic_schedule_sha256": self.semantic_schedule_sha256,
            "trajectory_report_sha256": self.trajectory_report_sha256,
            "controller_joint_interpretation": self.controller_joint_interpretation,
            "controller_frame_physically_correlated": False,
            "initial_route_waypoint_sha256": self.initial_route_waypoint_sha256,
            "initial_joint_result_sha256": self.initial_joint_result_sha256,
            "initial_controller_pose": self.initial_controller_pose.to_dict(),
            "initial_controller_pose_sha256": controller_pose_sha256(
                self.initial_controller_pose
            ),
            "commands": [item.to_dict() for item in self.commands],
            "contact_slices": [item.to_dict() for item in self.contact_slices],
            "runtime_config": self.runtime_config.to_dict(),
            "runtime_config_sha256": self.runtime_config.canonical_sha256,
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document()) != self._sealed_sha256:
            raise DenseRouteScheduleError("dense route schedule changed after construction")

    def assert_matches_trajectory(
        self,
        trajectory: TrajectorySimulationReport,
    ) -> None:
        """Recompute every controller target from the exact trajectory joints.

        The schedule's own seal proves only that its rows have not changed since
        construction.  This independent join check proves that those rows were
        originally derived from the selected trajectory rather than from a
        self-consistent, substituted controller-pose chain.
        """

        self.validate()
        if type(trajectory) is not TrajectorySimulationReport:
            raise TypeError("trajectory must be exactly TrajectorySimulationReport")
        if self.trajectory_report_sha256 != trajectory.report_hash:
            raise DenseRouteScheduleError("dense route is bound to another trajectory")
        final = trajectory.final_round
        if final is None or not final.all_waypoints_accepted:
            raise DenseRouteScheduleError("trajectory final round must be fully accepted")
        waypoints = tuple(final.waypoints)
        results = tuple(final.joint_results)
        if (
            len(waypoints) != self.route_waypoint_count
            or len(results) != self.route_waypoint_count
            or not waypoints
        ):
            raise DenseRouteScheduleError(
                "dense route does not exactly cover the trajectory final round"
            )
        if (
            self.initial_route_waypoint_sha256 != _waypoint_hash(waypoints[0])
            or self.initial_joint_result_sha256 != _joint_result_hash(results[0])
        ):
            raise DenseRouteScheduleError("dense route initial trajectory binding differs")
        expected_initial_pose = _controller_pose(results[0])
        if self.initial_controller_pose != expected_initial_pose:
            raise DenseRouteScheduleError(
                "dense route initial controller pose was not derived from trajectory joints"
            )

        previous_pose_sha256 = controller_pose_sha256(expected_initial_pose)
        semantic_action_order: list[int] = []
        for waypoint in waypoints:
            if (
                waypoint.action_index is not None
                and waypoint.action_index not in semantic_action_order
            ):
                semantic_action_order.append(waypoint.action_index)
        if not semantic_action_order:
            raise DenseRouteScheduleError("trajectory has no physical semantic action")
        contact_by_semantic = {
            semantic: contact
            for contact, semantic in enumerate(semantic_action_order)
        }
        final_semantic = semantic_action_order[-1]
        final_contact = len(semantic_action_order) - 1
        for route_ordinal, (binding, waypoint, result) in enumerate(
            zip(self.commands, waypoints[1:], results[1:]),
            start=1,
        ):
            expected_pose = _controller_pose(result)
            command = binding.command
            if (
                binding.route_waypoint_ordinal != route_ordinal
                or binding.authorization_command_ordinal != route_ordinal - 1
                or binding.phase is not waypoint.phase
                or binding.semantic_step_ordinal
                != (
                    waypoint.action_index
                    if waypoint.action_index is not None
                    else final_semantic
                )
                or binding.contact_occurrence_ordinal
                != (
                    contact_by_semantic[waypoint.action_index]
                    if waypoint.action_index is not None
                    else final_contact
                )
                or binding.semantic_target != waypoint.semantic_target
                or binding.phase_endpoint != waypoint.phase_endpoint
                or binding.mission_tail != (waypoint.action_index is None)
                or binding.waypoint_sha256 != _waypoint_hash(waypoint)
                or binding.joint_result_sha256 != _joint_result_hash(result)
                or result.waypoint_sequence != route_ordinal
                or result.phase is not waypoint.phase
                or result.action_index != waypoint.action_index
                or result.semantic_target != waypoint.semantic_target
            ):
                raise DenseRouteScheduleError(
                    "dense command row differs from its trajectory waypoint/result"
                )
            if (
                command.command_id
                != f"{self.mission_id}-cmd-{route_ordinal - 1:04d}"
                or command.session_id != self.controller_session_id
                or command.sequence_ordinal != route_ordinal - 1
                or command.expected_previous_pose_sha256 != previous_pose_sha256
                or command.route_sha256 != trajectory.report_hash
                or command.joint_result_sha256 != _joint_result_hash(result)
                or command.target.target_id
                != f"route-{route_ordinal:04d}-{waypoint.phase.value.lower()}"
                or command.target.pose != expected_pose
            ):
                raise DenseRouteScheduleError(
                    "non-wire controller command was not derived from trajectory joints"
                )
            previous_pose_sha256 = controller_pose_sha256(expected_pose)

        expected_slices: list[DenseContactRouteSlice] = []
        for contact_ordinal in range(len(self.contact_slices)):
            owned = tuple(
                item
                for item in self.commands
                if item.contact_occurrence_ordinal == contact_ordinal
            )
            if not owned or owned[0].semantic_target is None:
                raise DenseRouteScheduleError(
                    "contact slice has no trajectory-owned command group"
                )

            def exact_endpoint(phase: MotionPhase) -> int:
                candidates = tuple(
                    item.route_waypoint_ordinal
                    for item in owned
                    if item.phase is phase
                    and item.phase_endpoint
                    and not item.mission_tail
                )
                if len(candidates) != 1:
                    raise DenseRouteScheduleError(
                        f"contact {contact_ordinal} has non-exact {phase.value} coverage"
                    )
                return candidates[0]

            expected_slices.append(
                DenseContactRouteSlice(
                    semantic_step_ordinal=owned[0].semantic_step_ordinal,
                    contact_occurrence_ordinal=contact_ordinal,
                    target_id=owned[0].semantic_target.partition(":")[2],
                    first_authorization_command_ordinal=(
                        owned[0].authorization_command_ordinal
                    ),
                    last_authorization_command_ordinal=(
                        owned[-1].authorization_command_ordinal
                    ),
                    final_hover_route_waypoint_ordinal=exact_endpoint(
                        MotionPhase.HOVER
                    ),
                    contact_route_waypoint_ordinal=exact_endpoint(
                        MotionPhase.CONTACT
                    ),
                    final_retract_route_waypoint_ordinal=exact_endpoint(
                        MotionPhase.RETRACT
                    ),
                    includes_mission_tail=any(item.mission_tail for item in owned),
                )
            )
        if tuple(expected_slices) != self.contact_slices:
            raise DenseRouteScheduleError(
                "contact slices were not derived from exact trajectory phase endpoints"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


def _contact_steps_by_semantic(
    schedule: SemanticStepSchedule,
) -> Mapping[int, ContactSemanticStep]:
    return {
        step.semantic_step_ordinal: step
        for step in schedule.steps
        if type(step) is ContactSemanticStep
    }


def build_dense_route_schedule(
    *,
    mission_id: str,
    controller_session_id: str,
    semantic_schedule: SemanticStepSchedule,
    trajectory: TrajectorySimulationReport,
    spd_coefficient: float = 100.0,
    fault_injections: Sequence[T104FaultInjection] = (),
) -> DenseRouteSchedule:
    """Build the exact one-command-per-dense-waypoint non-wire schedule."""

    mission = _identifier(mission_id, "mission_id")
    session = _identifier(controller_session_id, "controller_session_id")
    if type(semantic_schedule) is not SemanticStepSchedule:
        raise TypeError("semantic_schedule must be exactly SemanticStepSchedule")
    semantic_schedule.validate()
    if type(trajectory) is not TrajectorySimulationReport:
        raise TypeError("trajectory must be exactly TrajectorySimulationReport")
    if isinstance(spd_coefficient, bool) or type(spd_coefficient) not in (int, float):
        raise TypeError("spd_coefficient must be a non-boolean number")
    speed = float(spd_coefficient)
    if not math.isfinite(speed) or speed <= 0.0:
        raise DenseRouteScheduleError("spd_coefficient must be finite and positive")
    if trajectory.device != semantic_schedule.device.value:
        raise DenseRouteScheduleError("trajectory device differs from semantic schedule")
    provenance = dict(trajectory.source_provenance)
    if provenance.get("plan_hash") != semantic_schedule.source_plan_sha256:
        raise DenseRouteScheduleError("trajectory is not bound to the semantic source plan")
    final = trajectory.final_round
    if final is None or not final.all_waypoints_accepted:
        raise DenseRouteScheduleError("trajectory final round must be fully accepted")
    waypoints = tuple(final.waypoints)
    results = tuple(final.joint_results)
    if not waypoints or len(waypoints) != len(results):
        raise DenseRouteScheduleError("trajectory waypoint/result coverage is incomplete")
    if tuple(item.sequence for item in waypoints) != tuple(range(len(waypoints))):
        raise DenseRouteScheduleError("trajectory waypoint sequences must be dense")
    if tuple(item.waypoint_sequence for item in results) != tuple(range(len(results))):
        raise DenseRouteScheduleError("joint-result waypoint sequences must be dense")
    for waypoint, result in zip(waypoints, results):
        if (
            waypoint.sequence != result.waypoint_sequence
            or waypoint.phase is not result.phase
            or waypoint.action_index != result.action_index
            or waypoint.semantic_target != result.semantic_target
        ):
            raise DenseRouteScheduleError("trajectory waypoint and joint result differ")
        if waypoint.phase not in _SUPPORTED_PHASES:
            raise DenseRouteScheduleError("trajectory contains an unsupported mission phase")
        if not result.accepted:
            raise DenseRouteScheduleError("trajectory contains a rejected joint result")
    if not (
        waypoints[0].phase is MotionPhase.PARK
        and waypoints[0].phase_endpoint
        and waypoints[0].action_index is None
        and waypoints[-1].phase is MotionPhase.PARK
        and waypoints[-1].phase_endpoint
        and waypoints[-1].action_index is None
    ):
        raise DenseRouteScheduleError("trajectory must start and end at PARK endpoints")

    contact_by_semantic = _contact_steps_by_semantic(semantic_schedule)
    if len(contact_by_semantic) != semantic_schedule.contact_count or not contact_by_semantic:
        raise DenseRouteScheduleError("semantic contact mapping is incomplete")

    initial_pose = _controller_pose(results[0])
    previous_pose_hash = controller_pose_sha256(initial_pose)
    bindings: list[DenseRouteCommandBinding] = []
    tail_started = False
    last_contact = semantic_schedule.contact_count - 1
    for route_ordinal, (waypoint, result) in enumerate(
        zip(waypoints[1:], results[1:]), start=1
    ):
        if waypoint.action_index is None:
            tail_started = True
            resolved_step = next(
                value
                for value in contact_by_semantic.values()
                if value.contact_occurrence_ordinal == last_contact
            )
            mission_tail = True
        else:
            if tail_started:
                raise DenseRouteScheduleError("semantic action appears after mission tail")
            candidate_step = contact_by_semantic.get(waypoint.action_index)
            if candidate_step is None:
                raise DenseRouteScheduleError(
                    "trajectory waypoint refers to an observation-only or unknown semantic step"
                )
            resolved_step = candidate_step
            mission_tail = False
            expected_target = f"{trajectory.device}:{resolved_step.target_id}"
            if waypoint.semantic_target != expected_target:
                raise DenseRouteScheduleError(
                    "trajectory semantic target differs from its scheduled contact"
                )
        target_pose = _controller_pose(result)
        authorization_ordinal = route_ordinal - 1
        joint_hash = _joint_result_hash(result)
        command = NonWireT104Command(
            command_id=f"{mission}-cmd-{authorization_ordinal:04d}",
            session_id=session,
            sequence_ordinal=authorization_ordinal,
            expected_previous_pose_sha256=previous_pose_hash,
            route_sha256=trajectory.report_hash,
            joint_result_sha256=joint_hash,
            target=NonWireT104Target(
                target_id=f"route-{route_ordinal:04d}-{waypoint.phase.value.lower()}",
                pose=target_pose,
            ),
            spd_coefficient=speed,
        )
        bindings.append(
            DenseRouteCommandBinding(
                semantic_step_ordinal=resolved_step.semantic_step_ordinal,
                contact_occurrence_ordinal=resolved_step.contact_occurrence_ordinal,
                route_waypoint_ordinal=route_ordinal,
                authorization_command_ordinal=authorization_ordinal,
                phase=waypoint.phase,
                semantic_target=waypoint.semantic_target,
                phase_endpoint=waypoint.phase_endpoint,
                mission_tail=mission_tail,
                waypoint_sha256=_waypoint_hash(waypoint),
                joint_result_sha256=joint_hash,
                command=command,
            )
        )
        previous_pose_hash = controller_pose_sha256(target_pose)

    slices: list[DenseContactRouteSlice] = []
    for contact_ordinal in range(semantic_schedule.contact_count):
        owned = tuple(
            item
            for item in bindings
            if item.contact_occurrence_ordinal == contact_ordinal
        )
        if not owned:
            raise DenseRouteScheduleError("contact occurrence owns no trajectory commands")
        step = next(
            value
            for value in contact_by_semantic.values()
            if value.contact_occurrence_ordinal == contact_ordinal
        )

        def endpoint(phase: MotionPhase) -> int:
            values = tuple(
                item.route_waypoint_ordinal
                for item in owned
                if item.phase is phase and item.phase_endpoint and not item.mission_tail
            )
            if len(values) != 1:
                raise DenseRouteScheduleError(
                    f"contact {contact_ordinal} needs exactly one final {phase.value} endpoint"
                )
            return values[0]

        slices.append(
            DenseContactRouteSlice(
                semantic_step_ordinal=step.semantic_step_ordinal,
                contact_occurrence_ordinal=contact_ordinal,
                target_id=step.target_id,
                first_authorization_command_ordinal=(
                    owned[0].authorization_command_ordinal
                ),
                last_authorization_command_ordinal=(
                    owned[-1].authorization_command_ordinal
                ),
                final_hover_route_waypoint_ordinal=endpoint(MotionPhase.HOVER),
                contact_route_waypoint_ordinal=endpoint(MotionPhase.CONTACT),
                final_retract_route_waypoint_ordinal=endpoint(MotionPhase.RETRACT),
                includes_mission_tail=any(item.mission_tail for item in owned),
            )
        )
    if not slices[-1].includes_mission_tail or any(
        item.includes_mission_tail for item in slices[:-1]
    ):
        raise DenseRouteScheduleError("only the final contact may own the mission tail")

    commands = tuple(item.command for item in bindings)
    runtime = T104RuntimeConfig.bind_commands(
        session_id=session,
        initial_pose=initial_pose,
        commands=commands,
        fault_injections=fault_injections,
    )
    return DenseRouteSchedule(
        mission_id=mission,
        controller_session_id=session,
        source_plan_sha256=semantic_schedule.source_plan_sha256,
        semantic_schedule_sha256=semantic_schedule.canonical_sha256,
        trajectory_report_sha256=trajectory.report_hash,
        initial_route_waypoint_sha256=_waypoint_hash(waypoints[0]),
        initial_joint_result_sha256=_joint_result_hash(results[0]),
        initial_controller_pose=initial_pose,
        commands=tuple(bindings),
        contact_slices=tuple(slices),
        runtime_config=runtime,
    )


__all__ = [
    "CONTROLLER_JOINT_INTERPRETATION",
    "DENSE_ROUTE_COMMAND_SCHEMA",
    "DENSE_ROUTE_SCHEDULE_SCHEMA",
    "DenseContactRouteSlice",
    "DenseRouteCommandBinding",
    "DenseRouteSchedule",
    "DenseRouteScheduleError",
    "build_dense_route_schedule",
]
