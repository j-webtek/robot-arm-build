"""Offline native recovery source policy; no controller connection."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_fixed_recovery_source_and_faults(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "recovery-policy.exe"
    compiled = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_recovery_policy.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
