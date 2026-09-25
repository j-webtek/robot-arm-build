from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest


SOFTWARE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SOFTWARE_ROOT / "src"
REPOSITORY_ROOT = SOFTWARE_ROOT.parent


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    rc03 = workspace / "active-project" / "RoCell_v0_3"
    sources: dict[str, dict[str, Any]] = {
        "config/measurement_record.json": {
            "design_revision": "RC03-INT-R1",
            "selected_routes": {
                "keyboard_rod_route": True,
                "phone_stylus_route": True,
                "camera_mast_optional": True,
            },
            "gates": {"physical_example": {"status": "NOT_TESTED"}},
        },
        "fiducials/apriltag_map.json": {
            "design_revision": "RC03-INT-R1",
            "coordinate_source": "nominal_layout",
        },
        "BUILD_BY_STEP/ACTIVE_BUILD.json": {"active_build_id": None},
    }
    snapshot = []
    for relative, document in sources.items():
        path = rc03 / relative
        _write_json(path, document)
        snapshot.append({"path": relative, "sha256": _sha256(path)})

    manifest = {
        "schema_version": 1,
        "manifest_id": "TEST-FREEZE-001",
        "rc03": {
            "root": "active-project/RoCell_v0_3",
            "design_revision": "RC03-INT-R1",
            "physical_release_status": "UNRELEASED",
            "active_build_id": None,
            "source_snapshot": snapshot,
        },
        "mission_routes": {
            route: {"selected": True}
            for route in (
                "keyboard_rod_route",
                "phone_stylus_route",
                "camera_mast_optional",
            )
        },
        "hardware": {
            "camera": {
                "exact_model": None,
                "state": "SELECTED_UNQUALIFIED_CAMERA_IDENTITY_OPEN_BLOCKING",
            }
        },
        "fiducials": {"coordinate_source": "nominal_layout"},
        "current_build_state": {
            "safe_to_power_robot": False,
            "contact_enabled": False,
        },
        "hard_blockers": [
            "ACTIVE_BUILD_ID_NULL",
            "PHYSICAL_RELEASE_UNRELEASED",
            "CAMERA_INTRINSICS_AND_INSTALLATION_MISSING",
        ],
    }
    _write_json(workspace / "software" / "config" / "system_manifest.json", manifest)
    return workspace


def _virtual_workspace(tmp_path: Path) -> Path:
    """Copy only hash-linked inputs needed for startup, sessions, and evidence."""

    workspace = tmp_path / "virtual-workspace"
    for relative in (
        "software/config/runtime.json",
        "software/config/system_manifest.json",
        "software/config/simulation_bundle_lock.json",
        "software/config/gate_projection.json",
        "software/config/arm_connection.json",
        "software/calibrations/registry.json",
    ):
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / relative, destination)

    manifest = json.loads(
        (REPOSITORY_ROOT / "software/config/system_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rc03_relative = manifest["rc03"]["root"]
    for entry in manifest["rc03"]["source_snapshot"]:
        relative = entry["path"]
        destination = workspace / rc03_relative / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / rc03_relative / relative, destination)

    # The synthetic pixel renderer validates these controlled artworks against
    # its independently shared tag codebook, then hashes their exact bytes into
    # each render.  They are supporting raster assets rather than RC03 geometry
    # snapshot entries, so this deliberately minimal relocated fixture copies
    # them explicitly.
    for tag_id in range(6):
        relative = (
            f"fiducials/tag36h11_id{tag_id:02d}_tile55_marker40.png"
        )
        destination = workspace / rc03_relative / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / rc03_relative / relative, destination)

    bundle = json.loads(
        (REPOSITORY_ROOT / "software/config/simulation_bundle_lock.json").read_text(
            encoding="utf-8"
        )
    )
    for artifact in bundle["artifacts"].values():
        relative = artifact["path"]
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / relative, destination)

    source_registry = REPOSITORY_ROOT / "software/calibrations"
    destination_registry = workspace / "software/calibrations"
    if (source_registry / "index.json").is_file():
        shutil.copyfile(
            source_registry / "index.json",
            destination_registry / "index.json",
        )
    if (source_registry / "artifacts").is_dir():
        shutil.copytree(
            source_registry / "artifacts",
            destination_registry / "artifacts",
        )
    (workspace / "software/runs").mkdir(parents=True)
    return workspace


def _sentinel_modules(workspace: Path) -> tuple[Path, Path, Path]:
    modules = workspace / "sentinel_modules"
    modules.mkdir(parents=True)
    serial_marker = workspace / "serial-imported.txt"
    cv2_marker = workspace / "cv2-imported.txt"
    (modules / "serial.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "Path(os.environ['ROCELL_SERIAL_IMPORT_MARKER']).write_text('imported')\n"
        "raise RuntimeError('serial must not be imported')\n",
        encoding="utf-8",
    )
    (modules / "cv2.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "Path(os.environ['ROCELL_CV2_IMPORT_MARKER']).write_text('imported')\n"
        "raise RuntimeError('cv2 must not be imported')\n",
        encoding="utf-8",
    )
    return modules, serial_marker, cv2_marker


def _run(workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    modules, serial_marker, cv2_marker = _sentinel_modules(workspace)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["ROCELL_SERIAL_IMPORT_MARKER"] = str(serial_marker)
    environment["ROCELL_CV2_IMPORT_MARKER"] = str(cv2_marker)
    existing = environment.get("PYTHONPATH")
    paths = [str(modules), str(SRC_ROOT)]
    if existing:
        paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "rocell",
            "--workspace",
            str(workspace),
            *arguments,
        ],
        cwd=workspace,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_repository(
    temporary_root: Path,
    *arguments: str,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run against the checked-in, hash-linked RC03 simulation fixture."""

    modules, serial_marker, cv2_marker = _sentinel_modules(temporary_root)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["ROCELL_SERIAL_IMPORT_MARKER"] = str(serial_marker)
    environment["ROCELL_CV2_IMPORT_MARKER"] = str(cv2_marker)
    existing = environment.get("PYTHONPATH")
    paths = [str(modules), str(SRC_ROOT)]
    if existing:
        paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "rocell",
            "--workspace",
            str(REPOSITORY_ROOT),
            *arguments,
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed, serial_marker, cv2_marker


def test_status_reports_current_denials_without_hardware_imports(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    completed = _run(workspace, "status", "--json")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["schema"] == "rocell.status.v1"
    assert result["integrity_verified"] is True
    assert result["safe_to_power_robot"] is False
    assert result["contact_enabled"] is False
    assert result["capabilities"]["digital_plan"]["allowed"] is True
    assert result["capabilities"]["arm_feedback"]["allowed"] is False
    assert "ROBOT_POWER_NOT_RELEASED" in result["capabilities"]["arm_feedback"]["reasons"]
    assert not (workspace / "serial-imported.txt").exists()
    assert not (workspace / "cv2-imported.txt").exists()


@pytest.mark.parametrize("abbreviation", ("--work", "--man"))
def test_cli_rejects_abbreviated_source_override(
    tmp_path: Path,
    abbreviation: str,
) -> None:
    """Launcher-prepended source controls cannot be replaced by abbreviations."""

    workspace = _workspace(tmp_path)
    completed = _run(
        workspace,
        abbreviation,
        str(tmp_path / "untrusted-workspace"),
        "status",
        "--json",
    )

    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr
    assert "untrusted-workspace" in completed.stderr
    assert not (workspace / "serial-imported.txt").exists()
    assert not (workspace / "cv2-imported.txt").exists()


def test_doctor_sim_passes_with_explicit_hardware_holds(tmp_path: Path) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "doctor",
        "--mode",
        "sim",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS_WITH_HARDWARE_HOLDS"
    checks = {row["id"]: row for row in result["checks"]}
    assert checks["build_snapshot_integrity"]["status"] == "PASS"
    assert checks["virtual_workcell_bootstrap"]["status"] == "PASS"
    assert checks["semantic_simulated_dry_run"]["status"] == "PASS"
    assert checks["live_arm_feedback"]["status"] == "NOT_RUN_BLOCKED"
    assert checks["optional_hardware_imports"]["status"] == "NOT_IMPORTED"
    virtual = result["virtual_bootstrap"]
    assert virtual["simulation_ready"] is True
    assert len(virtual["bootstrap_hash"]) == 64
    assert {gap["id"] for gap in virtual["declared_gaps"]} == {
        "physical_calibration",
        "collision_geometry",
        "physical_release",
    }
    assert virtual["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
    }
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_b0477_profile_command_does_not_import_or_access_hardware(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "camera-profile",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["profile"]["published_identity"]["model"] == "B0477"
    assert result["profile"]["simulation_proxy"]["width_px"] == 2736
    assert result["authority"]["hardware_accessed"] is False
    assert result["authority"]["hardware_commands_generated"] == 0
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_b0477_commissioning_rehearsal_is_synthetic_only(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "rehearse-camera-commissioning",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["assessment"]["passed"] is True
    assert result["assessment"]["commissioned"] is False
    assert result["authority"]["camera_frames_requested"] == 0
    assert result["authority"]["robot_motion_authorized"] is False
    assert result["authority"]["contact_authorized"] is False
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_b0477_uvc_inventory_rehearsal_does_not_import_hardware_backends(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "rehearse-b0477-uvc-inventory",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["assessment"]["status"] == "DIAGNOSTIC_REHEARSAL_PASS"
    assert result["fixture"]["provider_id"] == "deterministic_fake"
    assert result["authority"]["hardware_accessed"] is False
    assert result["authority"]["live_capture_performed"] is False
    assert result["authority"]["camera_frames_requested"] == 0
    assert result["authority"]["hardware_commands_generated"] == 0
    assert result["authority"]["robot_motion_authority"] is False
    assert result["authority"]["contact_authority"] is False
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_b0477_intrinsics_rehearsal_does_not_import_hardware_backends(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "rehearse-b0477-intrinsics",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["assessment"]["status"] == "SYNTHETIC_REHEARSAL_ONLY"
    assert result["dataset"]["training_views"] == 24
    assert result["dataset"]["held_out_views"] == 8
    assert result["target_mode"] == {
        "fps": 9.0,
        "height_px": 3648,
        "pixel_format": "YUY2",
        "width_px": 5472,
    }
    assert result["authority"]["physical_calibration_valid"] is False
    assert result["authority"]["hardware_accessed"] is False
    assert result["authority"]["camera_frames_requested"] == 0
    assert result["authority"]["hardware_commands_generated"] == 0
    assert result["authority"]["robot_motion_authority"] is False
    assert result["authority"]["contact_authority"] is False
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_b0477_stack_fast_rehearsal_does_not_import_hardware_backends(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "rehearse-b0477-stack",
        "--skip-pixel-vision",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "SYNTHETIC_B0477_STACK_COHERENT"
    assert result["passed"] is True
    assert result["pixel_vision"]["executed"] is False
    assert all(check["passed"] for check in result["report"]["checks"])
    assert result["report"]["execution"] == {
        "arm_motion_commands": 0,
        "camera_frames_requested": 0,
        "contact_commands": 0,
        "hardware_accessed": False,
        "simulation_only": True,
    }
    assert result["authority"]["live_capture_authority"] is False
    assert result["authority"]["robot_motion_authority"] is False
    assert result["authority"]["contact_authority"] is False
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_b0477_static_pixel_rehearsal_does_not_import_hardware_backends(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-b0477-vision",
        "--mode",
        "tag-loss",
        "--require-expected",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["scenario_behaved_as_expected"] is True
    assert result["report"]["status"] == "REJECTED"
    assert result["report"]["detail_code"] == (
        "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
    )
    assert result["report"]["tag_ids"]["detected_from_jpeg_pixels"] == [4, 5]
    assert result["authority"]["hardware_commands_generated"] == 0
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_bootstrap_sim_reports_complete_zero_authority_startup(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "bootstrap-sim",
        "--runtime",
        "software/config/runtime.json",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["schema"] == "rocell.virtual_workcell_bootstrap.v1"
    assert result["simulation_ready"] is True
    assert result["status"] == "READY_SIMULATION_ONLY_WITH_DECLARED_GAPS"
    assert len(result["bootstrap_hash"]) == 64
    assert result["authority"] == {
        "simulation_only": True,
        "execution_authorized": False,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "can_release_physical_gates": False,
        "safe_to_power_robot_conferred": False,
        "contact_enabled_conferred": False,
    }
    assert result["synthetic_overview"]["visible_tag_count"] == 6
    assert result["collision_readiness"]["diagnostic_ready"] is False
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_bootstrap_sim_invalid_runtime_is_configuration_error_without_hardware_imports(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "bootstrap-sim",
        "--runtime",
        "software/config/missing-runtime.json",
        "--json",
    )
    assert completed.returncode == 3
    result = json.loads(completed.stderr)
    assert result["error"]["code"] == "VIRTUAL_BOOTSTRAP_INVALID"
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_session_keyboard_completes_with_zero_hardware_authority(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    session = result["virtual_session"]
    assert result["schema"] == "rocell.simulate_session_cli.v1"
    assert result["pipeline_completed"] is True
    assert result["fault_profile"] == "none"
    assert session["action_plan"]["device"] == "keyboard"
    assert session["device_plant"]["schema"] == "rocell.virtual_keyboard.v2"
    assert session["device_plant"]["contact_input_contract"] == (
        "ACHIEVED_BOARD_XYZ_NORMAL_DWELL_ONLY"
    )
    assert session["outcome_observer"]["input_contract"] == "CONTACT_RESULT_ONLY"
    assert session["outcome"]["matches"] is True
    assert session["requested_text"]["plaintext_serialized"] is False
    assert session["virtual_calibrations"]["physical_calibration_ready"] is False
    assert session["pixel_vision_completed"] is True
    assert session["pixel_vision"]["attempt_count"] == 1
    assert session["pixel_vision"]["passed_attempt_count"] == 1
    assert result["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
    }
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_session_phone_completes_and_verifies_android_state(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-session",
        "--device",
        "phone",
        "--text",
        "a",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    session = result["virtual_session"]
    assert result["pipeline_completed"] is True
    assert session["action_plan"]["device"] == "phone"
    assert session["device_plant"]["schema"] == "rocell.virtual_android.v2"
    assert session["outcome_observer"]["result_count"] == 1
    assert session["device_plant"]["ui_state"] == "KEYBOARD_LOWER"
    assert session["outcome"]["matches"] is True
    assert session["authority"]["hardware_commands_generated"] == 0
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_adaptive_session_zero_offset_passes_without_correction(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-adaptive-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    session = result["adaptive_virtual_session"]

    assert result["schema"] == "rocell.simulate_adaptive_session_cli.v1"
    assert result["pipeline_completed"] is True
    assert result["adaptive_session_report_hash"] == session["report_sha256"]
    assert result["synthetic_truth_injection"] == {
        "can_update_calibration_registry": False,
        "scope": "HIDDEN_VIRTUAL_PLANT_SIMULATION_ONLY",
        "transform_serialized": False,
    }
    assert session["private_plant_truth"]["transform_serialized"] is False
    assert session["correction_installations"] == []
    assert [attempt["decision"]["status"] for attempt in session["vision_attempts"]] == [
        "NO_CHANGE"
    ]
    assert [attempt["accepted"] for attempt in session["contact_attempts"]] == [
        True
    ]
    assert result["authority"]["hardware_accessed"] is False
    assert result["authority"]["hardware_commands_generated"] == 0
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_adaptive_session_corrects_twelve_mm_hidden_truth_offset(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-adaptive-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--truth-offset-x-mm",
        "12",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    session = result["adaptive_virtual_session"]
    installation = session["correction_installations"][0]

    assert result["pipeline_completed"] is True
    assert len(session["correction_installations"]) == 1
    assert installation["replacement_built_and_accepted_before_mutation"] is True
    assert installation["old_queue_discarded_atomically"] is True
    assert installation["old_joint_results_executable_after_install"] is False
    assert [attempt["decision"]["status"] for attempt in session["vision_attempts"]] == [
        "APPLY",
        "NO_CHANGE",
    ]
    assert [attempt["accepted"] for attempt in session["contact_attempts"]] == [
        True
    ]
    assert session["outcome_verified"] is True
    assert session["ended_at_park"] is True
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_adaptive_session_reject_is_nonzero_when_pass_is_required(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-adaptive-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--truth-offset-x-mm",
        "16",
        "--require-pass",
        "--json",
    )
    assert completed.returncode == 3, completed.stderr
    result = json.loads(completed.stdout)
    session = result["adaptive_virtual_session"]

    assert result["pipeline_completed"] is False
    assert result["status"] == "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
    assert session["fault_reason"] == (
        "BOARD_POSE_CORRECTION_REJECTED:TRANSLATION_DELTA_LIMIT_EXCEEDED"
    )
    assert session["vision_attempts"][0]["decision"]["status"] == "REJECT"
    assert session["contact_attempts"] == []
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_adaptive_session_rejects_nonfinite_truth_input_before_run(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate-adaptive-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--truth-offset-x-mm",
        "NaN",
        "--json",
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "must be finite" in completed.stderr
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_qualify_prehardware_quick_runs_locked_campaign_without_hardware_imports(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "qualify-prehardware",
        "--profile",
        "quick",
        "--require-pass",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    report = result["prehardware_qualification"]
    assert result["schema"] == "rocell.qualify_prehardware_cli.v1"
    assert result["campaign_passed"] is True
    assert result["coverage_state"] == "NOT_RUN"
    assert result["all_mission_routes_accepted"] is False
    assert result["physical_ready"] is False
    assert report["profile"] == "quick"
    assert report["diagnostic_pass"] is True
    assert report["case_summary"] == {
        "selected": 5,
        "passed": 5,
        "failed": 0,
        "expected_fail_stop_cases": 1,
    }
    assert [row["case"]["case_id"] for row in report["cases"]] == [
        "startup.integrity",
        "adaptive.keyboard.offset_x_plus_12mm",
        "adaptive.phone.offset_x_plus_8mm",
        "fault.camera_tag_loss.keyboard",
        "determinism.keyboard.offset_x_plus_12mm",
    ]
    assert report["resource_usage"]["hardware_commands_generated"] == 0
    assert report["authority"]["hardware_accessed"] is False
    assert report["authority"]["hardware_commands_generated"] == 0
    assert report["authority"]["execution_authorized"] is False
    assert report["authority"]["physical_release_effect"] == "NONE"
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("ROCELL_RUN_STANDARD_QUALIFICATION") != "1",
    reason=(
        "set ROCELL_RUN_STANDARD_QUALIFICATION=1 to run the multi-minute "
        "real standard qualification campaign"
    ),
)
def test_qualify_prehardware_standard_runs_real_17_case_75_route_gate(
    tmp_path: Path,
) -> None:
    """Nightly/opt-in proof that the unfaked aggregate composition still works."""

    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "qualify-prehardware",
        "--profile",
        "standard",
        "--require-pass",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    wrapper = json.loads(completed.stdout)
    report = wrapper["prehardware_qualification"]
    expected_case_ids = [
        "startup.integrity",
        "adaptive.keyboard.nominal",
        "adaptive.phone.nominal",
        "adaptive.keyboard.offset_x_plus_12mm",
        "adaptive.phone.offset_x_plus_8mm",
        "adaptive.keyboard.offset_x_plus_16mm_rejected",
        "fault.arm_connect.keyboard",
        "fault.arm_reference.keyboard",
        "fault.arm_stall.keyboard",
        "fault.camera_unavailable.keyboard",
        "fault.camera_tag_loss.keyboard",
        "fault.contact_missed.keyboard",
        "fault.keyboard_double",
        "fault.phone_wrong_ui",
        "fault.focus_lost.phone",
        "determinism.keyboard.offset_x_plus_12mm",
        "coverage.locked_catalog",
    ]

    assert wrapper["schema"] == "rocell.qualify_prehardware_cli.v1"
    assert wrapper["campaign_passed"] is True
    assert wrapper["coverage_state"] == "ALL_ROUTES_ACCEPTED"
    assert wrapper["all_mission_routes_accepted"] is True
    assert wrapper["physical_ready"] is False
    assert report["profile"] == "standard"
    assert report["campaign_passed"] is True
    assert report["diagnostic_pass"] is True
    assert report["physical_ready"] is False
    assert report["final_source_revalidation_passed"] is True
    assert report["case_summary"] == {
        "selected": 17,
        "passed": 17,
        "failed": 0,
        "expected_fail_stop_cases": 10,
    }
    assert [item["case"]["case_id"] for item in report["cases"]] == (
        expected_case_ids
    )
    assert all(item["passed"] is True for item in report["cases"])
    assert all(item["authority_verified"] is True for item in report["cases"])
    assert all(len(item["source_report_sha256"]) == 64 for item in report["cases"])

    coverage = report["coverage_summary"]
    assert coverage["evaluated"] is True
    assert coverage["complete_catalog_evidence"] is True
    assert coverage["route_count"] == 75
    assert coverage["accepted_route_count"] == 75
    assert coverage["rejected_route_count"] == 0
    assert coverage["keyboard"]["route_count"] == 46
    assert coverage["keyboard"]["accepted_route_count"] == 46
    assert coverage["phone"]["route_count"] == 29
    assert coverage["phone"]["accepted_route_count"] == 29
    assert coverage["all_routes_accepted"] is True

    usage = report["resource_usage"]
    policy = report["policy"]
    route_bounds = policy["route_policy"]["planned_resource_upper_bounds"]
    assert usage["case_count"] == 17
    assert usage["case_count"] <= policy["maximum_cases"]
    assert usage["session_run_count"] <= policy["maximum_session_runs"]
    assert usage["virtual_commands_executed"] <= (
        policy["maximum_total_virtual_commands"]
    )
    assert usage["camera_capture_count"] <= policy["maximum_total_camera_captures"]
    assert usage["legacy_event_count"] <= policy["maximum_total_legacy_events"]
    assert usage["mission_route_count"] == 75
    assert usage["mission_total_waypoint_records"] <= route_bounds[
        "waypoint_records"
    ]
    assert usage["mission_total_ik_solves"] <= route_bounds["ik_solves"]
    assert usage["mission_total_task_jacobian_fk_evaluations"] <= route_bounds[
        "task_jacobian_fk_evaluations"
    ]
    assert usage["hardware_commands_generated"] == 0
    assert report["authority"]["hardware_accessed"] is False
    assert report["authority"]["hardware_commands_generated"] == 0
    assert report["authority"]["execution_authorized"] is False
    assert report["authority"]["physical_release_effect"] == "NONE"
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("ROCELL_RUN_ADAPTIVE_CAMPAIGNS") != "1",
    reason=(
        "set ROCELL_RUN_ADAPTIVE_CAMPAIGNS=1 to run the multi-minute real "
        "adaptive coverage campaign"
    ),
)
def test_adaptive_mission_coverage_runs_real_75_target_pipeline(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "screen-adaptive-mission-routes",
        "--require-all",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    wrapper = json.loads(completed.stdout)
    report = wrapper["adaptive_mission_coverage"]
    summary = report["summary"]
    assert wrapper["schema"] == "rocell.adaptive_mission_coverage_cli.v1"
    assert wrapper["all_routes_accepted"] is True
    assert summary["route_count"] == 75
    assert summary["accepted_route_count"] == 75
    assert summary["rejected_route_count"] == 0
    assert summary["contact_count"] == 75
    assert report["catalog"]["complete_catalog_evidence"] is True
    assert len(report["catalog"]["keyboard_target_ids"]) == 46
    assert len(report["catalog"]["phone_target_ids"]) == 29
    assert summary["final_revalidation_passed"] is True
    assert summary["physical_ready"] is False
    assert wrapper["authority"]["hardware_accessed"] is False
    assert wrapper["authority"]["hardware_commands_generated"] == 0
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("ROCELL_RUN_ADAPTIVE_CAMPAIGNS") != "1",
    reason=(
        "set ROCELL_RUN_ADAPTIVE_CAMPAIGNS=1 to run the multi-minute real "
        "adaptive perturbation campaign"
    ),
)
def test_adaptive_perturbation_campaign_runs_real_seeded_boundaries(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "stress-adaptive-session",
        "--seed",
        "20260903",
        "--generated-cases",
        "8",
        "--require-pass",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    wrapper = json.loads(completed.stdout)
    report = wrapper["adaptive_perturbation_campaign"]
    summary = report["summary"]
    assert wrapper["schema"] == "rocell.adaptive_perturbation_campaign_cli.v1"
    assert wrapper["campaign_passed"] is True
    assert summary["case_count"] == 20
    assert summary["passed_count"] == 20
    assert summary["failed_count"] == 0
    assert summary["expected_rejection_count"] == 4
    assert summary["final_revalidation_passed"] is True
    assert summary["physical_ready"] is False
    serialized = json.dumps(wrapper, sort_keys=True)
    assert "translation_Wv_mm" not in serialized
    assert "yaw_board_rad" not in serialized
    assert wrapper["authority"]["hardware_accessed"] is False
    assert wrapper["authority"]["hardware_commands_generated"] == 0
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_simulate_session_fault_is_advisory_unless_pass_is_required(
    tmp_path: Path,
) -> None:
    arguments = (
        "simulate-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--fault-profile",
        "contact-missed",
        "--json",
    )
    advisory, advisory_serial, advisory_cv2 = _run_repository(
        tmp_path / "advisory",
        *arguments,
    )
    required, required_serial, required_cv2 = _run_repository(
        tmp_path / "required",
        *arguments[:-1],
        "--require-pass",
        "--json",
    )
    assert advisory.returncode == 0, advisory.stderr
    assert required.returncode == 3, required.stderr
    advisory_result = json.loads(advisory.stdout)
    required_result = json.loads(required.stdout)
    assert advisory_result["pipeline_completed"] is False
    assert advisory_result["status"] == "VIRTUAL_SESSION_FAULTED"
    assert advisory_result["virtual_session"]["fault_reason"] == (
        "KEYBOARD_MISSED_CONTACT"
    )
    assert required_result["session_report_hash"] == (
        advisory_result["session_report_hash"]
    )
    assert not advisory_serial.exists()
    assert not advisory_cv2.exists()
    assert not required_serial.exists()
    assert not required_cv2.exists()


def test_simulate_session_camera_tag_loss_fails_from_decoded_pixels(
    tmp_path: Path,
) -> None:
    workspace = _virtual_workspace(tmp_path)
    completed = _run(
        workspace,
        "simulate-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--fault-profile",
        "camera-tag-loss",
        "--record",
        "--runtime",
        "software/config/runtime.json",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    session = result["virtual_session"]
    evidence_directory = Path(result["evidence_record"]["directory"])
    vision = json.loads((evidence_directory / "vision.json").read_text(encoding="utf-8"))
    attempt = vision["attempts"][0]["result"]

    assert result["pipeline_completed"] is False
    assert result["fault_profile"] == "camera-tag-loss"
    assert session["fault_reason"] == "CAMERA_TAG_LOSS"
    assert attempt["capture_mode"] == "TAG_LOSS"
    assert attempt["stage"] == "POSE"
    assert attempt["status"] == "FAULT"
    assert [
        detection["tag"]["id"]
        for detection in attempt["detection_batch"]["detections"]
        if detection["detector_accepted"]
    ] == [4, 5]
    assert attempt["pose_observation"] is None
    assert not (workspace / "serial-imported.txt").exists()
    assert not (workspace / "cv2-imported.txt").exists()


def test_simulate_record_and_replay_round_trip_is_identical(tmp_path: Path) -> None:
    workspace = _virtual_workspace(tmp_path)
    recorded = _run(
        workspace,
        "simulate-session",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--record",
        "--runtime",
        "software/config/runtime.json",
        "--require-pass",
        "--json",
    )
    assert recorded.returncode == 0, recorded.stderr
    record_result = json.loads(recorded.stdout)
    manifest = Path(record_result["evidence_record"]["manifest"])
    assert manifest.is_file()

    shutil.rmtree(workspace / "sentinel_modules")
    replayed = _run(
        workspace,
        "replay-session",
        "--manifest",
        str(manifest),
        "--runtime",
        "software/config/runtime.json",
        "--require-identical",
        "--json",
    )
    assert replayed.returncode == 0, replayed.stderr
    replay_result = json.loads(replayed.stdout)
    assert replay_result["schema"] == "rocell.replay_session_cli.v1"
    assert replay_result["status"] == "REPLAY_IDENTICAL"
    assert replay_result["identical"] is True
    assert replay_result["replay"]["recorded_report_hash"] == (
        record_result["session_report_hash"]
    )
    assert replay_result["replay"]["recomputed_report_hash"] == (
        record_result["session_report_hash"]
    )
    assert not (workspace / "serial-imported.txt").exists()
    assert not (workspace / "cv2-imported.txt").exists()


def test_replay_session_rejects_manifest_outside_runtime_evidence_root(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "replay-session",
        "--manifest",
        str(REPOSITORY_ROOT / "software/config/system_manifest.json"),
        "--json",
    )
    assert completed.returncode == 2
    result = json.loads(completed.stderr)
    assert result["error"]["code"] == "SESSION_MANIFEST_OUTSIDE_EVIDENCE_ROOT"
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_keyboard_plan_is_semantic_hashed_and_non_executable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    completed = _run(
        workspace,
        "plan",
        "--device",
        "keyboard",
        "--text",
        "ab ",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["mode"] == "plan"
    assert result["execution_authorized"] is False
    assert result["action_plan"]["device_profile"] == (
        "development/keyboard-us-lowercase-semantic-v1"
    )
    assert result["action_plan"]["actions"] == [
        {"type": "press_key", "key": "A"},
        {"type": "press_key", "key": "B"},
        {"type": "press_key", "key": "SPACE"},
    ]
    assert "ab " not in completed.stdout
    assert all(set(action) <= {"type", "key"} for action in result["action_plan"]["actions"])


def test_phone_plan_uses_ui_state_actions_without_coordinates(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    completed = _run(
        workspace,
        "plan",
        "--device",
        "phone",
        "--text",
        "ab",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    actions = result["action_plan"]["actions"]
    assert result["action_plan"]["device_profile"] == (
        "development/phone-lowercase-semantic-v1"
    )
    assert actions[0] == {"type": "verify_phone_state", "state": "KEYBOARD_LOWER"}
    assert actions[1]["target"] == "key_a"
    assert actions[2]["target"] == "key_b"
    assert all(not ({"x", "y", "z"} & set(action)) for action in actions)


def test_dry_run_is_honest_semantic_trace_and_never_hardware(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    completed = _run(
        workspace,
        "dry-run",
        "--device",
        "keyboard",
        "--text",
        "test",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    simulation = json.loads(completed.stdout)["simulation"]
    assert simulation["scope"] == "SEMANTIC_ACTIONS_ONLY_NO_GEOMETRY"
    assert simulation["hardware_access"] is False
    assert simulation["hardware_accessed"] is False
    assert simulation["arm_commands_generated"] == 0
    assert simulation["geometric_path_checks_performed"] is False
    assert simulation["collision_checks_performed"] is False
    phases = [step["phase"] for step in simulation["steps"]]
    assert phases[0] == "PARK"
    assert phases[-2:] == ["PARK", "COMPLETE"]
    assert phases.count("CONTACT") == 4
    assert all(step["simulated"] is True for step in simulation["steps"])
    assert not (workspace / "serial-imported.txt").exists()
    assert not (workspace / "cv2-imported.txt").exists()


def test_arm_feedback_is_denied_before_pyserial_import_or_com_open(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    completed = _run(
        workspace,
        "arm-feedback",
        "--port",
        "COM_DO_NOT_OPEN",
        "--json",
    )
    assert completed.returncode == 4
    result = json.loads(completed.stderr)
    assert result["error"]["code"] == "CAPABILITY_DENIED"
    assert result["error"]["details"]["capability"] == "arm_feedback"
    assert "ROBOT_POWER_NOT_RELEASED" in result["error"]["details"]["reasons"]
    assert not (workspace / "serial-imported.txt").exists()
    assert not (workspace / "cv2-imported.txt").exists()


def test_simulate_runs_geometry_provisional_ik_and_synthetic_vision_without_hardware(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate",
        "--device",
        "keyboard",
        "--text",
        "a",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["schema"] == "rocell.simulation_run.v1"
    assert result["status"] in {
        "PASS_SIMULATION_ONLY_WITH_PHYSICAL_HOLDS",
        "PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS",
    }
    assert result["simulation_only"] is True
    assert result["execution_authorized"] is False
    assert result["hardware_accessed"] is False
    assert result["hardware_commands_generated"] == 0
    assert result["required_simulation_checks_pass"] is True
    if result["all_sampled_ik_converged"]:
        assert result["status"] == "PASS_SIMULATION_ONLY_WITH_PHYSICAL_HOLDS"
    else:
        assert result["status"] == (
            "PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS"
        )
    assert result["snapshot"]["integrity_verified"] is True

    alignment = result["placemat_alignment"]
    assert alignment["status"] == "PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS"
    assert alignment["all_checks_pass"] is True
    assert len(alignment["checks"]) == 17

    geometry = result["geometry"]
    assert geometry["required_for_simulation_pass"] is True
    assert geometry["all_checks_pass"] is True
    assert geometry["hardware_accessed"] is False
    assert geometry["hardware_commands_generated"] == 0
    assert geometry["checks"]
    assert all(check["status"] == "PASS" for check in geometry["checks"])

    ik = result["ik"]
    assert ik["schema"] == "rocell.simulation.ik_summary.v1"
    assert ik["required_for_simulation_pass"] is False
    assert ik["live_motion_authorized"] is False
    assert ik["hardware_commands_generated"] == 0
    assert 0 < ik["sampled_tip_point_count"] <= 8
    assert ik["unique_tip_point_count"] >= ik["sampled_tip_point_count"]
    assert all(row["hardware_commands_generated"] == 0 for row in ik["results"])

    vision = result["vision"]
    assert vision["scenario_id"] == "SYNTHETIC_FIXED_OVERVIEW_TEST_FIXTURE"
    assert vision["scenario_is_arm_mounted_camera"] is False
    assert vision["physical_camera_accessed"] is False
    assert vision["required_for_simulation_pass"] is True
    assert vision["status"] == "PASS"
    assert vision["tag_count"] == 6
    assert vision["visible_tag_count"] == 6
    assert vision["eye_on_arm_coverage"]["status"] == (
        "NOT_RUN_INSTALL_TRANSFORMS_MISSING"
    )

    verification = result["verification"]
    assert verification["status"] == "NOT_PERFORMED_OBSERVERS_NOT_IMPLEMENTED"
    assert verification["phone_ui_state_observation_performed"] is False

    assert result["controller_bridge"]["status"] == (
        "NOT_RUN_R_CTRL_CORRELATION_MISSING"
    )
    assert result["controller_bridge"]["t104_commands_generated"] == 0

    physical = result["physical_readiness"]
    assert physical["changed_by_run"] is False
    assert physical["safe_to_power_robot"] is False
    assert physical["contact_enabled"] is False
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_workcell_command_reports_full_placemat_alignment_without_hardware(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "workcell",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["schema"] == "rocell.placemat_alignment.v1"
    assert result["status"] == "PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS"
    assert result["execution_authorized"] is False
    assert result["physical_release_effect"] == "NONE"
    assert result["simulation_bundle"]["physical_release_effect"] == "NONE"
    assert len(result["checks"]) == 17
    assert all(check["status"] == "PASS" for check in result["checks"])
    assert not serial_marker.exists()
    assert not cv2_marker.exists()


def test_phone_simulate_maps_phone_targets_and_human_output_denies_execution(
    tmp_path: Path,
) -> None:
    completed, serial_marker, cv2_marker = _run_repository(
        tmp_path,
        "simulate",
        "--device",
        "phone",
        "--text",
        "a",
    )
    assert completed.returncode == 0, completed.stderr
    assert "simulation: PASS" in completed.stdout
    assert "physical execution/readiness: not authorized and unchanged" in completed.stdout
    assert "synthetic overview vision: 6/6 tags visible" in completed.stdout
    assert not serial_marker.exists()
    assert not cv2_marker.exists()
