from pathlib import Path
import shutil
import subprocess

import pytest


def test_park_reanchor_policy_native(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / 'park_reanchor_policy.exe'
    built = subprocess.run(
        [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
         str(root / 'firmware/diagnostics/test_park_reanchor_policy.cpp'),
         '-o', str(target)], capture_output=True, text=True, timeout=30,
    )
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
