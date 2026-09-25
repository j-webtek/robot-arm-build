"""Board routes are tested with inert filesystem/network/runtime doubles."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_hold_only_board_routes(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'hold-routes.exe'
    build = subprocess.run([compiler, '-std=c++17',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_configured_hold_routes.cpp'), '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    for mode in range(9):
        result = subprocess.run([str(exe), str(mode)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
