from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from rocell.application.trajectory_simulation import TrajectorySimulationReport
from rocell.application.virtual_session import (
    VirtualSessionReport,
    run_default_virtual_session,
)
from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.motion import MotionPhase
from rocell.simulation.collision import (
    CollisionBindingMode,
    CollisionClearanceEvidenceState,
    CollisionClearancePolicy,
    CollisionEvaluationPolicy,
    CollisionPose,
    OrientedBoxMm,
    SampledCollisionGeometry,
    SphereMm,
)
from rocell.simulation.static_mission_route import (
    STATIC_B0477_MISSION_ROUTE_REPORT_SCHEMA,
    StaticMissionEndpointPose,
    StaticMissionIncomingMidpointPose,
    StaticMissionRouteError,
    StaticMissionRouteStatus,
    evaluate_static_b0477_mission_route,
)
from rocell.simulation.static_route_collision import (
    REQUIRED_STATIC_ROUTE_SOURCE_KEYS,
    STATIC_ROUTE_BODY_REQUIREMENTS,
    StaticB0477RouteCollisionContract,
    StaticRouteBody,
    StaticRouteBodyRole,
    StaticRouteCollisionPolicy,
    StaticRouteGeometryProvenance,
    StaticRouteSampleDisposition,
    StaticRouteSourceBinding,
    StaticRouteTargetBinding,
    bind_static_route_target,
)
from rocell.targets import NominalTargetCatalog, load_nominal_target_catalog


WORKSPACE = Path(__file__).resolve().parents[3]


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def catalog() -> NominalTargetCatalog:
    return load_nominal_target_catalog(WORKSPACE)


@pytest.fixture(scope="module")
def keyboard_session() -> VirtualSessionReport:
    return run_default_virtual_session(WORKSPACE, "keyboard", "test")


@pytest.fixture(scope="module")
def phone_session() -> VirtualSessionReport:
    return run_default_virtual_session(WORKSPACE, "phone", "test.")


def _body_primitive(requirement_index: int, role: StaticRouteBodyRole):
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
    # Static bodies are separated by construction.  The fixture tests the
    # mission binding and evaluator rather than an accidental support overlap.
    return SphereMm(
        Vec3(2000.0 + 20.0 * requirement_index, 2000.0, 2000.0), 0.25
    )


def _complete_bodies() -> tuple[StaticRouteBody, ...]:
    result: list[StaticRouteBody] = []
    for index, requirement in enumerate(STATIC_ROUTE_BODY_REQUIREMENTS):
        primitives = (
            ()
            if requirement.binding_mode
            is CollisionBindingMode.CONFIGURATION_SAMPLED
            else (_body_primitive(index, requirement.role),)
        )
        result.append(
            StaticRouteBody(
                body_id=requirement.body_id,
                parent_frame=requirement.parent_frame,
                role=requirement.role,
                binding_mode=requirement.binding_mode,
                provenance=(
                    StaticRouteGeometryProvenance.CONSERVATIVE_SYNTHETIC
                ),
                source_key=requirement.source_key,
                source_reference="explicit conservative dense-mission fixture",
                primitives=primitives,
            )
        )
    return tuple(result)


def _contract(
    trajectory: TrajectorySimulationReport,
    *,
    source_overrides: dict[str, str] | None = None,
    bodies: tuple[StaticRouteBody, ...] | None = None,
) -> StaticB0477RouteCollisionContract:
    provenance = dict(trajectory.source_provenance)
    source_hashes = {
        key: _digest(f"dense-mission:{key}")
        for key in REQUIRED_STATIC_ROUTE_SOURCE_KEYS
    }
    source_hashes["robot_model"] = provenance["model_sha256"]
    source_hashes["target_profile"] = provenance["target_profile_sha256"]
    if source_overrides:
        source_hashes.update(source_overrides)
    return StaticB0477RouteCollisionContract(
        contract_id="synthetic-static-b0477-dense-mission-v1",
        root_frame="board",
        sources=StaticRouteSourceBinding(
            support_design_id="synthetic-static-portal-fixture-v1",
            support_design_sha256=source_hashes["static_support_design"],
            source_hashes=source_hashes,
        ),
        bodies=_complete_bodies() if bodies is None else bodies,
    )


def _policy() -> StaticRouteCollisionPolicy:
    return StaticRouteCollisionPolicy(
        CollisionEvaluationPolicy(
            maximum_bodies=64,
            maximum_body_pairs_per_pose=2048,
            maximum_primitive_pair_tests_per_pose=32768,
            clearance_policy=CollisionClearancePolicy(
                minimum_separation_mm=0.02,
                geometry_uncertainty_mm_per_body=0.0,
                pose_uncertainty_mm_per_body=0.0,
                evidence_state=(
                    CollisionClearanceEvidenceState.SYNTHETIC_TEST_ONLY
                ),
                source_reference="synthetic dense mission clearance",
            ),
        )
    )


def _rotation_with_z_axis(raw_axis: tuple[float, float, float]) -> Rotation3:
    z_axis = Vec3.from_iterable(raw_axis).normalized()
    reference = (
        Vec3(1.0, 0.0, 0.0)
        if abs(z_axis.x) < 0.9
        else Vec3(0.0, 1.0, 0.0)
    )
    x_axis = (reference - z_axis.scaled(reference.dot(z_axis))).normalized()
    y_axis = z_axis.cross(x_axis).normalized()
    # Rotation3 is row-major; basis vectors occupy matrix columns.
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
    rigid_index = 0
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
            point = Vec3(
                -2000.0 - 20.0 * rigid_index,
                -2000.0,
                1000.0,
            )
            rotation = Rotation3.identity()
            rigid_index += 1
        transforms[requirement.parent_frame] = RigidTransform(
            "board", requirement.parent_frame, rotation, point
        )
    configuration = {
        "attachment:arm_harness": SampledCollisionGeometry(
            (SphereMm(Vec3.zero(), 0.3),),
            StaticRouteGeometryProvenance.CONSERVATIVE_SYNTHETIC.collision_evidence_state,
            "fresh per-pose conservative synthetic harness envelope",
        )
    }
    return CollisionPose(pose_id, "board", transforms, configuration)


def _inputs(
    trajectory: TrajectorySimulationReport,
) -> tuple[
    tuple[StaticMissionEndpointPose, ...],
    tuple[StaticMissionIncomingMidpointPose, ...],
]:
    final = trajectory.final_round
    assert final is not None
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
                    f"endpoint-{ordinal}",
                    tip,
                    tool_rotation=_rotation_with_z_axis(
                        result.achieved_hand_tcp_z_axis_board
                    ),
                ),
            )
        )
    midpoints: list[StaticMissionIncomingMidpointPose] = []
    for command_ordinal, (start, end) in enumerate(
        zip(endpoints, endpoints[1:])
    ):
        start_tip = start.pose.root_t_parent["tool_tip"].translation_mm
        end_tip = end.pose.root_t_parent["tool_tip"].translation_mm
        midpoints.append(
            StaticMissionIncomingMidpointPose(
                start_route_waypoint_ordinal=command_ordinal,
                end_route_waypoint_ordinal=command_ordinal + 1,
                global_authorization_command_ordinal=command_ordinal,
                interpolation_fraction=0.5,
                joint_positions_rad=tuple(
                    (left_name, (left_value + right_value) * 0.5)
                    for (left_name, left_value), (
                        right_name,
                        right_value,
                    ) in zip(
                        start.joint_positions_rad, end.joint_positions_rad
                    )
                    if left_name == right_name
                ),
                pose=_pose(
                    f"midpoint-{command_ordinal}",
                    (start_tip + end_tip).scaled(0.5),
                ),
            )
        )
    return tuple(endpoints), tuple(midpoints)


def _targets(
    catalog: NominalTargetCatalog,
    trajectory: TrajectorySimulationReport,
) -> tuple[StaticRouteTargetBinding, ...]:
    return tuple(
        bind_static_route_target(catalog, trajectory.device, target_id)
        for target_id in trajectory.route_target_ids
    )


def _evaluate(
    catalog: NominalTargetCatalog,
    trajectory: TrajectorySimulationReport,
):
    endpoints, midpoints = _inputs(trajectory)
    return evaluate_static_b0477_mission_route(
        trajectory,
        _contract(trajectory),
        _policy(),
        _targets(catalog, trajectory),
        endpoints,
        midpoints,
    )


def _replace_pose_transform(
    pose: CollisionPose,
    frame: str,
    transform: RigidTransform,
) -> CollisionPose:
    transforms = dict(pose.root_t_parent)
    transforms[frame] = transform
    return CollisionPose(
        pose.pose_id,
        pose.root_frame,
        transforms,
        pose.configuration_primitives,
    )


def test_real_keyboard_dense_route_maps_48_waypoints_to_47_commands(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    report = _evaluate(catalog, keyboard_session.trajectory)

    assert report.status is StaticMissionRouteStatus.PASS_DIAGNOSTIC_ONLY
    assert report.passed_diagnostic
    assert len(report.endpoint_results) == 48
    assert len(report.midpoint_results) == 47
    assert len(report.command_bindings) == 47
    assert report.endpoint_results[0].endpoint.route_waypoint_ordinal == 0
    assert (
        report.endpoint_results[0].endpoint.global_authorization_command_ordinal
        is None
    )
    assert tuple(
        (item.global_authorization_command_ordinal, item.route_waypoint_ordinal)
        for item in report.command_bindings
    ) == tuple((ordinal, ordinal + 1) for ordinal in range(47))
    contact_bindings = tuple(
        item
        for item in report.command_bindings
        if item.designated_contact_overlap_allowed
    )
    assert len(contact_bindings) == 4
    assert tuple(item.semantic_target for item in contact_bindings) == (
        "keyboard:T",
        "keyboard:E",
        "keyboard:S",
        "keyboard:T",
    )
    assert all(
        item.phase is MotionPhase.CONTACT and item.phase_endpoint
        for item in contact_bindings
    )
    assert all(
        item.pose_result.disposition
        is not StaticRouteSampleDisposition.ALLOWED_DESIGNATED_CONTACT
        for item in report.midpoint_results
    )

    document = report.to_dict()
    assert document["schema"] == STATIC_B0477_MISSION_ROUTE_REPORT_SCHEMA
    assert document["coverage"]["separate_ordinal_domains"] is True
    assert document["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_messages_generated": 0,
        "can_release_physical_gates": False,
        "can_authorize_motion": False,
        "can_authorize_contact": False,
        "physical_release_effect": "NONE",
    }
    assert len(report.report_hash) == 64
    assert len(report.command_binding_sequence_sha256) == 64
    with pytest.raises(StaticMissionRouteError, match="diagnostic-only"):
        report.as_authorization_v2_physical_evidence()


def test_real_phone_dense_route_maps_61_waypoints_to_60_commands_without_fake_verify(
    catalog: NominalTargetCatalog,
    phone_session: VirtualSessionReport,
) -> None:
    report = _evaluate(catalog, phone_session.trajectory)

    assert report.status is StaticMissionRouteStatus.PASS_DIAGNOSTIC_ONLY
    assert len(report.endpoint_results) == 61
    assert len(report.midpoint_results) == 60
    assert len(report.command_bindings) == 60
    actions = {
        item.action_index
        for item in report.command_bindings
        if item.action_index is not None
    }
    assert actions == {1, 2, 3, 4, 5}
    assert 0 not in actions
    contacts = tuple(
        item for item in report.command_bindings if item.phase is MotionPhase.CONTACT
    )
    assert len(contacts) == 5
    assert all(item.designated_contact_overlap_allowed for item in contacts)
    assert report.command_bindings[-1].route_waypoint_ordinal == 60
    assert report.command_bindings[-1].global_authorization_command_ordinal == 59
    assert report.command_bindings[-1].phase is MotionPhase.PARK
    assert report.command_bindings[-1].action_index is None


@pytest.mark.parametrize("kind", ["missing", "reordered", "gapped_command"])
def test_endpoint_coverage_order_and_global_command_ordinals_fail_closed(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
    kind: str,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    if kind == "missing":
        endpoints = endpoints[:-1]
    elif kind == "reordered":
        endpoints = (endpoints[1], endpoints[0], *endpoints[2:])
    else:
        endpoints = (
            endpoints[0],
            replace(endpoints[1], global_authorization_command_ordinal=8),
            *endpoints[2:],
        )
    with pytest.raises(StaticMissionRouteError):
        evaluate_static_b0477_mission_route(
            trajectory,
            _contract(trajectory),
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )


@pytest.mark.parametrize("kind", ["missing", "reordered", "wrong_joint_midpoint"])
def test_every_incoming_joint_midpoint_is_required_and_exact(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
    kind: str,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    if kind == "missing":
        midpoints = midpoints[:-1]
    elif kind == "reordered":
        midpoints = (midpoints[1], midpoints[0], *midpoints[2:])
    else:
        first = midpoints[0]
        values = list(first.joint_positions_rad)
        name, position = values[0]
        values[0] = (name, position + 1e-4)
        midpoints = (
            replace(first, joint_positions_rad=tuple(values)),
            *midpoints[1:],
        )
    with pytest.raises(StaticMissionRouteError):
        evaluate_static_b0477_mission_route(
            trajectory,
            _contract(trajectory),
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )


def test_rejected_or_identity_tampered_ik_result_is_not_collision_screened(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    final = trajectory.final_round
    assert final is not None
    results = list(final.joint_results)
    results[4] = replace(results[4], accepted=False)
    tampered_round = replace(final, joint_results=tuple(results))
    tampered = replace(
        trajectory,
        rounds=(*trajectory.rounds[:-1], tampered_round),
    )
    endpoints, midpoints = _inputs(trajectory)
    with pytest.raises(StaticMissionRouteError, match="final accepted"):
        evaluate_static_b0477_mission_route(
            tampered,
            _contract(tampered),
            _policy(),
            _targets(catalog, tampered),
            endpoints,
            midpoints,
        )


@pytest.mark.parametrize("source_key", ["target_profile", "robot_model"])
def test_trajectory_profile_and_robot_model_must_match_source_closure(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
    source_key: str,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    with pytest.raises(StaticMissionRouteError, match="differs"):
        evaluate_static_b0477_mission_route(
            trajectory,
            _contract(trajectory, source_overrides={source_key: _digest("wrong")}),
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )


def test_contract_requires_exactly_nine_sources_and_26_bodies(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    contract_with_extra_source = _contract(
        trajectory,
        source_overrides={"unmodelled_source": _digest("unmodelled")},
    )
    with pytest.raises(StaticMissionRouteError, match="exactly nine"):
        evaluate_static_b0477_mission_route(
            trajectory,
            contract_with_extra_source,
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )

    contract_missing_body = _contract(
        trajectory,
        bodies=_complete_bodies()[:-1],
    )
    with pytest.raises(StaticMissionRouteError, match="26-body"):
        evaluate_static_b0477_mission_route(
            trajectory,
            contract_missing_body,
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )


@pytest.mark.parametrize("missing", ["transform", "harness"])
def test_every_endpoint_requires_complete_transforms_and_fresh_harness_geometry(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
    missing: str,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    original = endpoints[3].pose
    if missing == "transform":
        transforms = dict(original.root_t_parent)
        del transforms["link2"]
        altered_pose = CollisionPose(
            original.pose_id,
            original.root_frame,
            transforms,
            original.configuration_primitives,
        )
    else:
        altered_pose = CollisionPose(
            original.pose_id,
            original.root_frame,
            original.root_t_parent,
            {},
        )
    endpoints = (
        *endpoints[:3],
        replace(endpoints[3], pose=altered_pose),
        *endpoints[4:],
    )
    with pytest.raises(StaticMissionRouteError, match="exact"):
        evaluate_static_b0477_mission_route(
            trajectory,
            _contract(trajectory),
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )


def test_endpoint_tool_pose_must_match_accepted_trajectory_position_and_axis(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    endpoint = endpoints[2]
    pose = endpoint.pose
    tool = pose.root_t_parent["tool_tip"]
    changed = _replace_pose_transform(
        pose,
        "tool_tip",
        replace(
            tool,
            translation_mm=tool.translation_mm + Vec3(0.01, 0.0, 0.0),
        ),
    )
    endpoints = (
        *endpoints[:2],
        replace(endpoint, pose=changed),
        *endpoints[3:],
    )
    with pytest.raises(StaticMissionRouteError, match="achieved IK position"):
        evaluate_static_b0477_mission_route(
            trajectory,
            _contract(trajectory),
            _policy(),
            _targets(catalog, trajectory),
            endpoints,
            midpoints,
        )


def test_incoming_contact_midpoint_never_inherits_contact_allowance(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    final = trajectory.final_round
    assert final is not None
    endpoints, midpoints = _inputs(trajectory)
    contact_ordinal = next(
        index
        for index, waypoint in enumerate(final.waypoints)
        if waypoint.phase is MotionPhase.CONTACT
    )
    command_ordinal = contact_ordinal - 1
    midpoint = midpoints[command_ordinal]
    target = _targets(catalog, trajectory)[0]
    tool = midpoint.pose.root_t_parent["tool_tip"]
    collision_pose = _replace_pose_transform(
        midpoint.pose,
        "tool_tip",
        replace(tool, translation_mm=target.center_board_mm),
    )
    midpoints = (
        *midpoints[:command_ordinal],
        replace(midpoint, pose=collision_pose),
        *midpoints[command_ordinal + 1 :],
    )

    report = evaluate_static_b0477_mission_route(
        trajectory,
        _contract(trajectory),
        _policy(),
        _targets(catalog, trajectory),
        endpoints,
        midpoints,
    )
    result = report.midpoint_results[command_ordinal]
    assert report.status is StaticMissionRouteStatus.COLLISION_DETECTED
    assert (
        result.pose_result.disposition is StaticRouteSampleDisposition.COLLISION
    )
    assert result.to_dict()["designated_contact_overlap_allowed"] is False


def test_final_contact_allows_only_exact_tool_tip_device_pair(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    final = trajectory.final_round
    assert final is not None
    endpoints, midpoints = _inputs(trajectory)
    contact_ordinal = next(
        index
        for index, waypoint in enumerate(final.waypoints)
        if waypoint.phase is MotionPhase.CONTACT
    )
    endpoint = endpoints[contact_ordinal]
    tip = endpoint.pose.root_t_parent["tool_tip"].translation_mm
    additional_collision = _replace_pose_transform(
        endpoint.pose,
        "link1",
        RigidTransform(
            "board", "link1", Rotation3.identity(), tip
        ),
    )
    endpoints = (
        *endpoints[:contact_ordinal],
        replace(endpoint, pose=additional_collision),
        *endpoints[contact_ordinal + 1 :],
    )
    report = evaluate_static_b0477_mission_route(
        trajectory,
        _contract(trajectory),
        _policy(),
        _targets(catalog, trajectory),
        endpoints,
        midpoints,
    )
    assert report.status is StaticMissionRouteStatus.COLLISION_DETECTED
    assert (
        report.endpoint_results[contact_ordinal].pose_result.disposition
        is StaticRouteSampleDisposition.COLLISION
    )


def test_designated_contact_overlap_is_required_by_the_frozen_policy(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    bodies = list(_complete_bodies())
    keyboard_index = next(
        index
        for index, body in enumerate(bodies)
        if body.body_id == "workcell:keyboard"
    )
    bodies[keyboard_index] = replace(
        bodies[keyboard_index],
        primitives=(SphereMm(Vec3(1500.0, 1500.0, 1500.0), 0.25),),
    )
    endpoints, midpoints = _inputs(trajectory)
    report = evaluate_static_b0477_mission_route(
        trajectory,
        _contract(trajectory, bodies=tuple(bodies)),
        _policy(),
        _targets(catalog, trajectory),
        endpoints,
        midpoints,
    )
    assert report.status is StaticMissionRouteStatus.CONTACT_OVERLAP_MISSING
    assert sum(
        item.pose_result.disposition
        is StaticRouteSampleDisposition.REQUIRED_CONTACT_MISSING
        for item in report.endpoint_results
    ) == 4


def test_final_park_collision_blocks_the_complete_mission(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    final_endpoint = endpoints[-1]
    final_tip = final_endpoint.pose.root_t_parent["tool_tip"].translation_mm
    colliding_final_pose = _replace_pose_transform(
        final_endpoint.pose,
        "link1",
        RigidTransform(
            "board", "link1", Rotation3.identity(), final_tip
        ),
    )
    endpoints = (
        *endpoints[:-1],
        replace(final_endpoint, pose=colliding_final_pose),
    )
    report = evaluate_static_b0477_mission_route(
        trajectory,
        _contract(trajectory),
        _policy(),
        _targets(catalog, trajectory),
        endpoints,
        midpoints,
    )
    assert report.status is StaticMissionRouteStatus.COLLISION_DETECTED
    assert report.endpoint_results[-1].phase is MotionPhase.PARK
    assert not report.endpoint_results[-1].accepted
    assert not report.passed_diagnostic


def test_target_binding_order_and_contact_center_tampering_fail_closed(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    endpoints, midpoints = _inputs(trajectory)
    targets = _targets(catalog, trajectory)
    reordered = (targets[1], targets[0], *targets[2:])
    with pytest.raises(StaticMissionRouteError, match="trajectory occurrence"):
        evaluate_static_b0477_mission_route(
            trajectory,
            _contract(trajectory),
            _policy(),
            reordered,
            endpoints,
            midpoints,
        )

    shifted = (
        replace(
            targets[0],
            center_board_mm=targets[0].center_board_mm + Vec3(2.0, 0.0, 0.0),
        ),
        *targets[1:],
    )
    report = evaluate_static_b0477_mission_route(
        trajectory,
        _contract(trajectory),
        _policy(),
        shifted,
        endpoints,
        midpoints,
    )
    assert report.status is StaticMissionRouteStatus.BLOCKED_POSE_INPUT
    assert any("bound target center" in item for item in report.blockers)


def test_final_park_identity_cannot_be_relabelled(
    catalog: NominalTargetCatalog,
    keyboard_session: VirtualSessionReport,
) -> None:
    trajectory = keyboard_session.trajectory
    final = trajectory.final_round
    assert final is not None
    waypoints = list(final.waypoints)
    joint_results = list(final.joint_results)
    waypoints[-1] = replace(waypoints[-1], phase=MotionPhase.TRANSIT)
    joint_results[-1] = replace(joint_results[-1], phase=MotionPhase.TRANSIT)
    changed_round = replace(
        final,
        waypoints=tuple(waypoints),
        joint_results=tuple(joint_results),
    )
    changed = replace(
        trajectory,
        rounds=(*trajectory.rounds[:-1], changed_round),
    )
    endpoints, midpoints = _inputs(trajectory)
    with pytest.raises(StaticMissionRouteError, match="end at an endpoint PARK"):
        evaluate_static_b0477_mission_route(
            changed,
            _contract(changed),
            _policy(),
            _targets(catalog, changed),
            endpoints,
            midpoints,
        )
