"""Assemble a dense, camera/collision/authorization-bound mission V2.

V1 intentionally models four compound arm operations per contact.  The real
trajectory simulator produces more waypoints, and Android plans also contain
observation-only semantic steps.  This additive V2 assembly preserves those
facts instead of forcing them into the V1 shape:

* semantic, contact-occurrence, route-waypoint, and authorization-command
  ordinals remain separate;
* every post-park waypoint maps to one strict non-wire T104 emulator target;
* every command maps to its endpoint and incoming-midpoint collision results;
* every contact maps to a fresh B0477 report captured at its final hover;
* Android state observations are retained but own no contact or command; and
* authorization_v2 binds the complete dense sequence.

All inputs and outputs remain zero-authority simulation evidence.  In
particular, the synthetic calibration projection and isolated collision
fixture cannot be promoted into physical release evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re

from rocell.models.actions import ActionPlan, Device
from rocell.safety.authorization_v2 import (
    SimulatedContactCapability,
    SimulationTrajectoryCommand,
)
from rocell.safety.synthetic_authorization import (
    SyntheticAuthorizationBundle,
    SyntheticEmulatorIdentity,
    build_synthetic_authorization_evidence,
    project_static_phase1_synthetic_closure,
)
from rocell.simulation.b0477_replay_camera import B0477ReplayFaultInjection
from rocell.simulation.static_mission_fixture import IsolatedStaticMissionFixture
from rocell.simulation.static_mission_route import (
    StaticMissionCommandCollisionBinding,
)
from rocell.simulation.virtual_workcell import VirtualAndroid, VirtualKeyboard

from .b0477_mission_observations import B0477MissionObservationSet
from .bootstrap import (
    VirtualWorkcellBootstrap,
    revalidate_virtual_workcell,
)
from .dense_route_schedule import DenseRouteCommandBinding, DenseRouteSchedule
from .mission_journal import ActionOccurrence
from .semantic_step_schedule import (
    ContactSemanticStep,
    SemanticStepSchedule,
)
from .static_phase1_calibration import (
    build_static_phase1_synthetic_closure,
    static_phase1_context_hashes,
)
from .trajectory_simulation import (
    TrajectorySimulationReport,
    revalidate_trajectory_simulation_report,
)


ZERO_HARDWARE_MISSION_V2_SCHEMA = "rocell.zero_authority.mission_v2.v1"
ZERO_HARDWARE_COMMAND_BINDING_SCHEMA = (
    "rocell.zero_authority.mission_v2_command_binding.v1"
)
DEVICE_SAFETY_CONTEXT_SCHEMA = "rocell.zero_authority.device_safety_context.v1"
MAX_MISSION_V2_BYTES = 64 * 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class MultiActionMissionV2Error(ValueError):
    """The integrated mission graph is incomplete, altered, or unsafe."""


def _canonical_bytes(value: object, *, maximum: int = MAX_MISSION_V2_BYTES) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MultiActionMissionV2Error("value is not canonical JSON") from exc
    if len(encoded) > maximum:
        raise MultiActionMissionV2Error("mission V2 document exceeds its byte limit")
    return encoded


def _hash(value: object, *, maximum: int = MAX_MISSION_V2_BYTES) -> str:
    return hashlib.sha256(_canonical_bytes(value, maximum=maximum)).hexdigest()


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MultiActionMissionV2Error(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise MultiActionMissionV2Error(f"{label} must be a bounded identifier")
    return value


def _text(value: object, label: str, *, maximum: int = 512) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise MultiActionMissionV2Error(f"{label} must be bounded, trimmed text")
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "physical_authority": "ZERO",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_messages_generated": 0,
        "power_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "can_release_physical_gates": False,
        "physical_release_effect": "NONE",
    }


@dataclass(frozen=True, slots=True)
class DeviceSafetyContext:
    """Stable device facts used during one authorization permit.

    Accumulated text and attempt counters are intentionally excluded: they are
    outcome evidence, not safety configuration.  Focus, UI mode, model, target
    regions, outputs, and state transitions remain bound.  Mission V2 currently
    rejects plans that intentionally change UI mode because those need a new
    permit segment rather than silently changing this context.
    """

    device: Device
    profile_id: str
    model_definition_sha256: str
    region_definition_sha256: str
    output_map_sha256: str
    state_transition_map_sha256: str
    focused: bool
    android_ui_state: str | None
    schema: str = DEVICE_SAFETY_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DEVICE_SAFETY_CONTEXT_SCHEMA:
            raise MultiActionMissionV2Error("unsupported device safety context schema")
        if type(self.device) is not Device:
            raise TypeError("device must be exactly Device")
        _text(self.profile_id, "profile_id")
        for name in (
            "model_definition_sha256",
            "region_definition_sha256",
            "output_map_sha256",
            "state_transition_map_sha256",
        ):
            _digest(getattr(self, name), name)
        if type(self.focused) is not bool:
            raise TypeError("focused must be bool")
        if self.device is Device.PHONE:
            _identifier(self.android_ui_state, "android_ui_state")
        elif self.android_ui_state is not None:
            raise MultiActionMissionV2Error("keyboard safety context cannot have UI state")

    @property
    def context_sha256(self) -> str:
        return _hash(self.to_dict(), maximum=64 * 1024)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "device": self.device.value,
            "profile_id": self.profile_id,
            "model_definition_sha256": self.model_definition_sha256,
            "region_definition_sha256": self.region_definition_sha256,
            "output_map_sha256": self.output_map_sha256,
            "state_transition_map_sha256": self.state_transition_map_sha256,
            "focused": self.focused,
            "android_ui_state": self.android_ui_state,
            "mutable_output_and_attempt_counters_excluded": True,
            "ui_state_change_requires_new_permit_segment": True,
        }

    @classmethod
    def from_device(
        cls,
        device: VirtualKeyboard | VirtualAndroid,
        *,
        source_device: Device,
        profile_id: str,
    ) -> "DeviceSafetyContext":
        if source_device is Device.KEYBOARD and type(device) is not VirtualKeyboard:
            raise MultiActionMissionV2Error("keyboard plan has a non-keyboard truth model")
        if source_device is Device.PHONE and type(device) is not VirtualAndroid:
            raise MultiActionMissionV2Error("phone plan has a non-Android truth model")
        return cls(
            device=source_device,
            profile_id=profile_id,
            model_definition_sha256=device.model_definition_hash,
            region_definition_sha256=device.region_definition_hash,
            output_map_sha256=device.output_map_hash,
            state_transition_map_sha256=device.state_transition_map_hash,
            focused=device.focused,
            android_ui_state=(device.ui_state if type(device) is VirtualAndroid else None),
        )


@dataclass(frozen=True, slots=True)
class MissionV2CommandBinding:
    """Exact join of route, collision, camera, occurrence, and authorization."""

    dense: DenseRouteCommandBinding
    collision: StaticMissionCommandCollisionBinding
    camera_observation_sha256: str
    action_occurrence_sha256: str
    simulation_command: SimulationTrajectoryCommand
    schema: str = ZERO_HARDWARE_COMMAND_BINDING_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _hash(self._document()))

    @property
    def binding_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        if self.schema != ZERO_HARDWARE_COMMAND_BINDING_SCHEMA:
            raise MultiActionMissionV2Error("unsupported V2 command-binding schema")
        if type(self.dense) is not DenseRouteCommandBinding:
            raise TypeError("dense must be exactly DenseRouteCommandBinding")
        self.dense.validate()
        if type(self.collision) is not StaticMissionCommandCollisionBinding:
            raise TypeError(
                "collision must be exactly StaticMissionCommandCollisionBinding"
            )
        if (
            self.dense.authorization_command_ordinal
            != self.collision.global_authorization_command_ordinal
            or self.dense.route_waypoint_ordinal
            != self.collision.route_waypoint_ordinal
            or self.dense.phase is not self.collision.phase
            or self.dense.semantic_target != self.collision.semantic_target
            or self.dense.phase_endpoint != self.collision.phase_endpoint
            or self.dense.waypoint_sha256 != self.collision.waypoint_sha256
            or self.dense.joint_result_sha256
            != self.collision.joint_result_sha256
        ):
            raise MultiActionMissionV2Error(
                "dense command and collision binding do not describe the same waypoint"
            )
        _digest(self.camera_observation_sha256, "camera_observation_sha256")
        _digest(self.action_occurrence_sha256, "action_occurrence_sha256")
        if type(self.simulation_command) is not SimulationTrajectoryCommand:
            raise TypeError("simulation_command must be SimulationTrajectoryCommand")
        self.simulation_command.__post_init__()
        if (
            self.simulation_command.action_occurrence_id
            != self.action_occurrence_sha256
            or self.simulation_command.primitive is not self.dense.primitive
            or self.simulation_command.target_state_sha256
            != self.dense.command_sha256
        ):
            raise MultiActionMissionV2Error(
                "authorization command differs from its dense command binding"
            )
        expected_constraint = _command_constraint_hash(
            self.dense,
            self.collision,
            camera_observation_sha256=self.camera_observation_sha256,
        )
        if self.simulation_command.constraint_set_sha256 != expected_constraint:
            raise MultiActionMissionV2Error("command constraint set drifted")
        expected_id = _command_occurrence_hash(
            self.dense,
            self.collision,
            action_occurrence_sha256=self.action_occurrence_sha256,
        )
        if self.simulation_command.command_occurrence_id != expected_id:
            raise MultiActionMissionV2Error("authorization command identity drifted")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "semantic_step_ordinal": self.dense.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.dense.contact_occurrence_ordinal,
            "route_waypoint_ordinal": self.dense.route_waypoint_ordinal,
            "authorization_command_ordinal": (
                self.dense.authorization_command_ordinal
            ),
            "dense_command_binding_sha256": self.dense.binding_sha256,
            "non_wire_t104_command_sha256": self.dense.command_sha256,
            "collision_command_binding_sha256": self.collision.content_hash,
            "camera_observation_sha256": self.camera_observation_sha256,
            "action_occurrence_sha256": self.action_occurrence_sha256,
            "authorization_v2_command": self.simulation_command.to_dict(),
            "authorization_v2_command_sha256": (
                self.simulation_command.command_sha256
            ),
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document()) != self._sealed_sha256:
            raise MultiActionMissionV2Error("V2 command binding changed after construction")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


def _command_constraint_hash(
    dense: DenseRouteCommandBinding,
    collision: StaticMissionCommandCollisionBinding,
    *,
    camera_observation_sha256: str,
) -> str:
    return _hash(
        {
            "schema": "rocell.zero_authority.mission_v2_command_constraints.v1",
            "dense_command_binding_sha256": dense.binding_sha256,
            "collision_command_binding_sha256": collision.content_hash,
            "camera_observation_sha256": camera_observation_sha256,
            "final_contact_overlap_allowed": (
                collision.designated_contact_overlap_allowed
            ),
        },
        maximum=256 * 1024,
    )


def _command_occurrence_hash(
    dense: DenseRouteCommandBinding,
    collision: StaticMissionCommandCollisionBinding,
    *,
    action_occurrence_sha256: str,
) -> str:
    return _hash(
        {
            "schema": "rocell.zero_authority.mission_v2_command_occurrence.v1",
            "authorization_command_ordinal": dense.authorization_command_ordinal,
            "route_waypoint_ordinal": dense.route_waypoint_ordinal,
            "non_wire_t104_command_sha256": dense.command_sha256,
            "collision_command_binding_sha256": collision.content_hash,
            "action_occurrence_sha256": action_occurrence_sha256,
        },
        maximum=256 * 1024,
    )


@dataclass(frozen=True, slots=True)
class MultiActionMissionSpecV2:
    """Complete immutable assembly consumed by the integrated emulator."""

    mission_id: str
    bootstrap: VirtualWorkcellBootstrap
    plan: ActionPlan
    normalized_text: str = field(repr=False, compare=False)
    semantic_schedule: SemanticStepSchedule = field(compare=False)
    trajectory: TrajectorySimulationReport = field(compare=False)
    dense_route: DenseRouteSchedule = field(compare=False)
    camera_observations: B0477MissionObservationSet = field(compare=False)
    collision_fixture: IsolatedStaticMissionFixture = field(compare=False)
    device_safety_context: DeviceSafetyContext = field(compare=False)
    occurrences: tuple[ActionOccurrence, ...] = field(compare=False)
    command_bindings: tuple[MissionV2CommandBinding, ...] = field(compare=False)
    authorization: SyntheticAuthorizationBundle = field(compare=False)
    camera_fault_injection: B0477ReplayFaultInjection | None = None
    schema: str = ZERO_HARDWARE_MISSION_V2_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed(recompute_collision=True)
        object.__setattr__(self, "_sealed_sha256", _hash(self._document()))

    @property
    def assembly_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    @property
    def command_count(self) -> int:
        return len(self.command_bindings)

    @property
    def contact_count(self) -> int:
        return len(self.occurrences)

    @property
    def observation_only_step_count(self) -> int:
        return self.semantic_schedule.observation_count

    def _validate_unsealed(self, *, recompute_collision: bool = False) -> None:
        if self.schema != ZERO_HARDWARE_MISSION_V2_SCHEMA:
            raise MultiActionMissionV2Error("unsupported mission V2 schema")
        _identifier(self.mission_id, "mission_id")
        if type(self.bootstrap) is not VirtualWorkcellBootstrap:
            raise TypeError("bootstrap must be exactly VirtualWorkcellBootstrap")
        revalidate_virtual_workcell(self.bootstrap)
        if type(self.plan) is not ActionPlan:
            raise TypeError("plan must be exactly ActionPlan")
        if type(self.normalized_text) is not str:
            raise TypeError("normalized_text must be str")
        if hashlib.sha256(self.normalized_text.encode("utf-8")).hexdigest() != self.plan.requested_text_sha256:
            raise MultiActionMissionV2Error("normalized plaintext hash differs from plan")
        if type(self.semantic_schedule) is not SemanticStepSchedule:
            raise TypeError("semantic_schedule must be SemanticStepSchedule")
        self.semantic_schedule.assert_matches_action_plan(self.plan)
        if type(self.trajectory) is not TrajectorySimulationReport:
            raise TypeError("trajectory must be TrajectorySimulationReport")
        revalidate_trajectory_simulation_report(
            self.bootstrap.context,
            self.plan,
            self.trajectory,
        )
        if type(self.dense_route) is not DenseRouteSchedule:
            raise TypeError("dense_route must be DenseRouteSchedule")
        if self.trajectory.report_hash != self.dense_route.trajectory_report_sha256:
            raise MultiActionMissionV2Error("trajectory differs from dense route")
        self.dense_route.assert_matches_trajectory(self.trajectory)
        if (
            self.dense_route.mission_id != self.mission_id
            or self.dense_route.source_plan_sha256 != self.plan.plan_hash
            or self.dense_route.semantic_schedule_sha256
            != self.semantic_schedule.canonical_sha256
        ):
            raise MultiActionMissionV2Error("dense route source identity differs")
        if type(self.camera_observations) is not B0477MissionObservationSet:
            raise TypeError("camera_observations must be B0477MissionObservationSet")
        self.camera_observations.assert_matches_schedules(
            self.semantic_schedule,
            self.dense_route,
        )
        if (
            self.camera_observations.source_plan_sha256 != self.plan.plan_hash
            or self.camera_observations.dense_route_schedule_sha256
            != self.dense_route.canonical_sha256
        ):
            raise MultiActionMissionV2Error("camera observations differ from mission")
        if self.camera_fault_injection is not None:
            if type(self.camera_fault_injection) is not B0477ReplayFaultInjection:
                raise TypeError(
                    "camera_fault_injection must be B0477ReplayFaultInjection or None"
                )
            self.camera_fault_injection.validate()
            if (
                self.camera_fault_injection.contact_occurrence_ordinal
                >= self.camera_observations.observation_count
            ):
                raise MultiActionMissionV2Error(
                    "camera fault injection is outside the mission contact range"
                )
        if type(self.collision_fixture) is not IsolatedStaticMissionFixture:
            raise TypeError("collision_fixture must be IsolatedStaticMissionFixture")
        self.collision_fixture.assert_current_sources(
            self.bootstrap.context.workspace,
            self.trajectory,
        )
        self.collision_fixture.assert_matches_trajectory(
            self.trajectory,
            recompute_collision=recompute_collision,
        )
        if (
            self.collision_fixture.report.trajectory_report_sha256
            != self.trajectory.report_hash
            or not self.collision_fixture.report.passed_diagnostic
        ):
            raise MultiActionMissionV2Error("collision report differs from trajectory")
        if type(self.device_safety_context) is not DeviceSafetyContext:
            raise TypeError("device_safety_context must be DeviceSafetyContext")
        self.device_safety_context.__post_init__()
        if (
            self.device_safety_context.device is not self.plan.device
            or self.device_safety_context.profile_id != self.plan.profile_id
        ):
            raise MultiActionMissionV2Error("device safety context differs from plan")
        if type(self.occurrences) is not tuple:
            raise TypeError("occurrences must be an immutable tuple")
        occurrences = self.occurrences
        if len(occurrences) != self.semantic_schedule.contact_count or any(
            type(item) is not ActionOccurrence for item in occurrences
        ):
            raise MultiActionMissionV2Error("physical occurrence set is incomplete")
        if tuple(item.action_ordinal for item in occurrences) != tuple(
            range(len(occurrences))
        ):
            raise MultiActionMissionV2Error("physical occurrence ordinals are not dense")
        if any(
            item.mission_id != self.mission_id or item.plan_sha256 != self.plan.plan_hash
            for item in occurrences
        ):
            raise MultiActionMissionV2Error("physical occurrence source differs")
        if type(self.command_bindings) is not tuple:
            raise TypeError("command_bindings must be an immutable tuple")
        commands = self.command_bindings
        if len(commands) != self.dense_route.command_count or any(
            type(item) is not MissionV2CommandBinding for item in commands
        ):
            raise MultiActionMissionV2Error("integrated command coverage is incomplete")
        for item in commands:
            item.validate()
        if tuple(item.dense for item in commands) != self.dense_route.commands:
            raise MultiActionMissionV2Error("integrated dense command order differs")
        if tuple(item.collision for item in commands) != self.collision_fixture.report.command_bindings:
            raise MultiActionMissionV2Error("integrated collision command order differs")
        observation_by_contact = {
            item.contact_occurrence_ordinal: item
            for item in self.camera_observations.observations
        }
        occurrence_by_contact = {
            item.action_ordinal: item for item in occurrences
        }
        for item in commands:
            contact = item.dense.contact_occurrence_ordinal
            if (
                item.camera_observation_sha256
                != observation_by_contact[contact].observation_sha256
                or item.action_occurrence_sha256
                != occurrence_by_contact[contact].occurrence_hash
            ):
                raise MultiActionMissionV2Error(
                    "command has wrong camera or physical occurrence binding"
                )
        if type(self.authorization) is not SyntheticAuthorizationBundle:
            raise TypeError("authorization must be SyntheticAuthorizationBundle")
        self.authorization.validate()
        if (
            self.authorization.plan_sha256 != self.plan.plan_hash
            or self.authorization.collision_report_sha256
            != self.collision_fixture.report.report_hash
            or self.authorization.device_safety_context_sha256
            != self.device_safety_context.context_sha256
            or self.authorization.build_snapshot_sha256
            != self.bootstrap.bootstrap_hash
            or self.authorization.emulator.configuration_sha256
            != self.dense_route.runtime_config.canonical_sha256
            or self.authorization.emulator.session_id
            != self.dense_route.controller_session_id
            or self.authorization.ordered_physical_occurrence_ids
            != tuple(item.occurrence_hash for item in occurrences)
            or self.authorization.ordered_commands
            != tuple(item.simulation_command for item in commands)
        ):
            raise MultiActionMissionV2Error("synthetic authorization differs from assembly")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "mission_id": self.mission_id,
            "bootstrap_sha256": self.bootstrap.bootstrap_hash,
            "source_action_plan_sha256": self.plan.plan_hash,
            "requested_text": {
                "sha256": self.plan.requested_text_sha256,
                "normalized_codepoint_length": len(self.normalized_text),
                "raw_plaintext_field_serialized": False,
                "semantic_target_metadata_may_reconstruct_text": True,
            },
            "semantic_schedule_sha256": self.semantic_schedule.canonical_sha256,
            "semantic_step_count": len(self.semantic_schedule.steps),
            "observation_only_step_count": self.semantic_schedule.observation_count,
            "contact_count": self.contact_count,
            "trajectory_report_sha256": self.trajectory.report_hash,
            "route_waypoint_count": self.dense_route.route_waypoint_count,
            "dense_route_schedule_sha256": self.dense_route.canonical_sha256,
            "camera_observation_set_sha256": self.camera_observations.canonical_sha256,
            "camera_observation_count": self.camera_observations.observation_count,
            "camera_replay_fault_injection": (
                None
                if self.camera_fault_injection is None
                else self.camera_fault_injection.to_dict()
            ),
            "collision_fixture_sha256": self.collision_fixture.fixture_sha256,
            "collision_report_sha256": self.collision_fixture.report.report_hash,
            "physical_clearance_established": False,
            "device_safety_context": self.device_safety_context.to_dict(),
            "device_safety_context_sha256": self.device_safety_context.context_sha256,
            "physical_occurrences": [item.to_dict() for item in self.occurrences],
            "command_bindings": [item.to_dict() for item in self.command_bindings],
            "authorization_bundle_sha256": self.authorization.bundle_sha256,
            "authorization_context_sha256": self.authorization.evidence.context_sha256,
            "physical_blockers": [
                "RECEIVED_ARM_AND_CONTROLLER_NOT_PRESENT_OR_QUALIFIED",
                "B0477_CAMERA_IDENTITY_MODE_FOCUS_EXPOSURE_NOT_MEASURED",
                "STATIC_CAMERA_INTRINSICS_EXTRINSIC_AND_TAG_MAP_NOMINAL_ONLY",
                "FULL_LINK_TOOL_GANTRY_LIGHT_CABLE_GEOMETRY_NOT_MEASURED",
                "R_CTRL_TO_ROBOT_AND_BOARD_FRAME_CORRELATION_UNCOMMISSIONED",
                "KEYBOARD_PHONE_SURFACES_AND_SAFE_TARGET_INSETS_UNMEASURED",
                "CONTACT_FORCE_COMPLIANCE_AND_INTERLOCKS_UNQUALIFIED",
            ],
        }

    def validate(self) -> None:
        self._validate_unsealed(recompute_collision=False)
        if _hash(self._document()) != self._sealed_sha256:
            raise MultiActionMissionV2Error("mission V2 assembly changed after construction")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {**self._document(), "assembly_sha256": self._sealed_sha256}


def assemble_zero_hardware_mission_v2(
    *,
    mission_id: str,
    bootstrap: VirtualWorkcellBootstrap,
    plan: ActionPlan,
    normalized_text: str,
    semantic_schedule: SemanticStepSchedule,
    trajectory: TrajectorySimulationReport,
    dense_route: DenseRouteSchedule,
    camera_observations: B0477MissionObservationSet,
    collision_fixture: IsolatedStaticMissionFixture,
    virtual_device: VirtualKeyboard | VirtualAndroid,
    camera_fault_injection: B0477ReplayFaultInjection | None = None,
) -> MultiActionMissionSpecV2:
    """Join already-produced component evidence into one executable assembly."""

    mission = _identifier(mission_id, "mission_id")
    if any(
        type(step) is ContactSemanticStep and step.resulting_state is not None
        for step in semantic_schedule.steps
    ):
        raise MultiActionMissionV2Error(
            "UI-changing contacts require segmented authorization and are not yet supported"
        )
    safety_context = DeviceSafetyContext.from_device(
        virtual_device,
        source_device=plan.device,
        profile_id=plan.profile_id,
    )
    contacts = tuple(
        step
        for step in semantic_schedule.steps
        if type(step) is ContactSemanticStep
    )
    occurrences = tuple(
        ActionOccurrence.from_action_document(
            mission_id=mission,
            plan_sha256=plan.plan_hash,
            action_ordinal=step.contact_occurrence_ordinal,
            action=step.to_dict(),
        )
        for step in contacts
    )
    observation_by_contact = {
        item.contact_occurrence_ordinal: item
        for item in camera_observations.observations
    }
    collision_bindings = collision_fixture.report.command_bindings
    if len(collision_bindings) != len(dense_route.commands):
        raise MultiActionMissionV2Error("collision and dense route command counts differ")
    command_bindings: list[MissionV2CommandBinding] = []
    for dense, collision in zip(dense_route.commands, collision_bindings):
        contact = dense.contact_occurrence_ordinal
        observation_hash = observation_by_contact[contact].observation_sha256
        occurrence_hash = occurrences[contact].occurrence_hash
        simulation_command = SimulationTrajectoryCommand(
            command_occurrence_id=_command_occurrence_hash(
                dense,
                collision,
                action_occurrence_sha256=occurrence_hash,
            ),
            action_occurrence_id=occurrence_hash,
            primitive=dense.primitive,
            target_state_sha256=dense.command_sha256,
            constraint_set_sha256=_command_constraint_hash(
                dense,
                collision,
                camera_observation_sha256=observation_hash,
            ),
        )
        command_bindings.append(
            MissionV2CommandBinding(
                dense=dense,
                collision=collision,
                camera_observation_sha256=observation_hash,
                action_occurrence_sha256=occurrence_hash,
                simulation_command=simulation_command,
            )
        )
    capability = (
        SimulatedContactCapability.KEYBOARD
        if plan.device is Device.KEYBOARD
        else SimulatedContactCapability.PHONE
    )
    synthetic_closure = build_static_phase1_synthetic_closure(
        static_phase1_context_hashes(bootstrap.context)
    )
    calibration = project_static_phase1_synthetic_closure(
        synthetic_closure,
        capability=capability,
    )
    emulator = SyntheticEmulatorIdentity(
        emulator_id="rocell-in-memory-non-wire-t104-runtime-v1",
        configuration_sha256=dense_route.runtime_config.canonical_sha256,
        session_id=dense_route.controller_session_id,
    )
    authorization = build_synthetic_authorization_evidence(
        calibration=calibration,
        ordered_physical_occurrence_ids=tuple(
            item.occurrence_hash for item in occurrences
        ),
        ordered_commands=tuple(
            item.simulation_command for item in command_bindings
        ),
        collision_report_sha256=collision_fixture.report.report_hash,
        device_safety_context_sha256=safety_context.context_sha256,
        build_snapshot_sha256=bootstrap.bootstrap_hash,
        plan_sha256=plan.plan_hash,
        emulator=emulator,
    )
    return MultiActionMissionSpecV2(
        mission_id=mission,
        bootstrap=bootstrap,
        plan=plan,
        normalized_text=normalized_text,
        semantic_schedule=semantic_schedule,
        trajectory=trajectory,
        dense_route=dense_route,
        camera_observations=camera_observations,
        collision_fixture=collision_fixture,
        device_safety_context=safety_context,
        occurrences=occurrences,
        command_bindings=tuple(command_bindings),
        authorization=authorization,
        camera_fault_injection=camera_fault_injection,
    )


__all__ = [
    "DEVICE_SAFETY_CONTEXT_SCHEMA",
    "ZERO_HARDWARE_COMMAND_BINDING_SCHEMA",
    "ZERO_HARDWARE_MISSION_V2_SCHEMA",
    "DeviceSafetyContext",
    "MissionV2CommandBinding",
    "MultiActionMissionSpecV2",
    "MultiActionMissionV2Error",
    "assemble_zero_hardware_mission_v2",
]
