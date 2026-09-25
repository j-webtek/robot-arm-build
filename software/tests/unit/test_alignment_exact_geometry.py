from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import rocell.workcell.alignment as alignment_module
from rocell.models.frames import Point3Mm
from rocell.geometry import Rotation3, Vec3
from rocell.simulation import (
    load_rc03_nominal_scene,
    load_simulation_hardware_profile,
    load_simulation_scenario,
)
from rocell.targets import load_nominal_target_catalog
from rocell.typing import development_keyboard_profile, development_phone_profile
from rocell.workcell import validate_placemat_alignment


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def nominal_sources():
    profile = load_simulation_hardware_profile(WORKSPACE)
    scenario = load_simulation_scenario(WORKSPACE)
    scene = load_rc03_nominal_scene(
        WORKSPACE / "active-project/RoCell_v0_3",
        assumed_tag_plane_z_mm=scenario.assumed_tag_plane_z_mm,
        station_proxy_height_mm=scenario.station_proxy_height_mm,
    )
    targets = load_nominal_target_catalog(WORKSPACE)
    return profile, scenario, scene, targets


def test_alignment_rejects_non_anchor_keyboard_target_drift(nominal_sources) -> None:
    profile, scenario, scene, targets = nominal_sources
    keyboard_targets = dict(targets.keyboard_targets)
    original = keyboard_targets["W"]
    keyboard_targets["W"] = replace(
        original,
        center=Point3Mm(
            "board",
            original.center.x + 1.0,
            original.center.y,
            original.center.z,
        ),
    )

    report = validate_placemat_alignment(
        profile,
        scenario,
        scene,
        replace(targets, keyboard_targets=keyboard_targets),
    )

    check = next(item for item in report.checks if item.check_id == "target_regions_and_planes")
    assert check.status == "FAIL"


def test_alignment_rejects_exact_fiducial_pose_drift(nominal_sources) -> None:
    profile, scenario, scene, targets = nominal_sources
    fiducials = list(scene.fiducials)
    index = next(index for index, tag in enumerate(fiducials) if tag.name == "T2")
    original = fiducials[index]
    fiducials[index] = replace(
        original,
        center=Point3Mm(
            "board",
            original.center.x + 1.0,
            original.center.y,
            original.center.z,
        ),
    )

    report = validate_placemat_alignment(
        profile,
        scenario,
        replace(scene, fiducials=tuple(fiducials)),
        targets,
    )

    check = next(item for item in report.checks if item.check_id == "fiducial_tiles_on_board")
    assert check.status == "FAIL"


def test_alignment_rejects_coordinated_tag_plane_drift(nominal_sources) -> None:
    profile, scenario, scene, targets = nominal_sources
    changed_scenario = replace(scenario, assumed_tag_plane_z_mm=0.4)
    changed_tags = tuple(
        replace(
            tag,
            center=Point3Mm("board", tag.center.x, tag.center.y, 0.4),
        )
        for tag in scene.fiducials
    )

    report = validate_placemat_alignment(
        profile,
        changed_scenario,
        replace(scene, fiducials=changed_tags),
        targets,
    )

    check = next(item for item in report.checks if item.check_id == "fiducial_tiles_on_board")
    assert check.status == "FAIL"


def test_alignment_rejects_coordinated_station_height_drift(nominal_sources) -> None:
    profile, scenario, scene, targets = nominal_sources
    changed_scenario = replace(scenario, station_proxy_height_mm=1.0)
    changed_obstacles = tuple(
        replace(
            obstacle,
            maximum=Point3Mm(
                "board",
                obstacle.maximum.x,
                obstacle.maximum.y,
                1.0,
            ),
        )
        if obstacle.obstacle_id.startswith("station:")
        else obstacle
        for obstacle in scene.obstacles
    )

    report = validate_placemat_alignment(
        profile,
        changed_scenario,
        replace(scene, obstacles=changed_obstacles),
        targets,
    )

    check = next(item for item in report.checks if item.check_id == "station_envelopes_on_board")
    assert check.status == "FAIL"


def test_alignment_rejects_nominal_tcp_calibration_target_drift(nominal_sources) -> None:
    profile, scenario, scene, targets = nominal_sources
    original = scene.tcp_calibration_target
    changed_scene = replace(
        scene,
        tcp_calibration_target=replace(
            original,
            center=Point3Mm(
                "board",
                original.center.x + 1.0,
                original.center.y,
                original.center.z,
            ),
        ),
    )

    report = validate_placemat_alignment(profile, scenario, changed_scene, targets)

    check = next(item for item in report.checks if item.check_id == "tcp_calibration_target")
    assert check.status == "FAIL"


def test_alignment_rejects_same_id_keyboard_semantic_mapping_swap(
    nominal_sources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, scenario, scene, targets = nominal_sources
    semantic = development_keyboard_profile()
    changed_mapping = dict(semantic.character_keys)
    changed_mapping["a"], changed_mapping["b"] = (
        changed_mapping["b"],
        changed_mapping["a"],
    )
    changed_semantic = replace(semantic, character_keys=changed_mapping)
    monkeypatch.setattr(
        alignment_module,
        "development_keyboard_profile",
        lambda: changed_semantic,
    )

    report = validate_placemat_alignment(profile, scenario, scene, targets)

    check = next(
        item for item in report.checks if item.check_id == "semantic_geometry_profile_binding"
    )
    assert check.status == "FAIL"


def test_alignment_rejects_same_id_phone_semantic_mapping_swap(
    nominal_sources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, scenario, scene, targets = nominal_sources
    semantic = development_phone_profile()
    changed_mapping = dict(semantic.character_targets)
    changed_mapping["a"], changed_mapping["b"] = (
        changed_mapping["b"],
        changed_mapping["a"],
    )
    changed_semantic = replace(semantic, character_targets=changed_mapping)
    monkeypatch.setattr(
        alignment_module,
        "development_phone_profile",
        lambda: changed_semantic,
    )

    report = validate_placemat_alignment(profile, scenario, scene, targets)

    check = next(
        item for item in report.checks if item.check_id == "semantic_geometry_profile_binding"
    )
    assert check.status == "FAIL"


@pytest.mark.parametrize(
    "translation,rotation",
    (
        (Vec3(305.0, 457.0, 100.0), None),
        (None, Rotation3.identity()),
    ),
)
def test_alignment_rejects_nominal_robot_transform_drift(
    nominal_sources,
    translation,
    rotation,
) -> None:
    profile, scenario, scene, targets = nominal_sources
    changed_transform = replace(
        scenario.board_T_world,
        translation_mm=(
            scenario.board_T_world.translation_mm if translation is None else translation
        ),
        rotation=scenario.board_T_world.rotation if rotation is None else rotation,
    )
    changed_scenario = replace(scenario, board_T_world=changed_transform)

    report = validate_placemat_alignment(profile, changed_scenario, scene, targets)

    check = next(item for item in report.checks if item.check_id == "nominal_arm_clamp_placement")
    assert check.status == "FAIL"


def test_alignment_rejects_arm_clamp_zone_drift(nominal_sources) -> None:
    profile, scenario, scene, targets = nominal_sources
    changed_scene = replace(
        scene,
        arm_clamp_rear_edge_x_range_mm=(200.0, 400.0),
    )

    report = validate_placemat_alignment(
        profile,
        scenario,
        changed_scene,
        targets,
    )

    check = next(item for item in report.checks if item.check_id == "nominal_arm_clamp_placement")
    assert check.status == "FAIL"
