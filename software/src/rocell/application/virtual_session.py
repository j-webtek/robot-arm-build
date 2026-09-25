"""End-to-end, deterministic virtual commissioning for typing missions.

This service joins the semantic compiler, locked workcell startup, canonical
trajectory diagnostic, virtual calibration surrogates, joint-level arm plant,
synthetic vision checks, and virtual keyboard/Android outcomes.  It consumes
accepted joint waypoints only.  It cannot create a physical permit, translate
to the controller's uncorrelated Cartesian frame, open a serial/camera device,
or emit a Waveshare command.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

from rocell.models.actions import (
    ActionPlan,
    Device,
    PressKey,
    TapPhoneTarget,
    VerifyPhoneState,
)
from rocell.motion import MotionPhase
from rocell.simulation.virtual_workcell import (
    ContactEvent,
    ContactRegion,
    VirtualAndroid,
    VirtualArmLifecycle,
    VirtualArmPlant,
    VirtualClock,
    VirtualEventLedger,
    VirtualExecutionEvent,
    VirtualExecutionToken,
    VirtualFaultKind,
    VirtualFaultScript,
    VirtualFaultTrigger,
    VirtualJointWaypoint,
    VirtualKeyboard,
    VirtualLifecycleError,
    VirtualResourceLimitError,
    VirtualValidationError,
    issue_virtual_execution_token,
)
from rocell.simulation.virtual_outcome import VirtualTextOutcomeObserver
from rocell.typing.development_profiles import (
    compile_development_text,
    development_keyboard_profile,
    development_phone_profile,
)
from rocell.typing.unicode_support import normalize_line_endings

from .bootstrap import (
    VirtualWorkcellBootstrap,
    bootstrap_virtual_workcell,
    revalidate_virtual_workcell,
)
from .reach_optimizer import ReachStudyInput
from .trajectory_simulation import (
    JointTrajectoryWaypointResult,
    TrajectorySimulationPolicy,
    TrajectorySimulationReport,
    run_trajectory_simulation,
)
from .virtual_calibrations import (
    VirtualCalibrationClosure,
    resolve_virtual_calibrations,
)
from .virtual_pixel_vision import (
    VirtualPixelCaptureMode,
    VirtualPixelVisionAttemptLedger,
    VirtualPixelVisionService,
)


MAX_VIRTUAL_SESSION_TARGETS = 8
MAX_VIRTUAL_SESSION_EVENTS = 320

# These are deliberately simulation policies, not measurements of the real
# keyboard or phone.  The nominal path commands 1 mm of overtravel; this band
# admits bounded IK residual while still rejecting a hover or deep strike.
VIRTUAL_CONTACT_DEPTH_TOLERANCE_MM = 0.5
VIRTUAL_CONTACT_MAXIMUM_NORMAL_ANGLE_DEG = 5.0
VIRTUAL_CONTACT_DWELL_TICKS = 1


class VirtualSessionError(ValueError):
    """A virtual session input or planner/executor correlation is invalid."""


class VirtualSessionLifecycle(str, Enum):
    CREATED = "CREATED"
    SOURCES_REVALIDATED = "SOURCES_REVALIDATED"
    PLAN_VALIDATED = "PLAN_VALIDATED"
    VIRTUAL_CALIBRATIONS_RESOLVED = "VIRTUAL_CALIBRATIONS_RESOLVED"
    TRAJECTORY_ACCEPTED = "TRAJECTORY_ACCEPTED"
    VIRTUAL_ADAPTERS_INITIALIZED = "VIRTUAL_ADAPTERS_INITIALIZED"
    EXECUTING = "EXECUTING"
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    RETURNED_TO_PARK = "RETURNED_TO_PARK"
    CLOSED_COMPLETE = "CLOSED_COMPLETE"
    FAULTED = "FAULTED"
    CLOSED = "CLOSED"


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


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VirtualSessionScenarioBinding:
    """Hash/park subset consumed from a locked virtual scenario profile."""

    scenario_id: str
    scenario_hash: str
    park_point_board_mm: tuple[float, float, float]
    evidence_classification: str = "UNMEASURED_SENSITIVITY_OVERLAY"

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise VirtualSessionError("scenario_id must be non-empty")
        if (
            not isinstance(self.scenario_hash, str)
            or len(self.scenario_hash) != 64
            or any(character not in "0123456789abcdef" for character in self.scenario_hash)
        ):
            raise VirtualSessionError("scenario_hash must be lowercase SHA-256")
        point = tuple(float(value) for value in self.park_point_board_mm)
        if len(point) != 3 or any(not (-1e9 < value < 1e9) for value in point):
            raise VirtualSessionError("park point must contain three finite coordinates")
        object.__setattr__(self, "park_point_board_mm", point)
        if self.evidence_classification != "UNMEASURED_SENSITIVITY_OVERLAY":
            raise VirtualSessionError(
                "virtual session scenario must remain an unmeasured sensitivity overlay"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_hash": self.scenario_hash,
            "evidence_classification": self.evidence_classification,
            "park_point_board_mm": list(self.park_point_board_mm),
            "simulation_only": True,
            "physical_release_effect": "NONE",
        }


@dataclass(frozen=True, slots=True)
class VirtualSessionReport:
    """Immutable result for one no-I/O mission execution."""

    bootstrap_hash: str
    plan: ActionPlan
    requested_text_length: int
    scenario: VirtualSessionScenarioBinding
    study_input: ReachStudyInput
    calibrations: VirtualCalibrationClosure
    trajectory: TrajectorySimulationReport
    token: VirtualExecutionToken
    ledger: VirtualEventLedger
    arm_document: Mapping[str, Any]
    device_document: Mapping[str, Any]
    observer_document: Mapping[str, Any]
    vision_document: Mapping[str, Any]
    final_fault_script: VirtualFaultScript
    lifecycle_history: tuple[VirtualSessionLifecycle, ...]
    outcome_verified: bool
    ended_at_park: bool
    fault_reason: str | None

    @property
    def pipeline_completed(self) -> bool:
        return (
            self.pixel_vision_completed
            and self.outcome_verified
            and self.ended_at_park
            and self.lifecycle_history[-1] is VirtualSessionLifecycle.CLOSED_COMPLETE
        )

    @property
    def pixel_vision_completed(self) -> bool:
        expected_attempts = sum(
            isinstance(action, (PressKey, TapPhoneTarget))
            for action in self.plan.actions
        )
        return (
            self.vision_document.get("sealed") is True
            and self.vision_document.get("attempt_count") == expected_attempts
            and expected_attempts > 0
            and self.vision_document.get("all_attempts_passed") is True
        )

    @property
    def legacy_outcome_pipeline_completed(self) -> bool:
        """Retain the non-vision completion predicate for explicit reporting.

        This is not used as session success.  It distinguishes a later vision
        failure from device/outcome/park failures without silently treating the
        pre-pixel behavior as complete.
        """

        return (
            self.outcome_verified
            and self.ended_at_park
            and self.lifecycle_history[-1] is VirtualSessionLifecycle.CLOSED_COMPLETE
        )

    @property
    def status(self) -> str:
        if self.pipeline_completed:
            return "VIRTUAL_SESSION_COMPLETE_WITH_MODEL_AND_PHYSICAL_HOLDS"
        if self.fault_reason is not None:
            return "VIRTUAL_SESSION_FAULTED"
        return "VIRTUAL_SESSION_VERIFICATION_FAILED"

    def _without_hash(self) -> dict[str, Any]:
        device = dict(self.device_document)
        observer = dict(self.observer_document)
        vision = dict(self.vision_document)
        expected_hash = self.plan.requested_text_sha256
        observed_hash = observer.get("output_sha256")
        observed_length = observer.get("output_length")
        return {
            "schema": "rocell.virtual_session_report.v3",
            "status": self.status,
            "pipeline_completed": self.pipeline_completed,
            "pixel_vision_completed": self.pixel_vision_completed,
            "outcome_verified": self.outcome_verified,
            # The current model remains deliberately incomplete even when the
            # exercised software pipeline passes.
            "virtual_model_complete": False,
            "bootstrap_hash": self.bootstrap_hash,
            "scenario": self.scenario.to_dict(),
            "study_input": self.study_input.to_dict(),
            "action_plan": self.plan.to_dict(),
            "plan_hash": self.plan.plan_hash,
            "requested_text": {
                "sha256": expected_hash,
                "normalized_codepoint_length": self.requested_text_length,
                "plaintext_serialized": False,
            },
            "virtual_calibrations": {
                **self.calibrations.to_dict(),
                "closure_hash": self.calibrations.closure_hash,
            },
            "trajectory": {
                "report_hash": self.trajectory.report_hash,
                "status": self.trajectory.status,
                "route_target_count": len(self.trajectory.route_target_ids),
                "final_waypoint_count": (
                    0
                    if self.trajectory.final_round is None
                    else len(self.trajectory.final_round.waypoints)
                ),
                "total_ik_solves": self.trajectory.total_ik_solves,
                "all_final_waypoints_accepted": (
                    self.trajectory.final_round is not None
                    and self.trajectory.final_round.all_waypoints_accepted
                ),
            },
            "execution_token": self.token.to_dict(),
            "event_ledger": {
                **self.ledger.to_dict(),
                "ledger_hash": self.ledger.ledger_hash,
            },
            "arm_plant": dict(self.arm_document),
            "device_plant": device,
            "outcome_observer": observer,
            "pixel_vision": {
                "ledger_hash": vision.get("ledger_hash"),
                "service_definition_sha256": vision.get(
                    "service_definition_sha256"
                ),
                "sealed": vision.get("sealed"),
                "attempt_count": vision.get("attempt_count"),
                "passed_attempt_count": vision.get("passed_attempt_count"),
                "all_attempts_passed": vision.get("all_attempts_passed"),
                "fixed_overview_fixture": vision.get("fixed_overview_fixture"),
                "arm_mounted_camera_simulated": vision.get(
                    "arm_mounted_camera_simulated"
                ),
                "robot_frame_correction_applied": vision.get(
                    "robot_frame_correction_applied"
                ),
            },
            "outcome": {
                "expected_sha256": expected_hash,
                "expected_length": self.requested_text_length,
                "observed_sha256": observed_hash,
                "observed_length": observed_length,
                "matches": self.outcome_verified,
                "raw_output_serialized": False,
            },
            "fault_script": self.final_fault_script.to_dict(),
            "lifecycle_history": [state.value for state in self.lifecycle_history],
            "ended_at_park": self.ended_at_park,
            "fault_reason": self.fault_reason,
            "model_and_physical_holds": [
                "ROBOT_LINK_AND_SELF_COLLISION_NOT_DIAGNOSTIC_READY",
                "TOOL_CAMERA_HOLDER_AND_MOVING_CABLE_VOLUMES_INCOMPLETE",
                "EYE_ON_ARM_CAMERA_MOUNT_AND_EXTRINSIC_UNMEASURED",
                "CONTROLLER_R_CTRL_CORRELATION_UNCOMMISSIONED",
                "PHYSICAL_CALIBRATION_REGISTRY_INCOMPLETE",
                "DYNAMICS_PAYLOAD_FORCE_AND_CONTACT_GUARD_UNQUALIFIED",
                "SYNTHETIC_FIXED_OVERVIEW_PIXEL_PIPELINE_NOT_ARM_MOUNTED_OR_PHYSICAL",
                "PHYSICAL_KEYBOARD_AND_ANDROID_OUTCOME_OBSERVERS_UNIMPLEMENTED",
                "CONTACT_MODEL_PARAMETERS_ARE_SYNTHETIC_NOT_MEASURED",
            ],
            "authority": {
                "simulation_only": True,
                "execution_authorized": False,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "virtual_commands_executed": self.ledger.virtual_commands_executed,
                "physical_release_effect": "NONE",
                "can_release_physical_gates": False,
            },
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, Any]:
        return {**self._without_hash(), "report_hash": self.report_hash}


def build_virtual_device_model(
    bootstrap: VirtualWorkcellBootstrap,
    plan: ActionPlan,
    normalized_text: str,
) -> tuple[VirtualKeyboard | VirtualAndroid, int]:
    """Create a complete geometry-driven device model and validate the plan.

    The output map is the device definition: it covers every target in the
    locked nominal catalog.  It is never indexed by action during execution.
    The reconstruction below is only a compiler/canonical-plan consistency
    check and is intentionally discarded before the executor is constructed.
    """

    character_by_target: dict[str, str] = {}
    required_state_by_target: dict[str, str] = {}
    resulting_state_by_target: dict[str, str] = {}
    if plan.device is Device.KEYBOARD:
        keyboard_profile = development_keyboard_profile()
        if keyboard_profile.profile_id != plan.profile_id:
            raise VirtualSessionError("keyboard plan profile is not the development profile")
        for character, keys in keyboard_profile.character_keys.items():
            if len(keys) != 1:
                raise VirtualSessionError(
                    "virtual keyboard outcome model supports one contact per character"
            )
            semantic_target_id = keys[0]
            if semantic_target_id in character_by_target:
                raise VirtualSessionError(
                    f"ambiguous keyboard target {semantic_target_id!r}"
                )
            character_by_target[semantic_target_id] = character
        catalog = bootstrap.context.targets.keyboard_targets
        device_name = "keyboard"
    else:
        phone_profile = development_phone_profile()
        if phone_profile.profile_id != plan.profile_id:
            raise VirtualSessionError("phone plan profile is not the development profile")
        for character, spec in phone_profile.character_targets.items():
            if spec.target_id in character_by_target:
                raise VirtualSessionError(f"ambiguous phone target {spec.target_id!r}")
            character_by_target[spec.target_id] = character
            required_state_by_target[spec.target_id] = spec.required_state
            if spec.resulting_state is not None:
                resulting_state_by_target[spec.target_id] = spec.resulting_state
        catalog = bootstrap.context.targets.phone_targets
        device_name = "phone"

    if set(character_by_target) != set(catalog):
        missing_outputs = sorted(set(catalog) - set(character_by_target))
        missing_geometry = sorted(set(character_by_target) - set(catalog))
        raise VirtualSessionError(
            "semantic profile and nominal target catalog differ; "
            f"targets_without_output={missing_outputs}, "
            f"outputs_without_target={missing_geometry}"
        )

    reconstructed_parts: list[str] = []
    physical_action_count = 0
    for action in plan.actions:
        action_target: str | None = (
            action.key_id
            if isinstance(action, PressKey)
            else action.target_id
            if isinstance(action, TapPhoneTarget)
            else None
        )
        if action_target is not None:
            try:
                reconstructed_parts.append(character_by_target[action_target])
            except KeyError as exc:
                raise VirtualSessionError(
                    f"semantic target {action_target!r} has no device output mapping"
                ) from exc
            physical_action_count += 1
    reconstructed = "".join(reconstructed_parts)
    if reconstructed != normalized_text:
        raise VirtualSessionError(
            "action plan does not reconstruct the normalized requested text"
        )

    overtravel = bootstrap.context.scenario.path_policy.contact_overtravel_mm
    minimum_depth = max(0.0, overtravel - VIRTUAL_CONTACT_DEPTH_TOLERANCE_MM)
    maximum_depth = overtravel + VIRTUAL_CONTACT_DEPTH_TOLERANCE_MM
    regions: list[ContactRegion] = []
    output_map: dict[str, str] = {}
    transition_map: dict[str, str] = {}
    for target_id in sorted(catalog):
        catalog_target = catalog[target_id]
        left, front, right, rear = catalog_target.safe_rectangle_board_mm
        region_id = f"{device_name}:{target_id}"
        regions.append(
            ContactRegion(
                region_id=region_id,
                polygon_xy_mm=(
                    (left, front),
                    (right, front),
                    (right, rear),
                    (left, rear),
                ),
                surface_z_mm=catalog_target.center.z,
                minimum_contact_depth_mm=minimum_depth,
                maximum_contact_depth_mm=maximum_depth,
                required_contact_normal_board=(0.0, 0.0, -1.0),
                maximum_normal_angle_deg=(
                    VIRTUAL_CONTACT_MAXIMUM_NORMAL_ANGLE_DEG
                ),
                minimum_dwell_ticks=VIRTUAL_CONTACT_DWELL_TICKS,
                maximum_dwell_ticks=VIRTUAL_CONTACT_DWELL_TICKS,
                required_ui_state=required_state_by_target.get(target_id),
            )
        )
        output_map[region_id] = character_by_target[target_id]
        if target_id in resulting_state_by_target:
            transition_map[region_id] = resulting_state_by_target[target_id]

    if plan.device is Device.KEYBOARD:
        device: VirtualKeyboard | VirtualAndroid = VirtualKeyboard(
            regions=tuple(regions),
            output_map=output_map,
        )
    else:
        device = VirtualAndroid(
            initial_ui_state=development_phone_profile().initial_state,
            regions=tuple(regions),
            output_map=output_map,
            state_transition_map=transition_map,
        )
    return device, physical_action_count


def _validate_fault_script(script: VirtualFaultScript, device: Device) -> None:
    if not isinstance(script, VirtualFaultScript):
        raise TypeError("fault_script must be a VirtualFaultScript")
    # A session has no recovery/retry path.  One injected fault is enough to
    # exercise fail-stop behavior while keeping exact-once semantics testable.
    if len(script.triggers) > 1:
        raise VirtualSessionError("virtual session v1 permits at most one fault trigger")
    allowed: dict[VirtualFaultKind, tuple[tuple[str, str], ...]] = {
        VirtualFaultKind.ARM_CONNECT_FAILURE: (("arm", "connect"),),
        VirtualFaultKind.ARM_REFERENCE_FAILURE: (("arm", "reference"),),
        VirtualFaultKind.ARM_STALL: (("arm", "execute_waypoint"),),
        VirtualFaultKind.ARM_FEEDBACK_STALE: (("arm", "execute_waypoint"),),
        VirtualFaultKind.CAMERA_UNAVAILABLE: (("camera", "observe"),),
        VirtualFaultKind.CAMERA_TAG_LOSS: (("camera", "observe"),),
        VirtualFaultKind.KEYBOARD_MISSED_CONTACT: (("keyboard", "contact"),),
        VirtualFaultKind.KEYBOARD_DOUBLE_CONTACT: (("keyboard", "contact"),),
        VirtualFaultKind.ANDROID_MISSED_CONTACT: (("android", "contact"),),
        VirtualFaultKind.ANDROID_WRONG_UI_STATE: (
            ("android", "contact"),
            ("android", "verify_state"),
        ),
        VirtualFaultKind.DEVICE_FOCUS_LOST: (
            ("keyboard", "contact"),
            ("android", "contact"),
        ),
    }
    for trigger in script.triggers:
        if (trigger.component, trigger.operation) not in allowed[trigger.kind]:
            raise VirtualSessionError(
                f"fault {trigger.kind.value} cannot target "
                f"{trigger.component}/{trigger.operation}"
            )
        if device is Device.KEYBOARD and trigger.component == "android":
            raise VirtualSessionError("Android fault cannot target a keyboard session")
        if device is Device.PHONE and trigger.component == "keyboard":
            raise VirtualSessionError("keyboard fault cannot target a phone session")


def validate_virtual_session_trajectory(
    plan: ActionPlan,
    trajectory: TrajectorySimulationReport,
) -> None:
    final = trajectory.final_round
    if final is None or not final.all_waypoints_accepted:
        raise VirtualSessionError("canonical trajectory did not accept every final waypoint")
    if len(final.waypoints) != len(final.joint_results):
        raise VirtualSessionError("trajectory waypoint/result cardinality differs")
    if not final.waypoints:
        raise VirtualSessionError("trajectory contains no waypoints")
    if (
        final.waypoints[0].phase is not MotionPhase.PARK
        or final.waypoints[-1].phase is not MotionPhase.PARK
        or not final.waypoints[0].phase_endpoint
        or not final.waypoints[-1].phase_endpoint
    ):
        raise VirtualSessionError("trajectory must start and finish at park endpoints")
    physical_indices = {
        index
        for index, action in enumerate(plan.actions)
        if isinstance(action, (PressKey, TapPhoneTarget))
    }
    contacts: dict[int, int] = {}
    for waypoint, result in zip(final.waypoints, final.joint_results):
        if (
            waypoint.sequence != result.waypoint_sequence
            or waypoint.phase is not result.phase
            or waypoint.action_index != result.action_index
            or waypoint.semantic_target != result.semantic_target
        ):
            raise VirtualSessionError("trajectory waypoint/result correlation changed")
        if waypoint.action_index is not None and waypoint.action_index not in physical_indices:
            raise VirtualSessionError("motion waypoint references a non-physical action")
        if waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint:
            if waypoint.action_index is None:
                raise VirtualSessionError("contact endpoint lacks an action index")
            contacts[waypoint.action_index] = contacts.get(waypoint.action_index, 0) + 1
    if contacts != {index: 1 for index in physical_indices}:
        raise VirtualSessionError(
            "each physical action must have exactly one contact phase endpoint"
        )


class _SessionExecutor:
    """Mutable, single-use implementation hidden behind an immutable report."""

    def __init__(
        self,
        *,
        bootstrap: VirtualWorkcellBootstrap,
        plan: ActionPlan,
        text_length: int,
        device: VirtualKeyboard | VirtualAndroid,
        scenario: VirtualSessionScenarioBinding,
        study_input: ReachStudyInput,
        calibrations: VirtualCalibrationClosure,
        trajectory: TrajectorySimulationReport,
        fault_script: VirtualFaultScript,
    ) -> None:
        self.bootstrap = bootstrap
        self.plan = plan
        self.text_length = text_length
        self.scenario = scenario
        self.study_input = study_input
        self.calibrations = calibrations
        self.trajectory = trajectory
        self.script = fault_script
        self.clock = VirtualClock()
        self.token = issue_virtual_execution_token(
            context_hash=bootstrap.bootstrap_hash,
            plan_hash=plan.plan_hash,
            trajectory_hash=trajectory.report_hash,
            scenario_hash=scenario.scenario_hash,
            fault_script_hash=fault_script.definition_hash,
        )
        self.ledger = VirtualEventLedger(
            token=self.token,
            maximum_events=MAX_VIRTUAL_SESSION_EVENTS,
        )
        ready = {
            name: position.value
            for name, position in bootstrap.context.scenario.ready_arm_joint_positions_rad.items()
        }
        self.arm = VirtualArmPlant(
            token=self.token,
            clock=self.clock,
            initial_joint_positions_rad=ready,
            joint_bounds_rad=bootstrap.context.scenario.controller_joint_intersection_rad,
        )
        self.device = device
        # This is a distinct sink that only sees device ContactResult records.
        # It never receives target IDs or expected characters from the plan.
        self.observer = VirtualTextOutcomeObserver(
            observer_id="virtual-independent-device-output-v1"
        )
        # Pixel processing is intentionally plan-blind.  Action/target identity
        # is associated only with the returned result in ``_observe``.
        self.vision_service = VirtualPixelVisionService(bootstrap.context)
        self.vision_ledger = VirtualPixelVisionAttemptLedger.create(
            self.vision_service.service_definition_sha256
        )
        self.history = [
            VirtualSessionLifecycle.CREATED,
            VirtualSessionLifecycle.SOURCES_REVALIDATED,
            VirtualSessionLifecycle.PLAN_VALIDATED,
            VirtualSessionLifecycle.VIRTUAL_CALIBRATIONS_RESOLVED,
            VirtualSessionLifecycle.TRAJECTORY_ACCEPTED,
            VirtualSessionLifecycle.VIRTUAL_ADAPTERS_INITIALIZED,
        ]
        self.occurrences: dict[tuple[str, str], int] = {}
        self.next_action_index = 0
        self.current_contact_action: int | None = None
        self.fault_reason: str | None = None

    def _match_fault(
        self,
        component: str,
        operation: str,
        *,
        action_index: int | None = None,
        target_id: str | None = None,
        waypoint_sequence: int | None = None,
    ) -> VirtualFaultTrigger | None:
        key = (component, operation)
        occurrence = self.occurrences.get(key, 0) + 1
        self.occurrences[key] = occurrence
        trigger, self.script = self.script.match_once(
            component=component,
            operation=operation,
            occurrence=occurrence,
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
        )
        return trigger

    def _event(
        self,
        component: str,
        operation: str,
        status: str,
        detail: str,
        *,
        before: str | None = None,
        after: str | None = None,
        action_index: int | None = None,
        target_id: str | None = None,
        waypoint_sequence: int | None = None,
        trigger: VirtualFaultTrigger | None = None,
        virtual_command: bool = False,
        advance_clock: bool = False,
    ) -> None:
        if advance_clock:
            self.clock.advance()
        self.ledger.append(
            VirtualExecutionEvent(
                sequence=self.ledger.next_sequence,
                tick=self.clock.tick,
                component=component,
                operation=operation,
                status=status,
                detail_code=detail,
                before_state_hash=before,
                after_state_hash=after,
                action_index=action_index,
                target_id=target_id,
                waypoint_sequence=waypoint_sequence,
                fault_trigger_id=None if trigger is None else trigger.trigger_id,
                virtual_command_executed=virtual_command,
            )
        )

    def _fault(self, reason: str, *, trigger: VirtualFaultTrigger | None = None) -> None:
        self.fault_reason = reason
        if self.arm.lifecycle not in (VirtualArmLifecycle.FAULT, VirtualArmLifecycle.CLOSED):
            before = self.arm.state_hash
            self.arm.fault(reason)
            self._event(
                "arm",
                "fault",
                "FAULT",
                reason,
                before=before,
                after=self.arm.state_hash,
                trigger=trigger,
            )
        self.history.append(VirtualSessionLifecycle.FAULTED)

    def _close_faulted(self) -> None:
        if self.arm.lifecycle is not VirtualArmLifecycle.CLOSED:
            before = self.arm.state_hash
            self.arm.close()
            self._event(
                "arm",
                "close",
                "INFO",
                "VIRTUAL_ARM_CLOSED_AFTER_FAULT",
                before=before,
                after=self.arm.state_hash,
            )
        self.history.append(VirtualSessionLifecycle.CLOSED)
        self.vision_ledger = self.vision_ledger.seal()
        self.ledger.seal()

    def _initialize_arm(self) -> bool:
        for operation, method, fault_kind in (
            ("connect", self.arm.connect, VirtualFaultKind.ARM_CONNECT_FAILURE),
            ("reference", self.arm.reference, VirtualFaultKind.ARM_REFERENCE_FAILURE),
        ):
            trigger = self._match_fault("arm", operation)
            if trigger is not None:
                if trigger.kind is not fault_kind:
                    raise VirtualSessionError("fault kind does not match arm lifecycle operation")
                self._fault(trigger.kind.value, trigger=trigger)
                self._close_faulted()
                return False
            before = self.arm.state_hash
            method()
            detail = (
                "VIRTUAL_ARM_CONNECTED"
                if operation == "connect"
                else "VIRTUAL_ARM_REFERENCED"
            )
            self._event(
                "arm",
                operation,
                "PASS",
                detail,
                before=before,
                after=self.arm.state_hash,
            )
        before = self.arm.state_hash
        self.arm.mark_ready()
        self._event(
            "arm",
            "mark_ready",
            "PASS",
            "VIRTUAL_ARM_READY",
            before=before,
            after=self.arm.state_hash,
        )
        return True

    def _process_phone_verifications(self) -> bool:
        while self.next_action_index < len(self.plan.actions):
            action = self.plan.actions[self.next_action_index]
            if not isinstance(action, VerifyPhoneState):
                return True
            if not isinstance(self.device, VirtualAndroid):
                raise VirtualSessionError("phone verification appeared in keyboard session")
            trigger = self._match_fault(
                "android",
                "verify_state",
                action_index=self.next_action_index,
                target_id=action.state_id,
            )
            before = self.device.state_hash
            if trigger is not None:
                if trigger.kind is not VirtualFaultKind.ANDROID_WRONG_UI_STATE:
                    raise VirtualSessionError("fault kind does not match Android verification")
                self.device.set_ui_state_for_simulation(
                    trigger.parameter or "FAULT_INJECTED_WRONG_UI_STATE"
                )
            passed = self.device.verify_ui_state(action.state_id)
            self._event(
                "android",
                "verify_state",
                "PASS" if passed else "FAULT",
                "ANDROID_UI_STATE_ACCEPTED" if passed else "ANDROID_UI_STATE_REJECTED",
                before=before,
                after=self.device.state_hash,
                action_index=self.next_action_index,
                target_id=action.state_id,
                trigger=trigger,
                advance_clock=True,
            )
            if not passed:
                self._fault("ANDROID_UI_STATE_REJECTED", trigger=trigger)
                self._close_faulted()
                return False
            self.next_action_index += 1
        return True

    def _observe(
        self,
        action_index: int,
        target_id: str,
        waypoint_sequence: int,
    ) -> bool:
        trigger = self._match_fault(
            "camera",
            "observe",
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
        )
        mode = VirtualPixelCaptureMode.NORMAL
        if trigger is not None:
            if trigger.kind is VirtualFaultKind.CAMERA_UNAVAILABLE:
                mode = VirtualPixelCaptureMode.CAMERA_UNAVAILABLE
            elif trigger.kind is VirtualFaultKind.CAMERA_TAG_LOSS:
                mode = VirtualPixelCaptureMode.TAG_LOSS
            else:
                raise VirtualSessionError(
                    "fault kind does not match camera observation"
                )
        before = self.vision_ledger.ledger_hash
        result = self.vision_service.process(
            sequence=waypoint_sequence,
            capture_mode=mode,
        )
        self.vision_ledger = self.vision_ledger.associate(
            result,
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
        )
        passed = trigger is None and result.passed
        detail = result.detail_code if trigger is None else trigger.kind.value
        self._event(
            "camera",
            "observe",
            "PASS" if passed else "FAULT",
            detail,
            before=before,
            after=self.vision_ledger.ledger_hash,
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
            trigger=trigger,
            advance_clock=True,
        )
        if not passed:
            reason = result.detail_code if trigger is None else trigger.kind.value
            self._fault(reason, trigger=trigger)
            self._close_faulted()
            return False
        return True

    def _contact(
        self,
        action_index: int,
        target_id: str,
        waypoint_sequence: int,
        result: JointTrajectoryWaypointResult,
    ) -> bool:
        if action_index != self.next_action_index:
            raise VirtualSessionError(
                f"contact action {action_index} is out of semantic order; "
                f"expected {self.next_action_index}"
            )
        action = self.plan.actions[action_index]
        component = "keyboard" if self.plan.device is Device.KEYBOARD else "android"
        trigger = self._match_fault(
            component,
            "contact",
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
        )
        count = 1
        if trigger is not None:
            if trigger.kind in (
                VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
                VirtualFaultKind.ANDROID_MISSED_CONTACT,
            ):
                count = 0
            elif trigger.kind is VirtualFaultKind.KEYBOARD_DOUBLE_CONTACT:
                count = 2
            elif trigger.kind is VirtualFaultKind.DEVICE_FOCUS_LOST:
                self.device.set_focus(False)
            elif trigger.kind is VirtualFaultKind.ANDROID_WRONG_UI_STATE:
                if not isinstance(self.device, VirtualAndroid):
                    raise VirtualSessionError("Android state fault used for keyboard")
                self.device.set_ui_state_for_simulation(
                    trigger.parameter or "FAULT_INJECTED_WRONG_UI_STATE"
                )
            else:
                raise VirtualSessionError("fault kind does not match device contact")
        before = self.device.state_hash
        try:
            if not (
                isinstance(action, PressKey)
                and isinstance(self.device, VirtualKeyboard)
                or isinstance(action, TapPhoneTarget)
                and isinstance(self.device, VirtualAndroid)
            ):
                raise VirtualSessionError("device/action type mismatch")
            contact_result = self.device.apply_contact(
                ContactEvent(
                    action_index=action_index,
                    achieved_board_xyz_mm=result.achieved_tip_position_board_mm,
                    # The solver reports the hand TCP +Z axis.  A downward
                    # contact travels along its opposite direction.
                    achieved_contact_normal_board=(
                        -result.achieved_hand_tcp_z_axis_board[0],
                        -result.achieved_hand_tcp_z_axis_board[1],
                        -result.achieved_hand_tcp_z_axis_board[2],
                    ),
                    dwell_ticks=VIRTUAL_CONTACT_DWELL_TICKS,
                    activation_count=count,
                )
            )
            self.observer.consume(contact_result)
        except (
            VirtualLifecycleError,
            VirtualResourceLimitError,
            VirtualValidationError,
        ) as exc:
            self._event(
                component,
                "contact",
                "FAULT",
                "DEVICE_CONTACT_REJECTED",
                before=before,
                after=self.device.state_hash,
                action_index=action_index,
                target_id=target_id,
                waypoint_sequence=waypoint_sequence,
                trigger=trigger,
                advance_clock=True,
            )
            self._fault(f"DEVICE_CONTACT_REJECTED:{type(exc).__name__}", trigger=trigger)
            self._close_faulted()
            return False
        expected_region_id = (
            f"keyboard:{action.key_id}"
            if isinstance(action, PressKey)
            else f"phone:{action.target_id}"
        )
        resolved_expected_region = contact_result.resolved_target_id == expected_region_id
        accepted = trigger is None and contact_result.accepted and resolved_expected_region
        if trigger is not None:
            detail = trigger.kind.value
        elif not contact_result.accepted:
            detail = f"DEVICE_CONTACT_{contact_result.disposition.value}"
        elif not resolved_expected_region:
            detail = "DEVICE_CONTACT_TARGET_MISMATCH"
        else:
            detail = "DEVICE_CONTACT_ACCEPTED"
        self._event(
            component,
            "contact",
            "PASS" if accepted else "FAULT",
            detail,
            before=before,
            after=self.device.state_hash,
            action_index=action_index,
            target_id=target_id,
            waypoint_sequence=waypoint_sequence,
            trigger=trigger,
            advance_clock=True,
        )
        if not accepted:
            reason = trigger.kind.value if trigger is not None else detail
            self._fault(reason, trigger=trigger)
            self._close_faulted()
            return False
        self.current_contact_action = action_index
        return True

    def execute(self) -> VirtualSessionReport:
        if not self._initialize_arm():
            return self._report(False, False)
        if self.plan.device is Device.PHONE and not self._process_phone_verifications():
            return self._report(False, False)
        self.history.append(VirtualSessionLifecycle.EXECUTING)
        final = self.trajectory.final_round
        assert final is not None
        for waypoint, result in zip(final.waypoints, final.joint_results):
            action_index = waypoint.action_index
            target_id = waypoint.semantic_target
            trigger = self._match_fault(
                "arm",
                "execute_waypoint",
                action_index=action_index,
                target_id=target_id,
                waypoint_sequence=waypoint.sequence,
            )
            if trigger is not None:
                if trigger.kind not in (
                    VirtualFaultKind.ARM_STALL,
                    VirtualFaultKind.ARM_FEEDBACK_STALE,
                ):
                    raise VirtualSessionError("fault kind does not match arm waypoint")
                self._event(
                    "arm",
                    "execute_waypoint",
                    "FAULT",
                    trigger.kind.value,
                    before=self.arm.state_hash,
                    after=self.arm.state_hash,
                    action_index=action_index,
                    target_id=target_id,
                    waypoint_sequence=waypoint.sequence,
                    trigger=trigger,
                    advance_clock=True,
                )
                self._fault(trigger.kind.value, trigger=trigger)
                self._close_faulted()
                return self._report(False, False)
            command = VirtualJointWaypoint(
                sequence=waypoint.sequence,
                joint_positions_rad=result.solution_arm_joint_positions_rad,
                action_index=waypoint.action_index,
            )
            before = self.arm.state_hash
            self.arm.execute_waypoint(command)
            self._event(
                "arm",
                "execute_waypoint",
                "PASS",
                "VIRTUAL_JOINT_WAYPOINT_ACCEPTED",
                before=before,
                after=self.arm.state_hash,
                action_index=action_index,
                target_id=target_id,
                waypoint_sequence=waypoint.sequence,
                virtual_command=True,
            )
            if (
                waypoint.phase is MotionPhase.HOVER
                and waypoint.phase_endpoint
                and action_index is not None
                and target_id is not None
                and not self._observe(action_index, target_id, waypoint.sequence)
            ):
                return self._report(False, False)
            if (
                waypoint.phase is MotionPhase.CONTACT
                and waypoint.phase_endpoint
                and action_index is not None
                and target_id is not None
                and not self._contact(
                    action_index,
                    target_id,
                    waypoint.sequence,
                    result,
                )
            ):
                return self._report(False, False)
            if (
                waypoint.phase is MotionPhase.RETRACT
                and waypoint.phase_endpoint
                and action_index is not None
                and self.current_contact_action == action_index
            ):
                self.next_action_index = action_index + 1
                self.current_contact_action = None
                if self.plan.device is Device.PHONE and not self._process_phone_verifications():
                    return self._report(False, False)

        if self.next_action_index != len(self.plan.actions):
            raise VirtualSessionError("not every semantic action was consumed")
        if self.script.unconsumed_trigger_ids:
            raise VirtualSessionError(
                "fault trigger did not match exactly once: "
                + ", ".join(self.script.unconsumed_trigger_ids)
            )
        self.arm.complete()
        outcome = self.observer.output_matches(
            self.plan.requested_text_sha256,
            self.text_length,
        )
        self._event(
            "outcome_observer",
            "verify_text",
            "PASS" if outcome else "FAULT",
            "OUTPUT_HASH_AND_LENGTH_MATCH" if outcome else "OUTPUT_MISMATCH",
            before=self.observer.state_hash,
            after=self.observer.state_hash,
            advance_clock=True,
        )
        if not outcome:
            self._fault("OUTPUT_MISMATCH")
            self._close_faulted()
            return self._report(False, False)
        self.history.append(VirtualSessionLifecycle.OUTCOME_VERIFIED)
        ended_at_park = (
            final.waypoints[-1].phase is MotionPhase.PARK
            and self.arm.last_waypoint_sequence == final.waypoints[-1].sequence
        )
        if not ended_at_park:
            self._fault("FINAL_PARK_NOT_CONFIRMED")
            self._close_faulted()
            return self._report(True, False)
        self.history.append(VirtualSessionLifecycle.RETURNED_TO_PARK)
        before = self.arm.state_hash
        self.arm.close()
        self._event(
            "arm",
            "close",
            "PASS",
            "VIRTUAL_ARM_CLOSED_COMPLETE",
            before=before,
            after=self.arm.state_hash,
        )
        self.history.append(VirtualSessionLifecycle.CLOSED_COMPLETE)
        self.vision_ledger = self.vision_ledger.seal()
        self.ledger.seal()
        return self._report(True, True)

    def _report(self, outcome: bool, ended_at_park: bool) -> VirtualSessionReport:
        return VirtualSessionReport(
            bootstrap_hash=self.bootstrap.bootstrap_hash,
            plan=self.plan,
            requested_text_length=self.text_length,
            scenario=self.scenario,
            study_input=self.study_input,
            calibrations=self.calibrations,
            trajectory=self.trajectory,
            token=self.token,
            ledger=self.ledger,
            arm_document=self.arm.to_dict(),
            device_document=self.device.to_dict(),
            observer_document=self.observer.to_dict(),
            vision_document=self.vision_ledger.to_dict(),
            final_fault_script=self.script,
            lifecycle_history=tuple(self.history),
            outcome_verified=outcome,
            ended_at_park=ended_at_park,
            fault_reason=self.fault_reason,
        )


def run_virtual_session(
    bootstrap: VirtualWorkcellBootstrap,
    plan: ActionPlan,
    requested_text: str,
    study_input: ReachStudyInput,
    scenario: VirtualSessionScenarioBinding,
    *,
    fault_script: VirtualFaultScript | None = None,
    trajectory_policy: TrajectorySimulationPolicy | None = None,
) -> VirtualSessionReport:
    """Plan and execute one bounded virtual keyboard or Android mission."""

    if not isinstance(bootstrap, VirtualWorkcellBootstrap):
        raise TypeError("bootstrap must be a VirtualWorkcellBootstrap")
    if not isinstance(plan, ActionPlan):
        raise TypeError("plan must be an ActionPlan")
    if not isinstance(requested_text, str):
        raise TypeError("requested_text must be str")
    if not isinstance(study_input, ReachStudyInput):
        raise TypeError("study_input must be a ReachStudyInput")
    if not isinstance(scenario, VirtualSessionScenarioBinding):
        raise TypeError("scenario must be a VirtualSessionScenarioBinding")
    revalidate_virtual_workcell(bootstrap)
    normalized = normalize_line_endings(requested_text)
    if _text_sha256(normalized) != plan.requested_text_sha256:
        raise VirtualSessionError("requested text hash differs from the action plan")
    device_model, physical_action_count = build_virtual_device_model(
        bootstrap,
        plan,
        normalized,
    )
    if not physical_action_count:
        raise VirtualSessionError("virtual session requires at least one physical target")
    if physical_action_count > MAX_VIRTUAL_SESSION_TARGETS:
        raise VirtualSessionError(
            f"virtual session supports at most {MAX_VIRTUAL_SESSION_TARGETS} physical targets"
        )
    script = fault_script or VirtualFaultScript("none")
    _validate_fault_script(script, plan.device)
    park = scenario.park_point_board_mm
    policy = trajectory_policy or TrajectorySimulationPolicy(
        maximum_cartesian_step_mm=30.0,
        maximum_joint_step_rad=0.35,
        minimum_normalized_arm_joint_margin=0.01,
        maximum_refinement_rounds=2,
        maximum_waypoints_per_round=256,
        maximum_total_ik_solves=512,
        maximum_route_targets=MAX_VIRTUAL_SESSION_TARGETS,
        park_xy_board_mm=(park[0], park[1]),
    )
    if policy.park_xy_board_mm != (park[0], park[1]):
        raise VirtualSessionError("trajectory policy park differs from the locked scenario")
    trajectory = run_trajectory_simulation(
        bootstrap.context,
        plan,
        study_input,
        policy,
    )
    validate_virtual_session_trajectory(plan, trajectory)
    calibrations = resolve_virtual_calibrations(
        bootstrap.context,
        plan,
        study_input,
    )
    return _SessionExecutor(
        bootstrap=bootstrap,
        plan=plan,
        text_length=len(normalized),
        device=device_model,
        scenario=scenario,
        study_input=study_input,
        calibrations=calibrations,
        trajectory=trajectory,
        fault_script=script,
    ).execute()


def run_default_virtual_session(
    workspace: Path,
    device: str,
    requested_text: str,
    *,
    runtime_path: Path | None = None,
    fault_script: VirtualFaultScript | None = None,
) -> VirtualSessionReport:
    """Bootstrap and execute the one locked pre-hardware scenario.

    This is the primary hardware-free entry point.  Placement coordinates and
    tool lengths are intentionally not caller-controlled: they come from the
    hash-locked sensitivity profile and remain explicitly unmeasured.
    """

    # Import locally to keep the simulation profile's ReachStudyInput decoder
    # from participating in application-package initialization cycles.
    from rocell.simulation.virtual_profile import (
        VirtualProfileContext,
        load_virtual_commissioning_profile,
    )

    root = Path(workspace).resolve()
    bootstrap = bootstrap_virtual_workcell(root, runtime_path)
    profile = load_virtual_commissioning_profile(
        cast(VirtualProfileContext, bootstrap.context)
    )
    plan = compile_development_text(device, requested_text)
    park = profile.park_point_board
    scenario = VirtualSessionScenarioBinding(
        scenario_id=profile.profile_id,
        scenario_hash=profile.source_sha256,
        park_point_board_mm=(park.x, park.y, park.z),
    )
    return run_virtual_session(
        bootstrap,
        plan,
        requested_text,
        profile.study_input,
        scenario,
        fault_script=fault_script,
    )


__all__ = [
    "MAX_VIRTUAL_SESSION_EVENTS",
    "MAX_VIRTUAL_SESSION_TARGETS",
    "VirtualSessionError",
    "VirtualSessionLifecycle",
    "VirtualSessionReport",
    "VirtualSessionScenarioBinding",
    "build_virtual_device_model",
    "run_default_virtual_session",
    "run_virtual_session",
    "validate_virtual_session_trajectory",
]
