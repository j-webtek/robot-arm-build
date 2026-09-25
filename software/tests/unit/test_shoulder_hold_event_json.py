import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_native_command_correlated_records(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    binary=tmp_path/'records.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_shoulder_hold_event_json.cpp'),'-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    records=[json.loads(line) for line in result.stdout.splitlines()]
    assert [r['sequence'] for r in records]==list(range(7))
    assert all(r['command_id']=='shoulder-test-1' and not r['physical_accuracy_verified'] for r in records)
    for index,target in ((1,2455),(4,1659)):
        intent,action,readback=records[index:index+3]
        assert intent['requested_target']==action['requested_target']==target
        assert action['snapshot_role']=='PRE_ACTION'
        assert action['action_started_us']>=action['scan_finished_us']
        sid=action['servo_id']
        row=readback['joints'][sid-11]
        assert row[1:4]==[target,target,0]
        assert len(bytes.fromhex(row[4]))==15
