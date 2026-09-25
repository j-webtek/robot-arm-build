"""Deterministic tool-tip path simulation over nominal RC03 geometry.

This layer connects semantic actions to simulation-only target seeds and checks
the resulting point/segment path against conservative RC03 AABB proxies. It
does not solve IK, model robot links/cables, or emit controller commands.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from rocell.models.actions import ActionPlan, PressKey, TapPhoneTarget, VerifyPhoneState
from rocell.models.frames import Point3Mm
from rocell.models.units import finite_real
from rocell.rc03.build_snapshot import BuildSnapshot, Capability
from rocell.safety.supervisor import SafetySupervisor
from rocell.simulation import NominalWorkcellScene, SimulationHardwareProfile
from rocell.targets import NominalTargetCatalog, TargetMapError, TargetRegion

from .primitives import MotionPhase


class GeometricSimulationError(RuntimeError):
    """A nominal path cannot be constructed because an invariant is invalid."""


@dataclass(frozen=True, slots=True)
class GeometricSimulationSettings:
    clearance_above_highest_obstacle_mm: float = 35.0
    segment_clearance_mm: float = 5.0
    hover_height_mm: float = 12.0
    approach_height_mm: float = 3.0
    contact_overtravel_mm: float = 1.0
    park_xy_board_mm: tuple[float, float] = (305.0, 400.0)

    def __post_init__(self) -> None:
        for name in (
            "clearance_above_highest_obstacle_mm",
            "segment_clearance_mm",
            "hover_height_mm",
            "approach_height_mm",
            "contact_overtravel_mm",
        ):
            value = finite_real(getattr(self, name), name=name)
            if value <= 0.0:
                raise ValueError(f"{name} must be greater than zero")
            object.__setattr__(self, name, value)
        if self.hover_height_mm <= self.approach_height_mm:
            raise ValueError("hover height must exceed approach height")
        if not isinstance(self.park_xy_board_mm, tuple) or len(self.park_xy_board_mm) != 2:
            raise ValueError("park_xy_board_mm must contain exactly two values")
        park = tuple(finite_real(value, name="park coordinate") for value in self.park_xy_board_mm)
        object.__setattr__(self, "park_xy_board_mm", park)


@dataclass(frozen=True, slots=True)
class GeometricPathCheck:
    check_id: str
    status: str
    collisions: tuple[str, ...]
    ignored_obstacles: tuple[str, ...]
    method: str

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "FAIL"}:
            raise ValueError("check status must be PASS or FAIL")
        object.__setattr__(self, "collisions", tuple(self.collisions))
        object.__setattr__(self, "ignored_obstacles", tuple(self.ignored_obstacles))

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "collisions": list(self.collisions),
            "ignored_obstacles": list(self.ignored_obstacles),
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class GeometricPathStep:
    sequence: int
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    tip_point_board: Point3Mm | None
    check_id: str | None
    simulation_only: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if not isinstance(self.phase, MotionPhase):
            object.__setattr__(self, "phase", MotionPhase(self.phase))
        if self.tip_point_board is not None and self.tip_point_board.frame != "board":
            raise ValueError("tip point must be in the board frame")
        if self.simulation_only is not True:
            raise ValueError("geometric path steps are always simulation-only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "phase": self.phase.value,
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "tip_point_board_mm": (
                None
                if self.tip_point_board is None
                else [self.tip_point_board.x, self.tip_point_board.y, self.tip_point_board.z]
            ),
            "check_id": self.check_id,
            "simulation_only": True,
        }


@dataclass(frozen=True, slots=True)
class GeometricSimulationReport:
    plan_hash: str
    snapshot_hash: str
    hardware_profile_hash: str
    target_profile_sha256: str
    scene_source_hashes: Mapping[str, str]
    transit_plane_z_mm: float
    steps: tuple[GeometricPathStep, ...]
    checks: tuple[GeometricPathCheck, ...]
    assumptions: tuple[str, ...]
    schema: str = "rocell.geometric_simulation.v1"

    def __post_init__(self) -> None:
        source_hashes = dict(self.scene_source_hashes)
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in source_hashes.items()
        ):
            raise TypeError("scene_source_hashes must map strings to strings")
        object.__setattr__(
            self,
            "scene_source_hashes",
            MappingProxyType(source_hashes),
        )
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))

    @property
    def all_checks_pass(self) -> bool:
        return bool(self.checks) and all(check.status == "PASS" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "scope": "NOMINAL_TARGET_AND_TOOL_TIP_AABB_PATH_ONLY",
            "plan_hash": self.plan_hash,
            "snapshot_hash": self.snapshot_hash,
            "hardware_profile_hash": self.hardware_profile_hash,
            "target_profile_sha256": self.target_profile_sha256,
            "scene_source_hashes": dict(sorted(self.scene_source_hashes.items())),
            "transit_plane_z_mm": self.transit_plane_z_mm,
            "all_checks_pass": self.all_checks_pass,
            "steps": [step.to_dict() for step in self.steps],
            "checks": [check.to_dict() for check in self.checks],
            "assumptions": list(self.assumptions),
        }

    @property
    def report_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class GeometricDryRunEngine:
    """Produce a collision-checked nominal tool-tip path without hardware I/O."""

    def __init__(self, settings: GeometricSimulationSettings | None = None) -> None:
        self.settings = settings or GeometricSimulationSettings()

    @staticmethod
    def _ignored_for_target(target: TargetRegion) -> tuple[str, ...]:
        if target.device == "keyboard":
            return ("keyboard", "station:keyboard_left", "station:keyboard_right")
        if target.device == "phone":
            return ("phone", "station:phone_tcp")
        raise GeometricSimulationError(f"Unsupported target device {target.device!r}")

    @staticmethod
    def _semantic_target(action: PressKey | TapPhoneTarget) -> tuple[str, str]:
        if isinstance(action, PressKey):
            return "keyboard", action.key_id
        return "phone", action.target_id

    def run(
        self,
        plan: ActionPlan,
        snapshot: BuildSnapshot,
        profile: SimulationHardwareProfile,
        scene: NominalWorkcellScene,
        targets: NominalTargetCatalog,
    ) -> GeometricSimulationReport:
        if not isinstance(plan, ActionPlan):
            raise TypeError("plan must be an ActionPlan")
        if not isinstance(snapshot, BuildSnapshot):
            raise TypeError("snapshot must be a BuildSnapshot")
        if not isinstance(profile, SimulationHardwareProfile):
            raise TypeError("profile must be a SimulationHardwareProfile")
        if not isinstance(scene, NominalWorkcellScene):
            raise TypeError("scene must be a NominalWorkcellScene")
        if not isinstance(targets, NominalTargetCatalog):
            raise TypeError("targets must be a NominalTargetCatalog")
        if profile.hardware_io_allowed or profile.can_release_physical_gates:
            raise GeometricSimulationError("Simulation profile unexpectedly carries authority")
        if profile.design_revision != scene.design_revision or profile.design_revision != targets.design_revision:
            raise GeometricSimulationError("Simulation sources use different design revisions")
        bound_semantic_profile = targets.semantic_profile_id_for(plan.device.value)
        if plan.profile_id != bound_semantic_profile:
            raise GeometricSimulationError(
                "Action-plan profile is not bound to the selected target geometry: "
                f"plan={plan.profile_id!r}, target_binding={bound_semantic_profile!r}"
            )
        preflight = SafetySupervisor(snapshot).evaluate(
            Capability.SIMULATED_DRY_RUN,
            plan_hash=plan.plan_hash,
        )
        if not preflight.allowed:
            raise GeometricSimulationError(
                "Simulation preflight failed: " + "; ".join(preflight.blockers)
            )

        settings = self.settings
        highest_obstacle_z = max(obstacle.maximum.z for obstacle in scene.obstacles)
        transit_z = highest_obstacle_z + settings.clearance_above_highest_obstacle_mm
        if not math.isfinite(transit_z):
            raise GeometricSimulationError("Transit plane is non-finite")
        current = Point3Mm(
            "board", settings.park_xy_board_mm[0], settings.park_xy_board_mm[1], transit_z
        )
        current_local_ignored: tuple[str, ...] = ()
        steps: list[GeometricPathStep] = []
        checks: list[GeometricPathCheck] = []

        def append_step(
            phase: MotionPhase,
            action_index: int | None,
            semantic_target: str | None,
            point: Point3Mm | None,
            check_id: str | None,
        ) -> None:
            steps.append(GeometricPathStep(len(steps), phase, action_index, semantic_target, point, check_id))

        def check_segment(
            start: Point3Mm,
            end: Point3Mm,
            *,
            ignored: Iterable[str] = (),
            label: str,
        ) -> str:
            ignored_tuple = tuple(ignored)
            result = scene.check_segment_clearance(
                start,
                end,
                clearance_mm=settings.segment_clearance_mm,
                ignored_obstacle_ids=ignored_tuple,
            )
            check_id = f"segment-{len(checks):04d}-{label}"
            checks.append(
                GeometricPathCheck(
                    check_id,
                    "PASS" if result.clear else "FAIL",
                    result.colliding_obstacle_ids,
                    ignored_tuple,
                    result.method,
                )
            )
            return check_id

        append_step(MotionPhase.PARK, None, None, current, None)
        for action_index, action in enumerate(plan.actions):
            if isinstance(action, VerifyPhoneState):
                append_step(MotionPhase.VERIFY, action_index, f"phone_state:{action.state_id}", current, None)
                continue
            if not isinstance(action, (PressKey, TapPhoneTarget)):
                raise GeometricSimulationError(f"Unsupported action {type(action).__name__}")
            device, target_id = self._semantic_target(action)
            try:
                target = targets.resolve(device, target_id)
            except TargetMapError as exc:
                raise GeometricSimulationError(str(exc)) from exc
            semantic_target = f"{device}:{target_id}"
            ignored = self._ignored_for_target(target)
            transit = Point3Mm("board", target.center.x, target.center.y, transit_z)
            hover = Point3Mm("board", target.center.x, target.center.y, target.center.z + settings.hover_height_mm)
            approach = Point3Mm("board", target.center.x, target.center.y, target.center.z + settings.approach_height_mm)
            contact = Point3Mm("board", target.center.x, target.center.y, target.center.z - settings.contact_overtravel_mm)

            if current.z < transit_z:
                ascent = Point3Mm("board", current.x, current.y, transit_z)
                check_id = check_segment(
                    current,
                    ascent,
                    ignored=current_local_ignored,
                    label="ascent-to-transit",
                )
                append_step(MotionPhase.TRANSIT, action_index, semantic_target, ascent, check_id)
                current = ascent
                current_local_ignored = ()
            check_id = check_segment(current, transit, label="transit")
            append_step(MotionPhase.TRANSIT, action_index, semantic_target, transit, check_id)
            check_id = check_segment(transit, hover, ignored=ignored, label="descent-to-hover")
            append_step(MotionPhase.HOVER, action_index, semantic_target, hover, check_id)
            append_step(MotionPhase.VISION_CORRECT, action_index, semantic_target, hover, None)
            check_id = check_segment(hover, approach, ignored=ignored, label="approach")
            append_step(MotionPhase.APPROACH, action_index, semantic_target, approach, check_id)

            target_device = scene.devices[device]
            expected_contact = target_device.envelope.contains(contact)
            contact_clearance = scene.check_point_clearance(
                contact,
                clearance_mm=0.0,
                ignored_obstacle_ids=ignored,
            )
            contact_collisions = list(contact_clearance.colliding_obstacle_ids)
            contact_segment_clearance = scene.check_segment_clearance(
                approach,
                contact,
                clearance_mm=0.0,
                ignored_obstacle_ids=ignored,
            )
            contact_collisions.extend(contact_segment_clearance.colliding_obstacle_ids)
            if not expected_contact:
                contact_collisions.append(f"EXPECTED_{device.upper()}_CONTACT_NOT_REACHED")
            contact_check_id = f"contact-{len(checks):04d}-{device}"
            checks.append(
                GeometricPathCheck(
                    contact_check_id,
                    "PASS" if not contact_collisions else "FAIL",
                    tuple(sorted(set(contact_collisions))),
                    ignored,
                    "expected_target_envelope_plus_contact_segment_aabb_exclusion",
                )
            )
            append_step(MotionPhase.CONTACT, action_index, semantic_target, contact, contact_check_id)
            check_id = check_segment(contact, hover, ignored=ignored, label="retract")
            append_step(MotionPhase.RETRACT, action_index, semantic_target, hover, check_id)
            append_step(MotionPhase.VERIFY, action_index, semantic_target, hover, None)
            current = hover
            current_local_ignored = ignored

        park = Point3Mm("board", settings.park_xy_board_mm[0], settings.park_xy_board_mm[1], transit_z)
        if current != park:
            vertical = Point3Mm("board", current.x, current.y, transit_z)
            check_id = check_segment(
                current,
                vertical,
                ignored=current_local_ignored,
                label="final-ascent",
            )
            append_step(MotionPhase.TRANSIT, None, None, vertical, check_id)
            check_id = check_segment(vertical, park, label="return-park")
            append_step(MotionPhase.PARK, None, None, park, check_id)
        else:
            append_step(MotionPhase.PARK, None, None, park, None)
        append_step(MotionPhase.COMPLETE, None, None, park, None)

        report = GeometricSimulationReport(
            plan_hash=plan.plan_hash,
            snapshot_hash=snapshot.snapshot_hash,
            hardware_profile_hash=profile.profile_hash,
            target_profile_sha256=targets.content_sha256,
            scene_source_hashes=dict(scene.source_hashes),
            transit_plane_z_mm=transit_z,
            steps=tuple(steps),
            checks=tuple(checks),
            assumptions=(
                *scene.assumptions,
                "Only the tool-tip centreline is checked; robot links, gripper/tool volume, camera holder, moving USB cable, compliance, and uncertainty are not represented.",
                "Target centres and safe rectangles are synthetic nominal seeds, not measured key or screen calibrations.",
                "Expected target-device and coarse station proxies are ignored only during the vertical local descent/retract corridor.",
            ),
        )
        return report
