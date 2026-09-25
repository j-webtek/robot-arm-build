from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module',params=['','ROCELL_MIXED_TARGET_EXPERIMENT','ROCELL_POSE_PREPARATION','ROCELL_SHOULDER_RISE','ROCELL_CLEARANCE_RECOVERY','ROCELL_STABLE_CLEARANCE_RECOVERY','ROCELL_FAULT_SETTLING_CAPTURE','ROCELL_LOCAL_SHOULDER_STEP'])
def board_binary(tmp_path_factory,request):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    binary=tmp_path_factory.mktemp('board-ingress')/'board.exe'
    built=subprocess.run([compiler,'-std=c++17']+(['-D'+request.param] if request.param else [])+[
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_shoulder_board_session.cpp'),'-lbcrypt','-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    return binary


@pytest.mark.parametrize('mode',['success','conflict','missing_key','unhealthy','busy',
    'parameters','malformed','oversize','tampered','expired','admission_lost'])
def test_board_adapter_ingress_without_hardware(board_binary,mode):
    run=subprocess.run([str(board_binary),mode],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    assert 'BOARD_INGRESS_OFFLINE_PASSED' in run.stdout
    if 'LOCAL_OBJECT_BYTES' in run.stdout:
        for case in ('low_heap','fragmented'):
            checked=subprocess.run([str(board_binary),case],capture_output=True,text=True,timeout=10)
            assert checked.returncode==0,checked.stderr
