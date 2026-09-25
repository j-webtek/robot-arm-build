"""Execute actual board preparation with inert filesystem/network/runtime."""
from pathlib import Path
import shutil
import subprocess
import json
import pytest
from rocell.application.first_motion_contract import canonical


def test_board_recovery_prepare(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'board-recovery.exe'
    build = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_recovery_board_prepare.cpp'),
        '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    config = tmp_path / 'hold.json'
    config.write_bytes(canonical(json.loads((root / 'docs/hold-r7-supported-pose-draft.json').read_bytes())))
    for mode in range(12):
        run = subprocess.run([str(exe), str(config), str(mode)],
                             capture_output=True, text=True, timeout=10)
        assert run.returncode == 0, (mode, run.stderr)
