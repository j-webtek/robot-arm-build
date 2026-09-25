from pathlib import Path
import shutil
import subprocess
import pytest


def test_direct_control_reads(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'control-read.exe'
    result=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        str(root/'firmware/diagnostics/test_servo_control_state_read.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
