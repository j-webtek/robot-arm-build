from pathlib import Path
import shutil
import subprocess
import pytest


def test_precommand_evidence_composition(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'startup-evidence.exe'
    result=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_startup_precommand_evidence.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
