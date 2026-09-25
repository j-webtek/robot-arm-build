from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.p4_wrist_review import review_p4_wrist
from rocell.application.wizard_diagnostic_export import verify_export

ROOT=Path(__file__).resolve().parents[2]
MODEL=ROOT/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'
SOURCE=ROOT/'runs/wizard-exports/wizard-20260924T101235379282Z-701e8f9afca3454682c92dafbb258f43'

def test_retained_endpoint_review():
    assert verify_export(SOURCE)['valid']
    raw=bytes.fromhex((SOURCE/'attachment-large-pose-relief.hex.txt').read_text())
    review=review_p4_wrist(raw,expected_boot='30838e5a53f316c62ac21f976ce95424',model_path=MODEL)
    assert review['selected_servo_ids']==[15]
    assert review['command_delta_counts']==65
    assert review['absolute_target_minus_measured_position_counts']==68
    assert review['start_tcp_mm'][2]>review['nominal_tcp_mm'][2]>review['swept_minimum_tcp_z_mm']>35
    assert not review['physical_clearance_verified']
    assert not review['movement_authorized']
    with pytest.raises(ValueError,match='identity mismatch'):
        review_p4_wrist(raw,expected_boot='ab'*16,model_path=MODEL)
    with pytest.raises(ValueError,match='framing'):
        review_p4_wrist(raw[:-1],expected_boot='ab'*16,model_path=MODEL)

def test_native_wrist_policy(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    target=tmp_path/'policy.exe'
    result=subprocess.run([compiler,'-std=c++17',str(ROOT/'firmware/diagnostics/test_p4_wrist_policy.cpp'),'-o',str(target)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    subprocess.run([str(target)],check=True,timeout=10)
