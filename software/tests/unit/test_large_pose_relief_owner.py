from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.large_pose_relief_record import (
    RECORD_BYTES, assess_large_pose_relief_record,
)


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    target=tmp_path_factory.mktemp('large-pose-relief')/'test.exe'
    built=subprocess.run([compiler,'-std=c++17',
                          str(root/'firmware/diagnostics/test_large_pose_relief_owner.cpp'),
                          '-o',str(target)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    return target


@pytest.mark.parametrize('mode',[
    'success','source_rejected','prewrite_changed','write_uncertain',
    'wrong_goal','passive_drift','reverse','evidence_failure',
])
def test_one_shot_relief_fault_stops(binary,mode):
    run=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    if mode=='success':
        raw=bytes.fromhex(run.stdout.strip())
        assert len(raw)==RECORD_BYTES
        assert raw.startswith(b'RCRELIEF01')
        assessment=assess_large_pose_relief_record(raw,expected_boot='ab'*16)
        assert assessment['status']=='P1_JOINT_ENDPOINT_MEASURED'
        assert assessment['synchronized_servo_ids']==[14,15]
        assert assessment['position_delta_counts']==[0,0,0,-57,65,0,0]
