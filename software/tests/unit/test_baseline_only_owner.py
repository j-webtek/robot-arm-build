from pathlib import Path
import shutil
import subprocess
import pytest


def test_exclusive_baseline_owner(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'baseline-owner.exe'
    result=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_baseline_only_owner.cpp'),'-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
