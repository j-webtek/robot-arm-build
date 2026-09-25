from __future__ import annotations

import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import cast

import pytest

from rocell.application import (
    FREEZE005_REACH_REPORT_SHA256,
    FREEZE005_SELECTED_STUDY_INPUT_ID,
    ParkOptimizationError,
    ParkOptimizationPolicy,
    SimulationContext,
    load_simulation_context,
)
from rocell.geometry import UrdfModel
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
def simulation_context(tmp_path_factory: pytest.TempPathFactory) -> SimulationContext:
    root = tmp_path_factory.mktemp("park-optimizer") / "workspace"
    workspace, manifest_path = _coherent_frozen_copy(root)
    return load_simulation_context(workspace, manifest_path)


def _smooth_fake_ik_class() -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]

        def solve(self, target: object) -> SimpleNamespace:
            point = target.position_mm
            fraction = 0.12 + 0.15 * point.x / 610.0
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
                    position_error_mm=point.y / 100_000.0,
                    alignment_error_rad=0.0,
                ),
                attempts=(object(), object()),
                selected_attempt_index=0,
            )

    return FakeIk


def _boundary_fake_ik_class() -> type:
    class FakeIk:
        def __init__(self, **kwargs: object) -> None:
            self.bounds = kwargs["joint_bounds_rad"]

        def solve(self, target: object) -> SimpleNamespace:
            del target
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
                    position_error_mm=0.0,
                    alignment_error_rad=0.0,
                ),
                attempts=(object(),),
                selected_attempt_index=0,
            )

    return FakeIk


def _run_with_test_solver(
    context: SimulationContext,
    solver_class: type,
    policy: ParkOptimizationPolicy | None = None,
) -> object:
    import rocell.application.park_optimizer as park

    return park._run_park_optimization_with_solver(
        context,
        policy,
        solver_class=solver_class,
        solver_mode="EXPLICIT_UNIT_TEST_DOUBLE",
    )


@pytest.mark.parametrize(
    "manifest_id",
    (
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-006",
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-007",
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-008",
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-009",
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-010",
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-011",
    ),
)
def test_later_freezes_reuse_freeze005_source_and_unknown_freeze_rejects(
    monkeypatch: pytest.MonkeyPatch,
    manifest_id: str,
) -> None:
    import rocell.application.park_optimizer as park

    selected = SimpleNamespace(study_input_id=FREEZE005_SELECTED_STUDY_INPUT_ID)
    monkeypatch.setattr(
        park,
        "_default_reach_study_inputs_from_model",
        lambda *_: (selected,),
    )
    opaque_model = cast(UrdfModel, object())
    compatible_context = cast(
        SimulationContext,
        SimpleNamespace(
            snapshot=SimpleNamespace(manifest_id=manifest_id)
        ),
    )

    assert park._selected_study(compatible_context, opaque_model) is selected

    unknown_context = cast(
        SimulationContext,
        SimpleNamespace(
            snapshot=SimpleNamespace(
                manifest_id="ROCELL-PHASE0-RC03-INT-R1-FREEZE-999"
            )
        ),
    )
    with pytest.raises(ParkOptimizationError, match="no documented source binding"):
        park._selected_study(unknown_context, opaque_model)


def test_policy_is_hashed_and_all_resource_axes_are_bounded() -> None:
    policy = ParkOptimizationPolicy()

    assert policy.policy_hash == policy.policy_hash
    assert len(policy.policy_hash) == 64
    assert policy.maximum_coarse_raw_candidates == 128
    assert policy.maximum_coarse_eligible_candidates == 64
    assert policy.maximum_refinement_raw_candidates == 32
    assert policy.maximum_total_ik_solves == 192
    assert policy.to_dict()["hard_implementation_caps"]["total_ik_solves"] == 192
    assert (
        policy.to_dict()["hard_implementation_caps"]["captured_urdf_bytes"]
        == 1_000_000
    )

    with pytest.raises(ParkOptimizationError, match="coarse_maximum_spacing_mm"):
        ParkOptimizationPolicy(coarse_maximum_spacing_mm=10.0)
    with pytest.raises(ParkOptimizationError, match="candidate ceilings"):
        ParkOptimizationPolicy(maximum_total_ik_solves=100)
    with pytest.raises(ParkOptimizationError, match="raw-candidate budget"):
        ParkOptimizationPolicy(
            refinement_anchor_count=5,
            maximum_refinement_raw_candidates=32,
        )


def test_geometry_derived_search_is_deterministic_complete_and_non_authoritative(
    simulation_context: SimulationContext,
) -> None:
    assert simulation_context.snapshot.manifest_id == (
        "ROCELL-PHASE0-RC03-INT-R1-FREEZE-011"
    )
    scenario_before = simulation_context.scenario
    fake = _smooth_fake_ik_class()
    first = _run_with_test_solver(simulation_context, fake)
    second = _run_with_test_solver(simulation_context, fake)
    document = first.to_dict()

    assert first.report_hash == second.report_hash
    assert first.status == "PARK_POSE_DIAGNOSTIC_COMPLETE_CANDIDATE_FOUND"
    assert first.selected_study_input.study_input_id == (
        FREEZE005_SELECTED_STUDY_INPUT_ID
    )
    assert first.transit_plane_z_mm == pytest.approx(70.0)
    assert len(first.coarse_proposals) == 100
    assert len(first.coarse_evaluations) == 63
    assert len(first.fine_proposals) == 32
    assert first.ranked_candidates
    assert first.best_candidate is first.ranked_candidates[0]
    assert first.best_candidate.all_routes_accepted is True
    assert first.best_candidate.geometry.point_board.frame == "board"
    assert any(
        proposal.proposal_id == "coarse-baseline"
        for proposal in first.coarse_proposals
    )
    assert tuple(row.ranking_key for row in first.ranked_candidates) == tuple(
        sorted(row.ranking_key for row in first.ranked_candidates)
    )
    assert all(
        row.geometry.eligible_for_ik
        and row.geometry.point_board.z == pytest.approx(70.0)
        and len(row.route_results) == 2
        and row.all_routes_accepted
        for row in first.ranked_candidates
    )
    assert first.actual_ik_solve_count == len(first.ranked_candidates)
    assert first.unique_route_tool_length_count == 1
    assert all(
        row.route_results[0].reused_identical_tool_solution is False
        and row.route_results[1].reused_identical_tool_solution is True
        for row in first.ranked_candidates
    )
    assert any(
        reason.startswith("KEEPOUT_CLEARANCE_REJECTED")
        for proposal in first.coarse_proposals
        for reason in proposal.rejection_reasons
    )
    assert any(
        reason.startswith("TAG_CLEARANCE_REJECTED")
        for proposal in first.coarse_proposals
        for reason in proposal.rejection_reasons
    )
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["execution_authorized"] is False
    assert document["canonical_context_modified"] is False
    assert document["transit_plane"]["candidate_z_axis_searched"] is False
    assert document["geometry_generation"]["frozen_baseline_was_injected"] is True
    assert (
        document["geometry_generation"]["frozen_baseline_proposal_id"]
        == "coarse-baseline"
    )
    assert simulation_context.scenario is scenario_before

    provenance = document["source_provenance"]
    assert provenance["manifest_id"] == simulation_context.snapshot.manifest_id
    assert provenance["documented_selection_reach_report_sha256"] == (
        FREEZE005_REACH_REPORT_SHA256
    )
    assert provenance["reach_report_artifact_verified"] is False
    assert provenance["captured_model_sha256"] == provenance["model_sha256"]
    assert provenance["captured_model_matches_pinned_sha256"] is True
    assert 0 < provenance["captured_model_byte_count"] <= 1_000_000
    assert provenance["solver_mode"] == "EXPLICIT_UNIT_TEST_DOUBLE"
    assert provenance["ik_solver_algorithm_version"] == "EXPLICIT_TEST_DOUBLE"
    assert provenance["ik_solver_identity"].endswith("FakeIk")
    for name in (
        "park_optimizer_module_sha256",
        "ik_module_sha256",
        "active_ik_solver_source_sha256",
        "rocell_source_tree_sha256",
        "park_implementation_bundle_sha256",
    ):
        assert len(provenance[name]) == 64
        int(provenance[name], 16)

    detached = first.to_dict()
    original_hash = first.report_hash
    detached["best_candidate"]["geometry"]["point_board_mm"][0] = -1.0
    assert first.report_hash == original_hash


def test_frozen_baseline_is_evidenced_when_it_coincides_with_lattice(
    simulation_context: SimulationContext,
) -> None:
    report = _run_with_test_solver(
        simulation_context,
        _smooth_fake_ik_class(),
        ParkOptimizationPolicy(
            board_edge_inset_mm=57.0,
            coarse_maximum_spacing_mm=124.0,
            refinement_anchor_count=1,
            maximum_refinement_raw_candidates=8,
            maximum_refinement_eligible_candidates=8,
        ),
    )
    geometry = report.to_dict()["geometry_generation"]

    assert report.frozen_baseline_was_injected is False
    assert geometry["frozen_baseline_was_injected"] is False
    assert geometry["frozen_baseline_was_coincident_with_lattice"] is True
    assert geometry["frozen_baseline_candidate_id"] == (
        report.frozen_baseline_candidate_id
    )
    assert geometry["frozen_baseline_proposal_id"].startswith("coarse-")
    assert any(
        proposal.candidate_id == report.frozen_baseline_candidate_id
        for proposal in report.coarse_proposals
    )


def test_positive_arm_margin_gate_rejects_joint_boundary_solutions(
    simulation_context: SimulationContext,
) -> None:
    report = _run_with_test_solver(
        simulation_context,
        _boundary_fake_ik_class(),
    )

    assert report.status == "PARK_POSE_DIAGNOSTIC_NO_COMPLETE_CANDIDATE"
    assert report.ranked_candidates
    assert all(
        row.accepted_route_count == 0
        and all(
            route.feasibility.status
            == "MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED"
            and route.feasibility.minimum_normalized_arm_joint_margin == 0.0
            for route in row.route_results
        )
        for row in report.ranked_candidates
    )
    assert dict(report.source_provenance)["fixed_gripper_in_arm_margin_gate"] is False


def test_coarse_grid_fails_before_ik_when_raw_resource_cap_is_exceeded(
    simulation_context: SimulationContext,
) -> None:
    class ForbiddenIk:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("IK must not start for an oversized lattice")

    with pytest.raises(ParkOptimizationError, match="coarse lattice has"):
        _run_with_test_solver(
            simulation_context,
            ForbiddenIk,
            ParkOptimizationPolicy(coarse_maximum_spacing_mm=20.0),
        )


def test_model_mutation_after_context_revalidation_fails_before_ik(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.park_optimizer as park

    model_path = simulation_context.scenario.model_path
    original_payload = model_path.read_bytes()
    original_revalidate = park.revalidate_simulation_context

    def mutate_after_revalidation(context: SimulationContext) -> None:
        original_revalidate(context)
        model_path.write_bytes(original_payload + b"\n<!-- post-validation swap -->\n")

    class ForbiddenIk:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("IK must not start from a mutated model")

    monkeypatch.setattr(
        park, "revalidate_simulation_context", mutate_after_revalidation
    )
    try:
        with pytest.raises(ParkOptimizationError, match="pinned model byte hash mismatch"):
            _run_with_test_solver(simulation_context, ForbiddenIk)
    finally:
        model_path.write_bytes(original_payload)


def test_oversized_model_capture_fails_before_parse_or_ik(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application._pinned_model as pinned_model

    class ForbiddenIk:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("IK must not start for an oversized model capture")

    monkeypatch.setattr(pinned_model, "MAX_PINNED_URDF_BYTES", 32)
    with pytest.raises(ParkOptimizationError, match="pinned model exceeds"):
        _run_with_test_solver(simulation_context, ForbiddenIk)
