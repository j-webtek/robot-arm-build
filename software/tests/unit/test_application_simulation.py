from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from rocell.application import (
    SimulationContextError,
    assess_calibration_status,
    load_simulation_context,
    run_simulation,
)
from rocell.calibration import ordered_requirement_closure
from rocell.application.context import SimulationContext
from rocell.application.simulate import sample_ik_steps
from rocell.application.target_sweep import (
    SweepPhase,
    _complete_matrix_requested,
    run_target_sweep,
)
from rocell.models.frames import Point3Mm
from rocell.motion import GeometricPathStep, MotionPhase
from rocell.rc03.integrity import sha256_file
from rocell.simulation import (
    ToolTipPathPolicy,
)
from rocell.typing import compile_development_text
from rocell.workcell import validate_placemat_alignment


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
    """Refresh pins only in an isolated copy; controlled RC03 stays untouched."""

    manifest = json.loads(
        (WORKSPACE / "software/config/system_manifest.json").read_text(encoding="utf-8")
    )
    assert isinstance(manifest, dict)
    rc03 = manifest["rc03"]
    assert isinstance(rc03, dict)
    rc03_relative = rc03["root"]
    source_snapshot = rc03["source_snapshot"]
    assert isinstance(rc03_relative, str)
    assert isinstance(source_snapshot, list)
    for entry in source_snapshot:
        assert isinstance(entry, dict)
        relative = entry["path"]
        assert isinstance(relative, str)
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
    root = tmp_path_factory.mktemp("coherent-simulation-context") / "workspace"
    workspace, manifest_path = _coherent_frozen_copy(root)
    return load_simulation_context(workspace, manifest_path)


def _step(sequence: int, phase: MotionPhase, x: float) -> GeometricPathStep:
    return GeometricPathStep(
        sequence=sequence,
        phase=phase,
        action_index=sequence,
        semantic_target=f"keyboard:{sequence}",
        tip_point_board=Point3Mm("board", x, 100.0, 20.0),
        check_id=None,
    )


def test_contact_first_ik_sampling_is_typed_deterministic_and_bounded() -> None:
    steps = (
        _step(0, MotionPhase.PARK, 0.0),
        _step(1, MotionPhase.CONTACT, 1.0),
        _step(2, MotionPhase.HOVER, 2.0),
        _step(3, MotionPhase.CONTACT, 3.0),
        _step(4, MotionPhase.APPROACH, 4.0),
    )

    selected = sample_ik_steps(steps, 3)

    assert tuple(step.sequence for step in selected) == (0, 1, 3)
    assert selected[0].phase is MotionPhase.PARK
    assert sum(step.phase is MotionPhase.CONTACT for step in selected) == 2
    with pytest.raises(ValueError, match="positive integer"):
        sample_ik_steps(steps, 0)


def test_typed_scenario_drives_placemat_path_camera_and_controller_limits(
    simulation_context: SimulationContext,
) -> None:
    scenario = simulation_context.scenario

    assert scenario.path_policy == ToolTipPathPolicy(
        clearance_above_highest_obstacle_mm=35.0,
        segment_clearance_mm=5.0,
        hover_height_mm=12.0,
        approach_height_mm=3.0,
        contact_overtravel_mm=1.0,
        park_xy_board_mm=(305.0, 400.0),
    )
    assert scenario.overview.scenario_id == "SYNTHETIC_FIXED_OVERVIEW_TEST_FIXTURE"
    assert scenario.overview.scenario_is_arm_mounted_camera is False
    assert scenario.board_frame == "board"
    assert scenario.assumed_tag_plane_z_mm == pytest.approx(0.3)
    assert scenario.station_proxy_height_mm == pytest.approx(35.0)
    assert scenario.tool_case_id == "nominal_tool_100mm"
    assert len(scenario.tool_cases) == 4
    assert scenario.controller_joint_intersection_rad["link2_to_link3"] == (0.0, 2.95)
    assert scenario.controller_gripper_intersection_rad == (0.0, 1.5)
    assert scenario.fixed_gripper_position.value == pytest.approx(0.0)
    assert tuple(
        position.value for position in scenario.ready_arm_joint_positions_rad.values()
    ) == pytest.approx((0.0, 0.0, 2.618, -1.0472, 0.0))


def test_placemat_alignment_covers_semantics_geometry_camera_and_holds(
    simulation_context: SimulationContext,
) -> None:
    report = simulation_context.alignment
    checks = {check.check_id: check for check in report.checks}

    assert report.all_checks_pass is True
    assert report.status == "PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS"
    assert len(checks) == 17
    for required in (
        "board_frame_and_envelope",
        "fiducial_tiles_on_board",
        "semantic_geometry_profile_binding",
        "semantic_target_coverage",
        "nominal_arm_clamp_placement",
        "camera_identity_and_fixture_boundary",
        "physical_authority_holds",
    ):
        assert checks[required].status == "PASS"


def test_placemat_alignment_rejects_park_inside_keyboard_keepout(
    simulation_context: SimulationContext,
) -> None:
    policy = replace(
        simulation_context.scenario.path_policy,
        park_xy_board_mm=(100.0, 100.0),
    )
    scenario = replace(simulation_context.scenario, path_policy=policy)

    report = validate_placemat_alignment(
        simulation_context.hardware_profile,
        scenario,
        simulation_context.scene,
        simulation_context.targets,
    )

    check = next(item for item in report.checks if item.check_id == "nominal_park_point")
    assert check.status == "FAIL"
    assert report.all_checks_pass is False


def test_placemat_alignment_rejects_station_tag_and_target_aliasing(
    simulation_context: SimulationContext,
) -> None:
    scene = simulation_context.scene
    station_obstacles = list(scene.obstacles)
    phone_station_index = next(
        index
        for index, obstacle in enumerate(station_obstacles)
        if obstacle.obstacle_id == "station:phone_tcp"
    )
    phone_station = station_obstacles[phone_station_index]
    station_obstacles[phone_station_index] = replace(
        phone_station,
        minimum=Point3Mm("board", 0.0, 70.0, 0.0),
        maximum=Point3Mm("board", 186.3, 242.8, 35.0),
    )
    moved_station_scene = replace(scene, obstacles=tuple(station_obstacles))
    moved_report = validate_placemat_alignment(
        simulation_context.hardware_profile,
        simulation_context.scenario,
        moved_station_scene,
        simulation_context.targets,
    )
    assert next(
        check for check in moved_report.checks if check.check_id == "station_envelopes_on_board"
    ).status == "FAIL"

    fiducials = list(scene.fiducials)
    fiducials[-1] = replace(fiducials[-1], center=fiducials[0].center)
    overlapping_tag_scene = replace(scene, fiducials=tuple(fiducials))
    tag_report = validate_placemat_alignment(
        simulation_context.hardware_profile,
        simulation_context.scenario,
        overlapping_tag_scene,
        simulation_context.targets,
    )
    assert next(
        check for check in tag_report.checks if check.check_id == "fiducial_keepouts"
    ).status == "FAIL"

    keyboard_targets = dict(simulation_context.targets.keyboard_targets)
    keyboard_targets["B"] = replace(
        keyboard_targets["B"],
        center=keyboard_targets["A"].center,
    )
    overlapping_targets = replace(
        simulation_context.targets,
        keyboard_targets=keyboard_targets,
    )
    target_report = validate_placemat_alignment(
        simulation_context.hardware_profile,
        simulation_context.scenario,
        scene,
        overlapping_targets,
    )
    assert next(
        check for check in target_report.checks if check.check_id == "target_regions_and_planes"
    ).status == "FAIL"


def test_end_to_end_service_reports_unperformed_observers_and_never_commands_hardware(
    simulation_context: SimulationContext,
) -> None:
    report = run_simulation(
        simulation_context,
        compile_development_text("phone", "a"),
    )
    document = report.to_dict()

    assert document["required_simulation_checks_pass"] is True
    assert document["hardware_commands_generated"] == 0
    assert document["sources"]["simulation_bundle"]["bundle_id"] == (
        simulation_context.bundle_lock.bundle_id
    )
    assert document["sources"]["simulation_bundle"]["physical_release_effect"] == "NONE"
    loaded_model = document["sources"]["kinematic_model"]
    assert loaded_model["expected_sha256"] == simulation_context.scenario.model_sha256
    assert loaded_model["loaded_sha256"] == loaded_model["expected_sha256"]
    assert loaded_model["loaded_byte_count"] == (
        simulation_context.scenario.model_path.stat().st_size
    )
    assert loaded_model["maximum_bytes"] == 1_000_000
    assert loaded_model["exact_captured_bytes_verified"] is True
    assert document["ik"]["kinematic_model"] == loaded_model
    assert document["placemat_alignment"]["all_checks_pass"] is True
    assert document["vision"]["eye_on_arm_coverage"]["status"] == (
        "NOT_RUN_INSTALL_TRANSFORMS_MISSING"
    )
    assert document["verification"]["status"] == (
        "NOT_PERFORMED_OBSERVERS_NOT_IMPLEMENTED"
    )
    assert document["controller_bridge"]["frame_equivalence_assumed"] is False
    assert document["controller_bridge"]["t104_commands_generated"] == 0
    assert document["ik"]["fixed_gripper_position_rad"] == pytest.approx(0.0)
    assert document["ik"]["controller_gripper_intersection_rad"] == [0.0, 1.5]

    original_hash = report.report_hash
    document["vision"]["camera_model"]["distortion"]["k1"] = 9.0
    document["geometry"]["scene_source_hashes"]["tampered"] = "0" * 64
    assert report.report_hash == original_hash


def test_target_sweep_can_exhaustively_screen_a_selected_catalog_subset(
    simulation_context: SimulationContext,
) -> None:
    report = run_target_sweep(
        simulation_context,
        devices=("keyboard",),
        tool_case_ids=(simulation_context.scenario.tool_case_id,),
        phases=(SweepPhase.CONTACT,),
        target_ids=("A",),
    )
    document = report.to_dict()

    assert len(report.results) == 1
    assert document["hardware_commands_generated"] == 0
    assert document["simulation_bundle_id"] == simulation_context.bundle_lock.bundle_id
    assert document["loaded_model"] == {
        "used": True,
        "sha256": simulation_context.scenario.model_sha256,
        "byte_count": simulation_context.scenario.model_path.stat().st_size,
        "maximum_bytes": 1_000_000,
    }
    assert document["status"] in {"PASS_SELECTED_MATRIX", "FEASIBILITY_GAPS_REPORTED"}
    assert document["complete_matrix"] is False
    assert document["park_total_count"] == 1
    assert document["park_results"][0]["role"] == "REQUIRED_INITIAL_AND_FINAL_ROUTE_POSE"
    assert document["results"][0]["target_id"] == "A"
    assert document["results"][0]["phase"] == "contact"
    assert "accepted" in document["results"][0]

    original_hash = report.report_hash
    document["effective_scenario"]["path_policy"]["park_xy_board_mm"][0] = -999.0
    first_joint = next(
        iter(document["effective_scenario"]["ik_policy"]["joint_bounds"])
    )
    document["effective_scenario"]["ik_policy"]["joint_bounds"][first_joint][0] = -999.0
    assert report.report_hash == original_hash

    with pytest.raises(ValueError, match="Unknown targets"):
        run_target_sweep(
            simulation_context,
            devices=("keyboard",),
            tool_case_ids=(simulation_context.scenario.tool_case_id,),
            phases=(SweepPhase.CONTACT,),
            target_ids=("NOT_A_LOCKED_TARGET",),
        )


def test_complete_matrix_requires_the_entire_locked_target_catalog() -> None:
    common = {
        "selected_devices": ("keyboard", "phone"),
        "selected_case_ids": ("tool-0", "tool-1"),
        "all_case_ids": ("tool-0", "tool-1"),
        "selected_phases": tuple(SweepPhase),
        "catalog_target_count": 75,
    }

    assert _complete_matrix_requested(**common, selected_target_count=75) is True
    assert _complete_matrix_requested(**common, selected_target_count=2) is False


def test_all_context_services_reject_replaced_scenario_and_alignment(
    simulation_context: SimulationContext,
) -> None:
    bad_policy = replace(
        simulation_context.scenario.path_policy,
        park_xy_board_mm=(100.0, 100.0),
    )
    bad_scenario = replace(simulation_context.scenario, path_policy=bad_policy)
    bad_alignment = validate_placemat_alignment(
        simulation_context.hardware_profile,
        bad_scenario,
        simulation_context.scene,
        simulation_context.targets,
    )
    context = replace(
        simulation_context,
        scenario=bad_scenario,
        alignment=bad_alignment,
    )

    plan = compile_development_text("phone", "a")
    with pytest.raises(SimulationContextError, match="scenario.*alignment"):
        run_simulation(context, plan)
    with pytest.raises(SimulationContextError, match="scenario.*alignment"):
        run_target_sweep(
            context,
            devices=("phone",),
            tool_case_ids=(context.scenario.tool_case_id,),
            phases=(SweepPhase.CONTACT,),
        )
    with pytest.raises(SimulationContextError, match="scenario.*alignment"):
        assess_calibration_status(context, "phone")


def test_context_guard_rejects_each_replaced_locked_component(
    simulation_context: SimulationContext,
) -> None:
    only_a = {"A": simulation_context.targets.keyboard_targets["A"]}
    tampered_contexts = (
        (
            "snapshot",
            replace(
                simulation_context,
                snapshot=replace(
                    simulation_context.snapshot,
                    safe_to_power_robot=True,
                ),
            ),
        ),
        (
            "bundle_lock",
            replace(
                simulation_context,
                bundle_lock=replace(
                    simulation_context.bundle_lock,
                    bundle_id=simulation_context.bundle_lock.bundle_id + "-TAMPERED",
                ),
            ),
        ),
        (
            "hardware_profile",
            replace(
                simulation_context,
                hardware_profile=replace(
                    simulation_context.hardware_profile,
                    assumptions=simulation_context.hardware_profile.assumptions
                    + ("tampered in memory",),
                ),
            ),
        ),
        (
            "scenario",
            replace(
                simulation_context,
                scenario=replace(
                    simulation_context.scenario,
                    path_policy=replace(
                        simulation_context.scenario.path_policy,
                        park_xy_board_mm=(100.0, 100.0),
                    ),
                ),
            ),
        ),
        (
            "scene",
            replace(
                simulation_context,
                scene=replace(
                    simulation_context.scene,
                    assumptions=simulation_context.scene.assumptions
                    + ("tampered in memory",),
                ),
            ),
        ),
        (
            "targets",
            replace(
                simulation_context,
                targets=replace(
                    simulation_context.targets,
                    keyboard_targets=only_a,
                ),
            ),
        ),
        (
            "alignment",
            replace(
                simulation_context,
                alignment=replace(
                    simulation_context.alignment,
                    checks=simulation_context.alignment.checks[:-1],
                ),
            ),
        ),
    )

    for component, context in tampered_contexts:
        with pytest.raises(SimulationContextError, match=component):
            run_target_sweep(
                context,
                devices=("keyboard",),
                tool_case_ids=(context.scenario.tool_case_id,),
                phases=(SweepPhase.CONTACT,),
                target_ids=("A",),
            )


def test_calibration_graph_is_prerequisite_first_and_current_registry_is_blocked(
    simulation_context: SimulationContext,
) -> None:
    ordered = ordered_requirement_closure(("keyboard_tcp", "keyboard_outcome_observer"))
    assert ordered.index("robot_reference") < ordered.index("arm_board")
    assert ordered.index("arm_board") < ordered.index("controller_correlation")
    assert ordered.index("keyboard_pose") < ordered.index("keyboard_tcp")

    report = assess_calibration_status(simulation_context, "keyboard")
    document = report.to_dict()

    assert report.all_valid is False
    assert document["status"] == "BLOCKED_MISSING_OR_STALE"
    assert document["simulation_bundle_id"] == simulation_context.bundle_lock.bundle_id
    assert all(
        row["assessment"]["state"] == "MISSING"
        for row in document["ordered_requirements"]
    )
    assert document["hardware_accessed"] is False
