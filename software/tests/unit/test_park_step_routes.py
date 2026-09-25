from pathlib import Path
import shutil
import subprocess

import pytest


def test_park_step_routes_inert_and_one_use(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / 'routes.exe'
    build = subprocess.run([compiler, '-std=c++17',
                            str(root/'firmware/diagnostics/test_park_step_routes.cpp'),
                            '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
