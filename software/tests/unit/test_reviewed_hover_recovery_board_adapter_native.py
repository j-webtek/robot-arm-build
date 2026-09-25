"""Recovery board adapter accepts only the three fixed A poses."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_recovery_board_adapter_native(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "recovery-adapter.exe"
    stamp_source = (ROOT / ".firmware-tools/configured-diagnostic-candidate-r90"
                    / "RoArm-M3_example")
    build = subprocess.run([compiler, "-std=c++17", "-O2", "-I",
        str(stamp_source),
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_recovery_board_adapter.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
