from __future__ import annotations

from dataclasses import replace

import pytest

from rocell.calibration import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
    PlannerCalibrationSnapshotError,
    decode_planner_calibration_snapshot,
    required_planner_artifact_ids,
)


TARGET_HASH = "a" * 64
IDENTITY_HASH = "b" * 64
TOOL_HASH = "c" * 64


def transform(parent: str, child: str) -> dict[str, object]:
    return {
        "parent_frame": parent,
        "child_frame": child,
        "rotation_matrix_row_major": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
        "translation_mm": [1.0, 2.0, 3.0],
        "measurement_method_id": "heldout-rigid-fit-v1",
        "sample_count": 20,
        "heldout_count": 5,
        "heldout_max_translation_error_mm": 0.4,
        "heldout_max_rotation_error_rad": 0.01,
        "qualified": True,
    }


def payloads(device: str = "keyboard") -> dict[str, dict[str, object]]:
    pose_id, tcp_id, frame = (
        ("keyboard_pose", "keyboard_tcp", "keyboard")
        if device == "keyboard"
        else ("phone_screen", "phone_tcp", "phone_screen")
    )
    return {
        "robot_reference": {
            "schema": "rocell.robot_reference_payload.v1",
            "joint_order": [
                "b_base",
                "s_shoulder",
                "e_elbow",
                "t_wrist_pitch",
                "r_wrist_roll",
                "g_gripper",
            ],
            "zero_offsets_rad": [0.0] * 6,
            "lower_rad": [-2.0] * 6,
            "upper_rad": [2.0] * 6,
            "signs": [1, -1, 1, 1, -1, 1],
            "arm_identity_hash": "d" * 64,
            "controller_identity_hash": "e" * 64,
            "firmware_identity_hash": "f" * 64,
            "reference_procedure_id": "installed-reference-v1",
            "heldout_max_error_rad": 0.01,
            "qualified": True,
        },
        "arm_board": {
            "schema": "rocell.arm_board_payload.v1",
            "transform": transform("B", "Wv"),
        },
        "controller_correlation": {
            "schema": "rocell.controller_correlation_payload.v1",
            "model_frame": "Wv",
            "controller_frame": "R_ctrl",
            "correlation_model_id": "controller-fit-v1",
            "correlation_model_sha256": "1" * 64,
            "validation_sample_count": 30,
            "heldout_count": 8,
            "heldout_max_position_error_mm": 0.8,
            "heldout_max_angle_error_rad": 0.02,
            "qualified": True,
        },
        pose_id: {
            "schema": f"rocell.{pose_id}_payload.v1",
            "transform": transform("B", frame),
            "target_map_sha256": TARGET_HASH,
            "device_identity_hash": IDENTITY_HASH,
            "heldout_max_target_error_mm": 0.5,
            "qualified": True,
        },
        tcp_id: {
            "schema": f"rocell.{tcp_id}_payload.v1",
            "transform": transform("G", "T"),
            "tool_identity_hash": TOOL_HASH,
            "heldout_max_tip_error_mm": 0.5,
            "minimum_validated_clearance_mm": 12.0,
            "qualified": True,
        },
    }


def artifacts(device: str = "keyboard"):
    result = {
        artifact_id: CalibrationArtifact(
            artifact_id=artifact_id,
            version=1,
            state=ArtifactState.VALID,
            created_utc="2026-09-25T12:00:00Z",
            manifest_id="manifest",
            active_build_id="build",
            dependency_hashes={},
            parent_artifact_hashes={},
            payload=payload,
        )
        for artifact_id, payload in payloads(device).items()
    }
    assessments = {
        artifact_id: ArtifactAssessment(
            artifact_id, ArtifactState.VALID, artifact.content_hash, ()
        )
        for artifact_id, artifact in result.items()
    }
    return result, assessments


@pytest.mark.parametrize("device", ["keyboard", "phone"])
def test_decodes_exact_hash_bound_snapshot(device: str) -> None:
    current, assessments = artifacts(device)
    snapshot = decode_planner_calibration_snapshot(
        device=device,
        artifacts=current,
        assessments=assessments,
        expected_target_map_sha256=TARGET_HASH,
    )
    document = snapshot.to_dict()
    assert set(document["artifact_hashes"]) == set(
        required_planner_artifact_ids(device)
    )
    assert document["board_T_vendor_world"]["parent_frame"] == "B"
    assert document["board_T_vendor_world"]["child_frame"] == "Wv"
    assert document["board_T_device"]["child_frame"] == (
        "keyboard" if device == "keyboard" else "phone_screen"
    )
    assert document["hand_T_tool"]["parent_frame"] == "G"
    assert document["hand_T_tool"]["child_frame"] == "T"
    assert document["physical_authority"] is False
    assert document["manifest_id"] == "manifest"
    assert document["active_build_id"] == "build"
    assert len(snapshot.snapshot_sha256) == 64


def test_rejects_assessment_hash_mismatch() -> None:
    current, assessments = artifacts()
    assessments["arm_board"] = ArtifactAssessment(
        "arm_board", ArtifactState.VALID, "d" * 64, ()
    )
    with pytest.raises(PlannerCalibrationSnapshotError, match="hash mismatch"):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256=TARGET_HASH,
        )


def test_rejects_nominal_or_nonvalid_artifact() -> None:
    current, assessments = artifacts()
    current["arm_board"] = replace(
        current["arm_board"], state=ArtifactState.NOMINAL_ONLY
    )
    with pytest.raises(PlannerCalibrationSnapshotError, match="not VALID"):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256=TARGET_HASH,
        )


def test_rejects_wrong_transform_direction_and_target_map() -> None:
    current, assessments = artifacts()
    bad_payload = dict(current["keyboard_pose"].payload)
    bad_transform = dict(bad_payload["transform"])
    bad_transform["parent_frame"] = "Wv"
    bad_payload["transform"] = bad_transform
    current["keyboard_pose"] = replace(current["keyboard_pose"], payload=bad_payload)
    assessments["keyboard_pose"] = ArtifactAssessment(
        "keyboard_pose", ArtifactState.VALID, current["keyboard_pose"].content_hash, ()
    )
    with pytest.raises(PlannerCalibrationSnapshotError, match="B_T_keyboard"):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256=TARGET_HASH,
        )

    current, assessments = artifacts()
    with pytest.raises(PlannerCalibrationSnapshotError, match="target map binding"):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256="f" * 64,
        )


def test_rejects_invalid_joint_limits_and_unknown_payload_fields() -> None:
    current, assessments = artifacts()
    reference = dict(current["robot_reference"].payload)
    reference["lower_rad"] = [3.0] * 6
    current["robot_reference"] = replace(current["robot_reference"], payload=reference)
    assessments["robot_reference"] = ArtifactAssessment(
        "robot_reference",
        ArtifactState.VALID,
        current["robot_reference"].content_hash,
        (),
    )
    with pytest.raises(PlannerCalibrationSnapshotError, match="joint limits"):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256=TARGET_HASH,
        )


def test_rejects_mixed_manifest_or_build_lineage() -> None:
    current, assessments = artifacts()
    current["arm_board"] = replace(current["arm_board"], active_build_id="other-build")
    assessments["arm_board"] = ArtifactAssessment(
        "arm_board", ArtifactState.VALID, current["arm_board"].content_hash, ()
    )
    with pytest.raises(
        PlannerCalibrationSnapshotError, match="one manifest and active build"
    ):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256=TARGET_HASH,
        )


def test_rejects_unknown_payload_fields() -> None:
    current, assessments = artifacts()
    board = dict(current["arm_board"].payload)
    board["unreviewed"] = True
    current["arm_board"] = replace(current["arm_board"], payload=board)
    assessments["arm_board"] = ArtifactAssessment(
        "arm_board", ArtifactState.VALID, current["arm_board"].content_hash, ()
    )
    with pytest.raises(PlannerCalibrationSnapshotError, match="exact schema"):
        decode_planner_calibration_snapshot(
            device="keyboard",
            artifacts=current,
            assessments=assessments,
            expected_target_map_sha256=TARGET_HASH,
        )
