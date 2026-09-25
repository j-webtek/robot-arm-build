from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from rocell.application import (
    ReachStudyInput,
    SimulationContext,
    SimulationContextError,
    TrajectorySimulationError,
    TrajectorySimulationPolicy,
    load_simulation_context,
    revalidate_trajectory_simulation_report,
    run_trajectory_simulation,
)
from rocell.geometry import Point3Mm, RigidTransform, Vec3, load_urdf
from rocell.models.actions import TapPhoneTarget, VerifyPhoneState
from rocell.motion import (
    GeometricDryRunEngine,
    GeometricSimulationSettings,
    MotionPhase,
)
from rocell.rc03.integrity import sha256_file
from rocell.typing import compile_development_text


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('limit', ['files', 'bytes'])
def test_implementation_binding_still_rejects_oversized_source_tree(monkeypatch, limit):
    from rocell.application import trajectory_simulation as module
    from rocell.kinematics.ik import RoArmM3NumericalIk
    name = '_MAX_IMPLEMENTATION_SOURCE_FILES' if limit == 'files' else '_MAX_IMPLEMENTATION_SOURCE_BYTES'
    monkeypatch.setattr(module, name, 1)
    with pytest.raises(TrajectorySimulationError, match='exceeds'):
        module._implementation_hashes(RoArmM3NumericalIk, GeometricDryRunEngine,
                                      solver_mode='test-source-bounds')


def test_current_source_tree_fits_bounded_implementation_binding():
    from rocell.application import trajectory_simulation as module
    from rocell.kinematics.ik import RoArmM3NumericalIk
    assert module._MAX_IMPLEMENTATION_SOURCE_FILES == 2048
    assert module._MAX_IMPLEMENTATION_SOURCE_BYTES == 20_000_000
    hashes = dict(module._implementation_hashes(RoArmM3NumericalIk,
                  GeometricDryRunEngine, solver_mode='test-source-bounds'))
    assert len(hashes['rocell_source_tree_sha256']) == 64


SOFTWARE_BUNDLE_SOURCES = (
    "software/config/simulation_bundle_lock.json",
    "software/config/simulation_hardware_profile.json",
    "software/config/nominal_target_profiles.json",
    "software/config/arm_frame_contract.json",
    "software/config/camera_manifest.json",
    "software/config/virtual_commissioning_profile.json",
    "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf",
)


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _coherent_frozen_copy(root: Path) -> tuple[Path, Path]:
    manifest = json.loads(
        (WORKSPACE / "software/config/system_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rc03 = manifest["rc03"]
    rc03_relative = rc03["root"]
    for entry in rc03["source_snapshot"]:
        relative = entry["path"]
        source = WORKSPACE / rc03_relative / relative
        destination = root / rc03_relative / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        entry["sha256"] = sha256_file(destination)
    for relative in SOFTWARE_BUNDLE_SOURCES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)
    manifest_path = root / "software/config/system_manifest.json"
    _write_json(manifest_path, manifest)
    return root, manifest_path


@pytest.fixture(scope="module")
def simulation_context(tmp_path_factory: pytest.TempPathFactory) -> SimulationContext:
    root = tmp_path_factory.mktemp("trajectory-simulation") / "workspace"
    workspace, manifest_path = _coherent_frozen_copy(root)
    return load_simulation_context(workspace, manifest_path)


def _nominal_study(context: SimulationContext) -> ReachStudyInput:
    model = load_urdf(context.scenario.model_path)
    vendor_world_T_base = model.joint("world_to_base_link").transform_at(None)
    board_T_base = context.scenario.board_T_world.compose(vendor_world_T_base)
    yaw = math.atan2(
        board_T_base.rotation.matrix[3],
        board_T_base.rotation.matrix[0],
    )
    return ReachStudyInput(
        rear_clamp_contact_x_board_mm=305.0,
        clamp_to_base_axis_x_mm=0.0,
        base_axis_x_board_mm=305.0,
        rear_edge_to_base_axis_y_mm=0.0,
        base_link_z_board_mm=board_T_base.translation_mm.z,
        base_yaw_board_rad=yaw,
        keyboard_tool_length_mm=100.0,
        phone_tool_length_mm=120.0,
        board_T_base_link=board_T_base,
        board_T_vendor_world=context.scenario.board_T_world,
    )


@pytest.fixture(scope="module")
def canonical_attestation_case(
    simulation_context: SimulationContext,
) -> tuple[object, object]:
    """Create one real canonical report shared by all offline attestation tests."""

    plan = compile_development_text("keyboard", "a")
    board_T_base = RigidTransform.from_rpy_translation_mm(
        "board",
        "base_link",
        translation_mm=Vec3(385.0, 532.0, 70.1),
        yaw_rad=-1.832595714594046,
    )
    vendor_world_T_base = load_urdf(
        simulation_context.scenario.model_path
    ).joint("world_to_base_link").transform_at(None)
    study = ReachStudyInput(
        rear_clamp_contact_x_board_mm=385.0,
        clamp_to_base_axis_x_mm=0.0,
        base_axis_x_board_mm=385.0,
        rear_edge_to_base_axis_y_mm=75.0,
        base_link_z_board_mm=70.1,
        base_yaw_board_rad=-1.832595714594046,
        keyboard_tool_length_mm=120.0,
        phone_tool_length_mm=100.0,
        board_T_base_link=board_T_base,
        board_T_vendor_world=board_T_base.compose(vendor_world_T_base.inverse()),
    )
    report = run_trajectory_simulation(
        simulation_context,
        plan,
        study,
        TrajectorySimulationPolicy(park_xy_board_mm=(290.0, 10.0)),
    )
    assert report.final_round is not None
    assert report.final_round.all_waypoints_accepted
    return plan, report


def _replace_final_result(
    report: object,
    result_index: int,
    changed_result: object,
) -> object:
    final = report.final_round
    assert final is not None
    results = list(final.joint_results)
    results[result_index] = changed_result
    changed_round = replace(final, joint_results=tuple(results))
    return replace(report, rounds=(*report.rounds[:-1], changed_round))


def _smooth_fake_ik_class(
    *,
    achieved_frame: str | None = None,
    achieved_axis: Vec3 = Vec3(0.0, 0.0, 1.0),
) -> type:
    class FakeIk:
        seed_supplied: list[bool] = []

        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]

        def solve(
            self,
            target: object,
            *,
            seed_joint_positions: object = (),
        ) -> SimpleNamespace:
            type(self).seed_supplied.append(bool(seed_joint_positions))
            point = target.position_mm
            fraction = 0.25 + 0.02 * (point.x + point.y + point.z) / 1_200.0
            positions = tuple(
                SimpleNamespace(
                    name=name,
                    position=SimpleNamespace(
                        value=lower + fraction * (upper - lower)
                    ),
                )
                for name, (lower, upper) in self.bounds.items()
            )
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=positions,
                residual=SimpleNamespace(
                    tip_position_board_mm=Point3Mm(
                        achieved_frame or point.frame,
                        point.x + 0.125,
                        point.y - 0.25,
                        point.z + 0.5,
                    ),
                    hand_tcp_z_axis_board=achieved_axis,
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                selected_attempt_index=0,
                attempts=(object(), object()),
            )

    return FakeIk


def _alternating_branch_fake_ik_class() -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]
            self.call_count = 0

        def solve(
            self,
            target: object,
            *,
            seed_joint_positions: object = (),
        ) -> SimpleNamespace:
            del seed_joint_positions
            fraction = 0.20 if self.call_count % 2 == 0 else 0.45
            self.call_count += 1
            positions = tuple(
                SimpleNamespace(
                    name=name,
                    position=SimpleNamespace(
                        value=lower + fraction * (upper - lower)
                    ),
                )
                for name, (lower, upper) in self.bounds.items()
            )
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=positions,
                residual=SimpleNamespace(
                    tip_position_board_mm=target.position_mm,
                    hand_tcp_z_axis_board=Vec3(0.0, 0.0, 1.0),
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                selected_attempt_index=1,
                attempts=(object(), object()),
            )

    return FakeIk


def _boundary_fake_ik_class() -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]

        def solve(
            self,
            target: object,
            *,
            seed_joint_positions: object = (),
        ) -> SimpleNamespace:
            del seed_joint_positions
            positions = tuple(
                SimpleNamespace(
                    name=name,
                    position=SimpleNamespace(value=lower),
                )
                for name, (lower, _) in self.bounds.items()
            )
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=positions,
                residual=SimpleNamespace(
                    tip_position_board_mm=target.position_mm,
                    hand_tcp_z_axis_board=Vec3(0.0, 0.0, 1.0),
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                selected_attempt_index=0,
                attempts=(object(),),
            )

    return FakeIk


def _rank_deficient_fake_ik_class() -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]

        def solve(
            self,
            target: object,
            *,
            seed_joint_positions: object = (),
        ) -> SimpleNamespace:
            del seed_joint_positions
            values = (0.0, 0.0, 0.1, 0.0, -math.pi / 2.0)
            positions = tuple(
                SimpleNamespace(
                    name=name,
                    position=SimpleNamespace(value=value),
                )
                for name, value in zip(self.bounds, values)
            )
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=positions,
                residual=SimpleNamespace(
                    tip_position_board_mm=target.position_mm,
                    hand_tcp_z_axis_board=Vec3(0.0, 0.0, 1.0),
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                selected_attempt_index=0,
                attempts=(object(),),
            )

    return FakeIk


def _run_with_test_solver(
    context: SimulationContext,
    plan: object,
    study: ReachStudyInput,
    policy: TrajectorySimulationPolicy,
    solver_class: type,
) -> object:
    import rocell.application.trajectory_simulation as trajectory

    return trajectory._run_trajectory_simulation_with_implementations(
        context,
        plan,
        study,
        policy,
        solver_class=solver_class,
        geometry_engine_class=GeometricDryRunEngine,
        solver_mode="EXPLICIT_UNIT_TEST_DOUBLE",
    )


def test_policy_is_typed_hashed_and_resource_bounded() -> None:
    policy = TrajectorySimulationPolicy()
    assert policy.maximum_refinement_rounds == 2
    assert len(policy.policy_hash) == 64
    assert policy.to_dict()["hard_implementation_caps"]["total_ik_solves"] == 1024
    assert (
        policy.to_dict()["hard_implementation_caps"]
        ["task_jacobian_fk_evaluations_per_evaluated_waypoint"]
        == 11
    )
    assert (
        policy.to_dict()["hard_implementation_caps"]["kinematic_model_bytes"]
        == 1_000_000
    )
    assert policy.to_dict()["derived_maximum_plan_actions"] == 17

    with pytest.raises(TrajectorySimulationError, match="maximum_cartesian_step_mm"):
        TrajectorySimulationPolicy(maximum_cartesian_step_mm=0.5)
    with pytest.raises(TrajectorySimulationError, match="maximum_total_ik_solves"):
        TrajectorySimulationPolicy(maximum_total_ik_solves=1025)
    with pytest.raises(TrajectorySimulationError, match="maximum_route_targets"):
        TrajectorySimulationPolicy(maximum_route_targets=17)


def test_implementation_hash_reads_are_bounded_by_actual_stream_bytes(
    tmp_path: Path,
) -> None:
    import rocell.application.trajectory_simulation as trajectory

    source = tmp_path / "growing-source.py"
    source.write_bytes(b"x" * 101)
    with pytest.raises(TrajectorySimulationError, match="exceeds 100 bytes"):
        trajectory._hash_file_bounded(source, 100)

    source.write_bytes(b"x" * 100)
    digest, actual_bytes = trajectory._hash_file_bounded(source, 100)
    assert actual_bytes == 100
    assert len(digest) == 64


def test_canonical_report_revalidation_recomputes_evidence_without_solving(
    simulation_context: SimulationContext,
    canonical_attestation_case: tuple[object, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.trajectory_simulation as trajectory

    plan, report = canonical_attestation_case

    def forbidden_solve(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("trajectory attestation must not rerun IK optimization")

    monkeypatch.setattr(trajectory.RoArmM3NumericalIk, "solve", forbidden_solve)
    assert revalidate_trajectory_simulation_report(
        simulation_context,
        plan,
        report,
    ) is report


def test_canonical_report_revalidation_rejects_provenance_and_identity_drift(
    simulation_context: SimulationContext,
    canonical_attestation_case: tuple[object, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.trajectory_simulation as trajectory

    plan, report = canonical_attestation_case
    provenance = list(report.source_provenance)
    source_index = next(
        index
        for index, (name, _) in enumerate(provenance)
        if name == "rocell_source_tree_sha256"
    )
    provenance[source_index] = ("rocell_source_tree_sha256", "0" * 64)

    with pytest.raises(TrajectorySimulationError, match="source provenance"):
        revalidate_trajectory_simulation_report(
            simulation_context,
            plan,
            replace(report, source_provenance=tuple(provenance)),
        )
    with pytest.raises(TrajectorySimulationError, match="route targets"):
        revalidate_trajectory_simulation_report(
            simulation_context,
            plan,
            replace(report, route_target_ids=("WRONG",)),
        )
    with pytest.raises(SimulationContextError, match="target"):
        revalidate_trajectory_simulation_report(
            replace(
                simulation_context,
                targets=replace(
                    simulation_context.targets,
                    content_sha256="0" * 64,
                ),
            ),
            plan,
            report,
        )

    original_hashes = trajectory._implementation_hashes

    def drifted_hashes(*args: object, **kwargs: object) -> tuple[tuple[str, str], ...]:
        hashes = list(original_hashes(*args, **kwargs))
        index = next(
            position
            for position, (name, _) in enumerate(hashes)
            if name == "rocell_source_tree_sha256"
        )
        hashes[index] = ("rocell_source_tree_sha256", "f" * 64)
        return tuple(hashes)

    monkeypatch.setattr(trajectory, "_implementation_hashes", drifted_hashes)
    with pytest.raises(TrajectorySimulationError, match="current implementation"):
        revalidate_trajectory_simulation_report(
            simulation_context,
            plan,
            report,
        )


def test_canonical_report_revalidation_rejects_tampered_joint_derived_evidence(
    simulation_context: SimulationContext,
    canonical_attestation_case: tuple[object, object],
) -> None:
    plan, report = canonical_attestation_case
    final = report.final_round
    assert final is not None and len(final.joint_results) >= 2
    first = final.joint_results[0]
    second = final.joint_results[1]
    positions = list(first.solution_arm_joint_positions_rad)
    positions[0] = (positions[0][0], positions[0][1] + 0.02)
    assert first.solver_weighted_task_jacobian is not None
    assert second.solver_weighted_task_jacobian is not None

    corruptions = (
        replace(first, solution_arm_joint_positions_rad=tuple(positions)),
        replace(
            first,
            achieved_tip_position_board_mm=(
                first.achieved_tip_position_board_mm[0] + 0.01,
                *first.achieved_tip_position_board_mm[1:],
            ),
        ),
        replace(first, position_error_mm=first.position_error_mm + 0.01),
        replace(first, alignment_error_rad=first.alignment_error_rad + 0.01),
        replace(
            first,
            minimum_normalized_arm_joint_margin=(
                first.minimum_normalized_arm_joint_margin + 0.01
            ),
        ),
        replace(
            first,
            controller_intersection_passed=(
                not first.controller_intersection_passed
            ),
        ),
        replace(
            first,
            solver_weighted_task_jacobian=second.solver_weighted_task_jacobian,
        ),
        replace(
            second,
            joint_deltas_rad=tuple(
                (name, value + 0.01)
                for name, value in second.joint_deltas_rad
            ),
        ),
    )
    for index, corruption in enumerate(corruptions):
        result_index = 1 if corruption.waypoint_sequence == second.waypoint_sequence else 0
        changed = _replace_final_result(report, result_index, corruption)
        with pytest.raises(
            TrajectorySimulationError,
            match="joint/FK/residual/margin/continuity/conditioning",
        ):
            revalidate_trajectory_simulation_report(
                simulation_context,
                plan,
                changed,
            )


def test_pinned_model_loader_parses_the_exact_hashed_byte_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application._pinned_model as pinned_model

    source = tmp_path / "model.urdf"
    original_bytes = (
        WORKSPACE
        / "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
    ).read_bytes()
    source.write_bytes(original_bytes)
    expected = hashlib.sha256(original_bytes).hexdigest()
    original_parse = pinned_model.parse_urdf

    def mutate_path_then_parse(
        xml_text: str,
        *,
        source_name: str = "<memory>",
    ) -> object:
        source.write_bytes(b'<robot name="swapped"><link name="world"/></robot>')
        return original_parse(xml_text, source_name=source_name)

    monkeypatch.setattr(pinned_model, "parse_urdf", mutate_path_then_parse)
    loaded = pinned_model.load_pinned_urdf(
        source,
        expected,
    )

    assert loaded.model.name == "roarm_m3"
    assert loaded.sha256 == expected
    assert loaded.byte_count == len(original_bytes)
    assert hashlib.sha256(source.read_bytes()).hexdigest() != loaded.sha256


def test_pinned_model_loader_rejects_oversize_before_parsing(
    tmp_path: Path,
) -> None:
    import rocell.application._pinned_model as pinned_model

    source = tmp_path / "oversized.urdf"
    with source.open("wb") as stream:
        stream.seek(pinned_model.MAX_PINNED_URDF_BYTES)
        stream.write(b"x")

    with pytest.raises(
        pinned_model.PinnedModelLoadError,
        match="exceeds its byte limit",
    ):
        pinned_model.load_pinned_urdf(source, "0" * 64)


def test_plan_action_count_is_bounded_before_geometric_preprocessing(
    simulation_context: SimulationContext,
) -> None:
    base = compile_development_text("phone", "a")
    plan = replace(
        base,
        actions=(
            *(VerifyPhoneState("KEYBOARD_LOWER") for _ in range(17)),
            TapPhoneTarget("key_a", "KEYBOARD_LOWER"),
        ),
    )

    with pytest.raises(TrajectorySimulationError, match="derived policy maximum is 17"):
        run_trajectory_simulation(
            simulation_context,
            plan,
            _nominal_study(simulation_context),
        )


def test_per_target_motion_phase_order_fails_closed(
    simulation_context: SimulationContext,
) -> None:
    import rocell.application.trajectory_simulation as trajectory

    scenario = simulation_context.scenario
    settings = GeometricSimulationSettings(
        clearance_above_highest_obstacle_mm=(
            scenario.path_policy.clearance_above_highest_obstacle_mm
        ),
        segment_clearance_mm=scenario.path_policy.segment_clearance_mm,
        hover_height_mm=scenario.path_policy.hover_height_mm,
        approach_height_mm=scenario.path_policy.approach_height_mm,
        contact_overtravel_mm=scenario.path_policy.contact_overtravel_mm,
        park_xy_board_mm=scenario.path_policy.park_xy_board_mm,
    )
    geometry = GeometricDryRunEngine(settings).run(
        compile_development_text("keyboard", "a"),
        simulation_context.snapshot,
        simulation_context.hardware_profile,
        simulation_context.scene,
        simulation_context.targets,
    )
    corrupted = tuple(
        replace(step, semantic_target="keyboard:WRONG")
        if step.phase is MotionPhase.HOVER
        else step
        for step in geometry.steps
    )

    with pytest.raises(TrajectorySimulationError, match="lacks ordered HOVER"):
        trajectory._motion_steps(corrupted, ("keyboard:A",))


def test_geometric_check_inheritance_rejects_missing_unknown_and_duplicate_ids(
    simulation_context: SimulationContext,
) -> None:
    import rocell.application.trajectory_simulation as trajectory

    scenario = simulation_context.scenario
    settings = GeometricSimulationSettings(
        clearance_above_highest_obstacle_mm=(
            scenario.path_policy.clearance_above_highest_obstacle_mm
        ),
        segment_clearance_mm=scenario.path_policy.segment_clearance_mm,
        hover_height_mm=scenario.path_policy.hover_height_mm,
        approach_height_mm=scenario.path_policy.approach_height_mm,
        contact_overtravel_mm=scenario.path_policy.contact_overtravel_mm,
        park_xy_board_mm=scenario.path_policy.park_xy_board_mm,
    )
    geometry = GeometricDryRunEngine(settings).run(
        compile_development_text("keyboard", "a"),
        simulation_context.snapshot,
        simulation_context.hardware_profile,
        simulation_context.scene,
        simulation_context.targets,
    )
    checks = trajectory._index_path_checks(geometry.checks)
    hover_index = next(
        index
        for index, step in enumerate(geometry.steps)
        if step.phase is MotionPhase.HOVER
    )

    missing = list(geometry.steps)
    missing[hover_index] = replace(missing[hover_index], check_id=None)
    with pytest.raises(TrajectorySimulationError, match="lacks a path check ID"):
        trajectory._densify(
            tuple(missing), checks, ("keyboard:A",), 100.0, 256
        )

    unknown = list(geometry.steps)
    unknown[hover_index] = replace(
        unknown[hover_index], check_id="missing-check"
    )
    with pytest.raises(TrajectorySimulationError, match="references missing"):
        trajectory._densify(
            tuple(unknown), checks, ("keyboard:A",), 100.0, 256
        )

    with pytest.raises(TrajectorySimulationError, match="must be unique"):
        trajectory._index_path_checks((*geometry.checks, geometry.checks[0]))


def test_keyboard_route_is_densified_seeded_continuous_and_non_authoritative(
    simulation_context: SimulationContext,
) -> None:
    fake = _smooth_fake_ik_class()
    policy = TrajectorySimulationPolicy(
        maximum_cartesian_step_mm=100.0,
        maximum_joint_step_rad=0.35,
        maximum_refinement_rounds=0,
    )
    report = _run_with_test_solver(
        simulation_context,
        compile_development_text("keyboard", "ab"),
        _nominal_study(simulation_context),
        policy,
        fake,
    )
    document = report.to_dict()

    assert report.status == (
        "DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS"
    )
    assert document["schema"] == (
        "rocell.discrete_sequential_ik_waypoint_simulation.v2"
    )
    assert "CONTINUOUS_ROUTE" not in report.status
    assert report.route_target_ids == ("A", "B")
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["execution_authorized"] is False
    assert document["required_motion_phases_present"] is True
    assert document["geometry"]["all_checks_passed"] is True
    assert report.termination_reason == "ALL_DENSIFIED_WAYPOINTS_ACCEPTED"
    assert len(report.rounds) == 1
    round_ = report.rounds[0]
    assert round_.all_waypoints_accepted is True
    # Every densified waypoint retains the originating semantic-action
    # occurrence.  This makes repeated targets unambiguous to the virtual
    # executor; target names alone are not sufficient for text such as "aa".
    assert {
        waypoint.action_index
        for waypoint in round_.waypoints
        if waypoint.semantic_target == "keyboard:A"
    } == {0}
    assert {
        waypoint.action_index
        for waypoint in round_.waypoints
        if waypoint.semantic_target == "keyboard:B"
    } == {1}
    assert all(
        result.action_index == waypoint.action_index
        for waypoint, result in zip(round_.waypoints, round_.joint_results)
    )
    # Achieved pose comes from the solver residual, not from the planned
    # waypoint.  The test solver deliberately returns an offset pose so a
    # planner-value substitution cannot satisfy this assertion.
    for waypoint, result in zip(round_.waypoints, round_.joint_results):
        assert result.achieved_tip_position_board_mm == pytest.approx(
            (
                waypoint.point_board.x + 0.125,
                waypoint.point_board.y - 0.25,
                waypoint.point_board.z + 0.5,
            )
        )
        assert result.achieved_hand_tcp_z_axis_board == (0.0, 0.0, 1.0)
    first_result = round_.joint_results[0]
    first_document = first_result.to_dict()
    assert first_document["achieved_tip_position_board_mm"] == list(
        first_result.achieved_tip_position_board_mm
    )
    assert first_document["achieved_hand_tcp_z_axis_board"] == [0.0, 0.0, 1.0]
    with pytest.raises(TrajectorySimulationError, match="must be finite"):
        replace(
            first_result,
            achieved_tip_position_board_mm=(math.nan, 0.0, 0.0),
        )
    with pytest.raises(TrajectorySimulationError, match="unit vector"):
        replace(
            first_result,
            achieved_hand_tcp_z_axis_board=(0.0, 0.0, 2.0),
        )
    with pytest.raises(TrajectorySimulationError, match="immutable tuple"):
        replace(
            first_result,
            achieved_tip_position_board_mm=[0.0, 0.0, 0.0],  # type: ignore[arg-type]
        )
    assert all(
        waypoint.distance_from_previous_mm <= 100.0 + 1e-9
        and waypoint.source_path_check_passed
        for waypoint in round_.waypoints
    )
    assert fake.seed_supplied[0] is False
    assert all(fake.seed_supplied[index] for index in range(1, len(fake.seed_supplied)))
    assert all(
        len(result.solution_arm_joint_positions_rad) == 5
        and result.minimum_normalized_arm_joint_margin is not None
        and result.minimum_normalized_arm_joint_margin >= 0.01
        and result.solver_weighted_task_jacobian_numerical_rank_passed is True
        and result.solver_weighted_task_jacobian is not None
        and result.solver_weighted_task_jacobian.full_column_rank
        for result in round_.joint_results
    )
    assert report.task_jacobian_evaluated_waypoint_count == len(
        round_.joint_results
    )
    assert report.total_task_jacobian_fk_evaluations <= (
        report.task_jacobian_evaluated_waypoint_count * 11
    )
    assert document["search"]["total_task_jacobian_fk_evaluations"] == (
        report.total_task_jacobian_fk_evaluations
    )
    unsupported = {row["id"] for row in document["unsupported_diagnostics"]}
    assert "ROBOT_LINK_AND_SELF_COLLISION" in unsupported
    assert (
        "FULL_6D_PHYSICAL_SINGULARITY_AND_MANIPULABILITY_ACCEPTANCE"
        in unsupported
    )
    provenance = document["source_provenance"]
    assert provenance["solver_mode"] == "EXPLICIT_UNIT_TEST_DOUBLE"
    assert provenance["ik_solver_algorithm_version"] == "EXPLICIT_TEST_DOUBLE"
    assert provenance["ik_solver_identity"].endswith("FakeIk")
    assert provenance["ik_solver_implementation"].endswith("FakeIk")
    assert provenance["active_ik_solver_source_sha256"] != provenance["ik_module_sha256"]
    assert provenance["ik_options"]["max_attempts"] == 4
    assert provenance["ik_options"]["max_iterations_per_attempt"] == 45
    assert provenance["worst_case_solver_iteration_budget"] == 512 * 4 * 45
    assert provenance["task_jacobian_conditioning_additional_ik_solves"] == 0
    assert provenance["loaded_model_sha256"] == provenance["model_sha256"]
    assert provenance["loaded_model_bytes"] > 0
    assert provenance["task_jacobian_numerical_rank_gate"] == (
        "FULL_COLUMN_NUMERICAL_RANK_ONLY"
    )
    assert provenance["normalized_task_jacobian_conditioning_gate_enabled"] is False
    assert provenance["worst_case_task_jacobian_fk_evaluation_budget"] == 512 * 11
    for name in (
        "trajectory_module_sha256",
        "ik_module_sha256",
        "geometric_engine_module_sha256",
        "rocell_source_tree_sha256",
        "implementation_bundle_sha256",
    ):
        assert len(provenance[name]) == 64
        int(provenance[name], 16)

    # JSON/report hashing is detached from mutable returned documents.
    original_hash = report.report_hash
    document["search"]["rounds"][0]["waypoints"][0]["point_board_mm"][0] = -999.0
    assert report.report_hash == original_hash


def test_phone_route_uses_phone_tool_and_retains_all_required_phases(
    simulation_context: SimulationContext,
) -> None:
    report = _run_with_test_solver(
        simulation_context,
        compile_development_text("phone", "a"),
        _nominal_study(simulation_context),
        TrajectorySimulationPolicy(
            maximum_cartesian_step_mm=100.0,
            maximum_refinement_rounds=0,
        ),
        _smooth_fake_ik_class(),
    )

    assert report.device == "phone"
    assert report.route_target_ids == ("key_a",)
    assert report.tool_length_mm == 120.0
    assert set(result.phase for result in report.rounds[0].joint_results) >= {
        phase
        for phase in MotionPhase
        if phase.value in {"PARK", "TRANSIT", "HOVER", "APPROACH", "CONTACT", "RETRACT"}
    }


def test_achieved_tip_frame_must_match_the_board_waypoint_frame(
    simulation_context: SimulationContext,
) -> None:
    with pytest.raises(TrajectorySimulationError, match="frame does not match"):
        _run_with_test_solver(
            simulation_context,
            compile_development_text("keyboard", "a"),
            _nominal_study(simulation_context),
            TrajectorySimulationPolicy(
                maximum_cartesian_step_mm=100.0,
                maximum_refinement_rounds=0,
            ),
            _smooth_fake_ik_class(achieved_frame="camera_optical"),
        )


def test_joint_branch_discontinuity_triggers_bounded_refinement(
    simulation_context: SimulationContext,
) -> None:
    report = _run_with_test_solver(
        simulation_context,
        compile_development_text("keyboard", "a"),
        _nominal_study(simulation_context),
        TrajectorySimulationPolicy(
            maximum_cartesian_step_mm=100.0,
            maximum_joint_step_rad=0.10,
            maximum_refinement_rounds=1,
        ),
        _alternating_branch_fake_ik_class(),
    )

    assert report.status == (
        "DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_GAPS_REPORTED"
    )
    assert report.termination_reason == "REFINEMENT_ROUND_LIMIT_EXHAUSTED"
    assert len(report.rounds) == 2
    assert all(
        round_.failure_reason == "MAXIMUM_ADJACENT_JOINT_DELTA_EXCEEDED"
        for round_ in report.rounds
    )
    assert all(len(round_.joint_results) == 2 for round_ in report.rounds)
    assert report.total_ik_solves == 4


def test_arm_margin_failure_is_non_refinable_and_gripper_is_explicitly_excluded(
    simulation_context: SimulationContext,
) -> None:
    report = _run_with_test_solver(
        simulation_context,
        compile_development_text("keyboard", "a"),
        _nominal_study(simulation_context),
        TrajectorySimulationPolicy(),
        _boundary_fake_ik_class(),
    )

    assert len(report.rounds) == 1
    assert report.total_ik_solves == 1
    result = report.rounds[0].joint_results[0]
    assert result.failure_reason == "MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED"
    assert result.minimum_normalized_arm_joint_margin == 0.0
    provenance = dict(report.source_provenance)
    assert provenance["fixed_gripper_position_rad"] == 0.0
    assert provenance["fixed_gripper_in_arm_margin_gate"] is False


def test_solver_weighted_task_jacobian_rank_loss_is_non_refinable(
    simulation_context: SimulationContext,
) -> None:
    report = _run_with_test_solver(
        simulation_context,
        compile_development_text("keyboard", "a"),
        _nominal_study(simulation_context),
        TrajectorySimulationPolicy(),
        _rank_deficient_fake_ik_class(),
    )

    assert len(report.rounds) == 1
    assert report.total_ik_solves == 1
    assert report.termination_reason == (
        "NON_REFINABLE_FAILURE: "
        "SOLVER_WEIGHTED_TASK_JACOBIAN_NUMERICAL_RANK_DEFICIENT"
    )
    result = report.rounds[0].joint_results[0]
    assert result.arm_margin_passed is True
    assert result.solver_weighted_task_jacobian_numerical_rank_passed is False
    assert result.failure_reason == (
        "SOLVER_WEIGHTED_TASK_JACOBIAN_NUMERICAL_RANK_DEFICIENT"
    )
    assert result.solver_weighted_task_jacobian is not None
    assert result.solver_weighted_task_jacobian.numerical_rank == 4
    assert result.solver_weighted_task_jacobian.condition_number is None
    assert report.task_jacobian_evaluated_waypoint_count == 1
    assert report.total_task_jacobian_fk_evaluations == 11


def test_invalid_park_and_incoherent_study_are_rejected_before_ik(
    simulation_context: SimulationContext,
) -> None:
    plan = compile_development_text("keyboard", "a")
    study = _nominal_study(simulation_context)

    with pytest.raises(TrajectorySimulationError, match="aliases keepout"):
        run_trajectory_simulation(
            simulation_context,
            plan,
            study,
            TrajectorySimulationPolicy(park_xy_board_mm=(100.0, 100.0)),
        )
    with pytest.raises(TrajectorySimulationError, match="scalar placement fields"):
        run_trajectory_simulation(
            simulation_context,
            plan,
            replace(study, base_axis_x_board_mm=306.0),
        )

    base = study.board_T_base_link
    shifted_base = RigidTransform(
        base.parent_frame,
        base.child_frame,
        base.rotation,
        Vec3(
            base.translation_mm.x,
            base.translation_mm.y,
            base.translation_mm.z + 1.0,
        ),
    )
    vendor_world_T_base = load_urdf(simulation_context.scenario.model_path).joint(
        "world_to_base_link"
    ).transform_at(None)
    shifted = replace(
        study,
        base_link_z_board_mm=shifted_base.translation_mm.z,
        board_T_base_link=shifted_base,
        board_T_vendor_world=shifted_base.compose(vendor_world_T_base.inverse()),
    )
    with pytest.raises(TrajectorySimulationError, match="pinned reach-study assumption"):
        run_trajectory_simulation(simulation_context, plan, shifted)


def test_context_is_revalidated_before_trajectory_overlay(
    simulation_context: SimulationContext,
) -> None:
    changed = replace(
        simulation_context,
        scenario=replace(
            simulation_context.scenario,
            board_T_world=RigidTransform.from_rpy_translation_mm(
                "board",
                "world",
                translation_mm=simulation_context.scenario.board_T_world.translation_mm,
                yaw_rad=-1.4,
            ),
        ),
    )
    with pytest.raises(SimulationContextError, match="scenario"):
        run_trajectory_simulation(
            changed,
            compile_development_text("keyboard", "a"),
            _nominal_study(simulation_context),
        )
