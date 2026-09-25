from pathlib import Path
import shutil
import subprocess
import pytest


def test_actual_owner_header_with_inert_interfaces(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_espnow_owner.cpp'
    executable=tmp_path/'owner-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',str(source),
        '-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    for scenario in range(5):
        run=subprocess.run([str(executable),str(scenario)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(scenario,run.stdout,run.stderr)
