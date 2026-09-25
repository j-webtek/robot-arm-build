import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.local_shoulder_step import propose_local_step,sign_local_step
from rocell.application.shoulder_export_receipt import export_and_sign
from rocell.application.shoulder_fault_settling_export import FaultSettlingExport


@pytest.fixture(scope='module')
def session_bridge(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path_factory.mktemp('local-session')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17','-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_local_shoulder_step_session.cpp'),'-lbcrypt','-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('mode',['success','short','neighbor','prewrite','bad_receipt','bad_plan','bad_sent_receipt'])
def test_owned_capture_auth_write_and_fault_settling(session_bridge,tmp_path,mode):
    process=subprocess.Popen([str(session_bridge),mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,text=True)
    boot='11'*16;command='local-step-1';key=bytes(range(32));references=[];terminal=None;settling=None
    try:
        for _ in range(80):
            line=process.stdout.readline();assert line,process.stderr.read()
            raw=line.rstrip().encode();doc=json.loads(raw)
            if doc.get('authorize'):
                plan=propose_local_step(references,boot=boot,command=command,now_us=doc['now_us'])
                if mode=='bad_plan':plan['targets'][1]+=1
                receipt=sign_local_step(dict(schema='rocell.start_challenge.v1',boot_id=boot,nonce='00'*32,
                    issued_us=1,expires_us=30000001),plan,key)
            elif doc.get('terminal'):
                terminal=doc
                if mode not in ('short','neighbor'):break
                original=doc['original'].encode();original_doc=json.loads(original)
                settling=FaultSettlingExport(original,boot=boot,parent_command=command)
                receipt=export_and_sign(tmp_path,original,key=key,boot=boot,command=command,
                    sequence=original_doc['sequence'])['receipt']
            elif doc.get('settling_terminal'):
                assert doc['settled'];break
            elif settling:
                receipt=settling.export(tmp_path,raw,key=key)['receipt']
            else:
                if doc['sequence']<3:references.append(raw)
                receipt=export_and_sign(tmp_path,raw,key=key,boot=boot,command=command,sequence=doc['sequence'])['receipt']
                if mode=='bad_receipt' or (mode=='bad_sent_receipt' and doc['event']=='SHOULDER_STEP_SENT'):
                    receipt=receipt[:-1]+bytes([receipt[-1]^1])
            process.stdin.write(receipt.hex()+'\n');process.stdin.flush()
        assert terminal
        assert terminal['writes']==(0 if mode in ('prewrite','bad_receipt','bad_plan') else 1)
        assert terminal['fault']==(mode!='success')
        if mode=='short':assert terminal['reason']=='ARRIVAL_DEADLINE' and settling.count>=3
        if mode=='neighbor':assert terminal['reason']=='STEP_STATE_CHANGED' and settling.count>=3
        assert process.wait(timeout=5)==0,process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
