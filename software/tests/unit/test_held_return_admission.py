"""Synthetic signed continuations; native Windows HMAC, no hardware authority."""
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


def test_native_return_admission(tmp_path):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root=Path(__file__).resolve().parents[2]
    exe=tmp_path/'return-admission.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_return_admission.cpp'),'-lbcrypt','-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stderr
    plan=dict(schema='rocell.held_return_authorization.v1',boot_id='11'*16,
        session_sha256='a'*64,forward_plan_sha256='b'*64,evidence_sha256='c'*64,
        export_sha256='d'*64,return_target_count=2902,origin='DEVICE_CAPTURE')
    cases=[(canonical(plan),False,1001,True,True),
           (canonical(plan),True,1001,True,False),
           (canonical(plan),False,10001000,True,False),
           (canonical(plan),False,999,True,False),
           (canonical(plan),False,1001,False,False),
           (json.dumps(plan).encode(),False,1001,True,False)]
    for field,value in [('return_target_count',2908),('boot_id','33'*16),
                        ('session_sha256','e'*64),('forward_plan_sha256','e'*64),
                        ('evidence_sha256','e'*64),('export_sha256','bad'),
                        ('origin','SIMULATION'),('extra',1)]:
        cases.append((canonical(dict(plan,**{field:value})),False,1001,True,False))
    for i,(payload,corrupt,now,arrived,expected) in enumerate(cases):
        body=DOMAIN+bytes.fromhex('11'*16)+bytes.fromhex('22'*32)+struct.pack('>QQH',1000,10001000,len(payload))+payload
        signature=hmac.digest(b'k'*32,body,'sha256')
        if corrupt:signature=bytes([signature[0]^1])+signature[1:]
        token=tmp_path/f'test-token-{i}.bin';token.write_bytes(body+signature)
        run=subprocess.run([str(exe),str(token),str(int(expected)),str(now),str(int(arrived))],
                           capture_output=True,text=True,timeout=10)
        assert run.returncode==0,run.stderr
