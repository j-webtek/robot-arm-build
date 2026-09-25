import hashlib
import hmac
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.local_shoulder_step import propose_local_step,sign_local_step

BOOT='11'*16
POSITIONS=[2047,2429,1688,2904,1591,2041,2047]
GOALS=[2047,2419,1695,2907,1589,2040,2047]


def records(positions=None):
    positions=positions or POSITIONS
    return [json.dumps(dict(schema='rocell.shoulder_hold_event.v1',boot_id=BOOT,
        command_id='capture',snapshot_role='OBSERVATION',physical_accuracy_verified=False,
        scan_started_us=1+i*200000,scan_finished_us=1000+i*200000,
        joints=[[sid,p,g,1,p.to_bytes(2,'little').hex()+'00'*13]
                for sid,p,g in zip(range(11,18),positions,GOALS)])).encode() for i in range(3)]


def proposal(raw=None,**kwargs):
    return propose_local_step(raw or records(),boot=BOOT,command='local-step-1',now_us=402000,**kwargs)


def test_current_historical_proposal_preserves_pair_not_independent_offsets():
    plan=proposal()
    assert plan['targets']==[2405,1709]
    assert sum(plan['targets'])==sum(GOALS[1:3])==4114
    assert [plan['targets'][i]-POSITIONS[i+1] for i in range(2)]==[-24,21]
    changed=records();changed[0]+=b' '
    assert proposal(changed)['reference_sha256']!=plan['reference_sha256']


@pytest.mark.parametrize('mutation',['boot','moving','goal','drift','timestamp','raw','disabled'])
def test_invalid_baseline_rejected(mutation):
    raw=records();doc=json.loads(raw[1])
    if mutation=='boot':doc['boot_id']='22'*16
    if mutation=='moving':doc['joints'][0][4]='ff070100'+'00'*11
    if mutation=='goal':doc['joints'][0][2]+=1
    if mutation=='drift':doc['joints'][0][1]+=2;doc['joints'][0][4]='0108'+'00'*13
    if mutation=='timestamp':doc['scan_started_us']=1
    if mutation=='raw':doc['joints'][0][4]='00'*15
    if mutation=='disabled':doc['joints'][0][3]=0
    raw[1]=json.dumps(doc).encode()
    with pytest.raises(ValueError):proposal(raw)


def test_signed_parameters_are_bound_to_boot_nonce_and_exact_plan():
    challenge=dict(schema='rocell.start_challenge.v1',boot_id=BOOT,nonce='00'*32,
                   issued_us=402000,expires_us=30402000)
    key=bytes(range(32));plan=proposal();token=sign_local_step(challenge,plan,key)
    assert hmac.compare_digest(token[-32:],hmac.digest(key,token[:-32],'sha256'))
    plan['targets'][0]-=1
    assert sign_local_step(challenge,plan,key)!=token
    challenge['boot_id']='22'*16
    with pytest.raises(ValueError):sign_local_step(challenge,plan,key)


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path_factory.mktemp('local-step')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_local_shoulder_step_contract.cpp'),
                           '-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('a,b,step',[(a,b,s) for a,b in [(2427,1686),(2429,1688),(2431,1690),(2400,1688)]
                                  for s in (11,12,24,25)])
def test_python_native_contract_parity(native,a,b,step):
    positions=POSITIONS.copy();positions[1:3]=[a,b]
    result=subprocess.run([str(native),str(a),str(b),str(step)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    ok,left,right=map(int,result.stdout.split())
    try:plan=proposal(records(positions),step_counts=step)
    except ValueError:assert ok==0
    else:assert ok==1 and plan['targets']==[left,right]
