"""The native live-admission parser is structural only and performs no I/O."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_native_live_admission_requires_exact_boot_release_and_recipe(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "reviewed_hover_live_admission.exe"
    result = subprocess.run(
        [compiler, "-std=c++17", "-O2", "-Wall", "-Wextra",
         str(ROOT / "firmware/diagnostics/test_reviewed_hover_live_admission.cpp"),
         "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
