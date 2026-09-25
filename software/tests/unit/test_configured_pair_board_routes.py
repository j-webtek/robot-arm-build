"""Actual board prepare callback with inert files/runtime and public test key."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.first_motion_contract import canonical


def test_pair_board_configuration_failures(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'pair-board.exe'
    build=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_configured_pair_board_routes.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    config=tmp_path/'hold.json'
    config.write_bytes(canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes())))
    for mode in range(11):
        run=subprocess.run([str(exe),str(config),str(mode)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
