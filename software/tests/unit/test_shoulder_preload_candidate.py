from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('hold',[False,True])
def test_native_preload_without_enable(tmp_path,hold):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'preload.exe'
    built=subprocess.run([compiler,'-std=c++17',
        str(root/'firmware/diagnostics'/('test_shoulder_hold_candidate.cpp' if hold else 'test_shoulder_preload_candidate.cpp')),
        '-o',str(executable)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert ('SHOULDER_HOLD_OFFLINE_PASSED' if hold else 'SHOULDER_PRELOAD_OFFLINE_PASSED') in result.stdout
