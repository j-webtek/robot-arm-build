from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp("large-pose-lift") / "test.exe"
    build = subprocess.run(
        [compiler, "-std=c++17", str(root / "firmware/diagnostics/test_large_pose_lift_owner.cpp"),
         "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    return target


@pytest.mark.parametrize("mode", [
    "success", "source_rejected", "prewrite_changed", "write_uncertain",
    "wrong_goal", "passive_drift", "reverse", "evidence_failure",
])
def test_exact_three_servo_lift_is_one_shot_and_fault_stopping(binary, mode):
    run = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    if mode == "success":
        record = bytes.fromhex(run.stdout.strip())
        assert len(record) == 1133
        assert record[:10] == b"RCLIFT0001"
        assert record[26:32] == bytes.fromhex("092c06e60676")
