import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.compensated_shoulder_authorization import propose_compensated_step,sign_compensated_step
from rocell.application.compensated_shoulder_contract import REFERENCE,GOALS

BOOT='11'*16


def records():
    return [json.dumps(dict(schema='rocell.shoulder_hold_event.v1',boot_id=BOOT,command_id='capture',
        snapshot_role='OBSERVATION',physical_accuracy_verified=False,
        scan_started_us=1+i*200000,scan_finished_us=1000+i*200000,
        joints=[[sid,p,g,1,p.to_bytes(2,'little').hex()+'00'*13]
                for sid,p,g in zip(range(11,18),REFERENCE,GOALS)])).encode() for i in range(3)]


def proposal(raw):return propose_compensated_step(raw,boot=BOOT,command='compensated-step-1',now_us=402000)


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path_factory.mktemp('comp-auth')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17','-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_compensated_shoulder_authorization.cpp'),'-lbcrypt','-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('mode',['valid','bad_mac','digest','substitution','target','desired','predicted',
    'offset','model','sum','tolerance','speed','extra','command','moving','raw','boot','owner','drift',
    'stale','expired','prewrite_changed'])
def test_native_reconstructs_exact_signed_compensation(native,mode):
    raw=records();plan=proposal(raw)
    if mode=='digest':plan['reference_sha256']='00'*32
    if mode=='substitution':raw[0]+=b' '
    if mode=='target':plan['command_goals'][1]+=1
    if mode=='desired':plan['desired_positions'][0]-=1
    if mode=='predicted':plan['predicted_positions'][0]-=1
    if mode=='offset':plan['offsets'][0]+=1
    if mode=='model':plan['model_id']='another-model'
    if mode=='sum':plan['goal_sum']+=1
    if mode=='tolerance':plan['arrival_tolerance_counts']=20
    if mode=='speed':plan['speed']=200
    if mode=='extra':plan['retry']=True
    if mode=='command':plan['command_id']='another-command'
    if mode in ('moving','raw','boot','owner','drift'):
        doc=json.loads(raw[1])
        if mode=='moving':doc['joints'][0][4]='ff070100'+'00'*11
        if mode=='raw':doc['joints'][0][4]='00'*15
        if mode=='boot':doc['boot_id']='22'*16
        if mode=='owner':doc['command_id']='another-capture'
        if mode=='drift':
            doc['joints'][1][1]+=2
            doc['joints'][1][4]=doc['joints'][1][1].to_bytes(2,'little').hex()+'00'*13
        raw[1]=json.dumps(doc).encode()
        with pytest.raises(ValueError):proposal(raw)
    challenge=dict(schema='rocell.start_challenge.v1',boot_id=BOOT,nonce='00'*32,issued_us=402000,expires_us=30402000)
    token=sign_compensated_step(challenge,plan,bytes(range(32)))
    if mode=='bad_mac':token=token[:-1]+bytes([token[-1]^1])
    result=subprocess.run([str(native),mode],input='\n'.join(r.decode() for r in raw)+'\n'+token.hex()+'\n',
                          capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    expected=[1,1] if mode=='valid' else [1,0] if mode=='prewrite_changed' else [0,0]
    assert list(map(int,result.stdout.split()))==expected


def test_schema_is_distinct_from_installed_local_step():
    from rocell.application.local_shoulder_step import sign_local_step
    plan=proposal(records())
    challenge=dict(schema='rocell.start_challenge.v1',boot_id=BOOT,nonce='00'*32,issued_us=402000,expires_us=30402000)
    assert plan['desired_positions']==[2400,1716] and plan['command_goals']==[2391,1723]
    with pytest.raises(ValueError):sign_local_step(challenge,plan,bytes(range(32)))
