"""Compile the actual read-only native collector; no hardware or network calls."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_native_fault_settling_capture(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    executable = tmp_path / 'fault-settling.exe'
    built = subprocess.run([compiler, '-std=c++17',
        str(root / 'firmware/diagnostics/test_shoulder_fault_settling_capture.cpp'),
        '-o', str(executable)], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'FAULT_SETTLING_OFFLINE_PASSED' in result.stdout
