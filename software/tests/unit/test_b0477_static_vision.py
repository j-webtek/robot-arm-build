from __future__ import annotations

import builtins
from dataclasses import FrozenInstanceError, replace
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping, Sequence

import pytest

import rocell.application.b0477_static_vision as b0477_module
from rocell.application.b0477_static_vision import (
    B0477_OPTICAL_FRAME,
    B0477_HELD_OUT_STATION_TAG_IDS,
    B0477_POSE_FIT_TAG_IDS,
    B0477HeldOutStationResidual,
    B0477PoseComparison,
    B0477StaticVisionError,
    B0477StaticVisionMode,
    run_b0477_static_vision_capture_rehearsal,
    run_b0477_static_vision_rehearsal,
)
from rocell.vision.planar_pose_estimator import PlanarAprilTagBoardPoseEstimator
from rocell.vision.pixel_detector import AprilTag36h11PixelDetector


WORKSPACE = Path(__file__).resolve().parents[3]


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_values(child)


@pytest.fixture(scope="module")
def normal_report():  # type: ignore[no-untyped-def]
    pytest.importorskip("PIL")
    return run_b0477_static_vision_rehearsal(WORKSPACE, sequence=47)


def test_b0477_normal_path_uses_proxy_pixels_and_recovers_all_six_tags(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    report = normal_report
    assert report.status == "PASS"
    assert report.detail_code == "B0477_STATIC_PIXEL_POSE_ACCEPTED"
    assert report.mode is B0477StaticVisionMode.NORMAL
    assert report.visible_tag_ids == tuple(range(6))
    assert report.detected_tag_ids == tuple(range(6))
    assert report.inlier_tag_ids == B0477_POSE_FIT_TAG_IDS
    assert tuple(
        item.tag_id for item in report.held_out_station_residuals
    ) == B0477_HELD_OUT_STATION_TAG_IDS
    assert all(item.passed for item in report.held_out_station_residuals)
    assert report.held_out_station_checks_passed

    projection = report.nominal_projection
    assert projection.resolution_px == (2736, 1824)
    assert projection.optical_frame == "C_overhead_optical"
    assert B0477_OPTICAL_FRAME == "C_overhead_optical"
    assert projection.camera_axis_xy_board_mm == (305.0, 228.5)
    assert projection.entrance_pupil_z_board_mm == 1000.0
    assert projection.tag_plane_z_board_mm == 0.3
    assert projection.nominal_working_distance_mm == pytest.approx(999.7)
    assert projection.camera_T_board_row_major == (
        1.0,
        0.0,
        0.0,
        -305.0,
        0.0,
        -1.0,
        0.0,
        228.5,
        0.0,
        0.0,
        -1.0,
        1000.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )
    assert projection.intrinsics_row_major[0] == pytest.approx(
        2736.0 / (2.0 * math.tan(math.radians(49.0 / 2.0)))
    )
    # The published 49x38 pair is not a valid square-pixel 3:2 pinhole pair.
    # Renderer and estimator therefore share one focal length derived from H,
    # matching the static-support coverage rule.
    assert projection.intrinsics_row_major[4] == pytest.approx(
        projection.intrinsics_row_major[0]
    )
    expected_vertical_fov = math.degrees(
        2.0
        * math.atan(
            1824.0 / (2.0 * projection.intrinsics_row_major[0])
        )
    )
    assert projection.published_fov_deg == (49.0, 38.0)
    assert projection.effective_rectilinear_fov_deg == pytest.approx(
        (49.0, expected_vertical_fov)
    )
    assert expected_vertical_fov < 38.0
    assert any(value != 0.0 for value in projection.distortion_coefficients)

    pose = report.pose_comparison
    assert pose.estimate_available
    assert pose.translation_error_mm is not None and pose.translation_error_mm < 1.0
    assert pose.rotation_error_deg is not None and pose.rotation_error_deg < 0.1
    assert (
        pose.inlier_reprojection_rmse_px is not None
        and pose.inlier_reprojection_rmse_px < 1.0
    )


def test_report_has_real_jpeg_pixel_statistics_and_hash_linked_sources(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    report = normal_report
    pixels = report.pixel_statistics
    assert (pixels.width_px, pixels.height_px) == (2736, 1824)
    assert pixels.pixel_count == 2736 * 1824
    assert 1_024 < pixels.jpeg_byte_count < 16 * 1024 * 1024
    assert pixels.minimum_gray == 0
    assert pixels.maximum_gray == 255
    assert 0.0 < pixels.dark_fraction_below_128 < 1.0
    assert pixels.accepted_tag_edge_min_px is not None
    assert pixels.accepted_tag_edge_min_px > 100.0

    hashes = dict(report.source_hashes)
    assert hashes["camera_profile_file"] == hashes[
        "support_source:purchased_camera_profile"
    ]
    assert hashes["scene_source:config/workcell_layout.json"] == hashes[
        "support_source:workcell_layout"
    ]
    assert "scene_source:fiducials/apriltag_map.json" in hashes
    assert "renderer_source_bundle" in hashes
    assert "detector_implementation" in hashes
    assert "detected_batch" in hashes
    assert "raw_detected_batch" in hashes
    assert "rectified_detection_batch" in hashes
    assert hashes["detected_batch"] == hashes["rectified_detection_batch"]
    assert hashes["raw_detected_batch"] != hashes["rectified_detection_batch"]
    assert hashes["optical_contract"] == (
        report.nominal_projection.optical_contract_sha256
    )
    assert hashes["synthetic_undistortion_map"] == (
        report.nominal_projection.undistortion_map_sha256
    )
    assert "rectifier_configuration" in hashes
    assert "rectifier_implementation" in hashes
    assert "fit_detection_batch" in hashes
    assert "nominal_intrinsics" in hashes
    assert "nominal_tag_map" in hashes
    assert "nominal_fit_tag_map" in hashes
    assert "nominal_held_out_station_map" in hashes
    assert "pose_observation" in hashes
    assert all(len(value) == 64 for value in hashes.values())


def test_report_is_immutable_canonical_hashable_and_contains_no_pixel_bytes(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    document = normal_report.to_dict()
    expected_hash = hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert normal_report.content_sha256 == expected_hash
    assert not any(isinstance(value, bytes) for value in _nested_values(document))
    assert document["nominal_projection"]["published_fov_deg"][  # type: ignore[index]
        "evidence_state"
    ] == "MANUFACTURER_PUBLISHED_UNMEASURED"
    assert document["nominal_projection"]["physical_calibration_authority"] is False  # type: ignore[index]
    registration = document["board_registration"]
    assert registration["pose_fit_tag_ids"] == [0, 1, 2, 3]  # type: ignore[index]
    assert registration["held_out_station_tag_ids"] == [4, 5]  # type: ignore[index]
    assert registration["held_out_station_tags_used_for_pose_fit"] is False  # type: ignore[index]
    assert registration["physical_acceptance_claim"] is False  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        normal_report.status = "REJECTED"  # type: ignore[misc]


def test_pose_solver_receives_t0_t3_only_and_k0_p0_are_scored_afterward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    real_estimate = PlanarAprilTagBoardPoseEstimator.estimate

    def guarded_estimate(
        self: PlanarAprilTagBoardPoseEstimator,
        detection_batch: Any,
        intrinsics: Any,
        tag_map: Any,
    ) -> Any:
        detection_ids = tuple(
            item.tag_id for item in detection_batch.accepted_tags
        )
        map_ids = tuple(item.tag.tag_id for item in tag_map.tags)
        received.append((detection_ids, map_ids))
        return real_estimate(self, detection_batch, intrinsics, tag_map)

    monkeypatch.setattr(
        PlanarAprilTagBoardPoseEstimator,
        "estimate",
        guarded_estimate,
    )
    report = run_b0477_static_vision_rehearsal(WORKSPACE, sequence=49)

    assert received == [(B0477_POSE_FIT_TAG_IDS, B0477_POSE_FIT_TAG_IDS)]
    assert report.detected_tag_ids == tuple(range(6))
    assert report.inlier_tag_ids == B0477_POSE_FIT_TAG_IDS
    assert tuple(
        residual.tag_id for residual in report.held_out_station_residuals
    ) == B0477_HELD_OUT_STATION_TAG_IDS
    assert all(
        not residual.to_dict()["used_for_pose_fit"]
        for residual in report.held_out_station_residuals
    )


def test_passing_report_rejects_a_failed_held_out_station_check(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    k0, p0 = normal_report.held_out_station_residuals
    failed_k0 = B0477HeldOutStationResidual(
        station_name=k0.station_name,
        tag_id=k0.tag_id,
        corner_rmse_px=2.5,
        maximum_corner_error_px=2.5,
    )
    with pytest.raises(B0477StaticVisionError, match="passing K0/P0"):
        replace(
            normal_report,
            held_out_station_residuals=(failed_k0, p0),
        )


def test_report_recomputes_every_numeric_pass_condition(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    forged = B0477PoseComparison(
        estimate_available=True,
        translation_error_mm=999.0,
        rotation_error_deg=999.0,
        inlier_reprojection_rmse_px=999.0,
    )
    with pytest.raises(B0477StaticVisionError, match="complete synthetic acceptance"):
        replace(normal_report, pose_comparison=forged)

    with pytest.raises(B0477StaticVisionError, match="complete synthetic acceptance"):
        replace(normal_report, status="REJECTED")


def test_capture_recomputes_reported_pose_comparison() -> None:
    capture = run_b0477_static_vision_capture_rehearsal(WORKSPACE, sequence=49)
    comparison = capture.report.pose_comparison
    assert comparison.translation_error_mm is not None
    altered = replace(
        comparison,
        translation_error_mm=comparison.translation_error_mm / 2.0,
    )
    altered_report = replace(capture.report, pose_comparison=altered)
    with pytest.raises(B0477StaticVisionError, match="not derived"):
        replace(capture, report=altered_report)


def test_same_sequence_is_deterministic_and_new_sequence_changes_raw_frame_identity(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    repeated = run_b0477_static_vision_rehearsal(WORKSPACE, sequence=47)
    next_sequence = run_b0477_static_vision_rehearsal(WORKSPACE, sequence=48)
    assert repeated == normal_report
    assert repeated.content_sha256 == normal_report.content_sha256
    assert next_sequence.content_sha256 != normal_report.content_sha256
    # Sequence-seeded one-gray-level noise gives freshness checks a real raw
    # byte boundary without claiming to model a physical sensor distribution.
    assert (
        next_sequence.pixel_statistics.jpeg_sha256
        != normal_report.pixel_statistics.jpeg_sha256
    )


def test_tag_loss_changes_pixels_and_is_naturally_rejected_by_four_tag_pose_gate(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    lost = run_b0477_static_vision_rehearsal(
        WORKSPACE,
        sequence=47,
        mode=B0477StaticVisionMode.TAG_LOSS,
    )
    assert lost.status == "REJECTED"
    assert lost.detail_code == "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
    assert lost.visible_tag_ids == (4, 5)
    assert lost.detected_tag_ids == (4, 5)
    assert lost.inlier_tag_ids == ()
    assert not lost.pose_comparison.estimate_available
    assert lost.held_out_station_residuals == ()
    assert not lost.held_out_station_checks_passed
    assert lost.pose_comparison.translation_error_mm is None
    assert lost.pixel_statistics.jpeg_sha256 != normal_report.pixel_statistics.jpeg_sha256
    assert "pose_observation" not in dict(lost.source_hashes)


def test_rehearsal_has_a_frame_only_detector_boundary_and_never_imports_cv2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert tuple(inspect.signature(AprilTag36h11PixelDetector.detect).parameters) == (
        "self",
        "frame",
    )
    imported_cv2: list[str] = []
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        if name == "cv2" or name.startswith("cv2."):
            imported_cv2.append(name)
            raise AssertionError("B0477 static rehearsal attempted to import cv2")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setitem(sys.modules, "cv2", None)
    report = run_b0477_static_vision_rehearsal(WORKSPACE, sequence=91)
    assert report.status == "PASS"
    assert imported_cv2 == []
    boundary = report.to_dict()["processing_boundary"]
    assert boundary == {
        "pipeline": (
            "SYNTHETIC_DISTORTED_JPEG_TO_PIXEL_DETECTOR_TO_"
            "BOUND_RECTIFIER_TO_PLANAR_POSE"
        ),
        "capture_pixel_space": "B0477_SYNTHETIC_DISTORTED_PROXY_PIXELS",
        "pose_estimator_pixel_space": "UNDISTORTED_PINHOLE_PIXELS",
        "optical_contract_sha256": report.nominal_projection.optical_contract_sha256,
        "undistortion_map_sha256": (
            report.nominal_projection.undistortion_map_sha256
        ),
        "distortion_exercised": True,
        "distortion_is_measured_b0477_calibration": False,
        "detector_received_scene_truth": False,
        "detector_received_expected_corners": False,
        "opencv_or_cv2_required": False,
    }


def test_optical_contract_round_trip_and_drift_guards(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    projection = normal_report.nominal_projection
    contract = projection.optical_contract
    for rectified in ((1368.0, 912.0), (240.0, 240.0), (2480.0, 1550.0)):
        distorted = contract.distort_rectified_pixel(*rectified)
        recovered = contract.undistort_capture_pixel(*distorted)
        assert recovered == pytest.approx(rectified, abs=1e-7)

    with pytest.raises(B0477StaticVisionError, match="optical frame"):
        replace(projection, optical_frame="camera_b0477_static_overhead_optical")

    changed_fx = list(projection.intrinsics_row_major)
    changed_fx[0] += 1.0
    with pytest.raises(B0477StaticVisionError, match="aspect-consistent"):
        replace(projection, intrinsics_row_major=tuple(changed_fx))

    changed_fy = list(projection.intrinsics_row_major)
    changed_fy[4] -= 1.0
    with pytest.raises(B0477StaticVisionError, match="aspect-consistent"):
        replace(projection, intrinsics_row_major=tuple(changed_fy))

    with pytest.raises(B0477StaticVisionError, match="map hash drift"):
        replace(projection, undistortion_map_sha256="0" * 64)


def test_every_physical_live_motion_and_contact_authority_remains_false(
    normal_report,  # type: ignore[no-untyped-def]
) -> None:
    authority = normal_report.to_dict()["authority"]
    assert authority == {
        "simulation_only": True,
        "physical_camera_accessed": False,
        "hardware_presence_authority": False,
        "live_capture_authority": False,
        "physical_calibration_authority": False,
        "physical_static_extrinsic_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "hardware_commands_generated": 0,
    }


def test_inputs_are_strictly_bounded_and_workspace_contained() -> None:
    with pytest.raises(B0477StaticVisionError, match="sequence"):
        run_b0477_static_vision_rehearsal(WORKSPACE, sequence=-1)
    with pytest.raises(B0477StaticVisionError, match="sequence"):
        run_b0477_static_vision_rehearsal(WORKSPACE, sequence=True)  # type: ignore[arg-type]
    with pytest.raises(B0477StaticVisionError, match="sequence"):
        run_b0477_static_vision_rehearsal(
            WORKSPACE,
            sequence=b0477_module.MAX_B0477_REHEARSAL_SEQUENCE + 1,
        )
    with pytest.raises(TypeError, match="mode"):
        run_b0477_static_vision_rehearsal(
            WORKSPACE,
            mode="NORMAL",  # type: ignore[arg-type]
        )
    with pytest.raises(B0477StaticVisionError, match="escapes"):
        run_b0477_static_vision_rehearsal(
            WORKSPACE,
            camera_profile_path=WORKSPACE.parent / "outside-profile.json",
        )


def test_fresh_profile_bytes_are_revalidated_against_support_source_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_loader = b0477_module.load_camera_profile

    def altered_loader(path: Path):  # type: ignore[no-untyped-def]
        return replace(real_loader(path), source_file_sha256="0" * 64)

    monkeypatch.setattr(b0477_module, "load_camera_profile", altered_loader)
    with pytest.raises(B0477StaticVisionError, match="source lock differs"):
        run_b0477_static_vision_rehearsal(WORKSPACE)
