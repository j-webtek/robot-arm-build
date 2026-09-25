"""Compile and run native owner against synthetic register reads; no hardware."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_native_held_elbow_leg_owner(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    source = Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_held_elbow_leg_owner.cpp'
    exe = tmp_path/'held-leg.exe'
    built = subprocess.run([compiler, '-std=c++17', str(source), '-o', str(exe)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0, ran.stdout + ran.stderr
