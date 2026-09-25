"""Compile native experiment and replay its emitted evidence through host model."""
from pathlib import Path
import json
import shutil
import subprocess
import pytest
from rocell.application.hold_initialization_model import Joint,Snapshot
from rocell.application.mixed_shoulder_trial import MixedShoulderTrial


def snapshot(record):
    return Snapshot(record['scan_started_us'],record['scan_finished_us'],tuple(
        Joint(row[1],row[2],row[3],0,bytes.fromhex(row[4])[10]) for row in record['joints']))


def test_native_to_host(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path/'mixed.exe'
    built=subprocess.run([compiler,'-std=c++17','-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_mixed_shoulder_candidate.cpp'),'-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    ran=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert ran.returncode==0,ran.stderr
    assert 'MIXED_SHOULDER_NATIVE_PASSED' in ran.stdout
    rows=[json.loads(line) for line in ran.stdout.splitlines() if line.startswith('{')]
    assert len(rows)==12
    for offset,torque in ((0,'PASSIVE'),(6,'ENABLED')):
        records=rows[offset:offset+6]
        assert [r['event'] for r in records]==['BASELINE','PRELOAD_INTENT','PRELOAD_RESULT']+['PRELOAD_VERIFIED']*3
        assert [r['sequence'] for r in records]==list(range(6))
        trial=MixedShoulderTrial(snapshot(records[0]))
        command=trial.propose(snapshot(records[1]),now_us=records[2]['action_started_us'])
        assert command['target']==records[2]['requested_target']==1659
        assert records[2]['snapshot_role']=='PRE_ACTION'
        assert records[2]['result']==1 and records[2]['device_error']==0
        result=trial.assess([snapshot(r) for r in records[3:]],delivery_confirmed=True)
        assert result['category']=='TARGET_OBSERVED_'+torque
        assert result['progression_authority'] is False
