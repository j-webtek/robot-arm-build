from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from rocell.calibration.artifacts import ArtifactState
from rocell.calibration.eye_on_arm_dataset import (
    EQUATION,
    JOINT_ORDER,
    MAX_DATASET_BYTES,
    EyeOnArmDatasetError,
    eye_on_arm_dataset_from_dict,
    load_eye_on_arm_dataset,
)
from rocell.calibration.eye_on_arm_solver import (
    DEFAULT_EYE_ON_ARM_SOLVER_POLICY,
    EyeOnArmSolveError,
    EyeOnArmSolverPolicy,
    EyeOnArmSolverUnavailable,
    solve_eye_on_arm,
)
from rocell.cli import main
from rocell.geometry.transforms import RigidTransform, Vec3


def _transform_document(transform: RigidTransform) -> dict[str, Any]:
    return {
        "to_frame": transform.parent_frame,
        "from_frame": transform.child_frame,
        "rotation_row_major": list(transform.rotation.matrix),
        "translation_mm": [
            transform.translation_mm.x,
            transform.translation_mm.y,
            transform.translation_mm.z,
        ],
    }


def _truth() -> tuple[RigidTransform, RigidTransform]:
    extrinsic = RigidTransform.from_rpy_translation_mm(
        "E",
        "C_arm",
        translation_mm=Vec3(34.0, -12.0, 48.0),
        roll_rad=0.11,
        pitch_rad=-0.22,
        yaw_rad=0.17,
    )
    robot_world = RigidTransform.from_rpy_translation_mm(
        "Wv",
        "B",
        translation_mm=Vec3(305.0, 457.0, 22.0),
        roll_rad=-0.08,
        pitch_rad=0.03,
        yaw_rad=0.35,
    )
    return extrinsic, robot_world


def _carrier_poses() -> tuple[RigidTransform, ...]:
    # These deliberately excite multiple carrier axes. They are synthetic
    # Wv_T_E truth, not a claim that an unmeasured link2_T_E is commissioned.
    values = (
        (0.00, 0.00, 0.00, (80.0, 40.0, 210.0)),
        (0.20, -0.10, 0.15, (100.0, 35.0, 225.0)),
        (-0.15, 0.25, -0.20, (75.0, 70.0, 245.0)),
        (0.35, 0.15, 0.05, (120.0, 60.0, 200.0)),
        (-0.25, -0.20, 0.30, (95.0, 20.0, 260.0)),
        (0.10, 0.32, -0.28, (65.0, 55.0, 230.0)),
        (-0.32, 0.08, 0.12, (110.0, 45.0, 250.0)),
        (0.27, -0.25, -0.10, (90.0, 80.0, 215.0)),
    )
    return tuple(
        RigidTransform.from_rpy_translation_mm(
            "Wv",
            "E",
            translation_mm=Vec3(*translation),
            roll_rad=roll,
            pitch_rad=pitch,
            yaw_rad=yaw,
        )
        for roll, pitch, yaw, translation in values
    )


def _synthetic_document() -> dict[str, Any]:
    extrinsic, robot_world = _truth()
    samples: list[dict[str, Any]] = []
    for index, carrier_pose in enumerate(_carrier_poses()):
        # C_arm_T_B = inverse(E_T_C_arm) * inverse(Wv_T_E) * Wv_T_B.
        target_pose = (
            extrinsic.inverse().compose(carrier_pose.inverse()).compose(robot_world)
        )
        sample_id = f"pose_{index:02d}"
        samples.append(
            {
                "sample_id": sample_id,
                "frame": {
                    "sequence": index,
                    "timestamp_ns": 1_000_000_000 + index * 1_000_000_000,
                    "clock_id": "synthetic_clock",
                    "source_sha256": hashlib.sha256(sample_id.encode("ascii")).hexdigest(),
                    "width_px": 1920,
                    "height_px": 1080,
                },
                "joint_state": {
                    "sequence": index,
                    "timestamp_ns": 1_001_000_000 + index * 1_000_000_000,
                    "clock_id": "synthetic_clock",
                    "settled_duration_ms": 500.0,
                    "positions_rad": [
                        {
                            "joint": joint,
                            "position_rad": 0.01 * index * (joint_index + 1),
                        }
                        for joint_index, joint in enumerate(JOINT_ORDER)
                    ],
                },
                "carrier_pose": {
                    "joint_sequence": index,
                    "source": "synthetic_truth",
                    "Wv_T_E": _transform_document(carrier_pose),
                },
                "target_pose": {
                    "frame_sequence": index,
                    "detector": "synthetic_truth",
                    "C_arm_T_B": _transform_document(target_pose),
                    "observation_count": 24,
                    "reprojection_rms_px": 0.0,
                },
            }
        )
    return {
        "schema": "rocell.eye_on_arm_dataset.v1",
        "dataset_id": "SYNTHETIC-IMX335B-HAND-EYE-001",
        "dataset_kind": "SYNTHETIC",
        "physical_release_effect": "NONE",
        "frame_contract": {
            "robot_root": "Wv",
            "carrier": "E",
            "camera_optical": "C_arm",
            "static_target": "B",
            "equation": EQUATION,
        },
        "joint_contract": {"angle_unit": "rad", "joint_order": list(JOINT_ORDER)},
        "camera": {
            "manufacturer": "Waveshare",
            "model": "IMX335 5MP USB Camera (B)",
            "sku": "26719",
            "interface": "USB 2.0",
            "architecture": "eye_on_moving_upper_arm",
            "carrier_frame": "E",
            "optical_frame": "C_arm",
            "capture_mode": {
                "width_px": 1920,
                "height_px": 1080,
                "pixel_format": "MJPG",
                "fps": 30.0,
            },
        },
        "synchronization": {
            "mode": "settled_stop_and_look",
            "clock_id": "synthetic_clock",
            "timestamp_basis": "synthetic_exact",
            "max_pair_delta_ns": 2_000_000,
            "minimum_settled_duration_ms": 250.0,
        },
        "source_hashes": {
            "arm_frame_contract": "1" * 64,
            "camera_manifest": "2" * 64,
            "camera_intrinsics": "3" * 64,
            "carrier_registration": "4" * 64,
            "carrier_kinematic_model": "5" * 64,
            "measured_tag_map": "6" * 64,
            "robot_reference": "7" * 64,
        },
        "validation_split": {"held_out_sample_ids": ["pose_06", "pose_07"]},
        "samples": samples,
    }


def _replace_carrier_truth(
    document: dict[str, Any], index: int, carrier_pose: RigidTransform
) -> None:
    extrinsic, robot_world = _truth()
    target_pose = extrinsic.inverse().compose(carrier_pose.inverse()).compose(robot_world)
    document["samples"][index]["carrier_pose"]["Wv_T_E"] = _transform_document(
        carrier_pose
    )
    document["samples"][index]["target_pose"]["C_arm_T_B"] = _transform_document(
        target_pose
    )


def test_strict_dataset_round_trip_hash_and_deep_immutability() -> None:
    dataset = eye_on_arm_dataset_from_dict(_synthetic_document())
    reloaded = eye_on_arm_dataset_from_dict(dataset.to_dict())
    assert reloaded == dataset
    assert reloaded.content_hash == dataset.content_hash
    assert not dataset.exposure_synchronized
    with pytest.raises(TypeError):
        dataset.source_hashes["camera_manifest"] = "f" * 64  # type: ignore[index]
    with pytest.raises(TypeError):
        dataset.samples[0].joint_state.positions_by_name[JOINT_ORDER[0]] = 1.0  # type: ignore[index]


def test_loader_pins_file_and_source_hashes(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    payload = (json.dumps(_synthetic_document(), sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    dataset = load_eye_on_arm_dataset(
        path,
        expected_file_sha256=digest,
        expected_source_hashes=_synthetic_document()["source_hashes"],
    )
    assert dataset.dataset_id == "SYNTHETIC-IMX335B-HAND-EYE-001"
    with pytest.raises(EyeOnArmDatasetError, match="file hash mismatch"):
        load_eye_on_arm_dataset(path, expected_file_sha256="0" * 64)
    wrong_sources = dict(_synthetic_document()["source_hashes"])
    wrong_sources["camera_manifest"] = "f" * 64
    with pytest.raises(EyeOnArmDatasetError, match="source hash set mismatch"):
        load_eye_on_arm_dataset(path, expected_source_hashes=wrong_sources)


def test_loader_rejects_duplicate_fields(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
    with pytest.raises(EyeOnArmDatasetError, match="Duplicate JSON field"):
        load_eye_on_arm_dataset(path)


def test_loader_rejects_oversized_file_before_json_parsing(tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    with path.open("wb") as stream:
        stream.seek(MAX_DATASET_BYTES)
        stream.write(b"{")
    with pytest.raises(EyeOnArmDatasetError, match="byte limit"):
        load_eye_on_arm_dataset(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda value: value["source_hashes"].pop("carrier_registration"),
            "missing required source hashes",
        ),
        (
            lambda value: value["frame_contract"].update({"carrier": "link2"}),
            "frame_contract",
        ),
        (
            lambda value: value["samples"][0]["target_pose"].update(
                {"observation_count": 3}
            ),
            "observation_count",
        ),
        (
            lambda value: value["samples"][0]["frame"].update(
                {"timestamp_ns": 1_100_000_000}
            ),
            "frame/joint delta",
        ),
        (
            lambda value: value["samples"][0]["carrier_pose"].update(
                {"joint_sequence": 3}
            ),
            "different joint sequence",
        ),
    ),
)
def test_dataset_rejects_contract_occlusion_and_timing_failures(
    mutation: Any, message: str
) -> None:
    document = _synthetic_document()
    mutation(document)
    with pytest.raises(EyeOnArmDatasetError, match=message):
        eye_on_arm_dataset_from_dict(document)


def test_dataset_kind_cannot_relabel_synthetic_evidence_as_offline_capture() -> None:
    document = _synthetic_document()
    document["dataset_kind"] = "OFFLINE_CAPTURE"
    document["synchronization"]["timestamp_basis"] = "device_exposure"
    with pytest.raises(EyeOnArmDatasetError, match="synthetic evidence is forbidden"):
        eye_on_arm_dataset_from_dict(document)

    for sample in document["samples"]:
        sample["carrier_pose"]["source"] = "offline_fk"
        sample["target_pose"]["detector"] = "apriltag_bundle"
    dataset = eye_on_arm_dataset_from_dict(document)
    assert dataset.exposure_synchronized

    document["samples"][0]["target_pose"]["detector"] = "charuco"
    with pytest.raises(EyeOnArmDatasetError, match="target detector"):
        eye_on_arm_dataset_from_dict(document)


def test_synthetic_dataset_requires_synthetic_timestamp_basis() -> None:
    document = _synthetic_document()
    document["synchronization"]["timestamp_basis"] = "device_exposure"
    with pytest.raises(EyeOnArmDatasetError, match="synthetic_exact"):
        eye_on_arm_dataset_from_dict(document)


def test_solver_recovers_exact_transform_and_reports_held_out_residuals() -> None:
    dataset = eye_on_arm_dataset_from_dict(_synthetic_document())
    expected_extrinsic, expected_robot_world = _truth()
    result = solve_eye_on_arm(dataset)
    assert result.E_T_C_arm_candidate.almost_equal(
        expected_extrinsic, absolute_tolerance=1e-7
    )
    assert result.Wv_T_B_candidate.almost_equal(
        expected_robot_world, absolute_tolerance=1e-7
    )
    assert result.observability.carrier_rotation_axis_rank >= 2
    assert result.observability.translation_rank == 3
    assert result.training_summary.count == 6
    assert result.held_out_summary.count == 2
    assert result.training_summary.rms_translation_mm < 1e-8
    assert result.held_out_summary.rms_translation_mm < 1e-8
    assert result.relative_motion_summary.rms_translation_mm < 1e-8
    assert result.physical_release_effect == "NONE"
    assert result.diagnostic_pass
    assert result.status == (
        "DIAGNOSTIC_PASS_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
    )
    assert result.observability.second_axis_excitation_rad > (
        result.policy.minimum_second_axis_excitation_rad
    )
    assert len(result.report_hash) == 64
    expected_hash = hashlib.sha256(
        json.dumps(
            result.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    assert result.report_hash == expected_hash


def test_solver_exposes_deterministic_held_out_pose_error() -> None:
    document = _synthetic_document()
    target = document["samples"][7]["target_pose"]["C_arm_T_B"]
    target["translation_mm"][0] += 4.0
    target["translation_mm"][1] -= 3.0
    dataset = eye_on_arm_dataset_from_dict(document)
    result = solve_eye_on_arm(dataset)
    assert result.training_summary.rms_translation_mm < 1e-8
    assert result.held_out_summary.rms_translation_mm == pytest.approx(
        5.0 / (2.0**0.5), abs=1e-8
    )
    assert result.held_out_summary.max_translation_mm == pytest.approx(5.0, abs=1e-8)
    assert not result.diagnostic_pass
    assert any("HELD_OUT_RMS_TRANSLATION_MM" in item for item in result.diagnostic_failures)


def test_solver_rejects_downstream_only_or_repeated_carrier_motion() -> None:
    document = _synthetic_document()
    stationary_pose = copy.deepcopy(document["samples"][0]["carrier_pose"]["Wv_T_E"])
    for sample in document["samples"]:
        # Joint records still vary, mimicking many downstream changes that do
        # not move the link2-mounted carrier E.
        sample["carrier_pose"]["Wv_T_E"] = copy.deepcopy(stationary_pose)
    dataset = eye_on_arm_dataset_from_dict(document)
    with pytest.raises(EyeOnArmSolveError, match="near-duplicate carrier poses"):
        solve_eye_on_arm(dataset)


def test_solver_keeps_candidate_artifact_nominal_only() -> None:
    dataset = eye_on_arm_dataset_from_dict(_synthetic_document())
    result = solve_eye_on_arm(dataset)
    artifact = result.to_nominal_artifact(
        version=1,
        created_utc="2026-09-01T12:00:00Z",
        manifest_id="synthetic-manifest",
        active_build_id="SYNTHETIC-BUILD",
    )
    assert artifact.artifact_id == "eye_on_arm_extrinsic"
    assert artifact.state is ArtifactState.NOMINAL_ONLY
    assert artifact.dependency_hashes["eye_on_arm_dataset"] == dataset.content_hash
    assert artifact.parent_artifact_hashes["camera_intrinsics"] == "3" * 64
    assert artifact.payload["physical_release_effect"] == "NONE"


def test_solver_dependency_failure_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = eye_on_arm_dataset_from_dict(_synthetic_document())
    original = importlib.import_module

    def fail_numpy(name: str, package: str | None = None) -> Any:
        if name == "numpy":
            raise ImportError("synthetic missing dependency")
        return original(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_numpy)
    with pytest.raises(EyeOnArmSolverUnavailable, match="optional 'calibration'"):
        solve_eye_on_arm(dataset)


def test_precommitted_split_and_policy_are_report_hash_inputs() -> None:
    first_dataset = eye_on_arm_dataset_from_dict(_synthetic_document())
    changed_document = _synthetic_document()
    changed_document["validation_split"]["held_out_sample_ids"] = ["pose_07"]
    second_dataset = eye_on_arm_dataset_from_dict(changed_document)
    assert first_dataset.content_hash != second_dataset.content_hash
    assert solve_eye_on_arm(first_dataset).report_hash != solve_eye_on_arm(
        second_dataset
    ).report_hash

    relaxed_policy = replace(
        DEFAULT_EYE_ON_ARM_SOLVER_POLICY,
        maximum_training_rms_translation_mm=3.0,
    )
    assert solve_eye_on_arm(first_dataset).report_hash != solve_eye_on_arm(
        first_dataset, policy=relaxed_policy
    ).report_hash


def test_solver_enforces_sample_pair_and_cross_split_duplicate_bounds() -> None:
    dataset = eye_on_arm_dataset_from_dict(_synthetic_document())
    with pytest.raises(EyeOnArmSolveError, match="policy maximum is 7"):
        solve_eye_on_arm(
            dataset,
            policy=replace(DEFAULT_EYE_ON_ARM_SOLVER_POLICY, maximum_samples=7),
        )
    with pytest.raises(EyeOnArmSolveError, match="relative pairs"):
        solve_eye_on_arm(
            dataset,
            policy=replace(
                DEFAULT_EYE_ON_ARM_SOLVER_POLICY,
                maximum_relative_motion_pairs=10,
            ),
        )

    leaking = _synthetic_document()
    leaking["samples"][7]["carrier_pose"]["Wv_T_E"] = copy.deepcopy(
        leaking["samples"][0]["carrier_pose"]["Wv_T_E"]
    )
    with pytest.raises(EyeOnArmSolveError, match="TRAIN/HELD_OUT leakage"):
        solve_eye_on_arm(eye_on_arm_dataset_from_dict(leaking))


def test_solver_gates_measurable_second_axis_excitation() -> None:
    document = _synthetic_document()
    for index in range(len(document["samples"])):
        carrier = RigidTransform.from_rpy_translation_mm(
            "Wv",
            "E",
            translation_mm=Vec3(70.0 + 12.0 * index, 30.0 + 7.0 * index, 210.0),
            roll_rad=0.0008 * (-1.0 if index % 2 else 1.0),
            pitch_rad=0.0,
            yaw_rad=0.10 * index,
        )
        _replace_carrier_truth(document, index, carrier)
    dataset = eye_on_arm_dataset_from_dict(document)
    with pytest.raises(EyeOnArmSolveError, match="second-axis excitation"):
        solve_eye_on_arm(dataset)


def test_inconsistent_training_data_is_diagnostic_failure() -> None:
    document = _synthetic_document()
    for index, offset in enumerate((20.0, -24.0, 26.0)):
        document["samples"][index]["target_pose"]["C_arm_T_B"]["translation_mm"][
            0
        ] += offset
    result = solve_eye_on_arm(eye_on_arm_dataset_from_dict(document))
    assert not result.diagnostic_pass
    assert result.status == (
        "DIAGNOSTIC_FAIL_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
    )
    assert result.diagnostic_failures


def test_single_training_outlier_cannot_release_a_candidate() -> None:
    """One plausible-but-wrong pose must survive parsing but fail solve gates.

    This is a poisoning test, not a robustness claim.  The current bounded
    least-squares solver intentionally retains every precommitted training
    sample, so the independent residual gates must prevent the contaminated
    candidate from looking commissioned.
    """

    document = _synthetic_document()
    translation = document["samples"][2]["target_pose"]["C_arm_T_B"][
        "translation_mm"
    ]
    translation[0] += 25.0
    translation[1] -= 15.0
    translation[2] += 10.0

    result = solve_eye_on_arm(eye_on_arm_dataset_from_dict(document))

    assert not result.diagnostic_pass
    assert result.status == (
        "DIAGNOSTIC_FAIL_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
    )
    assert result.training_summary.max_translation_mm > (
        result.policy.maximum_training_max_translation_mm
    )
    assert any("TRAINING_" in failure for failure in result.diagnostic_failures)
    assert result.physical_release_effect == "NONE"


def test_pose_sample_miscorrelation_is_detected_by_residual_gates() -> None:
    """Swapped valid observations cannot masquerade as a valid calibration."""

    document = _synthetic_document()
    first = copy.deepcopy(document["samples"][0]["target_pose"]["C_arm_T_B"])
    fourth = copy.deepcopy(document["samples"][3]["target_pose"]["C_arm_T_B"])
    document["samples"][0]["target_pose"]["C_arm_T_B"] = fourth
    document["samples"][3]["target_pose"]["C_arm_T_B"] = first

    result = solve_eye_on_arm(eye_on_arm_dataset_from_dict(document))

    assert not result.diagnostic_pass
    assert result.diagnostic_failures
    assert (
        result.training_summary.max_translation_mm
        > result.policy.maximum_training_max_translation_mm
        or result.training_summary.max_rotation_rad
        > result.policy.maximum_training_max_rotation_rad
    )
    assert result.physical_release_effect == "NONE"


def test_offline_cli_emits_hashed_zero_authority_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic-eye-on-arm.json"
    payload = (json.dumps(_synthetic_document(), sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "rocell",
            "solve-eye-on-arm-offline",
            "--dataset",
            str(path),
            "--expected-sha256",
            hashlib.sha256(payload).hexdigest(),
            "--require-diagnostic-pass",
            "--json",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    report = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert report["schema"] == "rocell.eye_on_arm_solve_report.v1"
    assert len(report["report_hash"]) == 64
    assert report["hardware_access"] is False
    assert report["arm_commands_generated"] == 0
    assert report["camera_frames_requested"] == 0
    assert report["artifact_created"] is False
    assert report["artifact_installed"] is False
    assert report["physical_release_effect"] == "NONE"
    assert report["diagnostic_pass"] is True


def test_offline_cli_help_is_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(("solve-eye-on-arm-offline", "--help"))
    captured = capsys.readouterr()
    assert raised.value.code == 0
    assert "--expected-sha256" in captured.out
    assert "--require-diagnostic-pass" in captured.out


def test_offline_cli_can_require_diagnostic_pass_and_still_emit_report(
    tmp_path: Path,
) -> None:
    document = _synthetic_document()
    for index, offset in enumerate((20.0, -24.0, 26.0)):
        document["samples"][index]["target_pose"]["C_arm_T_B"]["translation_mm"][
            0
        ] += offset
    path = tmp_path / "inconsistent-eye-on-arm.json"
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "rocell",
            "solve-eye-on-arm-offline",
            "--dataset",
            str(path),
            "--require-diagnostic-pass",
            "--json",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    report = json.loads(completed.stdout)
    assert completed.returncode == 3
    assert completed.stderr == ""
    assert report["diagnostic_pass"] is False
    assert report["diagnostic_failures"]
