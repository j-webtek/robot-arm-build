from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.p3_extension_review import review_p3_extension
from rocell.application.wizard_diagnostic_export import verify_export

ROOT=Path(__file__).resolve().parents[2]
MODEL=ROOT/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'
SOURCE=ROOT/'runs/wizard-exports/wizard-20260923T201517566882Z-2a37583111464777b465b59ccec7b9f0'

def test_replayed_path_and_order():
    assert verify_export(SOURCE)['valid']
    raw=bytes.fromhex((SOURCE/'attachment-large-pose-relief.hex.txt').read_text())
    r=review_p3_extension(raw,expected_boot='ce3a5f51d59110826b67e3bf48d1f260',model_path=MODEL)
    start=r['start_tcp_mm']
    assert r['elbow_first_tcp_mm'][0]-start[0]>30
    assert r['elbow_first_tcp_mm'][2]-start[2]>6
    assert r['independent_progress']['minimum_tcp_z_mm']<start[2]-4
    assert r['elbow_first']['minimum_tcp_z_mm']==pytest.approx(start[2])
    assert r['next_command']['servo_id']==14
    assert r['next_command']['command_delta_counts']==-65
    assert r['next_command']['target_minus_measured_position_counts']==-67
    assert not r['movement_authorized'] and not r['physical_clearance_verified']
    with pytest.raises(ValueError,match='identity mismatch'):
        review_p3_extension(raw,expected_boot='ab'*16,model_path=MODEL)
    with pytest.raises(ValueError,match='framing'):
        review_p3_extension(raw[:-1],expected_boot='ab'*16,model_path=MODEL)

def test_native_elbow_policy(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    exe=tmp_path/'policy.exe'
    build=subprocess.run([compiler,'-std=c++17',str(ROOT/'firmware/diagnostics/test_p3_elbow_policy.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    subprocess.run([str(exe)],check=True,timeout=10)
