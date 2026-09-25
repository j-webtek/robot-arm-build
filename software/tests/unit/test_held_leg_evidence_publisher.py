"""Native raw records decoded independently; no device or network access."""
import json
import copy
import hashlib
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.hold_record_replay import _snapshot
from rocell.application.held_leg_replay import assess_simulated_held_leg, export_simulated_held_leg, replay_simulated_held_leg
from rocell.application.first_motion_contract import canonical


def test_held_leg_raw_publisher(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path/'leg-publisher.exe'
    build = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_leg_evidence_publisher.cpp'), '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    sessions, current = [], []
    for line in run.stdout.splitlines():
        record = json.loads(line)
        current.append(record)
        if record['schema'] == 'rocell.held_leg_terminal.v1':
            sessions.append(current);current=[]
    assert not current and len(sessions) == 3
    assert [s[-1]['state'] for s in sessions] == ['ARRIVED','NOT_ARRIVED','FAULT']
    for session in sessions[:2]:
        scans = [_snapshot(r) for r in session if r['schema']=='rocell.held_leg_snapshot.v1']
        assert scans[0].joints[3].position == 2902
        assert scans[-1].joints[3].goal == 2908
        assert all(s.joints[3].torque == 1 for s in scans)
    assert _snapshot(sessions[0][-2]).joints[3].position == 2908
    assert sessions[2][-1]['action_count'] == 0
    policy=json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes())['hold_policy']
    policy['joints']=[[p-16,p+16] for p in (2047,2395,1722,2902,2035,2045,2047)]
    plan=dict(schema='rocell.held_leg_plan.v1',boot_id='test-boot',command_id='test-leg',
              target_count=2908,tolerance_counts=2,policy_sha256=hashlib.sha256(canonical(policy)).hexdigest())
    def assess(records, **kwargs):
        return assess_simulated_held_leg(records, plan=kwargs.get('plan',plan), policy=policy)
    assert [assess(s)['category'] for s in sessions]==['VERIFIED_ARRIVAL','VERIFIED_NON_ARRIVAL','INCONCLUSIVE']
    success=assess(sessions[0])
    assert success['position_change_counts']==6 and success['signed_error_counts']==0
    assert success['origin']=='SIMULATION' and not success['progression_authority']
    for mutation in (
        lambda r:r[-1].update(state='NOT_ARRIVED'),
        lambda r:r[0].update(command_id='other'),
        lambda r:r[3].update(payload_hex='01000000001400'),
        lambda r:r[3].update(library_return=0),
        lambda r:r[3].update(started_us=1),
        lambda r:r[1].update(snapshot_index=0),
        lambda r:r.pop(1),
        lambda r:r[-2]['reads'][0][3].__setitem__(6,'0100'),
        lambda r:r[-2]['reads'][7][3].__setitem__(6,'530b00000000000000000000000000'),
    ):
        altered=copy.deepcopy(sessions[0]);mutation(altered)
        assert assess(altered)['category']=='INCONCLUSIVE'
    assert assess(sessions[0],plan=dict(plan,target_count=2907))['category']=='INCONCLUSIVE'
    assert assess(sessions[0],plan=dict(plan,policy_sha256='00'*32))['category']=='INCONCLUSIVE'
    for session in sessions:
        saved=export_simulated_held_leg(tmp_path/'exports',session,plan=plan,policy=policy)
        assert saved['replay_verified']
        assert replay_simulated_held_leg(tmp_path/'exports',Path(saved['export_path']).name)==assess(session)
