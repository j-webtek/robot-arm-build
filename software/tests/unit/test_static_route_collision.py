from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.simulation.collision import (
    CollisionBindingMode,
    CollisionClearanceEvidenceState,
    CollisionClearancePolicy,
    CollisionEvaluationPolicy,
    CollisionExclusionEvidenceState,
    CollisionExclusionScope,
    CollisionPairExclusion,
    CollisionPose,
    OrientedBoxMm,
    SampledCollisionGeometry,
    SphereMm,
)
from rocell.simulation.static_route_collision import (
    REQUIRED_STATIC_ROUTE_PHASES,
    REQUIRED_STATIC_ROUTE_SOURCE_KEYS,
    STATIC_ROUTE_BODY_REQUIREMENTS,
    StaticB0477RouteCollisionContract,
    StaticRouteBody,
    StaticRouteBodyRole,
    StaticRouteCollisionError,
    StaticRouteCollisionPolicy,
    StaticRouteCollisionStatus,
    StaticRouteGeometryProvenance,
    StaticRouteIntermediateSample,
    StaticRoutePhase,
    StaticRoutePhasePose,
    StaticRouteSampleDisposition,
    StaticRouteSegment,
    StaticRouteSourceBinding,
    StaticTargetRoute,
    bind_static_route_target,
    evaluate_static_b0477_target_route,
)
from rocell.targets import NominalTargetCatalog, load_nominal_target_catalog


WORKSPACE = Path(__file__).resolve().parents[3]


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def catalog() -> NominalTargetCatalog:
    return load_nominal_target_catalog(WORKSPACE)


def _sources(catalog: NominalTargetCatalog) -> StaticRouteSourceBinding:
    values = {key: _digest(key) for key in REQUIRED_STATIC_ROUTE_SOURCE_KEYS}
    values["target_profile"] = catalog.content_sha256
    return StaticRouteSourceBinding(
        support_design_id="synthetic-static-portal-fixture-v1",
        support_design_sha256=values["static_support_design"],
        source_hashes=values,
    )


def _body_primitive(requirement_index: int, role: StaticRouteBodyRole):
    # Device surfaces use the exact nominal top planes.  Every other static
    # fixture body is separated by construction so routes exercise the query,
    # not accidental fixture self-overlap.
    if role is StaticRouteBodyRole.KEYBOARD:
        return OrientedBoxMm(Vec3(242.5, 158.5, 10.5), Vec3(157.5, 73.5, 10.5))
    if role is StaticRouteBodyRole.PHONE:
        return OrientedBoxMm(Vec3(538.15, 166.4, 5.95), Vec3(38.95, 82.2, 5.95))
    if role is StaticRouteBodyRole.BOARD:
        return OrientedBoxMm(Vec3(305.0, 228.5, -2.0), Vec3(305.0, 228.5, 2.0))
    if role is StaticRouteBodyRole.TOOL_TIP:
        return SphereMm(Vec3.zero(), 0.4)
    if role in {
        StaticRouteBodyRole.ROARM_BASE,
        StaticRouteBodyRole.ROARM_LINK,
        StaticRouteBodyRole.ROARM_GRIPPER,
        StaticRouteBodyRole.CONTACT_TOOL_BODY,
    }:
        return SphereMm(Vec3.zero(), 0.25)
    return SphereMm(Vec3(2000.0 + 20.0 * requirement_index, 2000.0, 2000.0), 0.25)


def _complete_bodies(
    *,
    provenance: StaticRouteGeometryProvenance = (
        StaticRouteGeometryProvenance.CONSERVATIVE_SYNTHETIC
    ),
) -> tuple[StaticRouteBody, ...]:
    result: list[StaticRouteBody] = []
    for index, requirement in enumerate(STATIC_ROUTE_BODY_REQUIREMENTS):
        primitives = (
            ()
            if requirement.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED
            else (_body_primitive(index, requirement.role),)
        )
        result.append(
            StaticRouteBody(
                body_id=requirement.body_id,
                parent_frame=requirement.parent_frame,
                role=requirement.role,
                binding_mode=requirement.binding_mode,
                provenance=provenance,
                source_key=requirement.source_key,
                source_reference="explicit conservative unit-test envelope",
                primitives=primitives,
            )
        )
    return tuple(result)


def _contract(catalog: NominalTargetCatalog) -> StaticB0477RouteCollisionContract:
    return StaticB0477RouteCollisionContract(
        contract_id="synthetic-static-b0477-route-v1",
        root_frame="board",
        sources=_sources(catalog),
        bodies=_complete_bodies(),
    )


def _transform(frame: str, point: Vec3) -> RigidTransform:
    return RigidTransform("board", frame, Rotation3.identity(), point)


def _pose(pose_id: str, tool_tip: Vec3, *, include_harness: bool = True) -> CollisionPose:
    transforms: dict[str, RigidTransform] = {}
    rigid_index = 0
    for requirement in STATIC_ROUTE_BODY_REQUIREMENTS:
        if requirement.binding_mode is CollisionBindingMode.RIGID_FRAME:
            if requirement.role is StaticRouteBodyRole.TOOL_TIP:
                point = tool_tip
            elif requirement.role is StaticRouteBodyRole.CONTACT_TOOL_BODY:
                point = tool_tip + Vec3(0.0, 0.0, 15.0)
            else:
                point = Vec3(-2000.0 - 20.0 * rigid_index, -2000.0, 1000.0)
                rigid_index += 1
            transforms[requirement.parent_frame] = _transform(
                requirement.parent_frame, point
            )
        elif requirement.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED:
            transforms[requirement.parent_frame] = _transform(
                requirement.parent_frame, Vec3(-3000.0, -3000.0, 1000.0)
            )
    configuration = (
        {
            "attachment:arm_harness": SampledCollisionGeometry(
                (SphereMm(Vec3.zero(), 0.3),),
                # The route fixture remains explicitly synthetic.
                StaticRouteGeometryProvenance.CONSERVATIVE_SYNTHETIC.collision_evidence_state,
                "per-pose conservative synthetic harness envelope",
            )
        }
        if include_harness
        else {}
    )
    return CollisionPose(pose_id, "board", transforms, configuration)


def _mix(left: Vec3, right: Vec3, fraction: float) -> Vec3:
    return left + (right - left).scaled(fraction)


def _route(
    catalog: NominalTargetCatalog,
    device: str,
    target_id: str,
) -> StaticTargetRoute:
    target = bind_static_route_target(catalog, device, target_id)
    center = target.center_board_mm
    park = Vec3(50.0, 350.0, 100.0)
    points = (
        park,
        center + Vec3(0.0, 0.0, 50.0),
        center + Vec3(0.0, 0.0, 20.0),
        center + Vec3(0.0, 0.0, 5.0),
        center,
        center + Vec3(0.0, 0.0, 5.0),
        park,
    )
    prefix = f"{device}-{target_id}"
    phases = tuple(
        StaticRoutePhasePose(
            phase,
            _pose(f"{prefix}-phase-{index}-{phase.value}", point),
        )
        for index, (phase, point) in enumerate(zip(REQUIRED_STATIC_ROUTE_PHASES, points))
    )
    segments = tuple(
        StaticRouteSegment(
            index,
            index + 1,
            (
                StaticRouteIntermediateSample(
                    0.5,
                    _pose(
                        f"{prefix}-segment-{index}-midpoint",
                        _mix(points[index], points[index + 1], 0.5),
                    ),
                ),
            ),
        )
        for index in range(6)
    )
    return StaticTargetRoute(f"route-{prefix}", target, phases, segments)


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
                evidence_state=CollisionClearanceEvidenceState.SYNTHETIC_TEST_ONLY,
                source_reference="synthetic route unit-test clearance",
            ),
        )
    )


def _replace_phase_pose(
    route: StaticTargetRoute, phase_index: int, pose: CollisionPose
) -> StaticTargetRoute:
    phases = list(route.phase_poses)
    phases[phase_index] = replace(phases[phase_index], pose=pose)
    return replace(route, phase_poses=tuple(phases))


def _replace_segment_sample(
    route: StaticTargetRoute,
    segment_index: int,
    sample: StaticRouteIntermediateSample,
) -> StaticTargetRoute:
    segments = list(route.segments)
    segments[segment_index] = replace(
        segments[segment_index], intermediate_samples=(sample,)
    )
    return replace(route, segments=tuple(segments))


def test_required_catalog_covers_static_camera_arm_devices_cables_and_lighting() -> None:
    ids = {item.body_id for item in STATIC_ROUTE_BODY_REQUIREMENTS}
    assert len(ids) == 26
    assert {
        "robot:base_link",
        "robot:link1",
        "robot:link2",
        "robot:link3",
        "robot:link4",
        "robot:link5",
        "robot:gripper",
        "robot:contact_tool",
        "robot:tool_tip",
        "attachment:arm_harness",
        "workcell:board",
        "installation:base_clamp",
        "workcell:keyboard",
        "workcell:phone",
        "support:portal_left_post",
        "support:portal_right_post",
        "support:portal_crossbar",
        "support:camera_boom",
        "support:lighting_boom_left",
        "support:lighting_boom_right",
        "camera:b0477_enclosure",
        "camera:b0477_lens",
        "camera:b0477_connector",
        "cable:fixed_usb_route",
        "lighting:key_light_left",
        "lighting:key_light_right",
    } == ids
    harness = next(
        item for item in STATIC_ROUTE_BODY_REQUIREMENTS
        if item.body_id == "attachment:arm_harness"
    )
    assert harness.binding_mode is CollisionBindingMode.CONFIGURATION_SAMPLED
    fixed_usb = next(
        item for item in STATIC_ROUTE_BODY_REQUIREMENTS
        if item.body_id == "cable:fixed_usb_route"
    )
    assert fixed_usb.binding_mode is CollisionBindingMode.STATIC_ROOT


def test_source_closure_binds_support_design_and_every_required_input(
    catalog: NominalTargetCatalog,
) -> None:
    sources = _sources(catalog)
    assert sources.source_hashes["static_support_design"] == sources.support_design_sha256
    assert REQUIRED_STATIC_ROUTE_SOURCE_KEYS <= set(sources.source_hashes)
    assert len(sources.content_hash) == 64

    changed = dict(sources.source_hashes)
    changed["static_support_design"] = _digest("different")
    with pytest.raises(StaticRouteCollisionError, match="support_design_sha256"):
        replace(sources, source_hashes=changed)


def test_all_75_nominal_targets_have_every_phase_and_segment_result(
    catalog: NominalTargetCatalog,
) -> None:
    contract = _contract(catalog)
    policy = _policy()
    targets = tuple(
        (device, target_id)
        for device, mapping in (
            ("keyboard", catalog.keyboard_targets),
            ("phone", catalog.phone_targets),
        )
        for target_id in mapping
    )
    assert len(targets) == 75

    for device, target_id in targets:
        report = evaluate_static_b0477_target_route(
            contract, _route(catalog, device, target_id), policy
        )
        assert report.status is StaticRouteCollisionStatus.PASS_DIAGNOSTIC_ONLY
        assert len(report.phase_results) == 7
        assert tuple(item.phase for item in report.phase_results) == REQUIRED_STATIC_ROUTE_PHASES
        assert len(report.segment_results) == 6
        assert all(len(item.sample_results) == 1 for item in report.segment_results)
        assert all(item.accepted for item in report.phase_results)
        assert all(item.accepted for item in report.segment_results)
        assert report.phase_results[4].pose_result.disposition is (
            StaticRouteSampleDisposition.ALLOWED_DESIGNATED_CONTACT
        )
        assert not report.geometry_audit.physical_geometry_complete
        assert not report.can_produce_authorization_v2_physical_evidence


def test_synthetic_pass_is_diagnostic_only_and_refuses_authorization_evidence(
    catalog: NominalTargetCatalog,
) -> None:
    report = evaluate_static_b0477_target_route(
        _contract(catalog), _route(catalog, "keyboard", "A"), _policy()
    )
    document = report.to_dict()
    assert document["passed_diagnostic"] is True
    assert document["authority"]["hardware_commands_generated"] == 0
    assert document["authority"]["can_authorize_motion"] is False
    assert document["authorization_v2"]["eligible_as_physical_evidence"] is False
    assert len(report.report_hash) == 64
    with pytest.raises(StaticRouteCollisionError, match="authorization_v2"):
        report.as_authorization_v2_physical_evidence()


def test_midpoint_collision_is_detected_even_when_segment_endpoints_are_clear(
    catalog: NominalTargetCatalog,
) -> None:
    route = _route(catalog, "keyboard", "A")
    original = route.segments[0].intermediate_samples[0]
    # Inject a midpoint path excursion onto the keyboard surface.  Both PARK
    # and TRANSIT remain clear, proving the segment sample is independently run.
    collision_pose = _pose(
        "keyboard-A-injected-midpoint-collision",
        route.target.center_board_mm,
    )
    changed = _replace_segment_sample(
        route,
        0,
        replace(original, pose=collision_pose),
    )
    report = evaluate_static_b0477_target_route(
        _contract(catalog), changed, _policy()
    )

    assert report.phase_results[0].accepted
    assert report.phase_results[1].accepted
    assert report.status is StaticRouteCollisionStatus.COLLISION_DETECTED
    assert report.segment_results[0].sample_results[0].pose_result.disposition is (
        StaticRouteSampleDisposition.COLLISION
    )


@pytest.mark.parametrize("phase_index", [3, 5])
def test_designated_overlap_is_rejected_in_approach_and_retract(
    catalog: NominalTargetCatalog,
    phase_index: int,
) -> None:
    route = _route(catalog, "phone", "key_a")
    changed = _replace_phase_pose(
        route,
        phase_index,
        _pose(f"injected-overlap-phase-{phase_index}", route.target.center_board_mm),
    )
    report = evaluate_static_b0477_target_route(
        _contract(catalog), changed, _policy()
    )
    assert report.status is StaticRouteCollisionStatus.COLLISION_DETECTED
    assert report.phase_results[phase_index].pose_result.disposition is (
        StaticRouteSampleDisposition.COLLISION
    )


def test_contact_rejects_any_pair_other_than_exact_tip_and_designated_target(
    catalog: NominalTargetCatalog,
) -> None:
    route = _route(catalog, "keyboard", "A")
    bodies = list(_complete_bodies())
    index = next(
        i for i, item in enumerate(bodies)
        if item.body_id == "camera:b0477_enclosure"
    )
    bodies[index] = replace(
        bodies[index],
        primitives=(SphereMm(route.target.center_board_mm, 0.25),),
    )
    contract = replace(_contract(catalog), bodies=tuple(bodies))
    report = evaluate_static_b0477_target_route(contract, route, _policy())
    assert report.status is StaticRouteCollisionStatus.COLLISION_DETECTED
    assert report.phase_results[4].pose_result.disposition is (
        StaticRouteSampleDisposition.COLLISION
    )


def test_missing_required_body_blocks_contract(catalog: NominalTargetCatalog) -> None:
    contract = _contract(catalog)
    bodies = tuple(
        item for item in contract.bodies if item.body_id != "camera:b0477_connector"
    )
    report = evaluate_static_b0477_target_route(
        replace(contract, bodies=bodies),
        _route(catalog, "keyboard", "A"),
        _policy(),
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_CONTRACT
    assert any("camera:b0477_connector" in item for item in report.blockers)


def test_explicit_missing_provenance_blocks_contract(catalog: NominalTargetCatalog) -> None:
    contract = _contract(catalog)
    bodies = list(contract.bodies)
    index = next(i for i, item in enumerate(bodies) if item.body_id == "support:camera_boom")
    bodies[index] = replace(
        bodies[index],
        provenance=StaticRouteGeometryProvenance.MISSING,
        primitives=(),
    )
    report = evaluate_static_b0477_target_route(
        replace(contract, bodies=tuple(bodies)),
        _route(catalog, "phone", "key_a"),
        _policy(),
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_CONTRACT
    assert any("support:camera_boom" in item for item in report.blockers)


def test_missing_rigid_transform_blocks_pose_input(catalog: NominalTargetCatalog) -> None:
    route = _route(catalog, "keyboard", "A")
    original = route.phase_poses[2].pose
    transforms = dict(original.root_t_parent)
    del transforms["link3"]
    missing = replace(original, pose_id="hover-missing-link3", root_t_parent=transforms)
    report = evaluate_static_b0477_target_route(
        _contract(catalog), _replace_phase_pose(route, 2, missing), _policy()
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_POSE_INPUT
    assert "robot:link3" in (report.phase_results[2].pose_result.blocker or "")


def test_missing_harness_sample_blocks_segment(catalog: NominalTargetCatalog) -> None:
    route = _route(catalog, "keyboard", "A")
    original = route.segments[2].intermediate_samples[0]
    pose = original.pose
    missing = replace(
        pose,
        pose_id="segment-missing-harness-sample",
        configuration_primitives={},
    )
    changed = _replace_segment_sample(route, 2, replace(original, pose=missing))
    report = evaluate_static_b0477_target_route(
        _contract(catalog), changed, _policy()
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_POSE_INPUT
    assert "attachment:arm_harness" in (
        report.segment_results[2].sample_results[0].pose_result.blocker or ""
    )


def test_missing_policy_and_clearance_policy_both_block(
    catalog: NominalTargetCatalog,
) -> None:
    contract = _contract(catalog)
    route = _route(catalog, "keyboard", "A")
    assert evaluate_static_b0477_target_route(contract, route, None).status is (
        StaticRouteCollisionStatus.BLOCKED_POLICY
    )
    no_clearance = StaticRouteCollisionPolicy(CollisionEvaluationPolicy())
    assert evaluate_static_b0477_target_route(contract, route, no_clearance).status is (
        StaticRouteCollisionStatus.BLOCKED_POLICY
    )


def test_missing_phase_blocks_before_evaluation(catalog: NominalTargetCatalog) -> None:
    route = _route(catalog, "keyboard", "A")
    changed = replace(route, phase_poses=route.phase_poses[:-1])
    report = evaluate_static_b0477_target_route(
        _contract(catalog), changed, _policy()
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_PHASE_SEQUENCE
    assert not report.phase_results


def test_missing_segment_or_midpoint_blocks_coverage(
    catalog: NominalTargetCatalog,
) -> None:
    route = _route(catalog, "phone", "key_a")
    contract = _contract(catalog)
    missing_segment = replace(route, segments=route.segments[:-1])
    assert evaluate_static_b0477_target_route(
        contract, missing_segment, _policy()
    ).status is StaticRouteCollisionStatus.BLOCKED_SEGMENT_COVERAGE

    no_midpoint = list(route.segments)
    no_midpoint[0] = replace(
        no_midpoint[0],
        intermediate_samples=(
            replace(no_midpoint[0].intermediate_samples[0], interpolation_fraction=0.4),
        ),
    )
    assert evaluate_static_b0477_target_route(
        contract, replace(route, segments=tuple(no_midpoint)), _policy()
    ).status is StaticRouteCollisionStatus.BLOCKED_SEGMENT_COVERAGE


def test_target_profile_hash_mismatch_blocks(catalog: NominalTargetCatalog) -> None:
    route = _route(catalog, "keyboard", "A")
    changed = replace(
        route,
        target=replace(route.target, target_profile_sha256=_digest("wrong profile")),
    )
    report = evaluate_static_b0477_target_route(
        _contract(catalog), changed, _policy()
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_TARGET_BINDING


def test_global_exclusion_cannot_hide_contact_pair(catalog: NominalTargetCatalog) -> None:
    exclusion = CollisionPairExclusion(
        "robot:tool_tip",
        "workcell:keyboard",
        CollisionExclusionScope.SYNTHETIC_TEST_ONLY,
        CollisionExclusionEvidenceState.SYNTHETIC_TEST_ONLY,
        "invalid attempt to hide phase-specific contact",
        "unit test",
    )
    with pytest.raises(StaticRouteCollisionError, match="do not permit global"):
        replace(_contract(catalog), global_pair_exclusions=(exclusion,))


def test_contact_pose_must_match_bound_target_center(
    catalog: NominalTargetCatalog,
) -> None:
    route = _route(catalog, "keyboard", "A")
    shifted = route.target.center_board_mm + Vec3(1.0, 0.0, 0.0)
    changed = _replace_phase_pose(route, 4, _pose("shifted-contact", shifted))
    report = evaluate_static_b0477_target_route(
        _contract(catalog), changed, _policy()
    )
    assert report.status is StaticRouteCollisionStatus.BLOCKED_POSE_INPUT
    assert "bound target center" in (report.phase_results[4].pose_result.blocker or "")


def test_public_simulation_package_exports_route_service() -> None:
    import rocell.simulation as simulation

    assert simulation.StaticB0477RouteCollisionContract is (
        StaticB0477RouteCollisionContract
    )
    assert simulation.StaticTargetRoute is StaticTargetRoute
    assert simulation.evaluate_static_b0477_target_route is (
        evaluate_static_b0477_target_route
    )
