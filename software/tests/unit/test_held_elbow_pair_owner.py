"""Finite scheduler with simulated bus/admission; never opens hardware."""
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('filename', ['test_held_elbow_pair_owner.cpp',
                                    'test_held_pair_stored_evidence.cpp'])
def test_native_held_elbow_pair(tmp_path, filename):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    source = root / 'firmware/diagnostics' / filename
    exe = tmp_path / 'held-pair.exe'
    built = subprocess.run([compiler, '-std=c++17',
                            '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
                            str(source), '-o', str(exe)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert 'pair_bytes=' in ran.stdout
