from pathlib import Path
import shutil
import subprocess
import pytest


def test_native_startup_position_observation(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'startup-baseline.exe'
    run=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        str(root/'firmware/diagnostics/test_startup_position_baseline.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
