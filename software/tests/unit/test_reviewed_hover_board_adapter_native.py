"""Compile-only board seam and fake-bus test; never opens a hardware port."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_reviewed_hover_board_adapter_is_bounded_and_does_not_retry(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path / "reviewed_hover_board_adapter.exe"
    result = subprocess.run(
        [compiler, "-std=c++17", "-O2", "-Wall", "-Wextra",
         str(ROOT / "firmware/diagnostics/test_reviewed_hover_board_adapter.cpp"),
         "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
