from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any, Callable, cast

import pytest

from rocell.application import SimulationContext, load_simulation_context
from rocell.application.prehardware_layout_study import (
    LayoutSearchAxis,
    PrehardwareLayoutStudyError,
    PrehardwareLayoutStudyPolicy,
    _run_prehardware_layout_study_with_solver,
    default_prehardware_layout_study_policy,
)
from rocell.geometry import Point3Mm
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
def simulation_context(
    tmp_path_factory: pytest.TempPathFactory,
) -> SimulationContext:
    root = tmp_path_factory.mktemp("prehardware-layout") / "workspace"
    workspace, manifest_path = _coherent_frozen_copy(root)
    return load_simulation_context(workspace, manifest_path)


def _single_axis(axis: LayoutSearchAxis) -> LayoutSearchAxis:
    middle = axis.value_evidence[len(axis.value_evidence) // 2]
    return replace(axis, value_evidence=(middle,))


def _single_policy(context: SimulationContext) -> PrehardwareLayoutStudyPolicy:
    policy = default_prehardware_layout_study_policy(context)
    return replace(
        policy,
        rear_clamp_contact_x=_single_axis(policy.rear_clamp_contact_x),
        rear_edge_to_base_axis_y=_single_axis(
            policy.rear_edge_to_base_axis_y
        ),
        base_yaw_board=_single_axis(policy.base_yaw_board),
        keyboard_tool_length=_single_axis(policy.keyboard_tool_length),
        phone_tool_length=_single_axis(policy.phone_tool_length),
        refinement_anchor_count=1,
        full_catalog_candidate_count=1,
    )


def _park_optimizer(_context: SimulationContext) -> Any:
    point = Point3Mm("board", 290.0, 10.0, 70.0)
    candidate = SimpleNamespace(
        all_routes_accepted=True,
        geometry=SimpleNamespace(
            candidate_id="park-290000-010000-070000",
            point_board=point,
        ),
    )
    return SimpleNamespace(
        best_candidate=candidate,
        actual_ik_solve_count=95,
        report_hash="a" * 64,
    )


def _fake_ik_class(
    reject_point: Callable[[Point3Mm], bool] | None = None,
) -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = cast(dict[str, tuple[float, float]], kwargs["joint_bounds_rad"])

        def solve(self, target: object) -> SimpleNamespace:
            point = cast(Any, target).position_mm
            reject = reject_point is not None and reject_point(point)
            positions = tuple(
                SimpleNamespace(
                    name=name,
                    position=SimpleNamespace(
                        value=(
                            lower
                            if reject
                            else lower + 0.25 * (upper - lower)
                        )
                    ),
                )
                for name, (lower, upper) in self.bounds.items()
            )
            return SimpleNamespace(
                converged=True,
                status=SimpleNamespace(value="CONVERGED"),
                solution_arm_joint_positions=positions,
                residual=SimpleNamespace(
                    position_error_mm=0.001,
                    alignment_error_rad=0.0,
                ),
                attempts=(object(), object()),
                selected_attempt_index=0,
            )

    return FakeIk


def _run(
    context: SimulationContext,
    solver_class: type,
    policy: PrehardwareLayoutStudyPolicy | None = None,
) -> Any:
    return _run_prehardware_layout_study_with_solver(
        context,
        policy,
        solver_class=solver_class,
        solver_mode="EXPLICIT_UNIT_TEST_DOUBLE",
        park_optimizer=_park_optimizer,
    )


def test_default_axes_distinguish_exact_midpoint_and_sensitivity_sources(
    simulation_context: SimulationContext,
) -> None:
    policy = default_prehardware_layout_study_policy(simulation_context)
    document = policy.to_dict()

    assert policy.coarse_hypothesis_count == 243
    assert policy.rear_clamp_contact_x.values == (225.0, 305.0, 385.0)
    assert tuple(
        row.classification for row in policy.rear_clamp_contact_x.value_evidence
    ) == (
        "EXACT_LAYOUT_DERIVED",
        "MIDPOINT_SEARCH_DERIVED",
        "EXACT_LAYOUT_DERIVED",
    )
    assert policy.rear_edge_to_base_axis_y.values == (0.0, 50.0, 100.0)
    assert (
        policy.rear_edge_to_base_axis_y.value_evidence[1].classification
        == "MIDPOINT_SEARCH_DERIVED"
    )
    assert "screening_assumption" in (
        policy.rear_edge_to_base_axis_y.value_evidence[0].source_id
    )
    assert "sensitivity_case" in (
        policy.rear_edge_to_base_axis_y.value_evidence[-1].source_id
    )
    assert tuple(
        round(math.degrees(value), 6)
        for value in policy.base_yaw_board.values
    ) == (-105.0, -90.0, -75.0)
    assert (
        policy.base_yaw_board.envelope_classification
        == "SENSITIVITY_ONLY_NOT_MECHANICAL_ALLOWANCE"
    )
    assert all(
        "reach_optimizer.py#_study_inputs" in row.source_id
        for row in (
            policy.base_yaw_board.value_evidence[0],
            policy.base_yaw_board.value_evidence[-1],
        )
    )
    assert policy.keyboard_tool_length.values == (80.0, 100.0, 120.0)
    assert policy.phone_tool_length.values == (80.0, 100.0, 120.0)
    assert all(
        row.classification == "VIRTUAL_SENSITIVITY_SOURCE"
        for row in policy.phone_tool_length.value_evidence
    )
    assert document["hard_implementation_caps"]["layout_ik_solves"] == 4096
    assert document["hard_implementation_caps"]["total_service_ik_solves"] == 4288
    assert len(policy.policy_hash) == 64


def test_nonuniform_axis_refinement_uses_actual_adjacent_midpoints(
    simulation_context: SimulationContext,
) -> None:
    import rocell.application.prehardware_layout_study as layout

    policy = default_prehardware_layout_study_policy(simulation_context)
    original = policy.rear_edge_to_base_axis_y
    nonuniform = replace(
        original,
        value_evidence=(
            original.value_evidence[0],
            replace(original.value_evidence[1], value=20.0),
            original.value_evidence[2],
        ),
    )

    assert layout._adjacent_interval_midpoints(nonuniform, 0.0) == (10.0,)
    assert layout._adjacent_interval_midpoints(nonuniform, 20.0) == (
        10.0,
        60.0,
    )
    assert layout._adjacent_interval_midpoints(nonuniform, 100.0) == (60.0,)


def test_default_grid_refinement_transform_ranking_and_top_n_disclosure(
    simulation_context: SimulationContext,
) -> None:
    import rocell.application.prehardware_layout_study as layout

    report = _run(simulation_context, _fake_ik_class())
    document = report.to_dict()
    all_screens = (*report.coarse_screens, *report.refinement_screens)

    assert len(report.coarse_screens) == 243
    assert 0 < len(report.refinement_screens) <= 60
    all_ids = tuple(
        row.hypothesis.study_input.study_input_id for row in all_screens
    )
    assert len(all_ids) == len(set(all_ids))
    assert tuple(row.ranking_key for row in report.ranked_regression_passes) == (
        tuple(sorted(row.ranking_key for row in report.ranked_regression_passes))
    )

    ranked_ids = tuple(
        row.hypothesis.study_input.study_input_id
        for row in report.ranked_regression_passes
    )
    assert report.full_catalog_shortlist_candidate_ids == ranked_ids[:8]
    assert report.omitted_regression_pass_candidate_ids == ranked_ids[8:]
    shortlist = document["search"]["full_catalog_shortlist"]
    assert shortlist["policy_top_n"] == 8
    assert shortlist["total_regression_pass_candidates"] == len(ranked_ids)
    assert shortlist["screened_candidate_count"] == 8
    assert shortlist["screened_candidate_ids_in_rank_order"] == list(
        ranked_ids[:8]
    )
    assert shortlist["omitted_candidate_count"] == len(ranked_ids) - 8
    assert shortlist["omitted_candidate_ids_in_rank_order"] == list(
        ranked_ids[8:]
    )
    assert shortlist["truncated"] is True
    assert "only to the screened" in shortlist["status_scope"]
    assert report.status == (
        "CANDIDATES_ELIGIBLE_WITHIN_SCREENED_FULL_CATALOG_SHORTLIST"
    )

    coarse_by_id = {
        row.hypothesis.study_input.study_input_id: row.hypothesis.study_input
        for row in report.coarse_screens
    }
    policy = report.policy
    axes = {
        "rear_clamp_contact_x_board_mm": policy.rear_clamp_contact_x.values,
        "rear_edge_to_base_axis_y_mm": policy.rear_edge_to_base_axis_y.values,
        "base_yaw_board_rad": policy.base_yaw_board.values,
        "keyboard_tool_length_mm": policy.keyboard_tool_length.values,
        "phone_tool_length_mm": policy.phone_tool_length.values,
    }
    for screen in report.refinement_screens:
        hypothesis = screen.hypothesis
        assert hypothesis.anchor_study_input_id is not None
        anchor = coarse_by_id[hypothesis.anchor_study_input_id]
        refined = hypothesis.study_input
        changed = tuple(
            name
            for name in axes
            if not math.isclose(getattr(anchor, name), getattr(refined, name))
        )
        assert len(changed) == 1
        name = changed[0]
        anchor_value = getattr(anchor, name)
        refined_value = getattr(refined, name)
        values = axes[name]
        index = values.index(anchor_value)
        expected_midpoints = set()
        if index > 0:
            expected_midpoints.add((values[index - 1] + anchor_value) / 2.0)
        if index + 1 < len(values):
            expected_midpoints.add((anchor_value + values[index + 1]) / 2.0)
        assert any(
            math.isclose(refined_value, expected, abs_tol=1e-12)
            for expected in expected_midpoints
        )

    loaded = layout.load_pinned_urdf(
        simulation_context.scenario.model_path,
        simulation_context.scenario.model_sha256,
    )
    vendor_world_T_base_link = loaded.model.joint(
        "world_to_base_link"
    ).transform_at(None)
    for screen in all_screens:
        study = screen.hypothesis.study_input
        recomposed = study.board_T_vendor_world.compose(
            vendor_world_T_base_link
        )
        assert recomposed.to_transform().matrix == pytest.approx(
            study.board_T_base_link.to_transform().matrix,
            abs=1e-9,
        )
    assert document["transform_contract"][
        "verified_for_every_generated_hypothesis"
    ] is True


def test_complete_candidate_is_only_promoted_for_external_full_route_screen(
    simulation_context: SimulationContext,
) -> None:
    policy = _single_policy(simulation_context)
    first = _run(simulation_context, _fake_ik_class(), policy)
    second = _run(simulation_context, _fake_ik_class(), policy)
    document = first.to_dict()

    assert first.report_hash == second.report_hash
    assert first.status == (
        "CANDIDATES_ELIGIBLE_WITHIN_SCREENED_FULL_CATALOG_SHORTLIST"
    )
    assert len(first.coarse_screens) == 1
    assert len(first.refinement_screens) == 0
    assert len(first.full_catalog_screens) == 1
    full = first.full_catalog_screens[0]
    assert full.contacts.total_count("keyboard") == 46
    assert full.contacts.total_count("phone") == 29
    assert full.contacts.all_contacts_accepted is True
    assert full.phone_key_a_contact.feasibility.accepted is True
    assert full.phone_key_a_approach.accepted is True
    assert full.eligible_for_full_route_screen is True
    assert len(first.promoted_candidates) == 1
    promoted = first.promoted_candidates[0].to_dict()
    assert promoted["eligible_for_full_route_screen"] is True
    assert promoted["full_route_screen_executed"] is False
    assert promoted["physical_motion_authorized"] is False
    assert promoted["selected_park_probe"] == {
        "park_id": "freeze005-selected:park-290000-010000-070000",
        "point_board_mm": [290.0, 10.0, 70.0],
    }
    binding = document["selected_park_probe_binding"]
    assert binding["per_hypothesis_probe_set_size"] == 1
    assert binding["per_hypothesis_ranking_performed"] is False
    assert binding["re_screened_for_every_layout_and_route_tool"] is True
    assert "no per-layout park optimization" in binding["selection_algorithm"]
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["execution_authorized"] is False
    assert document["canonical_context_modified"] is False
    assert first.actual_layout_ik_solve_count <= first.planned_layout_ik_solve_upper_bound
    assert (
        first.actual_layout_ik_solve_count
        + first.park_optimizer_actual_ik_solve_count
        <= 4288
    )
    provenance = document["source_provenance"]
    assert provenance["captured_model_sha256"] == provenance["model_sha256"]
    assert provenance["captured_model_matches_pinned_sha256"] is True
    assert provenance["solver_mode"] == "EXPLICIT_UNIT_TEST_DOUBLE"
    assert provenance["ik_solver_algorithm_version"] == "EXPLICIT_TEST_DOUBLE"
    assert set(provenance["coarse_ik_options"]) == {
        "max_attempts",
        "max_iterations_per_attempt",
        "position_tolerance_mm",
        "alignment_tolerance_rad",
        "orientation_weight_mm_per_rad",
        "finite_difference_step_rad",
        "initial_damping",
        "minimum_damping",
        "maximum_damping",
        "max_joint_step_rad",
        "line_search_steps",
    }
    assert set(provenance["canonical_ik_options"]) == set(
        provenance["coarse_ik_options"]
    )
    assert provenance["coarse_ik_options"]["max_attempts"] == 2
    assert provenance["coarse_ik_options"]["max_iterations_per_attempt"] == 18
    assert provenance["canonical_ik_options"]["max_attempts"] == (
        simulation_context.scenario.ik_policy.max_attempts
    )
    assert provenance["canonical_ik_options"]["max_iterations_per_attempt"] == (
        simulation_context.scenario.ik_policy.max_iterations_per_attempt
    )
    assert len(provenance["reach_optimizer_policy_module_sha256"]) == 64
    assert len(provenance["rc03_workcell_layout_sha256"]) == 64
    assert len(provenance["rc03_robot_reach_screening_sha256"]) == 64


def test_phone_key_a_approach_is_a_named_positive_margin_regression(
    simulation_context: SimulationContext,
) -> None:
    context = simulation_context
    key_a = context.targets.phone_targets["key_a"]
    failure_z = (
        key_a.center.z
        - context.scenario.path_policy.contact_overtravel_mm
        + context.scenario.path_policy.approach_height_mm
    )
    report = _run(
        context,
        _fake_ik_class(lambda point: math.isclose(point.z, failure_z)),
        _single_policy(context),
    )

    assert report.status == (
        "NO_CANDIDATE_FOUND_WITHIN_SCREENED_FULL_CATALOG_SHORTLIST"
    )
    assert len(report.full_catalog_screens) == 0
    assert len(report.promoted_candidates) == 0
    screen = report.coarse_screens[0]
    assert screen.regression_passed is False
    approach = screen.named("PHONE_KEY_A_APPROACH")
    assert approach.feasibility.accepted is False
    assert approach.feasibility.status == (
        "MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED"
    )
    assert approach.feasibility.minimum_normalized_arm_joint_margin == 0.0
    assert screen.named("PHONE_KEY_A_CONTACT").feasibility.accepted is True


def test_full_catalog_failure_is_not_promoted_even_after_regression_pass(
    simulation_context: SimulationContext,
) -> None:
    # Choose a keyboard contact that is not one of the three deterministic
    # sentinels so the candidate reaches the canonical full-catalog stage.
    import rocell.application.prehardware_layout_study as layout

    targets = layout._target_catalog(simulation_context)
    sentinels = set(layout._spatial_sentinels(targets, 3))
    failed_target = next(
        row
        for row in targets
        if row.device == "keyboard" and row not in sentinels
    )
    failed_point = layout._contact_point(simulation_context, failed_target)

    def reject(point: Point3Mm) -> bool:
        return (
            math.isclose(point.x, failed_point.x)
            and math.isclose(point.y, failed_point.y)
            and math.isclose(point.z, failed_point.z)
        )

    report = _run(
        simulation_context,
        _fake_ik_class(reject),
        _single_policy(simulation_context),
    )

    assert report.coarse_screens[0].regression_passed is True
    assert len(report.full_catalog_screens) == 1
    full = report.full_catalog_screens[0]
    assert full.contacts.accepted_count("keyboard") == 45
    assert full.contacts.accepted_count("phone") == 29
    assert full.eligible_for_full_route_screen is False
    assert "FULL_46_KEYBOARD_PLUS_29_PHONE_CONTACTS_NOT_ACCEPTED" in (
        full.rejection_reasons
    )
    assert len(report.promoted_candidates) == 0


def test_planned_solve_cap_fails_before_full_catalog_stage(
    simulation_context: SimulationContext,
) -> None:
    policy = replace(
        _single_policy(simulation_context),
        maximum_layout_ik_solves=87,
    )
    with pytest.raises(
        PrehardwareLayoutStudyError,
        match="planned layout IK upper bound 88 exceeds policy cap 87",
    ):
        _run(simulation_context, _fake_ik_class(), policy)


def test_policy_rejects_axes_outside_sensitivity_caps(
    simulation_context: SimulationContext,
) -> None:
    policy = default_prehardware_layout_study_policy(simulation_context)
    rear = policy.rear_edge_to_base_axis_y
    bad_evidence = replace(rear.value_evidence[-1], value=100.001)
    bad_axis = replace(
        rear,
        value_evidence=(*rear.value_evidence[:-1], bad_evidence),
    )
    with pytest.raises(PrehardwareLayoutStudyError, match=r"\[0, 100\]"):
        replace(policy, rear_edge_to_base_axis_y=bad_axis)
