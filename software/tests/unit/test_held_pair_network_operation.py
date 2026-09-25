"""Single-connection scheduling without sockets or hardware."""
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('source',['test_held_pair_network_operation.cpp','test_held_pair_network_lifecycle.cpp',
                                   'test_configured_held_pair_routes.cpp'])
def test_pair_network_operation(tmp_path,source):
    compiler=shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'network.exe'
    build=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics'/source),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
    assert run.returncode==0,run.stderr
