"""Compile and execute native capture against a scripted bus, never hardware."""
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('source', ['test_hold_state_snapshot.cpp', 'test_hold_initialization_owner.cpp',
                                  'test_elbow_configuration_snapshot.cpp', 'test_supported_recovery.cpp',
                                  'test_configured_recovery_routes.cpp'])
def test_hold_state_snapshot_native(tmp_path, source):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Host compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'hold-snapshot.exe'
    result = subprocess.run([
        compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror',
        str(root / 'firmware/diagnostics' / source),
        '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
