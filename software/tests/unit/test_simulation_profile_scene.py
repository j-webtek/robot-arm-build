from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from rocell.models.frames import FrameMismatchError, Point3Mm
from rocell.simulation import (
    AabbMm,
    SceneImportError,
    SimulationProfileStatus,
    SimulationSourceError,
    load_rc03_nominal_scene,
    load_simulation_hardware_profile,
)
from rocell.rc03.integrity import sha256_file


WORKSPACE = Path(__file__).resolve().parents[3]
RC03_ROOT = WORKSPACE / "active-project" / "RoCell_v0_3"


def test_controlled_simulation_profile_is_hash_bound_and_has_no_authority() -> None:
    profile = load_simulation_hardware_profile(WORKSPACE)

    assert profile.status is SimulationProfileStatus.ASSUMED_GOOD_FOR_SIMULATION_ONLY
    assert profile.profile_id == "ROCELL-SIM-RC03-M3PRO-IMX335B-001"
    assert profile.arm.model == "RoArm-M3-Pro"
    assert profile.camera.model == "IMX335 5MP USB Camera (B)"
    assert profile.camera.sku == "26719"
    assert profile.source_physical_release_status == "UNRELEASED"
    assert profile.simulation_only
    assert not profile.hardware_io_allowed
    assert not profile.can_release_physical_gates
    assert not profile.physical_pass
    assert not profile.safe_to_power_robot
    assert not profile.contact_enabled
    assert len(profile.profile_hash) == 64
    authority = profile.to_dict()["authority"]
    assert authority == {
        "simulation_only": True,
        "hardware_io_allowed": False,
        "can_release_physical_gates": False,
        "physical_pass": False,
        "safe_to_power_robot": False,
        "contact_enabled": False,
    }


def test_profile_loader_rejects_camera_binding_for_another_freeze(tmp_path: Path) -> None:
    config = tmp_path / "software" / "config"
    config.mkdir(parents=True)
    system_source = WORKSPACE / "software" / "config" / "system_manifest.json"
    camera_source = WORKSPACE / "software" / "config" / "camera_manifest.json"
    profile_source = WORKSPACE / "software" / "config" / "simulation_hardware_profile.json"
    shutil.copyfile(system_source, config / "system_manifest.json")
    shutil.copyfile(profile_source, config / "simulation_hardware_profile.json")
    camera = json.loads(camera_source.read_text(encoding="utf-8"))
    camera["system_freeze_id"] = "different-freeze"
    (config / "camera_manifest.json").write_text(json.dumps(camera), encoding="utf-8")

    with pytest.raises(SimulationSourceError, match="does not reference"):
        load_simulation_hardware_profile(tmp_path)


def test_profile_loader_rejects_mechanically_incompatible_camera_binding(
    tmp_path: Path,
) -> None:
    config = tmp_path / "software" / "config"
    config.mkdir(parents=True)
    for name in ("system_manifest.json", "simulation_hardware_profile.json"):
        shutil.copyfile(WORKSPACE / "software/config" / name, config / name)
    camera = json.loads(
        (WORKSPACE / "software/config/camera_manifest.json").read_text(encoding="utf-8")
    )
    camera["primary"]["selected_candidate"]["camera_hole_center_spacing_mm"] = [
        20.0,
        13.5,
    ]
    (config / "camera_manifest.json").write_text(json.dumps(camera), encoding="utf-8")

    with pytest.raises(SimulationSourceError, match="mounting-hole spacing changed"):
        load_simulation_hardware_profile(tmp_path)


def test_nominal_scene_imports_controlled_rc03_geometry_and_assumptions() -> None:
    scene = load_rc03_nominal_scene(RC03_ROOT)

    assert scene.status is SimulationProfileStatus.ASSUMED_GOOD_FOR_SIMULATION_ONLY
    assert scene.design_revision == "RC03-INT-R1"
    assert scene.board_frame == "board"
    assert scene.board.minimum == Point3Mm("board", 0.0, 0.0, -18.0)
    assert scene.board.maximum == Point3Mm("board", 610.0, 457.0, 0.0)
    assert set(scene.devices) == {"keyboard", "phone"}
    assert scene.devices["keyboard"].envelope.maximum == Point3Mm(
        "board", 400.0, 232.0, 21.0
    )
    assert scene.devices["phone"].interaction_plane_z_mm == pytest.approx(11.9)
    assert scene.tcp_calibration_target.center == Point3Mm(
        "board", 441.0, 180.0, 10.5
    )
    assert scene.tcp_calibration_target.replaceable_part == "calibration_puck"
    assert [tag.tag_id for tag in scene.fiducials] == [0, 1, 2, 3, 4, 5]
    assert [tag.name for tag in scene.fiducials] == ["T0", "T1", "T2", "T3", "K0", "P0"]
    assert all(tag.center.z == pytest.approx(0.3) for tag in scene.fiducials)
    assert len(scene.obstacles) == 6
    assert any(obstacle.conservative_proxy for obstacle in scene.obstacles)
    assert scene.simulation_only
    assert not scene.can_release_physical_gates
    assert any("Null direct-tag plane Z" in assumption for assumption in scene.assumptions)
    assert scene.source_hashes["config/workcell_layout.json"] == sha256_file(
        RC03_ROOT / "config/workcell_layout.json"
    )
    evidence = scene.to_dict()
    assert evidence["schema"] == "rocell.nominal_workcell_scene.v1"
    assert evidence["can_release_physical_gates"] is False
    assert evidence["devices"]["keyboard"]["physical_contact_coordinate"] is False
    assert evidence["tcp_calibration_target"]["physical_contact_coordinate"] is False


def test_scene_import_rejects_layout_not_linked_to_tag_map(tmp_path: Path) -> None:
    root = tmp_path / "RoCell_v0_3"
    (root / "config").mkdir(parents=True)
    (root / "fiducials").mkdir(parents=True)
    layout_source = RC03_ROOT / "config" / "workcell_layout.json"
    tag_source = RC03_ROOT / "fiducials" / "apriltag_map.json"
    layout = json.loads(layout_source.read_text(encoding="utf-8"))
    layout["board"]["width"] = 611.0
    (root / "config" / "workcell_layout.json").write_text(
        json.dumps(layout), encoding="utf-8"
    )
    shutil.copyfile(tag_source, root / "fiducials" / "apriltag_map.json")

    with pytest.raises(SceneImportError, match="not linked"):
        load_rc03_nominal_scene(root)


def test_scene_import_rejects_redundant_apriltag_id_drift(tmp_path: Path) -> None:
    root = tmp_path / "RoCell_v0_3"
    (root / "config").mkdir(parents=True)
    (root / "fiducials").mkdir(parents=True)
    shutil.copyfile(
        RC03_ROOT / "config" / "workcell_layout.json",
        root / "config" / "workcell_layout.json",
    )
    tag_map = json.loads(
        (RC03_ROOT / "fiducials" / "apriltag_map.json").read_text(
            encoding="utf-8"
        )
    )
    tag_map["ids"]["T0"] = 99
    (root / "fiducials" / "apriltag_map.json").write_text(
        json.dumps(tag_map),
        encoding="utf-8",
    )

    with pytest.raises(SceneImportError, match="top-level identity map"):
        load_rc03_nominal_scene(root)


def test_scene_import_rejects_extra_declared_device_even_when_sources_are_relinked(
    tmp_path: Path,
) -> None:
    root = tmp_path / "RoCell_v0_3"
    (root / "config").mkdir(parents=True)
    (root / "fiducials").mkdir(parents=True)
    layout = json.loads(
        (RC03_ROOT / "config/workcell_layout.json").read_text(encoding="utf-8")
    )
    layout["devices"]["tablet"] = dict(layout["devices"]["keyboard"])
    layout_path = root / "config/workcell_layout.json"
    layout_path.write_text(json.dumps(layout), encoding="utf-8")
    tag_map = json.loads(
        (RC03_ROOT / "fiducials/apriltag_map.json").read_text(encoding="utf-8")
    )
    tag_map["layout_sha256"] = sha256_file(layout_path)
    (root / "fiducials/apriltag_map.json").write_text(
        json.dumps(tag_map),
        encoding="utf-8",
    )

    with pytest.raises(SceneImportError, match="exactly keyboard, phone, and tcp_target"):
        load_rc03_nominal_scene(root)


def test_scene_records_nondefault_simulation_only_proxy_values() -> None:
    scene = load_rc03_nominal_scene(
        RC03_ROOT,
        assumed_tag_plane_z_mm=1.25,
        station_proxy_height_mm=42.0,
    )
    assert all(tag.center.z == pytest.approx(1.25) for tag in scene.fiducials)
    station = next(item for item in scene.obstacles if item.obstacle_id == "station:phone_tcp")
    assert station.maximum.z - station.minimum.z == pytest.approx(42.0)
    assert any("1.25 mm" in item for item in scene.assumptions)
    assert any("42 mm" in item for item in scene.assumptions)


def test_aabb_point_and_segment_clearance_are_conservative_and_frame_safe() -> None:
    box = AabbMm.from_bounds(
        "fixture",
        "board",
        (10.0, 10.0, 0.0),
        (20.0, 20.0, 10.0),
        kind="test fixture",
        source="unit test",
    )
    assert box.contains(Point3Mm("board", 15.0, 15.0, 5.0))
    assert box.point_distance_mm(Point3Mm("board", 23.0, 24.0, 10.0)) == pytest.approx(5.0)
    assert box.intersects_segment(
        Point3Mm("board", 0.0, 15.0, 5.0),
        Point3Mm("board", 30.0, 15.0, 5.0),
    )
    assert not box.intersects_segment(
        Point3Mm("board", 0.0, 0.0, 20.0),
        Point3Mm("board", 30.0, 0.0, 20.0),
    )
    assert box.intersects_segment(
        Point3Mm("board", 0.0, 0.0, 12.0),
        Point3Mm("board", 30.0, 0.0, 12.0),
        clearance_mm=10.0,
    )
    with pytest.raises(FrameMismatchError):
        box.contains(Point3Mm("robot_base", 15.0, 15.0, 5.0))


def test_scene_clearance_reports_obstacles_and_supports_explicit_ignores() -> None:
    scene = load_rc03_nominal_scene(RC03_ROOT)
    above = scene.check_segment_clearance(
        Point3Mm("board", 20.0, 20.0, 100.0),
        Point3Mm("board", 590.0, 20.0, 100.0),
        clearance_mm=5.0,
    )
    assert above.clear
    phone_descent = scene.check_segment_clearance(
        Point3Mm("board", 520.0, 120.0, 80.0),
        Point3Mm("board", 520.0, 120.0, 11.9),
        clearance_mm=1.0,
    )
    assert not phone_descent.clear
    assert "phone" in phone_descent.colliding_obstacle_ids
    assert phone_descent.to_dict()["physical_authority"] is False
    ignored = scene.check_segment_clearance(
        Point3Mm("board", 520.0, 120.0, 80.0),
        Point3Mm("board", 520.0, 120.0, 11.9),
        ignored_obstacle_ids=("phone", "station:phone_tcp"),
    )
    assert ignored.clear
    assert "phone" not in ignored.checked_obstacle_ids


def test_fiducial_corner_order_respects_marked_positive_y_top_edge() -> None:
    scene = load_rc03_nominal_scene(RC03_ROOT)
    tag = scene.fiducials[0]
    top_left, top_right, bottom_right, bottom_left = tag.corners()
    assert top_left == Point3Mm("board", 27.0, 60.0, 0.3)
    assert top_right == Point3Mm("board", 67.0, 60.0, 0.3)
    assert bottom_right == Point3Mm("board", 67.0, 20.0, 0.3)
    assert bottom_left == Point3Mm("board", 27.0, 20.0, 0.3)
