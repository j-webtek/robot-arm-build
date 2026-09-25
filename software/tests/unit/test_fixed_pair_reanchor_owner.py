from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('fixed-reanchor-owner') / 'test.exe'
    build = subprocess.run([compiler, '-std=c++17',
                            str(root/'firmware/diagnostics/test_fixed_pair_reanchor_owner.cpp'),
                            '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    return target


@pytest.mark.parametrize('mode', [
    'success', 'start_mismatch', 'prewrite_changed', 'write_uncertain',
    'endpoint_wrong', 'evidence_failure',
])
def test_fixed_reanchor_owner_one_use(binary, mode):
    run = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
