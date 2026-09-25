from pathlib import Path
import shutil
import subprocess
import pytest


def test_one_use_scoped_start_and_bus_reservation(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    binary = tmp_path / 'start.exe'
    result = subprocess.run([compiler, '-std=c++17',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_shoulder_authorized_start.cpp'),
        '-o', str(binary)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'SHOULDER_AUTHORIZED_START_OFFLINE_PASSED' in result.stdout
