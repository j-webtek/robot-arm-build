import json
from pathlib import Path
import shutil
import subprocess
import pytest
from test_local_shoulder_step import records,proposal,BOOT
from rocell.application.local_shoulder_step import sign_local_step


@pytest.fixture(scope='module')
def native_auth(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path_factory.mktemp('local-auth')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_local_shoulder_step_authorization.cpp'),
        '-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('mode',['valid','bad_mac','wrong_digest','record_substitution','target',
    'speed','extra','wrong_command','moving','stale','expired','prewrite_changed'])
def test_real_native_signed_plan_recomputes_reference_and_targets(native_auth,mode):
    raw=records();plan=proposal()
    if mode=='wrong_digest':plan['reference_sha256']='00'*32
    if mode=='target':plan['targets'][1]+=1
    if mode=='speed':plan['speed']=200
    if mode=='extra':plan['retry']=True
    if mode=='wrong_command':plan['command_id']='another-command'
    if mode=='record_substitution':raw[0]+=b' '
    if mode=='moving':
        doc=json.loads(raw[1]);doc['joints'][0][4]='ff070100'+'00'*11;raw[1]=json.dumps(doc).encode()
    challenge=dict(schema='rocell.start_challenge.v1',boot_id=BOOT,nonce='00'*32,
        issued_us=402000,expires_us=30402000)
    token=sign_local_step(challenge,plan,bytes(range(32)))
    if mode=='bad_mac':token=token[:-1]+bytes([token[-1]^1])
    data='\n'.join(r.decode() for r in raw)+'\n'+token.hex()+'\n'
    result=subprocess.run([str(native_auth),mode],input=data,capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert list(map(int,result.stdout.split()))==([1,1] if mode=='valid' else [1,0] if mode=='prewrite_changed' else [0,0])
