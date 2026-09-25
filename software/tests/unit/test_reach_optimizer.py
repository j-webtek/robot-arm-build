from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from rocell.application.context import (
    SimulationContext,
    SimulationContextError,
    load_simulation_context,
)
from rocell.application.reach_optimizer import (
    ContactPoseResult,
    FullContactEvaluation,
    ParkEvaluation,
    PoseFeasibility,
    ReachOptimizationError,
    ReachStudyInput,
    ReachStudyPolicy,
    _rank_key,
    default_reach_study_inputs,
    default_reach_study_policy,
    run_reach_optimization,
)
from rocell.geometry import Point3Mm, RigidTransform, Rotation3, Vec3
from rocell.rc03.integrity import sha256_file


WORKSPACE = Path(__file__).resolve().parents[3]
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
    """Refresh source pins only in an isolated test copy."""

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
    root = tmp_path_factory.mktemp("reach-optimizer") / "workspace"
    workspace, manifest_path = _coherent_frozen_copy(root)
    return load_simulation_context(workspace, manifest_path)


def _fake_ik_class(*, at_lower_bound: bool = False) -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]
            self.board_T_world = kwargs["board_T_world"]

        def solve(self, target: object) -> SimpleNamespace:
            positions = []
            for name, bounds in self.bounds.items():
                lower, upper = bounds
                value = lower if at_lower_bound else (lower + upper) / 2.0
                positions.append(
                    SimpleNamespace(
                        name=name,
                        position=SimpleNamespace(value=value),
                    )
                )
            point = target.position_mm
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=tuple(positions),
                residual=SimpleNamespace(
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                attempts=(object(), object()),
                selected_attempt_index=0,
            )

    return FakeIk


def _margin_inversion_fake_ik_class() -> type:
    """Make rejected margins favor X=310 while accepted margins favor X=300."""

    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]
            self.board_T_world = kwargs["board_T_world"]

        def solve(self, target: object) -> SimpleNamespace:
            point = target.position_mm
            candidate_x = self.board_T_world.translation_mm.x
            if point.y > 300.0:  # park: accepted with generous margin
                fraction = 0.20
            elif point.x < 450.0:  # keyboard: accepted
                fraction = 0.10 if candidate_x < 305.0 else 0.05
            else:  # phone: rejected by the 0.01 policy margin
                fraction = 0.001 if candidate_x < 305.0 else 0.009
            positions = tuple(
                SimpleNamespace(
                    name=name,
                    position=SimpleNamespace(value=lower + fraction * (upper - lower)),
                )
                for name, (lower, upper) in self.bounds.items()
            )
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=positions,
                residual=SimpleNamespace(
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                attempts=(object(),),
                selected_attempt_index=0,
            )

    return FakeIk


def _single_policy(
    context: SimulationContext,
    *,
    minimum_margin: float = 0.01,
) -> ReachStudyPolicy:
    scenario = context.scenario
    nominal_yaw = math.atan2(
        scenario.board_T_world.rotation.matrix[3],
        scenario.board_T_world.rotation.matrix[0],
    )
    highest = max(obstacle.maximum.z for obstacle in context.scene.obstacles)
    park_x, park_y = scenario.path_policy.park_xy_board_mm
    return ReachStudyPolicy(
        rear_clamp_contact_x_board_mm=(scenario.board_T_world.translation_mm.x,),
        clamp_to_base_axis_x_mm=(0.0,),
        rear_edge_to_base_axis_y_mm=(0.0,),
        base_yaw_board_rad=(nominal_yaw,),
        keyboard_tool_length_mm=(-scenario.hand_tcp_to_tip_z_mm,),
        phone_tool_length_mm=(-scenario.hand_tcp_to_tip_z_mm,),
        park_points_board_mm=((
            park_x,
            park_y,
            highest + scenario.path_policy.clearance_above_highest_obstacle_mm,
        ),),
        finalist_count=1,
        coarse_targets_per_device=1,
        minimum_normalized_arm_joint_margin=minimum_margin,
    )


def test_default_policy_is_small_bounded_and_hashes_margin(
    simulation_context: SimulationContext,
) -> None:
    policy = default_reach_study_policy(simulation_context)

    assert policy.study_input_count == 18
    assert policy.study_input_count <= 25
    assert policy.rear_clamp_contact_x_board_mm == (225.0, 305.0, 385.0)
    assert policy.clamp_to_base_axis_x_mm == (0.0,)
    assert policy.finalist_count == 2
    assert policy.minimum_normalized_arm_joint_margin == pytest.approx(0.01)
    assert policy.to_dict()["fixed_planar_assumptions"]["base_roll_rad"] == 0.0

    changed = replace(policy, minimum_normalized_arm_joint_margin=0.02)
    assert changed.policy_hash != policy.policy_hash
    with pytest.raises(ReachOptimizationError, match=r"in \(0, 0.5\)"):
        replace(policy, minimum_normalized_arm_joint_margin=0.0)
    with pytest.raises(ReachOptimizationError, match="maximum is 25"):
        ReachStudyPolicy(
            rear_clamp_contact_x_board_mm=tuple(float(index) for index in range(26)),
            clamp_to_base_axis_x_mm=(0.0,),
            rear_edge_to_base_axis_y_mm=(0.0,),
            base_yaw_board_rad=(0.0,),
            keyboard_tool_length_mm=(100.0,),
            phone_tool_length_mm=(100.0,),
            park_points_board_mm=((305.0, 400.0, 70.0),),
        )


def test_default_input_replay_is_ik_free_unique_and_contains_freeze005_selection(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.reach_optimizer as optimizer

    class ForbiddenIk:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("default input replay must not run IK")

    monkeypatch.setattr(optimizer, "RoArmM3NumericalIk", ForbiddenIk)
    inputs = default_reach_study_inputs(simulation_context)
    identifiers = tuple(study.study_input_id for study in inputs)

    assert len(inputs) == 18
    assert identifiers == tuple(sorted(identifiers))
    assert len(set(identifiers)) == len(identifiers)
    assert "reach-00ed8c5820df03c7" in identifiers
    assert all(
        study.board_T_vendor_world.inverse()
        .compose(study.board_T_base_link)
        .translation_mm.z
        == pytest.approx(70.1)
        for study in inputs
    )


def test_optimizer_derives_vendor_world_from_physical_base_and_is_deterministic(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.reach_optimizer as optimizer

    monkeypatch.setattr(
        optimizer,
        "RoArmM3NumericalIk",
        _fake_ik_class(),
    )
    canonical_before = simulation_context.scenario.board_T_world

    first = run_reach_optimization(simulation_context)
    second = run_reach_optimization(simulation_context)
    document = first.to_dict()

    assert first.report_hash == second.report_hash
    assert first.status == "CONTACT_AND_PARK_DIAGNOSTIC_COMPLETE_FINALIST_FOUND"
    assert document["scope"] == "INDEPENDENT_CONTACT_AND_PARK_IK_DIAGNOSTIC_ONLY"
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["canonical_context_modified"] is False
    assert document["policy"]["minimum_normalized_arm_joint_margin"] == 0.01
    assert dict(first.source_provenance)["coarse_ik_options"]
    assert dict(first.source_provenance)["full_ik_options"]
    assert dict(first.source_provenance)["fixed_gripper_normalized_margin"] == 0.0
    assert dict(first.source_provenance)["fixed_gripper_in_arm_margin_gate"] is False
    assert dict(first.source_provenance)["ik_solver_implementation"] == (
        "RoArmM3NumericalIk"
    )
    assert first.vendor_world_T_base_link.translation_mm.z == pytest.approx(70.1)
    assert first.canonical_board_T_base_link.translation_mm.z == pytest.approx(70.1)
    assert simulation_context.scenario.board_T_world == canonical_before
    assert len(first.full_evaluations) == 2
    assert len(first.coarse_evaluations) == 18
    assert all(row.ranking_key for row in first.coarse_evaluations)
    assert all(row.ik_solve_count > 0 for row in first.coarse_evaluations)

    for evaluation in first.full_evaluations:
        study = evaluation.study_input
        derived = study.board_T_base_link.compose(
            first.vendor_world_T_base_link.inverse()
        )
        assert derived.almost_equal(study.board_T_vendor_world)
        assert evaluation.total_count("keyboard") == 46
        assert evaluation.accepted_count("keyboard") == 46
        assert evaluation.total_count("phone") == 29
        assert evaluation.accepted_count("phone") == 29
        assert all(
            len(row.feasibility.solution_arm_joint_positions_rad) == 5
            and row.feasibility.selected_attempt_index == 0
            for row in evaluation.outcomes
        )
    assert first.ranked_candidates[0].park_routes_accepted == 2
    assert first.ranked_candidates[0].mission_complete is True


def test_minimum_margin_gate_rejects_zero_margin_solutions(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.reach_optimizer as optimizer

    monkeypatch.setattr(
        optimizer,
        "RoArmM3NumericalIk",
        _fake_ik_class(at_lower_bound=True),
    )
    report = run_reach_optimization(
        simulation_context,
        _single_policy(simulation_context),
    )

    assert report.status == "CONTACT_AND_PARK_DIAGNOSTIC_NO_COMPLETE_FINALIST"
    assert report.ranked_candidates[0].mission_complete is False
    assert report.ranked_candidates[0].park_routes_accepted == 0
    assert all(
        row.feasibility.status == "MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED"
        for row in report.full_evaluations[0].outcomes
    )


def test_rear_clamp_contact_bounds_are_inclusive_and_fail_immediately_outside(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.reach_optimizer as optimizer

    monkeypatch.setattr(optimizer, "RoArmM3NumericalIk", _fake_ik_class())
    nominal = _single_policy(simulation_context)
    at_boundaries = replace(
        nominal,
        rear_clamp_contact_x_board_mm=(225.0, 385.0),
        finalist_count=2,
    )
    report = run_reach_optimization(simulation_context, at_boundaries)
    assert report.coarse_candidate_count == 2

    offset_study = run_reach_optimization(
        simulation_context,
        replace(
            nominal,
            rear_clamp_contact_x_board_mm=(305.0,),
            clamp_to_base_axis_x_mm=(10.0,),
        ),
    ).full_evaluations[0].study_input
    assert offset_study.rear_clamp_contact_x_board_mm == 305.0
    assert offset_study.clamp_to_base_axis_x_mm == 10.0
    assert offset_study.base_axis_x_board_mm == 315.0

    for just_outside in (224.999, 385.001):
        with pytest.raises(ReachOptimizationError, match="leaves RC03 zone"):
            run_reach_optimization(
                simulation_context,
                replace(nominal, rear_clamp_contact_x_board_mm=(just_outside,)),
            )


def test_coarse_selection_evaluates_every_park_and_can_choose_nonfirst(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.reach_optimizer as optimizer

    monkeypatch.setattr(optimizer, "RoArmM3NumericalIk", _fake_ik_class())
    nominal = _single_policy(simulation_context)
    policy = replace(
        nominal,
        park_points_board_mm=(
            (100.0, 100.0, 70.0),  # sorted first but aliases keyboard keepout
            nominal.park_points_board_mm[0],
        ),
    )

    report = run_reach_optimization(simulation_context, policy)
    coarse = report.coarse_evaluations[0]

    assert len(coarse.evaluated_parks) == 2
    assert coarse.evaluated_parks[0].geometry_valid is False
    assert coarse.park.park_id == "park-01"
    assert coarse.park.all_routes_accepted is True


def test_coarse_margin_tie_break_ignores_already_rejected_pose_margins(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.reach_optimizer as optimizer

    monkeypatch.setattr(
        optimizer,
        "RoArmM3NumericalIk",
        _margin_inversion_fake_ik_class(),
    )
    policy = replace(
        _single_policy(simulation_context),
        rear_clamp_contact_x_board_mm=(300.0, 310.0),
        finalist_count=1,
    )

    report = run_reach_optimization(simulation_context, policy)
    coarse_by_x = {
        row.study_input.rear_clamp_contact_x_board_mm: row
        for row in report.coarse_evaluations
    }

    assert coarse_by_x[300.0].keyboard_accepted == 1
    assert coarse_by_x[300.0].phone_accepted == 0
    assert coarse_by_x[310.0].keyboard_accepted == 1
    assert coarse_by_x[310.0].phone_accepted == 0
    assert coarse_by_x[300.0].minimum_normalized_arm_joint_margin == pytest.approx(0.1)
    assert coarse_by_x[310.0].minimum_normalized_arm_joint_margin == pytest.approx(0.05)
    assert report.full_evaluations[0].study_input.rear_clamp_contact_x_board_mm == 300.0


def test_park_z_resource_ceiling_is_enforced_before_ik(
    simulation_context: SimulationContext,
) -> None:
    policy = replace(
        _single_policy(simulation_context),
        park_points_board_mm=((305.0, 400.0, 371.0),),
    )
    with pytest.raises(ReachOptimizationError, match=r"bounded required\+300"):
        run_reach_optimization(simulation_context, policy)


def _study() -> ReachStudyInput:
    board_T_base = RigidTransform(
        "board", "base_link", Rotation3.identity(), Vec3(305.0, 457.0, 70.1)
    )
    vendor_T_base = RigidTransform(
        "world", "base_link", Rotation3.identity(), Vec3(0.0, 0.0, 70.1)
    )
    return ReachStudyInput(
        305.0,
        0.0,
        305.0,
        0.0,
        70.1,
        0.0,
        100.0,
        100.0,
        board_T_base,
        board_T_base.compose(vendor_T_base.inverse()),
    )


def _contacts(keyboard_ok: int, phone_ok: int) -> FullContactEvaluation:
    vector = (("joint", 0.5),)
    good = PoseFeasibility("CONVERGED", True, 0.0, 0.0, 0.5, 0.2, 2, 0, vector)
    bad = PoseFeasibility(
        "NO_CONVERGED_SOLUTION", False, 1.0, 0.1, None, None, 2, 0, ()
    )
    rows = tuple(
        ContactPoseResult(
            "keyboard",
            f"K{index}",
            Point3Mm("board", float(index), 1.0, 20.0),
            good if index < keyboard_ok else bad,
        )
        for index in range(46)
    ) + tuple(
        ContactPoseResult(
            "phone",
            f"P{index}",
            Point3Mm("board", float(index), 2.0, 12.0),
            good if index < phone_ok else bad,
        )
        for index in range(29)
    )
    return FullContactEvaluation(_study(), rows, 75)


def _park(accepted_routes: int) -> ParkEvaluation:
    vector = (("joint", 0.5),)
    good = PoseFeasibility("CONVERGED", True, 0.0, 0.0, 0.5, 0.2, 2, 0, vector)
    bad = PoseFeasibility(
        "NO_CONVERGED_SOLUTION", False, 1.0, 0.1, None, None, 2, 0, ()
    )
    return ParkEvaluation(
        "park-00",
        Point3Mm("board", 305.0, 400.0, 70.0),
        True,
        good if accepted_routes >= 1 else bad,
        good if accepted_routes >= 2 else bad,
    )


def test_ranking_prioritizes_parks_then_device_balance_before_raw_total() -> None:
    # Park is a hard prerequisite ahead of otherwise superior contact coverage.
    assert _rank_key(_contacts(10, 10), _park(2), 0.0) < _rank_key(
        _contacts(46, 29), _park(0), 0.0
    )

    # 30/46 + 25/29 is more balanced than 46/46 + 10/29, despite the latter
    # accepting one more raw target (56 versus 55).
    assert _rank_key(_contacts(30, 25), _park(2), 0.0) < _rank_key(
        _contacts(46, 10), _park(2), 0.0
    )


def test_optimizer_revalidates_before_accepting_candidate_overlays(
    simulation_context: SimulationContext,
) -> None:
    changed_scenario = replace(
        simulation_context.scenario,
        board_T_world=RigidTransform(
            "board",
            "world",
            simulation_context.scenario.board_T_world.rotation,
            Vec3(300.0, 457.0, 0.0),
        ),
    )
    changed_context = replace(simulation_context, scenario=changed_scenario)

    with pytest.raises(SimulationContextError, match="scenario"):
        run_reach_optimization(changed_context, _single_policy(simulation_context))
