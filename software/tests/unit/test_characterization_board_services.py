from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];target=tmp_path_factory.mktemp('campaign-board')/'test.exe'
    build=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_characterization_board_services.cpp'),
                          '-lbcrypt','-o',str(target)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    return target


@pytest.mark.parametrize('mode',['success','key','health','busy','heap','fragmented','shoulder',
    'diagnostic','pose','hold','configured','recovery','pair','boot'])
def test_platform_service_composition(binary,mode):
    run=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
