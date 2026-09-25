from pathlib import Path
import shutil
import subprocess
import pytest


def test_observed_zero_goal_startup_rejects_existing_motion_gates(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'zero-goal.exe'
    result=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        str(root/'firmware/diagnostics/test_power_on_zero_goal.cpp'),'-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
