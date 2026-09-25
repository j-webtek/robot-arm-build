"""Exercise the staged r89 adapter identity seam without device access."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_r89_adapter_exposes_compiled_stamp_and_pinned_recipe(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "r89-adapter.exe"
    include = ROOT / ".firmware-tools/configured-diagnostic-candidate-r89/RoArm-M3_example"
    source = ROOT / "tests/native/test_reviewed_hover_r89_adapter.cpp"
    build = subprocess.run([compiler, "-std=c++17", "-O2", "-I", str(include),
                            str(source), "-o", str(target)],
                           capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
