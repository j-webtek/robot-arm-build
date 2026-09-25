"""Exercise the staged r88 production recipe gate without hardware."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_r88_rejects_other_valid_recipe_before_reservation(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "r88-recipe.exe"
    include = ROOT / ".firmware-tools/configured-diagnostic-candidate-r88/RoArm-M3_example"
    source = ROOT / "tests/native/test_reviewed_hover_r88_recipe_pin.cpp"
    build = subprocess.run([compiler, "-std=c++17", "-O2", "-I", str(include),
                            str(source), "-o", str(target)],
                           capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
