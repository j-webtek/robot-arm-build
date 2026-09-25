"""Real signed-plan admission and native reports; entirely scripted servo bus."""
import hashlib
import copy
import hmac
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_start_authorization import DOMAIN
from rocell.application.supported_recovery_review import assess_recovery, export_recovery, replay_recovery
from rocell.application.supported_recovery_start import freeze_recovery_plan, sign_recovery


def test_six_count_auth_profile_binding(tmp_path, monkeypatch):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:pytest.skip('Windows crypto/compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'six-auth.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_six_count_recovery_runtime.cpp'),
        '-lbcrypt','-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stderr
    hold=dict(acceleration=1,age_us=250000,baseline_gap_us=100000,deadline_us=2000000,
        drift=2,joints=[[p-8,p+8] for p in (2048,2390,1727,2723,2041,2042,2051)],
        maximum_gap_us=500000,pair_us=10000,permit_explicit_enable=0,scan_us=100000,
        schema='rocell.hold_policy.v1',servo_id=14,settle_us=100000,speed=20)
    policy=dict(hold_policy=hold,initial_residual_counts=6,schema='rocell.six_count_recovery_policy.v1')
    plan=dict(boot_id='11'*16,command_id='reviewed-six-recovery',origin='DEVICE_CAPTURE',
        policy_sha256=hashlib.sha256(canonical(policy)).hexdigest(),schema='rocell.six_count_recovery_plan.v1')
    old_policy=dict(policy,initial_residual_counts=5,schema='rocell.supported_recovery_policy.v1')
    cases=[plan,dict(plan,schema='rocell.supported_recovery_plan.v1'),
        dict(plan,policy_sha256=hashlib.sha256(canonical(old_policy)).hexdigest()),
        dict(plan,command_id='other'),dict(plan,boot_id='33'*16),dict(plan,origin='SIMULATION'),plan]
    for index,candidate in enumerate(cases):
        payload=canonical(candidate)
        body=DOMAIN+bytes.fromhex('11'*16)+bytes.fromhex('22'*32)
        body+=struct.pack('>QQH',1000,10001000,len(payload))+payload
        signature=hmac.digest(b'k'*32,body,'sha256')
        if index==0:
            frozen=freeze_recovery_plan(policy,boot_id='11'*16,command_id='reviewed-six-recovery',profile='six_count')
            assert frozen.encoded==payload
            challenge=dict(schema='rocell.start_challenge.v1',boot_id='11'*16,
                nonce='22'*32,issued_us=1000,expires_us=10001000)
            assert sign_recovery(frozen,challenge,b'k'*32,approved_policy=policy,profile='six_count')==body+signature
            with pytest.raises(ValueError):sign_recovery(frozen,challenge,b'k'*32,approved_policy=policy)
        if index==len(cases)-1:signature=bytes([signature[0]^1])+signature[1:]
        token=tmp_path/f'{index}.bin';token.write_bytes(body+signature)
        run=subprocess.run([str(exe),str(token),'1' if index==0 else '0'],
            capture_output=True,text=True,timeout=10)
        assert run.returncode==0,run.stderr
        if index:
            assert not run.stdout
            continue
        records=[json.loads(line) for line in run.stdout.splitlines()]
        assert len(records)==8 and records[0]['policy']==policy
        assert all(row['schema'].startswith('rocell.six_count_recovery_') for row in records)
        assert all(row['plan_sha256']==hashlib.sha256(payload).hexdigest() for row in records)
        assert all(row['policy_sha256']==plan['policy_sha256'] for row in records)
        assert records[-1]['state']=='CAPTURED' and records[-1]['action_count']==1
        assert records[-1]['whole_arm_ready'] is False
        subject=dict(expected_plan=plan,expected_policy=policy,origin='SIMULATION')
        assert assess_recovery(records,**subject)['category']=='INCONCLUSIVE'
        assessed=assess_recovery(records,**subject,profile='six_count')
        assert assessed['category']=='SIMULATED_RECOVERY_VERIFIED'
        assert assessed['endpoint']['previous_goal']==2729
        assert assessed['endpoint']['requested_hold_target']==2723
        assert assessed['endpoint']['settled_error_counts']==0
        exported=export_recovery(tmp_path/'exports',records,**subject,profile='six_count')
        assert replay_recovery(exported['path'])==assessed
        with monkeypatch.context() as context:
            context.chdir(tmp_path)
            relative=Path(exported['path']).relative_to(tmp_path)
            assert replay_recovery(relative)==assessed
            assert replay_recovery(str(relative))==assessed
            # Relative-path support must not make modified reports acceptable.
            report=Path(exported['path'])/'attachment-recovery-assessment.json'
            original=report.read_bytes()
            report.write_bytes(original+b' ')
            with pytest.raises(ValueError,match='Invalid recovery export manifest'):
                replay_recovery(relative)
            report.write_bytes(original)
        for field,value in [('plan_sha256','0'*64),('schema','rocell.supported_recovery_snapshot.v1')]:
            damaged=copy.deepcopy(records);damaged[1][field]=value
            assert assess_recovery(damaged,**subject,profile='six_count')['category']=='INCONCLUSIVE'
        damaged=copy.deepcopy(records);damaged[1]['reads'][6][3][-1]='aa0a'
        assert assess_recovery(damaged,**subject,profile='six_count')['category']=='INCONCLUSIVE'
