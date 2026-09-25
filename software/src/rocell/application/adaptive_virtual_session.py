"""End-to-end adaptive arm-camera rehearsal with no hardware authority.

This opt-in session is the integration bridge between the existing typing
compiler/virtual device models and the new joint-dependent arm-camera path.  It
executes a nominal joint prefix in :class:`VirtualArmPlant`, observes every
physical-action hover from achieved joints and real synthetic JPEG pixels,
classifies a board registration, atomically installs a fully accepted corrected
suffix when required, and adjudicates contact from fresh achieved FK against
the same opaque virtual board truth used by the renderer.

The legacy ``virtual_session`` report remains unchanged for replay stability.
This module has a separate schema because adaptive execution has independent
camera, execution, source-waypoint, and registration counters.

No code in this module imports a serial or camera driver, emits a Waveshare
command, creates a physical permit, or updates a calibration registry.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, cast

from rocell.geometry import Point3Mm, Vec3
from rocell.models.actions import (
    ActionPlan,
    Device,
    PressKey,
    TapPhoneTarget,
    VerifyPhoneState,
)
from rocell.motion import MotionPhase
from rocell.simulation.virtual_outcome import VirtualTextOutcomeObserver
from rocell.simulation.virtual_workcell import (
    ContactEvent,
    ContactResult,
    VirtualAndroid,
    VirtualArmFeedback,
    VirtualArmLifecycle,
    VirtualArmPlant,
    VirtualClock,
    VirtualExecutionToken,
    VirtualFaultScript,
    VirtualJointWaypoint,
    VirtualKeyboard,
    issue_virtual_execution_token,
)
from rocell.typing.development_profiles import compile_development_text
from rocell.typing.unicode_support import normalize_line_endings

from .actual_contact_geometry import (
    ActualToolTipContactGeometry,
    ActualToolTipContactProjector,
)
from .board_pose_correction import (
    ArmCameraBoardMeasurement,
    BoardPoseCorrectionDecision,
    BoardPoseCorrectionPolicy,
    BoardPoseCorrectionStatus,
    BoardRegistration,
    decide_board_pose_correction,
)
from .bootstrap import (
    VirtualWorkcellBootstrap,
    bootstrap_virtual_workcell,
    revalidate_virtual_workcell,
)
from .corrected_trajectory_suffix import (
    CorrectedTrajectorySuffix,
    CorrectedTrajectorySuffixError,
    replan_corrected_trajectory_suffix,
)
from .reach_optimizer import ReachStudyInput
from .runtime_ports import RuntimeInstant
from .trajectory_simulation import (
    JointTrajectoryWaypointResult,
    TrajectorySimulationPolicy,
    TrajectorySimulationReport,
    run_trajectory_simulation,
)
from .virtual_arm_camera import (
    VIRTUAL_ARM_CAMERA_CLOCK,
    ArmCameraCaptureBracket,
    ArmCameraVisionQualityPolicy,
    VirtualArmCameraCaptureMode,
    VirtualArmCameraVisionService,
    VirtualArmCameraVisionResult,
    achieved_joint_sample_from_virtual_feedback,
    correction_measurement_from_vision_result,
    initial_planner_board_registration,
    make_hidden_virtual_board_truth,
    make_unmeasured_synthetic_arm_camera_binding,
    make_virtual_arm_camera_service,
)
from .virtual_board_truth import HiddenVirtualBoardTruth
from .virtual_calibrations import (
    VirtualCalibrationClosure,
    resolve_virtual_calibrations,
)
from .virtual_session import (
    MAX_VIRTUAL_SESSION_TARGETS,
    VIRTUAL_CONTACT_DWELL_TICKS,
    VirtualSessionScenarioBinding,
    build_virtual_device_model,
    validate_virtual_session_trajectory,
)


ADAPTIVE_VIRTUAL_SESSION_SCHEMA = "rocell.adaptive_arm_camera_session.v1"
MAX_ADAPTIVE_EXECUTION_WAYPOINTS = 512
MAX_ADAPTIVE_CAMERA_CAPTURES = 32
MAX_ADAPTIVE_CAMERA_FAULTS = MAX_ADAPTIVE_CAMERA_CAPTURES
MAX_ADAPTIVE_CORRECTION_REVISIONS = 1
ADAPTIVE_CAMERA_TICK_PERIOD_NS = 1_000_000

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AdaptiveVirtualSessionError(ValueError):
    """An adaptive session contract or fail-closed runtime gate was violated."""


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


def _freeze_json(value: object, label: str) -> object:
    """Recursively detach and freeze one JSON-compatible evidence value."""

    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise AdaptiveVirtualSessionError(f"{label} keys must be text")
            frozen[key] = _freeze_json(child, f"{label}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(child, f"{label}[{index}]")
            for index, child in enumerate(value)
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise AdaptiveVirtualSessionError(
        f"{label} must contain only finite JSON-compatible values"
    )


def _thaw_json(value: object) -> object:
    """Return a detached mutable JSON tree for public serialization."""

    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


def _freeze_document(
    value: Mapping[str, object], label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    frozen = _freeze_json(value, label)
    assert isinstance(frozen, Mapping)
    # Exercise the canonical JSON boundary now, rather than when a report is
    # finally requested after execution has already completed.
    _stable_hash(_thaw_json(frozen))
    return cast(Mapping[str, object], frozen)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise AdaptiveVirtualSessionError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "execution_authorized": False,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
        "can_release_physical_gates": False,
    }


def _point_dict(point: Point3Mm) -> dict[str, object]:
    return {"frame": point.frame, "xyz_mm": [point.x, point.y, point.z]}


def _bounded_text(value: object, label: str, *, maximum: int = 128) -> str:
    """Validate short identifiers without silently normalizing evidence."""

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise AdaptiveVirtualSessionError(
            f"{label} must be bounded, printable, non-empty text"
        )
    return value


@dataclass(frozen=True, slots=True)
class AdaptiveCameraFault:
    """One deterministic non-normal capture selected by capture sequence.

    Capture sequences are one-based because they identify completed achieved-
    state brackets, not semantic actions or nominal trajectory waypoints.  The
    selector therefore remains plan-blind while still being replayable.
    """

    capture_sequence: int
    capture_mode: VirtualArmCameraCaptureMode

    def __post_init__(self) -> None:
        if (
            isinstance(self.capture_sequence, bool)
            or not isinstance(self.capture_sequence, int)
            or not 1 <= self.capture_sequence <= MAX_ADAPTIVE_CAMERA_CAPTURES
        ):
            raise AdaptiveVirtualSessionError(
                "camera fault capture_sequence is outside the bounded session"
            )
        if not isinstance(self.capture_mode, VirtualArmCameraCaptureMode):
            raise TypeError("camera fault capture_mode is invalid")
        if self.capture_mode is VirtualArmCameraCaptureMode.NORMAL:
            raise AdaptiveVirtualSessionError(
                "camera fault capture_mode must be non-normal"
            )

    @property
    def fault_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "capture_sequence": self.capture_sequence,
            "capture_mode": self.capture_mode.value,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveCameraFaultSchedule:
    """Bounded immutable moving-camera fault definition.

    At most one fault may select a capture.  Faults must be declared in capture
    order so the definition has one canonical representation and deterministic
    consumption evidence.
    """

    schedule_id: str = "adaptive-camera-none"
    faults: tuple[AdaptiveCameraFault, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schedule_id",
            _bounded_text(self.schedule_id, "camera fault schedule_id"),
        )
        if not isinstance(self.faults, tuple):
            raise AdaptiveVirtualSessionError(
                "camera fault schedule faults must be an immutable tuple"
            )
        if len(self.faults) > MAX_ADAPTIVE_CAMERA_FAULTS:
            raise AdaptiveVirtualSessionError(
                f"camera fault schedule exceeds {MAX_ADAPTIVE_CAMERA_FAULTS} faults"
            )
        if any(not isinstance(item, AdaptiveCameraFault) for item in self.faults):
            raise TypeError("camera fault schedule contains an invalid fault")
        sequences = tuple(item.capture_sequence for item in self.faults)
        if sequences != tuple(sorted(sequences)):
            raise AdaptiveVirtualSessionError(
                "camera faults must be ordered by capture_sequence"
            )
        if len(sequences) != len(set(sequences)):
            raise AdaptiveVirtualSessionError(
                "camera fault capture_sequence selectors must be unique"
            )
        if not self.faults and self.schedule_id != "adaptive-camera-none":
            raise AdaptiveVirtualSessionError(
                "an empty camera fault schedule must use the canonical none ID"
            )
        if self.faults and self.schedule_id == "adaptive-camera-none":
            raise AdaptiveVirtualSessionError(
                "a non-empty camera fault schedule requires an explicit ID"
            )

    @property
    def definition_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def fault_for_capture(self, capture_sequence: int) -> AdaptiveCameraFault | None:
        if (
            isinstance(capture_sequence, bool)
            or not isinstance(capture_sequence, int)
            or not 1 <= capture_sequence <= MAX_ADAPTIVE_CAMERA_CAPTURES
        ):
            raise AdaptiveVirtualSessionError("capture_sequence is invalid")
        for fault in self.faults:
            if fault.capture_sequence == capture_sequence:
                return fault
            if fault.capture_sequence > capture_sequence:
                break
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.adaptive_camera_fault_schedule.v1",
            "schedule_id": self.schedule_id,
            "faults": [item.to_dict() for item in self.faults],
            "fault_count": len(self.faults),
            "selector_basis": "ONE_BASED_CAPTURE_SEQUENCE_ONLY",
            "semantic_plan_inputs_consumed": False,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveVirtualSessionPolicy:
    """Bounded orchestration policy for the synthetic adaptive runner."""

    correction_policy: BoardPoseCorrectionPolicy = field(
        default_factory=lambda: BoardPoseCorrectionPolicy(
            # The wide-FOV synthetic detector varies by a few tenths of a
            # millimetre across arm viewpoints.  This is a simulation
            # convergence deadband, not a released physical tolerance.
            translation_deadband_mm=0.75,
        )
    )
    maximum_execution_waypoints: int = MAX_ADAPTIVE_EXECUTION_WAYPOINTS
    maximum_camera_captures: int = MAX_ADAPTIVE_CAMERA_CAPTURES
    maximum_correction_revisions: int = MAX_ADAPTIVE_CORRECTION_REVISIONS
    camera_tick_period_ns: int = ADAPTIVE_CAMERA_TICK_PERIOD_NS
    camera_fault_schedule: AdaptiveCameraFaultSchedule = field(
        default_factory=AdaptiveCameraFaultSchedule
    )
    camera_quality_policy: ArmCameraVisionQualityPolicy | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.correction_policy, BoardPoseCorrectionPolicy):
            raise TypeError("correction_policy must be BoardPoseCorrectionPolicy")
        if not isinstance(self.camera_fault_schedule, AdaptiveCameraFaultSchedule):
            raise TypeError(
                "camera_fault_schedule must be AdaptiveCameraFaultSchedule"
            )
        if self.camera_quality_policy is not None and not isinstance(
            self.camera_quality_policy, ArmCameraVisionQualityPolicy
        ):
            raise TypeError(
                "camera_quality_policy must be ArmCameraVisionQualityPolicy or None"
            )
        limits = (
            (
                "maximum_execution_waypoints",
                self.maximum_execution_waypoints,
                1,
                MAX_ADAPTIVE_EXECUTION_WAYPOINTS,
            ),
            (
                "maximum_camera_captures",
                self.maximum_camera_captures,
                1,
                MAX_ADAPTIVE_CAMERA_CAPTURES,
            ),
            (
                "maximum_correction_revisions",
                self.maximum_correction_revisions,
                0,
                MAX_ADAPTIVE_CORRECTION_REVISIONS,
            ),
            (
                "camera_tick_period_ns",
                self.camera_tick_period_ns,
                1,
                1_000_000_000,
            ),
        )
        for name, value, lower, upper in limits:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise AdaptiveVirtualSessionError(
                    f"{name} must be an integer in [{lower}, {upper}]"
                )
        if any(
            fault.capture_sequence > self.maximum_camera_captures
            for fault in self.camera_fault_schedule.faults
        ):
            raise AdaptiveVirtualSessionError(
                "camera fault schedule exceeds maximum_camera_captures"
            )

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema": "rocell.adaptive_arm_camera_session_policy.v1",
            "correction_policy": self.correction_policy.to_dict(),
            "maximum_execution_waypoints": self.maximum_execution_waypoints,
            "maximum_camera_captures": self.maximum_camera_captures,
            "maximum_correction_revisions": self.maximum_correction_revisions,
            "camera_tick_period_ns": self.camera_tick_period_ns,
            "correction_deadband_is_physical_release_limit": False,
            "authority": _authority(),
        }
        # Preserve the established no-fault/default-quality policy document and
        # therefore its hash.  Opt-in simulation controls are still fully hash-
        # bound whenever they are selected.
        if self.camera_fault_schedule.faults:
            document["camera_fault_schedule"] = {
                **self.camera_fault_schedule.to_dict(),
                "definition_sha256": self.camera_fault_schedule.definition_hash,
            }
        if self.camera_quality_policy is not None:
            document["camera_quality_policy"] = {
                **self.camera_quality_policy.to_dict(),
                "policy_sha256": self.camera_quality_policy.content_hash,
            }
        return document


def synthetic_wide_fov_adaptive_session_policy(
    *,
    translation_deadband_mm: float = 1.5,
    angular_deadband_rad: float = math.radians(0.25),
    maximum_inlier_reprojection_rmse_px: float = 3.0,
    maximum_execution_waypoints: int = 128,
) -> AdaptiveVirtualSessionPolicy:
    """Return the explicit policy for exhaustive synthetic camera diagnostics.

    The unmeasured wide-FOV renderer rounds tag corners to image pixels.  This
    factory lets each exhaustive diagnostic bind its measured synthetic
    quantization envelope without changing the replay-stable default-session
    policy.  Inputs still pass through the bounded policy constructors.  The
    hard 15 mm translation, 5 degree yaw, and 3 degree tilt rejection limits
    remain unchanged, and none of these values are physical calibration or
    release tolerances.
    """

    return AdaptiveVirtualSessionPolicy(
        correction_policy=BoardPoseCorrectionPolicy(
            translation_deadband_mm=translation_deadband_mm,
            yaw_deadband_rad=angular_deadband_rad,
            tilt_deadband_rad=angular_deadband_rad,
            maximum_inlier_reprojection_rmse_px=(
                maximum_inlier_reprojection_rmse_px
            ),
        ),
        camera_quality_policy=ArmCameraVisionQualityPolicy(
            maximum_inlier_rmse_px=maximum_inlier_reprojection_rmse_px
        ),
        # Exhaustive diagnostic routes contain at most one 64-record nominal
        # trajectory plus one 64-record corrected replacement.
        maximum_execution_waypoints=maximum_execution_waypoints,
    )


@dataclass(frozen=True, slots=True)
class _ExecutableWaypoint:
    execution_sequence: int
    trajectory_revision: int
    source_nominal_sequence: int | None
    registration_sha256: str
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    point_board: Point3Mm
    phase_endpoint: bool
    joint_result: JointTrajectoryWaypointResult
    source_kind: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.execution_sequence, bool)
            or not isinstance(self.execution_sequence, int)
            or not 0 <= self.execution_sequence <= 1_000_000_000
        ):
            raise AdaptiveVirtualSessionError("execution sequence is invalid")
        if (
            isinstance(self.trajectory_revision, bool)
            or not isinstance(self.trajectory_revision, int)
            or self.trajectory_revision < 0
        ):
            raise AdaptiveVirtualSessionError("trajectory revision is invalid")
        _digest(self.registration_sha256, "waypoint registration hash")
        if self.joint_result.waypoint_sequence != self.execution_sequence:
            raise AdaptiveVirtualSessionError(
                "executable waypoint/result sequence differs"
            )
        if (
            self.joint_result.phase is not self.phase
            or self.joint_result.action_index != self.action_index
            or self.joint_result.semantic_target != self.semantic_target
            or not self.joint_result.accepted
        ):
            raise AdaptiveVirtualSessionError(
                "executable waypoint/result semantics are invalid"
            )
        if not isinstance(self.point_board, Point3Mm) or self.point_board.frame != "board":
            raise AdaptiveVirtualSessionError("executable point must be in board")
        if not isinstance(self.phase_endpoint, bool):
            raise AdaptiveVirtualSessionError("phase_endpoint must be boolean")
        if self.source_kind not in ("NOMINAL", "CORRECTED_SUFFIX"):
            raise AdaptiveVirtualSessionError("unsupported executable source kind")

    @property
    def executable_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_sequence": self.execution_sequence,
            "trajectory_revision": self.trajectory_revision,
            "source_nominal_sequence": self.source_nominal_sequence,
            "registration_sha256": self.registration_sha256,
            "phase": self.phase.value,
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "point_board": _point_dict(self.point_board),
            "phase_endpoint": self.phase_endpoint,
            "joint_result_sha256": _stable_hash(self.joint_result.to_dict()),
            "source_kind": self.source_kind,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveExecutionRecord:
    """One executed virtual command with source and achieved-state evidence."""

    executable: _ExecutableWaypoint
    command_sha256: str
    achieved_plant_state_sha256: str

    def __post_init__(self) -> None:
        _digest(self.command_sha256, "command_sha256")
        _digest(self.achieved_plant_state_sha256, "achieved plant state hash")

    def to_dict(self) -> dict[str, object]:
        return {
            **self.executable.to_dict(),
            "executable_sha256": self.executable.executable_hash,
            "virtual_command_sha256": self.command_sha256,
            "achieved_plant_state_sha256": self.achieved_plant_state_sha256,
            "hardware_command_emitted": False,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveCorrectionInstallation:
    """Proof that a complete replacement was validated before queue mutation."""

    suffix: CorrectedTrajectorySuffix
    discarded_suffix_sha256: str
    discarded_executable_sha256s: tuple[str, ...]
    installed_queue_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.suffix, CorrectedTrajectorySuffix):
            raise TypeError("suffix must be CorrectedTrajectorySuffix")
        if not isinstance(self.discarded_executable_sha256s, tuple):
            raise AdaptiveVirtualSessionError(
                "discarded executable hashes must be an immutable tuple"
            )
        if not self.suffix.passed:
            raise AdaptiveVirtualSessionError("cannot install a failed corrected suffix")
        _digest(self.discarded_suffix_sha256, "discarded suffix hash")
        _digest(self.installed_queue_sha256, "installed queue hash")
        if not self.discarded_executable_sha256s:
            raise AdaptiveVirtualSessionError(
                "discarded executable hashes are invalid"
            )
        for item in self.discarded_executable_sha256s:
            _digest(item, "discarded executable hash")
        if len(set(self.discarded_executable_sha256s)) != len(
            self.discarded_executable_sha256s
        ):
            raise AdaptiveVirtualSessionError(
                "discarded executable hashes must be unique"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "suffix": self.suffix.to_dict(),
            "suffix_sha256": self.suffix.suffix_hash,
            "discarded_suffix_sha256": self.discarded_suffix_sha256,
            "discarded_executable_sha256s": list(
                self.discarded_executable_sha256s
            ),
            "discarded_count": len(self.discarded_executable_sha256s),
            "installed_queue_sha256": self.installed_queue_sha256,
            "replacement_built_and_accepted_before_mutation": True,
            "old_queue_discarded_atomically": True,
            "old_joint_results_executable_after_install": False,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveVisionAttempt:
    """Plan-blind result followed by explicit semantic association."""

    action_index: int
    semantic_target: str
    execution_sequence: int
    source_nominal_sequence: int | None
    result: VirtualArmCameraVisionResult
    measurement: ArmCameraBoardMeasurement | None
    decision: BoardPoseCorrectionDecision | None
    installation: AdaptiveCorrectionInstallation | None

    def __post_init__(self) -> None:
        if not isinstance(self.result, VirtualArmCameraVisionResult):
            raise TypeError("result must be VirtualArmCameraVisionResult")
        if self.result.passed != (
            self.measurement is not None and self.decision is not None
        ):
            raise AdaptiveVirtualSessionError(
                "passing vision must have exactly one measurement and decision"
            )
        if self.installation is not None:
            if (
                self.decision is None
                or self.decision.status is not BoardPoseCorrectionStatus.APPLY
                or self.installation.suffix.correction_decision.decision_hash
                != self.decision.decision_hash
            ):
                raise AdaptiveVirtualSessionError(
                    "installed suffix does not match this APPLY decision"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "execution_sequence": self.execution_sequence,
            "source_nominal_sequence": self.source_nominal_sequence,
            "association_performed_after_plan_blind_processing": True,
            "result": self.result.to_dict(),
            "result_sha256": self.result.result_hash,
            "measurement": (
                None if self.measurement is None else self.measurement.to_dict()
            ),
            "measurement_sha256": (
                None
                if self.measurement is None
                else self.measurement.measurement_hash
            ),
            "decision": None if self.decision is None else self.decision.to_dict(),
            "decision_sha256": (
                None if self.decision is None else self.decision.decision_hash
            ),
            "installation": (
                None if self.installation is None else self.installation.to_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveContactAttempt:
    """Truth-derived contact correlated to semantics only after resolution."""

    action_index: int
    semantic_target: str
    execution_sequence: int
    geometry: ActualToolTipContactGeometry
    event_document: Mapping[str, object]
    event_sha256: str
    result_document: Mapping[str, object]
    result_sha256: str
    expected_region_matched: bool

    def __post_init__(self) -> None:
        _digest(self.event_sha256, "contact event hash")
        _digest(self.result_sha256, "contact result hash")
        object.__setattr__(
            self,
            "event_document",
            _freeze_document(self.event_document, "contact event document"),
        )
        object.__setattr__(
            self,
            "result_document",
            _freeze_document(self.result_document, "contact result document"),
        )
        if _stable_hash(_thaw_json(self.event_document)) != self.event_sha256:
            raise AdaptiveVirtualSessionError(
                "contact event hash does not match its document"
            )
        if _stable_hash(_thaw_json(self.result_document)) != self.result_sha256:
            raise AdaptiveVirtualSessionError(
                "contact result hash does not match its document"
            )
        if self.geometry.joint_sequence != self.execution_sequence:
            raise AdaptiveVirtualSessionError(
                "contact geometry feedback is not correlated to its execution"
            )
        if not isinstance(self.expected_region_matched, bool):
            raise AdaptiveVirtualSessionError(
                "expected_region_matched must be boolean"
            )

    @property
    def accepted(self) -> bool:
        return (
            self.result_document.get("accepted") is True
            and self.expected_region_matched
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "execution_sequence": self.execution_sequence,
            "geometry": self.geometry.to_dict(),
            "geometry_sha256": self.geometry.content_hash,
            "contact_event": _thaw_json(self.event_document),
            "contact_event_sha256": self.event_sha256,
            "contact_result": _thaw_json(self.result_document),
            "contact_result_sha256": self.result_sha256,
            "expected_region_matched_after_resolution": (
                self.expected_region_matched
            ),
            "accepted": self.accepted,
        }


@dataclass(frozen=True, slots=True)
class AdaptivePhoneVerification:
    action_index: int
    required_state: str
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "action_index": self.action_index,
            "required_state": self.required_state,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveVirtualSessionReport:
    """Redacted evidence for one complete or fail-stopped adaptive rehearsal."""

    bootstrap_sha256: str
    plan_sha256: str
    plan_profile_id: str
    device: str
    requested_text_sha256: str
    requested_text_length: int
    scenario: VirtualSessionScenarioBinding
    policy: AdaptiveVirtualSessionPolicy
    calibrations: VirtualCalibrationClosure
    nominal_trajectory: TrajectorySimulationReport
    token: VirtualExecutionToken
    truth_registration_sha256: str
    camera_service_document: Mapping[str, object]
    initial_registration: BoardRegistration
    final_registration: BoardRegistration
    executions: tuple[AdaptiveExecutionRecord, ...]
    vision_attempts: tuple[AdaptiveVisionAttempt, ...]
    correction_installations: tuple[AdaptiveCorrectionInstallation, ...]
    contact_attempts: tuple[AdaptiveContactAttempt, ...]
    phone_verifications: tuple[AdaptivePhoneVerification, ...]
    consumed_camera_faults: tuple[AdaptiveCameraFault, ...]
    arm_document: Mapping[str, object]
    device_document: Mapping[str, object]
    observer_document: Mapping[str, object]
    outcome_verified: bool
    ended_at_park: bool
    fault_reason: str | None

    def __post_init__(self) -> None:
        for name in (
            "bootstrap_sha256",
            "plan_sha256",
            "requested_text_sha256",
            "truth_registration_sha256",
        ):
            _digest(getattr(self, name), name)
        for name in (
            "camera_service_document",
            "arm_document",
            "device_document",
            "observer_document",
        ):
            object.__setattr__(
                self,
                name,
                _freeze_document(getattr(self, name), name),
            )
        if (
            self.camera_service_document.get("private_truth_registration_sha256")
            != self.truth_registration_sha256
        ):
            raise AdaptiveVirtualSessionError(
                "camera service and contact plant truth hashes differ"
            )
        if any(
            item.geometry.truth_registration_sha256
            != self.truth_registration_sha256
            for item in self.contact_attempts
        ):
            raise AdaptiveVirtualSessionError(
                "contact geometry and camera do not share virtual board truth"
            )
        execution_sequences = tuple(
            item.executable.execution_sequence for item in self.executions
        )
        if execution_sequences != tuple(range(len(execution_sequences))):
            raise AdaptiveVirtualSessionError(
                "adaptive execution sequences must be contiguous from zero"
            )
        if len(self.executions) > self.policy.maximum_execution_waypoints:
            raise AdaptiveVirtualSessionError("execution evidence exceeds policy cap")
        if len(self.vision_attempts) > self.policy.maximum_camera_captures:
            raise AdaptiveVirtualSessionError("vision evidence exceeds policy cap")
        if len(self.correction_installations) > (
            self.policy.maximum_correction_revisions
        ):
            raise AdaptiveVirtualSessionError("correction evidence exceeds policy cap")
        if not isinstance(self.consumed_camera_faults, tuple) or any(
            not isinstance(item, AdaptiveCameraFault)
            for item in self.consumed_camera_faults
        ):
            raise AdaptiveVirtualSessionError(
                "consumed camera faults must be an immutable fault tuple"
            )
        consumed_hashes = tuple(
            item.fault_hash for item in self.consumed_camera_faults
        )
        if len(consumed_hashes) != len(set(consumed_hashes)):
            raise AdaptiveVirtualSessionError(
                "a scheduled camera fault was consumed more than once"
            )
        scheduled = self.policy.camera_fault_schedule.faults
        if self.consumed_camera_faults != scheduled[: len(consumed_hashes)]:
            raise AdaptiveVirtualSessionError(
                "consumed camera faults are not an ordered schedule prefix"
            )
        expected_fault_definition_hash = (
            self.policy.camera_fault_schedule.definition_hash
            if scheduled
            else VirtualFaultScript("adaptive-none").definition_hash
        )
        if self.token.fault_script_hash != expected_fault_definition_hash:
            raise AdaptiveVirtualSessionError(
                "execution token does not bind the selected camera fault schedule"
            )
        attempts_by_capture = {
            item.result.capture_sequence: item for item in self.vision_attempts
        }
        for fault in self.consumed_camera_faults:
            attempt = attempts_by_capture.get(fault.capture_sequence)
            # An unexpected exception may interrupt camera processing before a
            # result exists.  When a result does exist, its selected mode must
            # agree exactly with the precommitted schedule.
            if (
                attempt is not None
                and attempt.result.capture_mode is not fault.capture_mode
            ):
                raise AdaptiveVirtualSessionError(
                    "vision evidence differs from its consumed camera fault"
                )

    @property
    def pipeline_completed(self) -> bool:
        return (
            self.fault_reason is None
            and self.outcome_verified
            and self.ended_at_park
            and bool(self.contact_attempts)
            and all(item.accepted for item in self.contact_attempts)
            and all(item.result.passed for item in self.vision_attempts)
            and self.arm_document.get("lifecycle") == "CLOSED"
        )

    @property
    def status(self) -> str:
        return (
            "ADAPTIVE_VIRTUAL_SESSION_COMPLETE_WITH_PHYSICAL_HOLDS"
            if self.pipeline_completed
            else "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
        )

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": ADAPTIVE_VIRTUAL_SESSION_SCHEMA,
            "status": self.status,
            "requested_text": {
                "sha256": self.requested_text_sha256,
                "normalized_codepoint_length": self.requested_text_length,
                "plaintext_serialized": False,
            },
            "source": {
                "bootstrap_sha256": self.bootstrap_sha256,
                "plan_sha256": self.plan_sha256,
                "plan_profile_id": self.plan_profile_id,
                "device": self.device,
                "scenario": self.scenario.to_dict(),
                "policy": {
                    **self.policy.to_dict(),
                    "policy_sha256": self.policy.policy_hash,
                },
                "calibrations": self.calibrations.to_dict(),
                "calibrations_sha256": self.calibrations.closure_hash,
                "nominal_trajectory": self.nominal_trajectory.to_dict(),
                "nominal_trajectory_sha256": self.nominal_trajectory.report_hash,
                "virtual_execution_token": self.token.to_dict(),
            },
            "private_plant_truth": {
                "registration_sha256": self.truth_registration_sha256,
                "transform_serialized": False,
                "shared_by_camera_and_contact": True,
            },
            "camera_service": _thaw_json(self.camera_service_document),
            "registration": {
                "initial": self.initial_registration.to_dict(),
                "initial_sha256": self.initial_registration.registration_hash,
                "final": self.final_registration.to_dict(),
                "final_sha256": self.final_registration.registration_hash,
            },
            "executions": [item.to_dict() for item in self.executions],
            "vision_attempts": [item.to_dict() for item in self.vision_attempts],
            **(
                {}
                if not self.policy.camera_fault_schedule.faults
                else {
                    "camera_fault_consumption": {
                        "schedule_sha256": (
                            self.policy.camera_fault_schedule.definition_hash
                        ),
                        "consumed_faults": [
                            item.to_dict() for item in self.consumed_camera_faults
                        ],
                        "consumed_fault_sha256s": [
                            item.fault_hash for item in self.consumed_camera_faults
                        ],
                        "unconsumed_fault_sha256s": [
                            item.fault_hash
                            for item in self.policy.camera_fault_schedule.faults[
                                len(self.consumed_camera_faults) :
                            ]
                        ],
                        "each_fault_consumed_at_most_once": True,
                    }
                }
            ),
            "correction_installations": [
                item.to_dict() for item in self.correction_installations
            ],
            "contact_attempts": [item.to_dict() for item in self.contact_attempts],
            "phone_verifications": [
                item.to_dict() for item in self.phone_verifications
            ],
            "arm": _thaw_json(self.arm_document),
            "device_model": _thaw_json(self.device_document),
            "outcome_observer": _thaw_json(self.observer_document),
            "outcome_verified": self.outcome_verified,
            "ended_at_park": self.ended_at_park,
            "fault_reason": self.fault_reason,
            "model_and_physical_holds": [
                "SYNTHETIC_CAMERA_MOUNT_AND_INTRINSICS_UNMEASURED",
                "FULL_ROBOT_LINK_SELF_HOLDER_TOOL_CABLE_COLLISION_UNEVALUATED",
                "CONTROLLER_R_CTRL_CORRELATION_UNCOMMISSIONED",
                "PHYSICAL_CALIBRATIONS_AND_TIMING_UNCOMMISSIONED",
                "DYNAMICS_PAYLOAD_FORCE_AND_CONTACT_GUARDS_UNQUALIFIED",
                "VIRTUAL_CONTACT_AND_OUTCOME_MODELS_NOT_PHYSICAL_EVIDENCE",
            ],
            "authority": {
                **_authority(),
                "virtual_commands_executed": len(self.executions),
            },
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_sha256": self.report_hash}


def _default_trajectory_policy(
    scenario: VirtualSessionScenarioBinding,
) -> TrajectorySimulationPolicy:
    park = scenario.park_point_board_mm
    return TrajectorySimulationPolicy(
        maximum_cartesian_step_mm=30.0,
        maximum_joint_step_rad=0.35,
        minimum_normalized_arm_joint_margin=0.01,
        maximum_refinement_rounds=2,
        maximum_waypoints_per_round=256,
        maximum_total_ik_solves=512,
        maximum_route_targets=MAX_VIRTUAL_SESSION_TARGETS,
        park_xy_board_mm=(park[0], park[1]),
    )


def _nominal_queue(
    trajectory: TrajectorySimulationReport,
    registration: BoardRegistration,
) -> tuple[_ExecutableWaypoint, ...]:
    final = trajectory.final_round
    assert final is not None
    return tuple(
        _ExecutableWaypoint(
            execution_sequence=waypoint.sequence,
            trajectory_revision=0,
            source_nominal_sequence=waypoint.sequence,
            registration_sha256=registration.registration_hash,
            phase=waypoint.phase,
            action_index=waypoint.action_index,
            semantic_target=waypoint.semantic_target,
            point_board=waypoint.point_board,
            phase_endpoint=waypoint.phase_endpoint,
            joint_result=result,
            source_kind="NOMINAL",
        )
        for waypoint, result in zip(final.waypoints, final.joint_results)
    )


def _corrected_queue(
    suffix: CorrectedTrajectorySuffix,
) -> tuple[_ExecutableWaypoint, ...]:
    registration_hash = (
        suffix.correction_decision.candidate_registration.registration_hash
    )
    return tuple(
        _ExecutableWaypoint(
            execution_sequence=waypoint.execution_sequence,
            trajectory_revision=waypoint.trajectory_revision,
            source_nominal_sequence=waypoint.source_waypoint_sequence,
            registration_sha256=registration_hash,
            phase=waypoint.phase,
            action_index=waypoint.action_index,
            semantic_target=waypoint.semantic_target,
            point_board=waypoint.point_board,
            phase_endpoint=waypoint.phase_endpoint,
            joint_result=result,
            source_kind="CORRECTED_SUFFIX",
        )
        for waypoint, result in zip(suffix.waypoints, suffix.joint_results)
    )


class _AdaptiveExecutor:
    """Single-use mutable engine hidden behind the immutable report."""

    def __init__(
        self,
        *,
        bootstrap: VirtualWorkcellBootstrap,
        plan: ActionPlan,
        normalized_text: str,
        study_input: ReachStudyInput,
        scenario: VirtualSessionScenarioBinding,
        policy: AdaptiveVirtualSessionPolicy,
        trajectory: TrajectorySimulationReport,
        calibrations: VirtualCalibrationClosure,
        truth: HiddenVirtualBoardTruth,
        device: VirtualKeyboard | VirtualAndroid,
    ) -> None:
        self.bootstrap = bootstrap
        self.plan = plan
        self.normalized_text = normalized_text
        self.study_input = study_input
        self.scenario = scenario
        self.policy = policy
        self.trajectory = trajectory
        self.calibrations = calibrations
        self.truth_hash = truth.content_hash
        if policy.camera_quality_policy is None:
            # Retain the established service factory on the default path so
            # no-fault report documents and hashes remain replay-compatible.
            self.camera = make_virtual_arm_camera_service(
                bootstrap.context, study_input, truth=truth
            )
        else:
            # A wider synthetic consensus gate is useful for high-perspective
            # multi-key rehearsals.  It remains explicit, hash-bound, and has
            # no physical-release meaning.
            self.camera = VirtualArmCameraVisionService(
                context=bootstrap.context,
                binding=make_unmeasured_synthetic_arm_camera_binding(
                    bootstrap.context
                ),
                truth=truth,
                quality_policy=policy.camera_quality_policy,
            )
        self.contact_projector = ActualToolTipContactProjector(
            model_path=bootstrap.context.scenario.model_path,
            tool_length_mm=trajectory.tool_length_mm,
            truth=truth,
            joint_bounds_rad=(
                bootstrap.context.scenario.controller_joint_intersection_rad
            ),
            gripper_bounds_rad=(
                bootstrap.context.scenario.controller_gripper_intersection_rad
            ),
        )
        if (
            self.camera.definition_dict()["private_truth_registration_sha256"]
            != self.contact_projector.truth_registration_sha256
        ):
            raise AdaptiveVirtualSessionError(
                "camera and contact projector do not share virtual board truth"
            )
        scheduled_faults = policy.camera_fault_schedule.faults
        fault_definition_hash = (
            policy.camera_fault_schedule.definition_hash
            if scheduled_faults
            else VirtualFaultScript("adaptive-none").definition_hash
        )
        self.token = issue_virtual_execution_token(
            context_hash=bootstrap.bootstrap_hash,
            plan_hash=plan.plan_hash,
            trajectory_hash=trajectory.report_hash,
            scenario_hash=scenario.scenario_hash,
            fault_script_hash=fault_definition_hash,
        )
        ready = {
            name: position.value
            for name, position in (
                bootstrap.context.scenario.ready_arm_joint_positions_rad.items()
            )
        }
        self.arm = VirtualArmPlant(
            token=self.token,
            clock=VirtualClock(),
            initial_joint_positions_rad=ready,
            joint_bounds_rad=(
                bootstrap.context.scenario.controller_joint_intersection_rad
            ),
        )
        self.device = device
        self.observer = VirtualTextOutcomeObserver(
            observer_id="adaptive-contact-result-observer-v1"
        )
        self.initial_registration = initial_planner_board_registration(study_input)
        self.active_registration = self.initial_registration
        self.queue = deque(_nominal_queue(trajectory, self.active_registration))
        self.executions: list[AdaptiveExecutionRecord] = []
        self.vision_attempts: list[AdaptiveVisionAttempt] = []
        self.installations: list[AdaptiveCorrectionInstallation] = []
        self.contacts: list[AdaptiveContactAttempt] = []
        self.phone_verifications: list[AdaptivePhoneVerification] = []
        self.consumed_camera_faults: list[AdaptiveCameraFault] = []
        self.capture_sequence = 0
        self.previous_frame_sequence = 0
        self.previous_freshness_token = "arm-camera:no-previous-frame"
        self.next_action_index = 0
        self.current_contact_action: int | None = None
        self.last_executable: _ExecutableWaypoint | None = None
        self.fault_reason: str | None = None
        self.active_boundary = "EXECUTOR_START"

    def _report(
        self,
        *,
        outcome_verified: bool = False,
        ended_at_park: bool = False,
    ) -> AdaptiveVirtualSessionReport:
        return AdaptiveVirtualSessionReport(
            bootstrap_sha256=self.bootstrap.bootstrap_hash,
            plan_sha256=self.plan.plan_hash,
            plan_profile_id=self.plan.profile_id,
            device=self.plan.device.value,
            requested_text_sha256=self.plan.requested_text_sha256,
            requested_text_length=len(self.normalized_text),
            scenario=self.scenario,
            policy=self.policy,
            calibrations=self.calibrations,
            nominal_trajectory=self.trajectory,
            token=self.token,
            truth_registration_sha256=self.truth_hash,
            camera_service_document=self.camera.definition_dict(),
            initial_registration=self.initial_registration,
            final_registration=self.active_registration,
            executions=tuple(self.executions),
            vision_attempts=tuple(self.vision_attempts),
            correction_installations=tuple(self.installations),
            contact_attempts=tuple(self.contacts),
            phone_verifications=tuple(self.phone_verifications),
            consumed_camera_faults=tuple(self.consumed_camera_faults),
            arm_document=self.arm.to_dict(),
            device_document=self.device.to_dict(),
            observer_document=self.observer.to_dict(),
            outcome_verified=outcome_verified,
            ended_at_park=ended_at_park,
            fault_reason=self.fault_reason,
        )

    def _close_fail_stop(self, reason: str) -> None:
        """Best-effort fault transition followed by mandatory virtual close."""

        self.fault_reason = reason
        if self.arm.lifecycle not in (
            VirtualArmLifecycle.FAULT,
            VirtualArmLifecycle.CLOSED,
        ):
            try:
                self.arm.fault(reason)
            except Exception:
                # Cleanup must not be defeated by a secondary lifecycle fault.
                # The final arm document will expose the degraded transition.
                pass
        if self.arm.lifecycle is not VirtualArmLifecycle.CLOSED:
            self.arm.close()

    def _fail(self, reason: str) -> AdaptiveVirtualSessionReport:
        self._close_fail_stop(reason)
        return self._report()

    def _process_phone_verifications(self) -> bool:
        while self.next_action_index < len(self.plan.actions):
            action = self.plan.actions[self.next_action_index]
            if not isinstance(action, VerifyPhoneState):
                return True
            if not isinstance(self.device, VirtualAndroid):
                raise AdaptiveVirtualSessionError(
                    "phone verification appeared in a keyboard session"
                )
            self.active_boundary = "PHONE_UI_VERIFICATION"
            passed = self.device.verify_ui_state(action.state_id)
            self.phone_verifications.append(
                AdaptivePhoneVerification(
                    action_index=self.next_action_index,
                    required_state=action.state_id,
                    passed=passed,
                )
            )
            if not passed:
                self.fault_reason = "ANDROID_UI_STATE_REJECTED"
                return False
            self.next_action_index += 1
        return True

    def _capture_bracket(
        self,
        feedback: VirtualArmFeedback,
    ) -> ArmCameraCaptureBracket:
        self.capture_sequence += 1
        if self.capture_sequence > self.policy.maximum_camera_captures:
            raise AdaptiveVirtualSessionError("camera capture budget exhausted")
        base = self.capture_sequence * 100
        period = self.policy.camera_tick_period_ns
        before = achieved_joint_sample_from_virtual_feedback(
            feedback,
            fixed_gripper_position=(
                self.bootstrap.context.scenario.fixed_gripper_position
            ),
            sample_id=f"adaptive-before-{self.capture_sequence:04d}",
            observed_at=RuntimeInstant(
                VIRTUAL_ARM_CAMERA_CLOCK, base, period
            ),
        )
        after = achieved_joint_sample_from_virtual_feedback(
            feedback,
            fixed_gripper_position=(
                self.bootstrap.context.scenario.fixed_gripper_position
            ),
            sample_id=f"adaptive-after-{self.capture_sequence:04d}",
            observed_at=RuntimeInstant(
                VIRTUAL_ARM_CAMERA_CLOCK, base + 6, period
            ),
        )
        return ArmCameraCaptureBracket(
            capture_sequence=self.capture_sequence,
            before_feedback=before,
            after_feedback=after,
            settled_since=RuntimeInstant(
                VIRTUAL_ARM_CAMERA_CLOCK, base - 30, period
            ),
            exposure_at=RuntimeInstant(
                VIRTUAL_ARM_CAMERA_CLOCK, base + 3, period
            ),
        )

    def _capture_mode(self) -> VirtualArmCameraCaptureMode:
        """Select and consume the precommitted mode for the current bracket."""

        fault = self.policy.camera_fault_schedule.fault_for_capture(
            self.capture_sequence
        )
        if fault is None:
            return VirtualArmCameraCaptureMode.NORMAL
        if fault in self.consumed_camera_faults:
            raise AdaptiveVirtualSessionError(
                "scheduled camera fault cannot be consumed more than once"
            )
        expected_index = len(self.consumed_camera_faults)
        if (
            expected_index >= len(self.policy.camera_fault_schedule.faults)
            or self.policy.camera_fault_schedule.faults[expected_index] != fault
        ):
            raise AdaptiveVirtualSessionError(
                "scheduled camera fault consumption left declaration order"
            )
        # Consume immediately before the camera boundary.  An exception inside
        # processing therefore cannot make a selected fault appear unattempted.
        self.consumed_camera_faults.append(fault)
        return fault.capture_mode

    def _observe_and_maybe_replace(
        self,
        executable: _ExecutableWaypoint,
        feedback: VirtualArmFeedback,
    ) -> bool:
        assert executable.action_index is not None
        assert executable.semantic_target is not None
        self.active_boundary = "ARM_CAMERA_CAPTURE_BRACKET"
        bracket = self._capture_bracket(feedback)
        capture_mode = self._capture_mode()
        self.active_boundary = "ARM_CAMERA_PROCESS"
        result = self.camera.process(
            bracket=bracket,
            capture_mode=capture_mode,
        )
        if not result.passed:
            self.vision_attempts.append(
                AdaptiveVisionAttempt(
                    action_index=executable.action_index,
                    semantic_target=executable.semantic_target,
                    execution_sequence=executable.execution_sequence,
                    source_nominal_sequence=executable.source_nominal_sequence,
                    result=result,
                    measurement=None,
                    decision=None,
                    installation=None,
                )
            )
            self.fault_reason = result.detail_code
            return False
        frame = result.rendered_frame
        assert frame is not None
        packet = frame.frame_packet
        assert packet.source_sequence is not None
        assert packet.freshness_token is not None
        self.active_boundary = "VISION_MEASUREMENT"
        measurement = correction_measurement_from_vision_result(
            result,
            previous_source_sequence=self.previous_frame_sequence,
            previous_freshness_token=self.previous_freshness_token,
            evaluated_at=RuntimeInstant(
                VIRTUAL_ARM_CAMERA_CLOCK,
                self.capture_sequence * 100 + 8,
                self.policy.camera_tick_period_ns,
            ),
        )
        self.active_boundary = "BOARD_POSE_CORRECTION"
        decision = decide_board_pose_correction(
            self.active_registration,
            measurement,
            self.policy.correction_policy,
        )
        self.previous_frame_sequence = packet.source_sequence
        self.previous_freshness_token = packet.freshness_token
        installation: AdaptiveCorrectionInstallation | None = None
        if decision.status is BoardPoseCorrectionStatus.REJECT:
            self.fault_reason = "BOARD_POSE_CORRECTION_REJECTED:" + ",".join(
                decision.rejection_reasons
            )
        elif decision.status is BoardPoseCorrectionStatus.APPLY:
            if len(self.installations) >= self.policy.maximum_correction_revisions:
                self.fault_reason = "BOARD_POSE_CORRECTION_ITERATION_LIMIT"
            elif executable.source_nominal_sequence is None:
                self.fault_reason = "CORRECTION_REVALIDATION_DID_NOT_CONVERGE"
            else:
                self.active_boundary = "CORRECTED_SUFFIX_REPLAN"
                try:
                    suffix = replan_corrected_trajectory_suffix(
                        self.bootstrap.context,
                        self.trajectory,
                        decision,
                        hover_waypoint_sequence=executable.source_nominal_sequence,
                        previous_execution_sequence=executable.execution_sequence,
                        # The post-exposure achieved sample—not a copied
                        # planner joint vector—is the correction boundary.
                        # Its source, sequence, timing, stale flag, six-joint
                        # state, and source-state digest are checked by the
                        # suffix replanner before any new IK work begins.
                        achieved_feedback_sample=bracket.after_feedback,
                    )
                except CorrectedTrajectorySuffixError as exc:
                    self.fault_reason = f"CORRECTED_SUFFIX_INVALID:{exc}"
                else:
                    if not suffix.passed:
                        self.fault_reason = suffix.termination_reason
                    else:
                        replacement = _corrected_queue(suffix)
                        if (
                            len(self.executions) + len(replacement)
                            > self.policy.maximum_execution_waypoints
                        ):
                            self.fault_reason = "ADAPTIVE_EXECUTION_BUDGET_EXHAUSTED"
                        else:
                            # Build and hash both immutable values before the
                            # sole queue assignment: no partial suffix can run.
                            discarded = tuple(self.queue)
                            discarded_hashes = tuple(
                                item.executable_hash for item in discarded
                            )
                            discarded_hash = _stable_hash(
                                [item.to_dict() for item in discarded]
                            )
                            replacement_hash = _stable_hash(
                                [item.to_dict() for item in replacement]
                            )
                            installation = AdaptiveCorrectionInstallation(
                                suffix=suffix,
                                discarded_suffix_sha256=discarded_hash,
                                discarded_executable_sha256s=discarded_hashes,
                                installed_queue_sha256=replacement_hash,
                            )
                            self.queue = deque(replacement)
                            self.active_registration = (
                                decision.candidate_registration
                            )
                            self.installations.append(installation)
        self.vision_attempts.append(
            AdaptiveVisionAttempt(
                action_index=executable.action_index,
                semantic_target=executable.semantic_target,
                execution_sequence=executable.execution_sequence,
                source_nominal_sequence=executable.source_nominal_sequence,
                result=result,
                measurement=measurement,
                decision=decision,
                installation=installation,
            )
        )
        return self.fault_reason is None

    def _contact(
        self,
        executable: _ExecutableWaypoint,
        feedback: VirtualArmFeedback,
    ) -> bool:
        assert executable.action_index is not None
        assert executable.semantic_target is not None
        action_index = executable.action_index
        if action_index != self.next_action_index:
            raise AdaptiveVirtualSessionError(
                "contact action does not match the next semantic action"
            )
        action = self.plan.actions[action_index]
        if not (
            isinstance(action, PressKey)
            and isinstance(self.device, VirtualKeyboard)
            or isinstance(action, TapPhoneTarget)
            and isinstance(self.device, VirtualAndroid)
        ):
            raise AdaptiveVirtualSessionError("contact action/device types differ")
        sample = achieved_joint_sample_from_virtual_feedback(
            feedback,
            fixed_gripper_position=(
                self.bootstrap.context.scenario.fixed_gripper_position
            ),
            sample_id=f"adaptive-contact-{action_index:04d}",
            observed_at=RuntimeInstant(
                "adaptive_virtual_contact_clock",
                executable.execution_sequence,
                1_000_000,
            ),
        )
        self.active_boundary = "CONTACT_GEOMETRY"
        geometry = self.contact_projector.project(sample)
        point = geometry.tip_position_truth_board_mm
        axis = geometry.hand_tcp_z_axis_truth_board
        event = ContactEvent(
            action_index=action_index,
            achieved_board_xyz_mm=(point.x, point.y, point.z),
            achieved_contact_normal_board=(-axis.x, -axis.y, -axis.z),
            dwell_ticks=VIRTUAL_CONTACT_DWELL_TICKS,
        )
        self.active_boundary = "DEVICE_CONTACT"
        result: ContactResult = self.device.apply_contact(event)
        expected_region = executable.semantic_target
        matched = result.resolved_target_id == expected_region
        self.active_boundary = "CONTACT_EVIDENCE"
        attempt = AdaptiveContactAttempt(
            action_index=action_index,
            semantic_target=executable.semantic_target,
            execution_sequence=executable.execution_sequence,
            geometry=geometry,
            event_document=event.to_dict(),
            event_sha256=event.event_hash,
            result_document=result.to_dict(),
            result_sha256=result.result_hash,
            expected_region_matched=matched,
        )
        # The device mutation has already occurred, so retain its immutable
        # contact evidence before invoking the independent observer.  If that
        # downstream observer fails, the fail-stop report cannot erase a
        # contact that really occurred in the virtual plant.
        self.contacts.append(attempt)
        self.active_boundary = "OUTCOME_OBSERVER_CONSUME"
        self.observer.consume(result)
        if not attempt.accepted:
            self.fault_reason = f"DEVICE_CONTACT_{result.disposition.value}"
            return False
        self.current_contact_action = action_index
        return True

    def _execute(self) -> AdaptiveVirtualSessionReport:
        self.active_boundary = "ARM_CONNECT"
        self.arm.connect()
        self.active_boundary = "ARM_REFERENCE"
        self.arm.reference()
        self.active_boundary = "ARM_READY"
        self.arm.mark_ready()
        if self.plan.device is Device.PHONE and not self._process_phone_verifications():
            assert self.fault_reason is not None
            return self._fail(self.fault_reason)

        while self.queue:
            if len(self.executions) >= self.policy.maximum_execution_waypoints:
                return self._fail("ADAPTIVE_EXECUTION_BUDGET_EXHAUSTED")
            executable = self.queue.popleft()
            command = VirtualJointWaypoint(
                sequence=executable.execution_sequence,
                joint_positions_rad=(
                    executable.joint_result.solution_arm_joint_positions_rad
                ),
                action_index=executable.action_index,
            )
            self.active_boundary = "ARM_EXECUTE_WAYPOINT"
            feedback = self.arm.execute_waypoint(command)
            self.executions.append(
                AdaptiveExecutionRecord(
                    executable=executable,
                    command_sha256=command.waypoint_hash,
                    achieved_plant_state_sha256=feedback.plant_state_hash,
                )
            )
            self.last_executable = executable

            if (
                executable.phase is MotionPhase.HOVER
                and executable.phase_endpoint
                and executable.action_index is not None
                and executable.semantic_target is not None
                and not self._observe_and_maybe_replace(executable, feedback)
            ):
                assert self.fault_reason is not None
                return self._fail(self.fault_reason)
            if (
                executable.phase is MotionPhase.CONTACT
                and executable.phase_endpoint
                and executable.action_index is not None
                and executable.semantic_target is not None
                and not self._contact(executable, feedback)
            ):
                assert self.fault_reason is not None
                return self._fail(self.fault_reason)
            if (
                executable.phase is MotionPhase.RETRACT
                and executable.phase_endpoint
                and executable.action_index is not None
                and self.current_contact_action == executable.action_index
            ):
                self.next_action_index = executable.action_index + 1
                self.current_contact_action = None
                if (
                    self.plan.device is Device.PHONE
                    and not self._process_phone_verifications()
                ):
                    assert self.fault_reason is not None
                    return self._fail(self.fault_reason)

        if self.next_action_index != len(self.plan.actions):
            raise AdaptiveVirtualSessionError(
                "not every semantic action was consumed"
            )
        if len(self.consumed_camera_faults) != len(
            self.policy.camera_fault_schedule.faults
        ):
            return self._fail("ADAPTIVE_CAMERA_FAULT_SCHEDULE_INCOMPLETE")
        self.active_boundary = "ARM_COMPLETE"
        self.arm.complete()
        self.active_boundary = "OUTCOME_OBSERVER_VERIFY"
        outcome = self.observer.output_matches(
            self.plan.requested_text_sha256, len(self.normalized_text)
        )
        if not outcome:
            return self._fail("OUTPUT_MISMATCH")
        ended_at_park = bool(
            self.last_executable is not None
            and self.last_executable.phase is MotionPhase.PARK
            and self.last_executable.phase_endpoint
            and self.arm.last_waypoint_sequence
            == self.last_executable.execution_sequence
        )
        if not ended_at_park:
            return self._fail("FINAL_PARK_NOT_CONFIRMED")
        self.active_boundary = "ARM_CLOSE"
        self.arm.close()
        return self._report(outcome_verified=True, ended_at_park=True)

    def execute(self) -> AdaptiveVirtualSessionReport:
        """Execute once and convert every unexpected runtime error to fail-stop.

        Configuration and planning errors are still raised before this engine
        starts.  Once the virtual arm lifecycle begins, an unexpected
        dependency exception may neither escape with the arm open nor allow a
        later queued command/contact to execute.  Exception messages are not
        serialized; the stable boundary name is sufficient deterministic
        evidence for rehearsal diagnostics.
        """

        try:
            return self._execute()
        except Exception:
            reason = f"ADAPTIVE_UNEXPECTED_FAILURE:{self.active_boundary}"
            self._close_fail_stop(reason)
            return self._report()


def run_adaptive_virtual_session(
    bootstrap: VirtualWorkcellBootstrap,
    plan: ActionPlan,
    requested_text: str,
    study_input: ReachStudyInput,
    scenario: VirtualSessionScenarioBinding,
    *,
    truth: HiddenVirtualBoardTruth,
    policy: AdaptiveVirtualSessionPolicy | None = None,
    trajectory_policy: TrajectorySimulationPolicy | None = None,
) -> AdaptiveVirtualSessionReport:
    """Plan and execute one bounded adaptive virtual typing mission."""

    if not isinstance(bootstrap, VirtualWorkcellBootstrap):
        raise TypeError("bootstrap must be VirtualWorkcellBootstrap")
    if not isinstance(plan, ActionPlan):
        raise TypeError("plan must be ActionPlan")
    if not isinstance(requested_text, str):
        raise TypeError("requested_text must be str")
    if not isinstance(study_input, ReachStudyInput):
        raise TypeError("study_input must be ReachStudyInput")
    if not isinstance(scenario, VirtualSessionScenarioBinding):
        raise TypeError("scenario must be VirtualSessionScenarioBinding")
    if not isinstance(truth, HiddenVirtualBoardTruth):
        raise TypeError("truth must be HiddenVirtualBoardTruth")
    selected_policy = policy or AdaptiveVirtualSessionPolicy()
    if not isinstance(selected_policy, AdaptiveVirtualSessionPolicy):
        raise TypeError("policy must be AdaptiveVirtualSessionPolicy")
    revalidate_virtual_workcell(bootstrap)
    normalized = normalize_line_endings(requested_text)
    if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != (
        plan.requested_text_sha256
    ):
        raise AdaptiveVirtualSessionError(
            "requested text hash differs from the action plan"
        )
    device, physical_count = build_virtual_device_model(
        bootstrap, plan, normalized
    )
    if not 1 <= physical_count <= MAX_VIRTUAL_SESSION_TARGETS:
        raise AdaptiveVirtualSessionError(
            "adaptive session physical target count is out of bounds"
        )
    selected_trajectory_policy = trajectory_policy or _default_trajectory_policy(
        scenario
    )
    park = scenario.park_point_board_mm
    if selected_trajectory_policy.park_xy_board_mm != (park[0], park[1]):
        raise AdaptiveVirtualSessionError(
            "trajectory park differs from the locked scenario"
        )
    trajectory = run_trajectory_simulation(
        bootstrap.context,
        plan,
        study_input,
        selected_trajectory_policy,
    )
    validate_virtual_session_trajectory(plan, trajectory)
    calibrations = resolve_virtual_calibrations(
        bootstrap.context, plan, study_input
    )
    return _AdaptiveExecutor(
        bootstrap=bootstrap,
        plan=plan,
        normalized_text=normalized,
        study_input=study_input,
        scenario=scenario,
        policy=selected_policy,
        trajectory=trajectory,
        calibrations=calibrations,
        truth=truth,
        device=device,
    ).execute()


def run_default_adaptive_virtual_session(
    workspace: Path,
    device: str,
    requested_text: str,
    *,
    truth_translation_Wv_mm: Vec3 = Vec3.zero(),
    truth_yaw_board_rad: float = 0.0,
    runtime_path: Path | None = None,
    policy: AdaptiveVirtualSessionPolicy | None = None,
) -> AdaptiveVirtualSessionReport:
    """Run the locked pre-hardware profile with an injected hidden board pose."""

    from rocell.simulation.virtual_profile import (
        VirtualProfileContext,
        load_virtual_commissioning_profile,
    )

    if not isinstance(truth_translation_Wv_mm, Vec3):
        raise TypeError("truth_translation_Wv_mm must be Vec3")
    if (
        isinstance(truth_yaw_board_rad, bool)
        or not isinstance(truth_yaw_board_rad, (int, float))
        or not math.isfinite(float(truth_yaw_board_rad))
    ):
        raise AdaptiveVirtualSessionError("truth_yaw_board_rad must be finite")
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
    truth = make_hidden_virtual_board_truth(
        profile.study_input,
        translation_Wv_mm=truth_translation_Wv_mm,
        yaw_board_rad=float(truth_yaw_board_rad),
    )
    return run_adaptive_virtual_session(
        bootstrap,
        plan,
        requested_text,
        profile.study_input,
        scenario,
        truth=truth,
        policy=policy,
    )


__all__ = [
    "ADAPTIVE_CAMERA_TICK_PERIOD_NS",
    "ADAPTIVE_VIRTUAL_SESSION_SCHEMA",
    "MAX_ADAPTIVE_CAMERA_CAPTURES",
    "MAX_ADAPTIVE_CAMERA_FAULTS",
    "MAX_ADAPTIVE_CORRECTION_REVISIONS",
    "MAX_ADAPTIVE_EXECUTION_WAYPOINTS",
    "AdaptiveCameraFault",
    "AdaptiveCameraFaultSchedule",
    "AdaptiveContactAttempt",
    "AdaptiveCorrectionInstallation",
    "AdaptiveExecutionRecord",
    "AdaptivePhoneVerification",
    "AdaptiveVirtualSessionError",
    "AdaptiveVirtualSessionPolicy",
    "AdaptiveVirtualSessionReport",
    "AdaptiveVisionAttempt",
    "run_adaptive_virtual_session",
    "run_default_adaptive_virtual_session",
    "synthetic_wide_fov_adaptive_session_policy",
]
