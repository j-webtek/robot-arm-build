"""Honest isolated-geometry fixture for dense static-camera mission tests.

This fixture lets the complete 26-body/nine-source collision query, ordinal
mapping, intended-contact exception, and midpoint coverage run before measured
link/support/cable geometry exists.  It intentionally places unmodelled robot
links and attachments in isolated locations.  Therefore a passing report says
that the *collision software contract* works; it does not say the RoArm route
is physically clear.

Keeping this fixture in its own explicitly named module prevents test geometry
from being confused with the future URDF-FK and surveyed-workcell adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from rocell.application.trajectory_simulation import TrajectorySimulationReport
from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.targets import load_nominal_target_catalog

from .collision import (
    CollisionBindingMode,
    CollisionClearanceEvidenceState,
    CollisionClearancePolicy,
    CollisionEvaluationPolicy,
    CollisionPose,
    OrientedBoxMm,
    SampledCollisionGeometry,
    SphereMm,
)
from .static_mission_route import (
    StaticMissionEndpointPose,
    StaticMissionIncomingMidpointPose,
    StaticMissionRouteCollisionReport,
    evaluate_static_b0477_mission_route,
)
from .static_route_collision import (
    REQUIRED_STATIC_ROUTE_SOURCE_KEYS,
    STATIC_ROUTE_BODY_REQUIREMENTS,
    StaticB0477RouteCollisionContract,
    StaticRouteBody,
    StaticRouteBodyRole,
    StaticRouteCollisionPolicy,
    StaticRouteGeometryProvenance,
    StaticRouteSourceBinding,
    StaticRouteTargetBinding,
    bind_static_route_target,
)


ISOLATED_STATIC_MISSION_FIXTURE_ID = (
    "isolated-static-b0477-binding-fixture-v1"
)
ISOLATED_STATIC_MISSION_GEOMETRY_SCOPE = (
    "SOFTWARE_BINDING_FIXTURE_NOT_WORKCELL_CLEARANCE_GEOMETRY"
)
MAX_ISOLATED_IK_CONTACT_ASSOCIATION_TOLERANCE_MM = 0.5


class StaticMissionFixtureError(ValueError):
    """The local source-bound diagnostic fixture cannot be assembled."""


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise StaticMissionFixtureError(f"fixture source is missing or unsafe: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source_hashes(
    workspace: Path, trajectory: TrajectorySimulationReport
) -> dict[str, str]:
    provenance = dict(trajectory.source_provenance)
    required = ("model_sha256", "target_profile_sha256")
    if any(key not in provenance for key in required):
        raise StaticMissionFixtureError("trajectory provenance lacks model/target hashes")
    files = {
        "workcell_layout": (
            workspace
            / "active-project/RoCell_v0_3/config/workcell_layout.json"
        ),
        "target_profile": workspace / "software/config/nominal_target_profiles.json",
        "static_support_design": (
            workspace / "hardware/static_overhead_camera/config/support_design.json"
        ),
        "camera_profile": (
            workspace
            / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
        ),
        "camera_bom": workspace / "hardware/static_overhead_camera/BOM.csv",
        "camera_architecture": workspace / "software/config/camera_architecture_plan.json",
        "system_manifest": workspace / "software/config/system_manifest.json",
    }
    file_hashes = {name: _file_sha256(path) for name, path in files.items()}
    if file_hashes["target_profile"] != provenance["target_profile_sha256"]:
        # The trajectory binds the canonical decoded target profile rather than
        # raw file bytes.  Retain the trajectory digest as the collision source
        # and record raw file provenance inside the composite fixture hashes.
        pass
    values = {
        "robot_model": str(provenance["model_sha256"]),
        "workcell_layout": file_hashes["workcell_layout"],
        "target_profile": str(provenance["target_profile_sha256"]),
        "static_support_design": file_hashes["static_support_design"],
        "b0477_mechanical_design": _canonical_hash(
            {
                "camera_profile_file_sha256": file_hashes["camera_profile"],
                "bom_file_sha256": file_hashes["camera_bom"],
                "geometry_status": ISOLATED_STATIC_MISSION_GEOMETRY_SCOPE,
            }
        ),
        "fixed_usb_route_design": _canonical_hash(
            {
                "support_sha256": file_hashes["static_support_design"],
                "architecture_sha256": file_hashes["camera_architecture"],
                "route_geometry_measured": False,
            }
        ),
        "lighting_design": _canonical_hash(
            {
                "bom_sha256": file_hashes["camera_bom"],
                "lighting_geometry_measured": False,
            }
        ),
        "arm_harness_design": _canonical_hash(
            {
                "manifest_sha256": file_hashes["system_manifest"],
                "harness_geometry_measured": False,
                "fixture_only": True,
            }
        ),
        "contact_tool_design": _canonical_hash(
            {
                "manifest_sha256": file_hashes["system_manifest"],
                "tool_geometry_measured": False,
                "fixture_only": True,
            }
        ),
    }
    if set(values) != set(REQUIRED_STATIC_ROUTE_SOURCE_KEYS):
        raise StaticMissionFixtureError("fixture source closure does not contain nine keys")
    return values


def _ik_contact_association_tolerance_mm(
    trajectory: TrajectorySimulationReport,
) -> float:
    """Use the exact solver acceptance tolerance already bound by the route.

    This tolerance only associates a final CONTACT result with its nominal
    target inside isolated software geometry.  It is not a physical placement
    tolerance, target safe inset, or clearance allowance.
    """

    provenance = dict(trajectory.source_provenance)
    try:
        options = dict(provenance["ik_options"])
        raw_tolerance = options["position_tolerance_mm"]
    except (KeyError, TypeError, ValueError) as exc:
        raise StaticMissionFixtureError(
            "trajectory provenance lacks a usable IK position tolerance"
        ) from exc
    if (
        isinstance(raw_tolerance, bool)
        or not isinstance(raw_tolerance, (int, float))
        or not math.isfinite(float(raw_tolerance))
    ):
        raise StaticMissionFixtureError(
            "trajectory IK position tolerance must be finite"
        )
    tolerance = float(raw_tolerance)
    if not 0.0 < tolerance <= MAX_ISOLATED_IK_CONTACT_ASSOCIATION_TOLERANCE_MM:
        raise StaticMissionFixtureError(
            "trajectory IK position tolerance exceeds the isolated fixture bound"
        )
    return tolerance


def _body_primitive(index: int, role: StaticRouteBodyRole):
    # These three surfaces match the nominal software target planes.  They are
    # used to test exact contact allowance and required-contact behavior.
    if role is StaticRouteBodyRole.KEYBOARD:
        return OrientedBoxMm(
            Vec3(242.5, 158.5, 10.5), Vec3(157.5, 73.5, 10.5)
        )
    if role is StaticRouteBodyRole.PHONE:
        return OrientedBoxMm(
            Vec3(538.15, 166.4, 5.95), Vec3(38.95, 82.2, 5.95)
        )
    if role is StaticRouteBodyRole.BOARD:
        return OrientedBoxMm(
            Vec3(305.0, 228.5, -2.0), Vec3(305.0, 228.5, 2.0)
        )
    if role is StaticRouteBodyRole.TOOL_TIP:
        return SphereMm(Vec3.zero(), 0.4)
    if role in {
        StaticRouteBodyRole.ROARM_BASE,
        StaticRouteBodyRole.ROARM_LINK,
        StaticRouteBodyRole.ROARM_GRIPPER,
        StaticRouteBodyRole.CONTACT_TOOL_BODY,
    }:
        return SphereMm(Vec3.zero(), 0.25)
    # Isolation is the defining limitation of this fixture.  Real support,
    # camera, light, cable, and link geometry must replace these placeholders.
    return SphereMm(Vec3(2000.0 + 20.0 * index, 2000.0, 2000.0), 0.25)


def _bodies() -> tuple[StaticRouteBody, ...]:
    values: list[StaticRouteBody] = []
    for index, requirement in enumerate(STATIC_ROUTE_BODY_REQUIREMENTS):
        primitives = (
            ()
            if requirement.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED
            else (_body_primitive(index, requirement.role),)
        )
        values.append(
            StaticRouteBody(
                body_id=requirement.body_id,
                parent_frame=requirement.parent_frame,
                role=requirement.role,
                binding_mode=requirement.binding_mode,
                provenance=StaticRouteGeometryProvenance.CONSERVATIVE_SYNTHETIC,
                source_key=requirement.source_key,
                source_reference=(
                    "isolated software-binding fixture; not installed-workcell geometry"
                ),
                primitives=primitives,
            )
        )
    return tuple(values)


def _rotation_with_z_axis(raw_axis: tuple[float, float, float]) -> Rotation3:
    z_axis = Vec3.from_iterable(raw_axis).normalized()
    reference = (
        Vec3(1.0, 0.0, 0.0)
        if abs(z_axis.x) < 0.9
        else Vec3(0.0, 1.0, 0.0)
    )
    x_axis = (reference - z_axis.scaled(reference.dot(z_axis))).normalized()
    y_axis = z_axis.cross(x_axis).normalized()
    return Rotation3(
        (
            x_axis.x,
            y_axis.x,
            z_axis.x,
            x_axis.y,
            y_axis.y,
            z_axis.y,
            x_axis.z,
            y_axis.z,
            z_axis.z,
        )
    )


def _pose(
    pose_id: str,
    tool_tip: Vec3,
    *,
    tool_rotation: Rotation3 = Rotation3.identity(),
) -> CollisionPose:
    transforms: dict[str, RigidTransform] = {}
    isolated_index = 0
    for requirement in STATIC_ROUTE_BODY_REQUIREMENTS:
        if requirement.binding_mode is CollisionBindingMode.STATIC_ROOT:
            continue
        if requirement.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED:
            point = Vec3(-4000.0, -4000.0, 1000.0)
            rotation = Rotation3.identity()
        elif requirement.role is StaticRouteBodyRole.TOOL_TIP:
            point = tool_tip
            rotation = tool_rotation
        elif requirement.role is StaticRouteBodyRole.CONTACT_TOOL_BODY:
            point = tool_tip + Vec3(0.0, 0.0, 15.0)
            rotation = Rotation3.identity()
        else:
            point = Vec3(-2000.0 - 20.0 * isolated_index, -2000.0, 1000.0)
            rotation = Rotation3.identity()
            isolated_index += 1
        transforms[requirement.parent_frame] = RigidTransform(
            "board", requirement.parent_frame, rotation, point
        )
    return CollisionPose(
        pose_id,
        "board",
        transforms,
        {
            "attachment:arm_harness": SampledCollisionGeometry(
                (SphereMm(Vec3.zero(), 0.3),),
                StaticRouteGeometryProvenance.CONSERVATIVE_SYNTHETIC.collision_evidence_state,
                "fresh isolated per-pose fixture; physical harness shape unmeasured",
            )
        },
    )


@dataclass(frozen=True, slots=True)
class IsolatedStaticMissionFixture:
    """Complete caller inputs plus the resulting dense collision report."""

    contract: StaticB0477RouteCollisionContract
    policy: StaticRouteCollisionPolicy
    target_bindings: tuple[StaticRouteTargetBinding, ...]
    endpoint_poses: tuple[StaticMissionEndpointPose, ...]
    incoming_midpoint_poses: tuple[StaticMissionIncomingMidpointPose, ...]
    report: StaticMissionRouteCollisionReport
    geometry_scope: str = ISOLATED_STATIC_MISSION_GEOMETRY_SCOPE

    def __post_init__(self) -> None:
        if self.geometry_scope != ISOLATED_STATIC_MISSION_GEOMETRY_SCOPE:
            raise StaticMissionFixtureError("fixture geometry scope was promoted")
        if self.report.contract != self.contract or self.report.policy != self.policy:
            raise StaticMissionFixtureError(
                "fixture report differs from its contract or policy"
            )
        if self.report.target_bindings != self.target_bindings:
            raise StaticMissionFixtureError(
                "fixture report differs from its target bindings"
            )
        if tuple(item.endpoint for item in self.report.endpoint_results) != (
            self.endpoint_poses
        ):
            raise StaticMissionFixtureError(
                "fixture report differs from its endpoint inputs"
            )
        if tuple(item.midpoint for item in self.report.midpoint_results) != (
            self.incoming_midpoint_poses
        ):
            raise StaticMissionFixtureError(
                "fixture report differs from its midpoint inputs"
            )
        if not self.report.passed_diagnostic:
            raise StaticMissionFixtureError("isolated collision contract did not pass")
        if len(self.endpoint_poses) != len(self.report.endpoint_results):
            raise StaticMissionFixtureError("fixture endpoint/report coverage differs")
        if len(self.incoming_midpoint_poses) != len(self.report.midpoint_results):
            raise StaticMissionFixtureError("fixture midpoint/report coverage differs")

    def assert_matches_trajectory(
        self,
        trajectory: TrajectorySimulationReport,
        *,
        recompute_collision: bool = False,
    ) -> None:
        """Validate and optionally recompute this exact fixture/route pairing."""

        self.__post_init__()
        self.report.assert_matches_trajectory(
            trajectory,
            recompute_collision=recompute_collision,
        )

    def assert_current_sources(
        self,
        workspace_root: Path,
        trajectory: TrajectorySimulationReport,
    ) -> None:
        """Re-hash every additive static-camera fixture source in place.

        An assembly is an immutable snapshot, but prepare/open/run must also
        refuse silently stale camera/support/BOM inputs in the active build.
        This is a read-only source-closure check and grants no physical status.
        """

        self.__post_init__()
        workspace = Path(workspace_root).resolve()
        current = _source_hashes(workspace, trajectory)
        if dict(self.contract.sources.source_hashes) != current:
            raise StaticMissionFixtureError(
                "isolated static mission fixture sources changed after assembly"
            )

    @property
    def fixture_sha256(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.isolated_static_mission_fixture.v1",
            "fixture_id": ISOLATED_STATIC_MISSION_FIXTURE_ID,
            "geometry_scope": self.geometry_scope,
            "physical_clearance_established": False,
            "contract_sha256": self.contract.content_hash,
            "policy_sha256": self.policy.content_hash,
            "target_binding_hashes": [
                item.content_hash for item in self.target_bindings
            ],
            "endpoint_input_hashes": [item.content_hash for item in self.endpoint_poses],
            "midpoint_input_hashes": [
                item.content_hash for item in self.incoming_midpoint_poses
            ],
            "report_sha256": self.report.report_hash,
            "authority": {
                "simulation_only": True,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "can_release_physical_gates": False,
                "physical_release_effect": "NONE",
            },
        }


def build_isolated_static_mission_fixture(
    workspace_root: Path,
    trajectory: TrajectorySimulationReport,
) -> IsolatedStaticMissionFixture:
    """Exercise full collision plumbing with explicitly nonphysical geometry."""

    if type(trajectory) is not TrajectorySimulationReport:
        raise TypeError("trajectory must be exactly TrajectorySimulationReport")
    final = trajectory.final_round
    if final is None or not final.all_waypoints_accepted:
        raise StaticMissionFixtureError("fixture requires a fully accepted trajectory")
    workspace = Path(workspace_root).resolve()
    sources = _source_hashes(workspace, trajectory)
    contract = StaticB0477RouteCollisionContract(
        contract_id=ISOLATED_STATIC_MISSION_FIXTURE_ID,
        root_frame="board",
        sources=StaticRouteSourceBinding(
            support_design_id="static-b0477-support-design-source-bound-fixture",
            support_design_sha256=sources["static_support_design"],
            source_hashes=sources,
        ),
        bodies=_bodies(),
    )
    policy = StaticRouteCollisionPolicy(
        CollisionEvaluationPolicy(
            maximum_bodies=64,
            maximum_body_pairs_per_pose=2048,
            maximum_primitive_pair_tests_per_pose=32768,
            clearance_policy=CollisionClearancePolicy(
                minimum_separation_mm=0.02,
                geometry_uncertainty_mm_per_body=0.0,
                pose_uncertainty_mm_per_body=0.0,
                evidence_state=CollisionClearanceEvidenceState.SYNTHETIC_TEST_ONLY,
                source_reference=(
                    "isolated binding-fixture clearance; not a physical uncertainty budget"
                ),
            ),
        ),
        source_reference=(
            "dense endpoint/midpoint software contract with isolated placeholder bodies"
        ),
        maximum_contact_target_offset_mm=(
            _ik_contact_association_tolerance_mm(trajectory)
        ),
    )
    catalog = load_nominal_target_catalog(workspace)
    targets = tuple(
        bind_static_route_target(catalog, trajectory.device, target_id)
        for target_id in trajectory.route_target_ids
    )
    endpoints: list[StaticMissionEndpointPose] = []
    for ordinal, result in enumerate(final.joint_results):
        tip = Vec3.from_iterable(result.achieved_tip_position_board_mm)
        endpoints.append(
            StaticMissionEndpointPose(
                route_waypoint_ordinal=ordinal,
                global_authorization_command_ordinal=(
                    None if ordinal == 0 else ordinal - 1
                ),
                joint_positions_rad=result.solution_arm_joint_positions_rad,
                pose=_pose(
                    f"isolated-endpoint-{ordinal:04d}",
                    tip,
                    tool_rotation=_rotation_with_z_axis(
                        result.achieved_hand_tcp_z_axis_board
                    ),
                ),
            )
        )
    midpoints: list[StaticMissionIncomingMidpointPose] = []
    for command_ordinal, (start, end) in enumerate(zip(endpoints, endpoints[1:])):
        start_tip = start.pose.root_t_parent["tool_tip"].translation_mm
        end_tip = end.pose.root_t_parent["tool_tip"].translation_mm
        midpoint_joints: list[tuple[str, float]] = []
        for (left_name, left_value), (right_name, right_value) in zip(
            start.joint_positions_rad, end.joint_positions_rad
        ):
            if left_name != right_name:
                raise StaticMissionFixtureError("adjacent joint vectors changed order")
            midpoint_joints.append((left_name, (left_value + right_value) * 0.5))
        midpoints.append(
            StaticMissionIncomingMidpointPose(
                start_route_waypoint_ordinal=command_ordinal,
                end_route_waypoint_ordinal=command_ordinal + 1,
                global_authorization_command_ordinal=command_ordinal,
                interpolation_fraction=0.5,
                joint_positions_rad=tuple(midpoint_joints),
                pose=_pose(
                    f"isolated-midpoint-{command_ordinal:04d}",
                    (start_tip + end_tip).scaled(0.5),
                ),
            )
        )
    report = evaluate_static_b0477_mission_route(
        trajectory,
        contract,
        policy,
        targets,
        tuple(endpoints),
        tuple(midpoints),
    )
    return IsolatedStaticMissionFixture(
        contract=contract,
        policy=policy,
        target_bindings=targets,
        endpoint_poses=tuple(endpoints),
        incoming_midpoint_poses=tuple(midpoints),
        report=report,
    )


__all__ = [
    "ISOLATED_STATIC_MISSION_FIXTURE_ID",
    "ISOLATED_STATIC_MISSION_GEOMETRY_SCOPE",
    "MAX_ISOLATED_IK_CONTACT_ASSOCIATION_TOLERANCE_MM",
    "IsolatedStaticMissionFixture",
    "StaticMissionFixtureError",
    "build_isolated_static_mission_fixture",
]
