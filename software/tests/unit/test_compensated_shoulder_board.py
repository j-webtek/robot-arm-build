from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module')
def board(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    binary=tmp_path_factory.mktemp('compensated-board')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17','-DROCELL_COMPENSATED_SHOULDER_STEP',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_compensated_shoulder_board.cpp'),'-lbcrypt','-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('mode',['success','conflict','missing_key','unhealthy','busy','parameters',
    'malformed','oversize','tampered','expired','admission_lost','low_heap','fragmented'])
def test_compensated_board_owned_read_only_ingress(board,mode):
    result=subprocess.run([str(board),mode],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'BOARD_INGRESS_OFFLINE_PASSED' in result.stdout
