from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.p2_wrist_review import review_p2_wrist
from rocell.application.wizard_diagnostic_export import verify_export

ROOT=Path(__file__).resolve().parents[2]
MODEL=ROOT/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'
SOURCE=ROOT/'runs/wizard-exports/wizard-20260923T194529289849Z-76fd6c1bf73a4a6eacf42e7510b2072d'

def test_retained_endpoint_review():
    assert verify_export(SOURCE)['valid']
    raw=bytes.fromhex((SOURCE/'attachment-large-pose-relief.hex.txt').read_text())
    review=review_p2_wrist(raw,expected_boot='6d2f06e84d08620829bd579b7f337c8b',model_path=MODEL)
    assert review['selected_servo_ids']==[15]
    assert review['command_delta_counts']==66
    assert review['absolute_target_minus_measured_position_counts']==65
    assert review['start_tcp_mm'][2]>review['nominal_tcp_mm'][2]>review['swept_minimum_tcp_z_mm']>23
    assert not review['physical_clearance_verified']
    assert not review['movement_authorized']
    with pytest.raises(ValueError,match='identity mismatch'):
        review_p2_wrist(raw,expected_boot='ab'*16,model_path=MODEL)
    with pytest.raises(ValueError,match='framing'):
        review_p2_wrist(raw[:-1],expected_boot='ab'*16,model_path=MODEL)

def test_native_wrist_policy(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    target=tmp_path/'policy.exe'
    result=subprocess.run([compiler,'-std=c++17',str(ROOT/'firmware/diagnostics/test_p2_wrist_policy.cpp'),'-o',str(target)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    subprocess.run([str(target)],check=True,timeout=10)
