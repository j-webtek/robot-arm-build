from pathlib import Path
import shutil
import subprocess
import pytest


def test_freshness_and_faults_at_actual_write_boundary(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'prewrite.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_prewrite_guard.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
