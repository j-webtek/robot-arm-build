from pathlib import Path
import shutil
import subprocess

import pytest


def test_fixed_reanchor_route_is_one_use_and_target_free(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    source = root / 'firmware/diagnostics/test_fixed_pair_reanchor_routes.cpp'
    target = tmp_path / 'routes.exe'
    build = subprocess.run([compiler, '-std=c++17', str(source), '-o', str(target)],
                           capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
