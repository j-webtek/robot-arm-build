import hmac
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.servo_session_plan import SessionPlan
from rocell.application.servo_start_authorization import DOMAIN, sign_start
from test_servo_start_authorization import fixture, KEY


def test_host_signed_requests_in_native_gate(tmp_path):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:pytest.skip('Windows crypto/compiler required')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'start-gate.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        str(root/'firmware/diagnostics/test_start_envelope.cpp'),'-lbcrypt','-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    plan,_=fixture();document=plan.to_dict();document['command']['boot_id']='11'*16
    plan=SessionPlan(canonical(document))
    challenge=dict(schema='rocell.start_challenge.v1',boot_id='11'*16,nonce='22'*32,
        issued_us=1000,expires_us=11000)
    token=sign_start(plan,challenge,KEY)
    cases=[('valid',token,1001,True,plan.encoded),('expired',token,11000,False,b''),
           ('rewound',token,999,False,b''),('truncated',token[:-1],1001,False,b''),
           ('extra',token+b'!',1001,False,b''),('oversized',b'x'*17000,1001,False,b'')]
    for name,offset in [('domain',0),('boot',len(DOMAIN)),('nonce',len(DOMAIN)+16),
                        ('issued',len(DOMAIN)+48),('length',len(DOMAIN)+64),('plan',len(DOMAIN)+66),('tag',-1)]:
        changed=bytearray(token);changed[offset]^=1
        cases.append((name,bytes(changed),1001,False,b''))
        if name not in ('plan','tag'):
            # Even a correctly authenticated envelope must match the issued challenge/framing.
            unsigned=bytes(changed[:-32]);signed=unsigned+hmac.digest(KEY,unsigned,'sha256')
            cases.append(('signed-'+name,signed,1001,False,b''))
    # Authentication is deliberately not semantic plan validation. Keep this
    # limitation explicit until the native parser/admission stage is integrated.
    unsigned=token[:len(DOMAIN)+64]+struct.pack('>H',2)+b'{}'
    cases.append(('authenticated-not-admitted',unsigned+hmac.digest(KEY,unsigned,'sha256'),1001,True,b'{}'))
    for name,data,now,accepted,expected in cases:
        path=tmp_path/(name+'.bin');path.write_bytes(data)
        run=subprocess.run([str(executable),str(path),str(now),'yes' if accepted else 'no'],
            capture_output=True,timeout=10)
        assert run.returncode==0,(name,run.stderr)
        assert run.stdout==expected,name
