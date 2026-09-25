from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path_factory.mktemp('campaign-owner')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_shoulder_characterization_owner.cpp'),
                           '-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('mode',['miss','accurate','manifest','neighbor','reverse','wrong_goal','torque',
    'no_response','unsettled','read_failure','export','intent_export','prewrite_delay','cancel','deadline',
    'receipt_replay','receipt_tamper','receipt_expired','export_interrupted','post_export_drift','delayed_receipt'])
def test_finite_owner_never_dispatches_past_fault(native,mode):
    result=subprocess.run([str(native),mode],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'OWNER_PASSED' in result.stdout
