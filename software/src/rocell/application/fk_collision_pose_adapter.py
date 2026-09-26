"""Derive collision poses from exact IK results and the pinned URDF.

Robot-link transforms are recomputed here; callers cannot override them.
Measured rigid attachments are expressed once as fixed transforms from a pinned
URDF link, then composed at every waypoint.  Configuration-sampled bodies
(notably the moving camera cable) remain explicit per-waypoint evidence.

The resulting samples feed the discrete collision boundary and retain its
continuous-sweep blocker.  This module performs no hardware access and creates
no execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.calibration import PlannerCalibrationSnapshot
from rocell.geometry import JointPosition, RigidTransform
from rocell.kinematics import ARM_JOINT_NAMES
from rocell.simulation.collision import (
    CollisionBindingMode,
    CollisionEvidenceState,
    CollisionPose,
    SampledCollisionGeometry,
)

from ._pinned_model import load_pinned_urdf
from .collision_readiness import assess_current_collision_readiness
from .context import SimulationContext, revalidate_simulation_context
from .installed_collision_geometry import InstalledCollisionGeometryProfile
from .measured_waypoint_collision_sequence import (
    MAX_WAYPOINT_COLLISION_SAMPLES,
    MeasuredWaypointCollisionSample,
    evaluate_measured_waypoint_collision_sequence,
)
from .measured_trajectory_screening import SCHEMA as TRAJECTORY_SCREENING_SCHEMA


SCHEMA = "rocell.fk_derived_waypoint_collision_sequence.v1"


class FkCollisionPoseAdapterError(ValueError):
    """FK or attachment evidence cannot reproduce every required pose."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FkCollisionPoseAdapterError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class MeasuredRigidAttachmentBinding:
    """A measured fixed transform from one pinned URDF link to an attachment."""

    parent_frame: str
    anchor_link_frame: str
    anchor_t_parent: RigidTransform
    source_sha256: str
    source_reference: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.parent_frame, "parent_frame"),
            (self.anchor_link_frame, "anchor_link_frame"),
            (self.source_reference, "source_reference"),
        ):
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise FkCollisionPoseAdapterError(f"{label} must be nonempty unpadded text")
        if not isinstance(self.anchor_t_parent, RigidTransform):
            raise TypeError("anchor_t_parent must be a RigidTransform")
        if (
            self.anchor_t_parent.parent_frame != self.anchor_link_frame
            or self.anchor_t_parent.child_frame != self.parent_frame
        ):
            raise FkCollisionPoseAdapterError(
                "attachment transform frames differ from its anchor/parent declaration"
            )
        _digest(self.source_sha256, "source_sha256")

    @property
    def content_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_frame": self.parent_frame,
            "anchor_link_frame": self.anchor_link_frame,
            "anchor_t_parent": {
                "parent_frame": self.anchor_t_parent.parent_frame,
                "child_frame": self.anchor_t_parent.child_frame,
                "rotation_row_major": list(self.anchor_t_parent.rotation.matrix),
                "translation_mm": [
                    self.anchor_t_parent.translation_mm.x,
                    self.anchor_t_parent.translation_mm.y,
                    self.anchor_t_parent.translation_mm.z,
                ],
            },
            "source_sha256": self.source_sha256,
            "source_reference": self.source_reference,
        }


@dataclass(frozen=True, slots=True)
class MeasuredConfigurationGeometryBinding:
    """One pose-local deformable geometry sample with profile-bound provenance."""

    body_id: str
    geometry: SampledCollisionGeometry
    source_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.body_id, str)
            or not self.body_id.strip()
            or self.body_id != self.body_id.strip()
        ):
            raise FkCollisionPoseAdapterError("body_id must be nonempty unpadded text")
        if not isinstance(self.geometry, SampledCollisionGeometry):
            raise TypeError("geometry must be SampledCollisionGeometry")
        if self.geometry.evidence_state is not CollisionEvidenceState.ACCEPTED_MEASURED:
            raise FkCollisionPoseAdapterError(
                "configuration geometry must be accepted measured evidence"
            )
        _digest(self.source_sha256, "source_sha256")

    @property
    def content_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_id": self.body_id,
            "geometry": self.geometry.to_dict(),
            "source_sha256": self.source_sha256,
        }


def _trajectory(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FkCollisionPoseAdapterError("trajectory_screening must be an object")
    document = dict(value)
    digest = document.pop("trajectory_screening_sha256", None)
    if document.get("schema") != TRAJECTORY_SCREENING_SCHEMA:
        raise FkCollisionPoseAdapterError("trajectory screening schema mismatch")
    if not isinstance(digest, str) or digest != _sha256(document):
        raise FkCollisionPoseAdapterError("trajectory screening hash is invalid")
    return dict(value)


def _bounded_sequence(values: Sequence[Any], label: str) -> tuple[Any, ...]:
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise TypeError(f"{label} must be a finite sequence") from exc
    result: list[Any] = []
    for _ in range(MAX_WAYPOINT_COLLISION_SAMPLES + 1):
        try:
            result.append(next(iterator))
        except StopIteration:
            return tuple(result)
    raise FkCollisionPoseAdapterError(f"{label} exceeds the hard maximum")


def derive_and_evaluate_fk_waypoint_collisions(
    context: SimulationContext,
    snapshot: PlannerCalibrationSnapshot,
    installed_profile: InstalledCollisionGeometryProfile,
    trajectory_screening: Mapping[str, Any],
    attachment_bindings: Sequence[MeasuredRigidAttachmentBinding],
    configuration_geometry_by_waypoint: Sequence[
        Mapping[str, MeasuredConfigurationGeometryBinding]
    ],
) -> dict[str, Any]:
    """Recompute rigid transforms and evaluate every discrete planner waypoint."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    if not isinstance(snapshot, PlannerCalibrationSnapshot):
        raise TypeError("snapshot must be a PlannerCalibrationSnapshot")
    if not isinstance(installed_profile, InstalledCollisionGeometryProfile):
        raise TypeError("installed_profile must be InstalledCollisionGeometryProfile")
    revalidate_simulation_context(context)
    route = _trajectory(trajectory_screening)
    readiness = assess_current_collision_readiness(context)
    if (
        snapshot.snapshot_sha256 != route.get("calibration_snapshot_sha256")
        or snapshot.manifest_id != context.snapshot.manifest_id
        or snapshot.active_build_id != context.snapshot.active_build_id
        or installed_profile.manifest_id != context.snapshot.manifest_id
        or installed_profile.manifest_sha256 != context.snapshot.manifest_sha256
        or installed_profile.active_build_id != context.snapshot.active_build_id
        or installed_profile.build_snapshot_sha256 != context.snapshot.snapshot_hash
        or installed_profile.robot_model_sha256 != context.scenario.model_sha256
        or installed_profile.base_contract_sha256 != readiness.contract.content_hash
        or route.get("build_snapshot_sha256") != context.snapshot.snapshot_hash
        or route.get("kinematic_model_sha256") != context.scenario.model_sha256
    ):
        raise FkCollisionPoseAdapterError(
            "context, calibration, collision profile, and trajectory lineage differ"
        )
    if not route.get("ik_all_waypoints_accepted"):
        raise FkCollisionPoseAdapterError("an all-accepted IK route is required")
    waypoints = route.get("waypoints")
    joint_results = route.get("joint_results")
    if not isinstance(waypoints, list) or not isinstance(joint_results, list):
        raise FkCollisionPoseAdapterError("trajectory waypoint collections are invalid")
    if not waypoints or len(waypoints) != len(joint_results):
        raise FkCollisionPoseAdapterError("trajectory waypoint collections are incomplete")
    if len(waypoints) > MAX_WAYPOINT_COLLISION_SAMPLES:
        raise FkCollisionPoseAdapterError("trajectory exceeds collision waypoint cap")

    model = load_pinned_urdf(
        context.scenario.model_path, context.scenario.model_sha256
    ).model
    board_t_world = RigidTransform(
        "board",
        model.root_link,
        snapshot.board_T_vendor_world.rotation,
        snapshot.board_T_vendor_world.translation_mm,
    )
    bindings = _bounded_sequence(attachment_bindings, "attachment_bindings")
    accepted_source_hashes = set(installed_profile.source_bindings.values())
    binding_by_parent: dict[str, MeasuredRigidAttachmentBinding] = {}
    for binding in bindings:
        if not isinstance(binding, MeasuredRigidAttachmentBinding):
            raise TypeError("attachment_bindings contains an invalid value")
        if binding.parent_frame in binding_by_parent:
            raise FkCollisionPoseAdapterError("attachment parent frames must be unique")
        if binding.anchor_link_frame not in model.link_names:
            raise FkCollisionPoseAdapterError("attachment anchor is absent from pinned URDF")
        if binding.parent_frame in model.link_names or binding.parent_frame == "board":
            raise FkCollisionPoseAdapterError(
                "attachment bindings cannot override URDF or root transforms"
            )
        if binding.source_sha256 not in accepted_source_hashes:
            raise FkCollisionPoseAdapterError(
                "attachment binding source is absent from installed profile"
            )
        binding_by_parent[binding.parent_frame] = binding

    rigid_parent_frames = {
        body.parent_frame
        for body in installed_profile.contract.bodies
        if body.binding_mode is CollisionBindingMode.RIGID_FRAME
    }
    required_attachment_frames = rigid_parent_frames - set(model.link_names)
    if set(binding_by_parent) != required_attachment_frames:
        raise FkCollisionPoseAdapterError(
            "attachment bindings do not exactly cover non-URDF rigid frames"
        )
    configurations = _bounded_sequence(
        configuration_geometry_by_waypoint, "configuration_geometry_by_waypoint"
    )
    if len(configurations) != len(waypoints):
        raise FkCollisionPoseAdapterError(
            "configuration geometry must cover every planner waypoint"
        )
    required_configuration_ids = {
        body.body_id
        for body in installed_profile.contract.bodies
        if body.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED
    }

    samples: list[MeasuredWaypointCollisionSample] = []
    derived_pose_records: list[dict[str, Any]] = []
    movable = set(model.movable_joint_names)
    arm_names = set(ARM_JOINT_NAMES)
    remaining = movable - arm_names
    if len(remaining) != 1:
        raise FkCollisionPoseAdapterError(
            "pinned URDF must have exactly one non-arm movable gripper joint"
        )
    gripper_name = next(iter(remaining))
    for index, (waypoint, joint_result, configuration) in enumerate(
        zip(waypoints, joint_results, configurations, strict=True)
    ):
        if (
            not isinstance(waypoint, Mapping)
            or waypoint.get("sequence") != index
            or not isinstance(joint_result, Mapping)
            or joint_result.get("waypoint_sequence") != index
            or joint_result.get("accepted") is not True
        ):
            raise FkCollisionPoseAdapterError(
                f"waypoint {index} is not an accepted canonical IK result"
            )
        solution = joint_result.get("solution_arm_joint_positions_rad")
        if not isinstance(solution, Mapping) or set(solution) != arm_names:
            raise FkCollisionPoseAdapterError(
                f"waypoint {index} arm joint solution is incomplete"
            )
        joint_positions: dict[str, JointPosition] = {}
        for name in ARM_JOINT_NAMES:
            value = solution[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise FkCollisionPoseAdapterError(
                    f"waypoint {index} joint {name} is not numeric"
                )
            number = float(value)
            if not math.isfinite(number):
                raise FkCollisionPoseAdapterError(
                    f"waypoint {index} joint {name} is not finite"
                )
            joint_positions[name] = JointPosition.radians(number)
        joint_positions[gripper_name] = context.scenario.fixed_gripper_position
        world_transforms = model.forward_kinematics(joint_positions)
        all_model_root_transforms = {
            frame: board_t_world.compose(transform)
            for frame, transform in world_transforms.items()
        }
        root_transforms = {
            frame: all_model_root_transforms[frame]
            for frame in rigid_parent_frames & set(model.link_names)
        }
        attachment_hashes: dict[str, str] = {}
        for frame, binding in sorted(binding_by_parent.items()):
            root_transforms[frame] = all_model_root_transforms[
                binding.anchor_link_frame
            ].compose(binding.anchor_t_parent)
            attachment_hashes[frame] = binding.content_sha256
        if not isinstance(configuration, Mapping) or set(configuration) != required_configuration_ids:
            raise FkCollisionPoseAdapterError(
                f"waypoint {index} configuration geometry coverage differs"
            )
        sampled_geometry: dict[str, SampledCollisionGeometry] = {}
        configuration_binding_hashes: dict[str, str] = {}
        for body_id, binding in configuration.items():
            if not isinstance(binding, MeasuredConfigurationGeometryBinding):
                raise TypeError(
                    "configuration geometry values must be measured bindings"
                )
            if binding.body_id != body_id:
                raise FkCollisionPoseAdapterError(
                    f"waypoint {index} configuration body key differs from binding"
                )
            if binding.source_sha256 not in accepted_source_hashes:
                raise FkCollisionPoseAdapterError(
                    f"waypoint {index} configuration source is absent from installed profile"
                )
            sampled_geometry[body_id] = binding.geometry
            configuration_binding_hashes[body_id] = binding.content_sha256
        for body in installed_profile.contract.bodies:
            if body.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED:
                if body.parent_frame == installed_profile.contract.root_frame:
                    transform = RigidTransform.identity(body.parent_frame)
                elif body.parent_frame in all_model_root_transforms:
                    transform = all_model_root_transforms[body.parent_frame]
                elif body.parent_frame in binding_by_parent:
                    transform = root_transforms[body.parent_frame]
                else:
                    raise FkCollisionPoseAdapterError(
                        f"waypoint {index} cannot derive configuration parent frame"
                    )
                root_transforms.setdefault(body.parent_frame, transform)
        pose = CollisionPose(
            f"waypoint-{index:04d}",
            installed_profile.contract.root_frame,
            root_transforms,
            sampled_geometry,
        )
        sample = MeasuredWaypointCollisionSample(
            index, _sha256(waypoint), _sha256(joint_result), pose
        )
        samples.append(sample)
        derived_pose_records.append(
            {
                "waypoint_sequence": index,
                "pose_sha256": pose.content_hash,
                "joint_result_sha256": _sha256(joint_result),
                "urdf_derived_frames": sorted(
                    rigid_parent_frames & set(model.link_names)
                ),
                "attachment_binding_sha256_by_frame": attachment_hashes,
                "configuration_geometry_sha256_by_body": {
                    body_id: configuration_binding_hashes[body_id]
                    for body_id in sorted(configuration_binding_hashes)
                },
            }
        )

    collision = evaluate_measured_waypoint_collision_sequence(
        installed_profile, route, tuple(samples)
    )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": collision["status"],
        "trajectory_screening_sha256": route["trajectory_screening_sha256"],
        "calibration_snapshot_sha256": snapshot.snapshot_sha256,
        "installed_collision_profile_sha256": installed_profile.content_sha256,
        "kinematic_model_sha256": context.scenario.model_sha256,
        "attachment_bindings": [item.to_dict() for item in bindings],
        "derived_pose_records": derived_pose_records,
        "collision_sequence": collision,
        "robot_link_transforms_recomputed_from_joint_results": True,
        "caller_robot_link_transform_overrides_accepted": False,
        "continuous_collision_proven": False,
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {**report, "fk_collision_sequence_sha256": _sha256(report)}
