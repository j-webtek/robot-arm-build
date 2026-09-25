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
    target = tmp_path_factory.mktemp('park-reanchor-routes') / 'test.exe'
    built = subprocess.run(
        [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
         str(root / 'firmware/diagnostics/test_park_reanchor_routes.cpp'),
         '-o', str(target)], capture_output=True, text=True, timeout=30,
    )
    assert built.returncode == 0, built.stderr
    return target


@pytest.mark.parametrize('mode', ['success', 'fault'])
def test_park_reanchor_routes(binary, mode):
    ran = subprocess.run([str(binary), mode], capture_output=True, text=True,
                         timeout=10)
    assert ran.returncode == 0, f'{mode}: {ran.stderr}'
