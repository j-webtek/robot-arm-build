from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.measured_target_reprojection import (
    MeasuredTargetReprojectionError,
    reproject_measured_target,
)
from rocell.calibration import PlannerCalibrationSnapshot, required_planner_artifact_ids
from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.models import ModelMotionProposal
from rocell.targets import load_nominal_target_catalog


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def catalog():
    return load_nominal_target_catalog(WORKSPACE)


def snapshot(
    catalog, device: str, transform: RigidTransform
) -> PlannerCalibrationSnapshot:
    return PlannerCalibrationSnapshot(
        device=device,
        manifest_id="manifest",
        active_build_id="build",
        artifact_hashes={
            item: "a" * 64 for item in required_planner_artifact_ids(device)
        },
        board_T_vendor_world=RigidTransform(
            "B", "Wv", Rotation3.identity(), Vec3.zero()
        ),
        board_T_device=transform,
        hand_T_tool=RigidTransform("G", "T", Rotation3.identity(), Vec3.zero()),
        robot_reference_identity={
            "arm_identity_hash": "1" * 64,
            "controller_identity_hash": "2" * 64,
            "firmware_identity_hash": "3" * 64,
        },
        joint_zero_offsets_rad=(0.0,) * 6,
        joint_lower_rad=(-2.0,) * 6,
        joint_upper_rad=(2.0,) * 6,
        joint_signs=(1,) * 6,
        controller_correlation={"model": "test"},
        target_map_sha256=catalog.content_sha256,
    )


def proposal(catalog, device: str = "keyboard", interaction: str = "HOVER"):
    target_id = "H" if device == "keyboard" else next(iter(catalog.phone_targets))
    region = catalog.resolve(device, target_id)
    if device == "keyboard":
        origin = catalog.keyboard_origin_board_xy_mm
        plane = catalog.keyboard_target_plane_z_board_mm
        frame = "keyboard_local"
    else:
        origin = catalog.phone_origin_board_xy_mm
        plane = catalog.phone_target_plane_z_board_mm
        frame = "phone_screen_local"
    return ModelMotionProposal.from_mapping(
        {
            "schema": "rocell.model_motion_proposal.v1",
            "proposal_id": f"{device}-target-001",
            "device": device,
            "target_id": target_id,
            "coordinate_frame": frame,
            "target_mm": {
                "x": region.center.x - origin[0],
                "y": region.center.y - origin[1],
                "z": region.center.z - plane,
            },
            "interaction": interaction,
            "approach_clearance_mm": 25.0,
            "speed_class": "SLOW",
            "confidence": 0.99,
            "source": {
                "model_id": "test-model",
                "frame_id": "frame-1",
                "image_sha256": "b" * 64,
            },
        }
    )


@pytest.mark.parametrize(
    ("device", "child"), (("keyboard", "keyboard"), ("phone", "phone_screen"))
)
def test_reprojects_device_local_target_through_measured_pose(
    catalog, device, child
) -> None:
    transform = RigidTransform.from_rpy_translation_mm(
        "B",
        child,
        translation_mm=Vec3(300.0, 100.0, 20.0),
        roll_rad=0.1,
        pitch_rad=0.2,
        yaw_rad=0.3,
    )
    result = reproject_measured_target(
        proposal(catalog, device),
        catalog,
        snapshot(catalog, device, transform),
        model_motion_candidate_sha256="c" * 64,
    )
    assert result["status"] == "READY_FOR_DETERMINISTIC_IK_AND_ROUTE_SCREENING"
    assert result["validated_target_device_mm"]["frame"] == child
    assert result["measured_surface_target_board_mm"]["frame"] == "B"
    surface = result["measured_surface_target_board_mm"]
    hover = result["requested_waypoints"][0]["point_mm"]
    expected_delta = transform.rotation.apply(Vec3(0.0, 0.0, 25.0))
    assert hover["x"] - surface["x"] == pytest.approx(expected_delta.x)
    assert hover["y"] - surface["y"] == pytest.approx(expected_delta.y)
    assert hover["z"] - surface["z"] == pytest.approx(expected_delta.z)
    assert result["controller_commands"] == []
    assert result["physical_authority"] is False


def test_contact_emits_measured_approach_contact_retract(catalog) -> None:
    transform = RigidTransform("B", "keyboard", Rotation3.identity(), Vec3(10, 20, 30))
    result = reproject_measured_target(
        proposal(catalog, interaction="CONTACT"),
        catalog,
        snapshot(catalog, "keyboard", transform),
        model_motion_candidate_sha256="c" * 64,
    )
    assert [item["phase"] for item in result["requested_waypoints"]] == [
        "APPROACH",
        "CONTACT_CANDIDATE",
        "RETRACT",
    ]
    assert (
        result["requested_waypoints"][0]["point_mm"]
        == result["requested_waypoints"][2]["point_mm"]
    )


def test_board_input_is_inverse_transformed_before_named_target_validation(
    catalog,
) -> None:
    local_proposal = proposal(catalog)
    transform = RigidTransform.from_rpy_translation_mm(
        "B", "keyboard", translation_mm=Vec3(50, 60, 70), yaw_rad=0.4
    )
    local = local_proposal.target
    measured = transform.transform_point(
        type(local)("keyboard", local.x, local.y, local.z)
    )
    board_proposal = replace(
        local_proposal, target=type(local)("board", measured.x, measured.y, measured.z)
    )
    result = reproject_measured_target(
        board_proposal,
        catalog,
        snapshot(catalog, "keyboard", transform),
        model_motion_candidate_sha256="c" * 64,
    )
    assert result["input_frame_binding"]["mode"] == "INVERSE_MEASURED_DEVICE_TRANSFORM"
    assert result["validated_target_device_mm"]["x"] == pytest.approx(local.x)
    assert result["validated_target_device_mm"]["y"] == pytest.approx(local.y)


def test_rejects_outside_named_target_after_reprojection(catalog) -> None:
    current = proposal(catalog)
    outside = replace(
        current,
        target=type(current.target)(
            current.target.frame,
            current.target.x + 20.0,
            current.target.y,
            current.target.z,
        ),
    )
    measured = snapshot(
        catalog,
        "keyboard",
        RigidTransform("B", "keyboard", Rotation3.identity(), Vec3.zero()),
    )
    with pytest.raises(
        MeasuredTargetReprojectionError, match="outside the named target"
    ):
        reproject_measured_target(
            outside, catalog, measured, model_motion_candidate_sha256="c" * 64
        )


def test_rejects_wrong_surface_plane_and_lineage(catalog) -> None:
    current = proposal(catalog)
    wrong_plane = replace(
        current,
        target=type(current.target)(
            current.target.frame, current.target.x, current.target.y, 1.0
        ),
    )
    measured = snapshot(
        catalog,
        "keyboard",
        RigidTransform("B", "keyboard", Rotation3.identity(), Vec3.zero()),
    )
    with pytest.raises(MeasuredTargetReprojectionError, match="surface plane"):
        reproject_measured_target(
            wrong_plane, catalog, measured, model_motion_candidate_sha256="c" * 64
        )
    with pytest.raises(MeasuredTargetReprojectionError, match="target map"):
        reproject_measured_target(
            current,
            catalog,
            replace(measured, target_map_sha256="d" * 64),
            model_motion_candidate_sha256="c" * 64,
        )


def test_output_is_deterministic(catalog) -> None:
    measured = snapshot(
        catalog,
        "keyboard",
        RigidTransform("B", "keyboard", Rotation3.identity(), Vec3.zero()),
    )
    first = reproject_measured_target(
        proposal(catalog), catalog, measured, model_motion_candidate_sha256="c" * 64
    )
    second = reproject_measured_target(
        proposal(catalog), catalog, measured, model_motion_candidate_sha256="c" * 64
    )
    assert first == second
