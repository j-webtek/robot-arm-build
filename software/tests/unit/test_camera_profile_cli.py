from __future__ import annotations

import json
from pathlib import Path
import shutil

from rocell.cli import main
from rocell.errors import ExitCode


WORKSPACE = Path(__file__).resolve().parents[3]


def test_camera_profile_reports_exact_b0477_without_hardware(
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "camera-profile",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.OK)
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["schema"] == "rocell.camera_profile_cli.v1"
    profile = report["profile"]
    assert profile["id"] == "arducam-b0477-imx283-16mm-purchased-001"
    assert profile["record_state"] == "PURCHASED_PENDING_RECEIPT"
    assert profile["published_identity"] == {
        "focal_length_mm": 16.0,
        "lens_mount": "C-mount",
        "manufacturer": "Arducam",
        "model": "B0477",
        "sensor": "Sony IMX283",
    }
    assert profile["intended_physical_mode"] == {
        "evidence_state": "MANUFACTURER_PUBLISHED_UNMEASURED",
        "height_px": 3648,
        "host_bus": "USB_3_2_GEN_1",
        "maximum_fps": 9.0,
        "pixel_format": "YUY2",
        "verified_on_received_hardware": False,
        "width_px": 5472,
    }
    proxy = profile["simulation_proxy"]
    assert (proxy["width_px"], proxy["height_px"]) == (2736, 1824)
    assert proxy["pixel_count"] == 4_990_464
    assert proxy["within_current_resource_limits"] is True
    assert proxy["physical_calibration_evidence"] is False
    assert profile["evidence_state"] == {
        "commissioning": "OPEN_NOT_COMMISSIONED",
        "physical_observation": "OPEN_PENDING_RECEIPT_INSPECTION",
        "usb_observation": "OPEN_PENDING_ENUMERATION",
    }
    assert len(profile["source_file_sha256"]) == 64
    assert len(profile["canonical_sha256"]) == 64
    assert report["authority"]["live_capture_authority"] is False
    assert report["authority"]["calibration_authority"] is False
    assert report["authority"]["robot_motion_authority"] is False
    assert report["authority"]["contact_authority"] is False
    assert report["authority"]["hardware_accessed"] is False
    assert report["authority"]["hardware_commands_generated"] == 0


def test_camera_profile_rejects_a_path_outside_the_workspace(
    tmp_path: Path,
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")

    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "camera-profile",
            "--profile-file",
            str(outside),
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "WORKSPACE_FILE_OUTSIDE_ROOT"


def test_camera_commissioning_rehearsal_is_a_zero_hardware_pass(
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "rehearse-camera-commissioning",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.OK)
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["schema"] == "rocell.camera_commissioning_rehearsal_cli.v1"
    assert report["profile"]["id"] == (
        "arducam-b0477-imx283-16mm-purchased-001"
    )
    assert report["profile"]["record_state"] == "PURCHASED_PENDING_RECEIPT"
    assert report["profile"]["commissioning_state"] == "OPEN_NOT_COMMISSIONED"
    assert report["fixture"]["class"] == "SYNTHETIC_ZERO_HARDWARE"
    assessment = report["assessment"]
    assert assessment["status"] == "SYNTHETIC_CAMERA_COMMISSIONING_REHEARSAL_PASS"
    assert assessment["passed"] is True
    assert assessment["reopen_snapshot_count"] == 2
    assert assessment["persistent_device_id"].startswith("synthetic://")
    assert len(report["assessment_sha256"]) == 64
    assert report["authority"] == {
        "camera_frames_requested": 0,
        "commissioned": False,
        "contact_authorized": False,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
        "robot_motion_authorized": False,
        "simulation_only": True,
    }


def test_camera_commissioning_rehearsal_rejects_non_b0477_fixture(
    tmp_path: Path,
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    workspace = tmp_path / "workspace"
    source = WORKSPACE / "software/tests/fixtures/camera/b0477_nominal_rehearsal.json"
    relative = Path("software/tests/fixtures/camera/invalid-model.json")
    destination = workspace / relative
    destination.parent.mkdir(parents=True)
    profile_relative = Path(
        "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    )
    profile_destination = workspace / profile_relative
    profile_destination.parent.mkdir(parents=True)
    shutil.copy2(WORKSPACE / profile_relative, profile_destination)
    mutated = source.read_text(encoding="utf-8").replace(
        '"model": "B0477"', '"model": "NOT-B0477"', 1
    )
    destination.write_text(mutated, encoding="utf-8")
    exit_code = main(
        [
            "--workspace",
            str(workspace),
            "rehearse-camera-commissioning",
            "--fixture",
            relative.as_posix(),
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "CAMERA_COMMISSIONING_REHEARSAL_INVALID"


def test_b0477_uvc_inventory_rehearsal_is_synthetic_and_zero_authority(
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "rehearse-b0477-uvc-inventory",
            "--require-pass",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.OK)
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["schema"] == "rocell.b0477_uvc_inventory_rehearsal_cli.v1"
    assert report["profile"]["id"] == (
        "arducam-b0477-imx283-16mm-purchased-001"
    )
    fixture = report["fixture"]
    assert fixture["provider_id"] == "deterministic_fake"
    assert fixture["purpose"] == "DIAGNOSTIC_REHEARSAL_ONLY"
    assert len(fixture["source_file_sha256"]) == 64
    assert len(fixture["canonical_sha256"]) == 64
    binding = report["synthetic_binding"]
    assert binding["persistent_selector"] == (
        "synthetic://camera/arducam-b0477/rehearsal-unit-001"
    )
    assert len(binding["selected_identity_sha256"]) == 64
    assert len(binding["reopen_settings_sha256"]) == 2
    assert len(set(binding["reopen_settings_sha256"])) == 1
    assert report["assessment"]["status"] == "DIAGNOSTIC_REHEARSAL_PASS"
    assert all(check["passed"] for check in report["assessment"]["checks"])
    assert len(report["assessment_sha256"]) == 64
    assert report["authority"] == {
        "camera_frames_requested": 0,
        "commissioned": False,
        "contact_authority": False,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_capture_authority": False,
        "live_capture_performed": False,
        "physical_release_effect": "NONE",
        "robot_motion_authority": False,
        "simulation_only": True,
    }


def test_b0477_uvc_inventory_require_pass_rejects_automatic_exposure(
    tmp_path: Path,
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    workspace = tmp_path / "workspace"
    profile_relative = Path(
        "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    )
    profile_destination = workspace / profile_relative
    profile_destination.parent.mkdir(parents=True)
    shutil.copy2(WORKSPACE / profile_relative, profile_destination)
    source = (
        WORKSPACE
        / "software/tests/fixtures/camera/b0477_nominal_uvc_inventory.json"
    )
    fixture_relative = Path(
        "software/tests/fixtures/camera/automatic-exposure-uvc.json"
    )
    fixture_destination = workspace / fixture_relative
    fixture_destination.parent.mkdir(parents=True)
    mutated = source.read_text(encoding="utf-8").replace(
        '"mode": "manual"', '"mode": "automatic"', 1
    )
    fixture_destination.write_text(mutated, encoding="utf-8")

    exit_code = main(
        [
            "--workspace",
            str(workspace),
            "rehearse-b0477-uvc-inventory",
            "--fixture",
            fixture_relative.as_posix(),
            "--require-pass",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["assessment"]["status"] == "DIAGNOSTIC_REHEARSAL_BLOCKED"
    checks = {
        check["check_id"]: check for check in report["assessment"]["checks"]
    }
    assert checks["manual_exposure"]["passed"] is False
    assert report["authority"]["commissioned"] is False
    assert report["authority"]["physical_release_effect"] == "NONE"


def test_b0477_intrinsics_rehearsal_is_sealed_and_zero_authority(
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "rehearse-b0477-intrinsics",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.OK)
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["schema"] == "rocell.b0477_intrinsics_rehearsal_cli.v1"
    assert report["profile"]["id"] == (
        "arducam-b0477-imx283-16mm-purchased-001"
    )
    assert report["fixture"]["artifact_class"] == "SYNTHETIC_REHEARSAL_ONLY"
    assert len(report["fixture"]["integrity_sha256"]) == 64
    assert report["target_mode"] == {
        "fps": 9.0,
        "height_px": 3648,
        "pixel_format": "YUY2",
        "width_px": 5472,
    }
    assert report["dataset"] == {
        "charuco_maximum_corner_count": 88,
        "held_out_views": 8,
        "training_views": 24,
    }
    assert report["bindings"]["persistent_camera_identity_sha256"] == (
        "ba5a62b5a58d06721fa4086aa1ed822988b46a072276f5f3e75284961d5b2a6e"
    )
    assert report["bindings"]["controls_snapshot_sha256"] == (
        "993f750d48b8d3aafbf15b87a60c68ab7b23f93c5e61e6861e25cedf712ac7f8"
    )
    assert report["assessment"]["structural_gates_passed"] is True
    assert report["assessment"]["status"] == "SYNTHETIC_REHEARSAL_ONLY"
    assert report["authority"] == {
        "camera_frames_requested": 0,
        "commissioned": False,
        "contact_authority": False,
        "contact_commands": 0,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_calibration_valid": False,
        "physical_release_effect": "NONE",
        "robot_motion_authority": False,
        "simulation_only": True,
    }


def test_b0477_intrinsics_rehearsal_rejects_unsealed_tampering(
    tmp_path: Path,
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    relative = Path("software/tests/fixtures/camera/tampered-intrinsics.json")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    source = (
        WORKSPACE
        / "software/tests/fixtures/camera/b0477_synthetic_intrinsics_rehearsal.json"
    )
    destination.write_text(
        source.read_text(encoding="utf-8").replace(
            '"artifact_id": "b0477-static-intrinsics-synthetic-rehearsal-001"',
            '"artifact_id": "tampered-without-resealing"',
            1,
        ),
        encoding="utf-8",
    )
    profile_relative = Path(
        "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
    )
    profile_destination = tmp_path / profile_relative
    profile_destination.parent.mkdir(parents=True)
    shutil.copy2(WORKSPACE / profile_relative, profile_destination)

    exit_code = main(
        [
            "--workspace",
            str(tmp_path),
            "rehearse-b0477-intrinsics",
            "--fixture",
            relative.as_posix(),
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "B0477_INTRINSICS_REHEARSAL_INVALID"
    assert "tampering detected" in error["error"]["message"]


def test_b0477_stack_rehearsal_fast_path_binds_every_component(
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "rehearse-b0477-stack",
            "--skip-pixel-vision",
            "--require-pass",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.OK)
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["schema"] == "rocell.b0477_stack_rehearsal_cli.v1"
    assert result["status"] == "SYNTHETIC_B0477_STACK_COHERENT"
    assert result["passed"] is True
    assert result["pixel_vision"] == {
        "executed": False,
        "reason": "SKIPPED_BY_EXPLICIT_CLI_OPTION",
    }
    report = result["report"]
    assert report["vision_evidence"] == {
        "reports_consumed": 0,
        "required_for_core_stack_coherence": False,
        "state": "NOT_SUPPLIED_OPTIONAL",
    }
    assert len(report["checks"]) == 9
    assert all(check["passed"] for check in report["checks"])
    assert {
        "camera_profile_file",
        "static_support_file",
        "commissioning_fixture_file",
        "uvc_inventory_file",
        "intrinsics_fixture_file",
    }.issubset(report["component_hashes"])
    assert result["authority"]["commissioned"] is False
    assert result["authority"]["live_capture_authority"] is False
    assert result["authority"]["robot_motion_authority"] is False
    assert result["authority"]["contact_authority"] is False
    assert result["authority"]["physical_release_effect"] == "NONE"


def test_b0477_static_vision_cli_crosses_pixels_with_zero_authority(
    capfd,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = main(
        [
            "--workspace",
            str(WORKSPACE),
            "simulate-b0477-vision",
            "--mode",
            "normal",
            "--sequence",
            "7",
            "--require-expected",
            "--json",
        ]
    )

    captured = capfd.readouterr()
    assert exit_code == int(ExitCode.OK)
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["schema"] == "rocell.b0477_static_vision_cli.v1"
    assert result["scenario_behaved_as_expected"] is True
    report = result["report"]
    assert report["status"] == "PASS"
    assert report["camera"]["mounting_architecture"] == (
        "STATIC_OVERHEAD_EYE_TO_HAND"
    )
    assert report["nominal_projection"]["resolution_px"] == [2736, 1824]
    assert report["tag_ids"]["detected_from_jpeg_pixels"] == list(range(6))
    assert report["tag_ids"]["planar_pose_inliers"] == [0, 1, 2, 3]
    assert report["board_registration"]["held_out_station_tag_ids"] == [4, 5]
    assert report["board_registration"]["held_out_station_checks_passed"] is True
    assert report["processing_boundary"]["opencv_or_cv2_required"] is False
    assert result["authority"]["physical_camera_accessed"] is False
    assert result["authority"]["physical_calibration_authority"] is False
    assert result["authority"]["robot_motion_authority"] is False
    assert result["authority"]["contact_authority"] is False
