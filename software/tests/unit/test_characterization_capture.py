from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];target=tmp_path_factory.mktemp('campaign-capture')/'test.exe'
    build=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_characterization_capture.cpp'),
                          '-lbcrypt','-o',str(target)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    return target


@pytest.mark.parametrize('mode',['success','conflict','lost','deadline','clock'])
def test_capture_to_preparation(binary,mode):
    run=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
