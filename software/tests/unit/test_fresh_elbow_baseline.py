from pathlib import Path
import shutil
import subprocess
import pytest


def test_fresh_baseline_rejects_invalid_moving_stale_or_large_delta(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_fresh_elbow_baseline.cpp'
    executable=tmp_path/'baseline-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',str(source),'-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
