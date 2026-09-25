import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from rocell.application.first_motion_contract import canonical
from test_servo_start_authorization import fixture
from rocell.application.servo_session_plan import SessionPlan
from rocell.application.servo_start_authorization import sign_start
from rocell.application.servo_planned_run import collect_planned_run,replay_planned_run
from rocell.application.servo_prepared_start import send_prepared_start
from rocell.application.servo_started_run import collect_started_run,replay_started_run
from test_servo_prepared_start import Sender


def test_native_payload_and_exact_reference_conversion(tmp_path):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:pytest.skip('Windows crypto/compiler required')
    root=Path(__file__).resolve().parents[2];tools=root/'.firmware-tools'
    path=tools/'reference/RoArm-M3_example/RoArm-M3_module.h';raw=path.read_bytes()
    manifest=json.loads((tools/'reference-build-inputs.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==manifest['files'][str(path.relative_to(tools))]
    text=raw.decode('utf-8-sig').replace('\r\r\n','\n').replace('\r\n','\n')
    bodies=[]
    for signature in ('double calculatePosByRad(', 'int RoArmM3_elbowJointCtrlRad('):
        start=text.index(signature);bodies.append(text[start:text.index('\n}',start)+2])
    (tmp_path/'pinned_elbow_functions.h').write_text('\n'.join(bodies))
    exe=tmp_path/'binding.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror','-I'+str(tmp_path),
        '-I'+str(tools/'user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_start_payload_binding.cpp'),'-lbcrypt','-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    plan,_=fixture();doc=plan.to_dict();doc['origin']='DEVICE_CAPTURE'
    doc['command'].update(boot_id='11'*16,conversion_version='test-reference',wire_count=2132,desired_count=2132)
    original=base64.b64decode(doc['sent_base64'])
    cases=[(doc,True,original)]
    reordered=b'{"T":101, "joint":3, "rad":1.7, "spd":20, "acc":1}'
    changed=copy.deepcopy(doc);changed['sent_base64']=base64.b64encode(reordered).decode()
    cases.append((changed,True,reordered))
    for field,value in [('wire_count',2133),('desired_count',2131),('payload_sha256','0'*64)]:
        changed=copy.deepcopy(doc);changed['command'][field]=value;cases.append((changed,False,b''))
    for raw in [original.replace(b'1.7',b'1.8'),b'{}',original+b'{}',
                original.replace(b'"spd":20',b'"spd":21'),
                original.replace(b'"joint":3',b'"joint":4'),
                original.replace(b'"joint":3',b'"joint":3,"joint":3'),
                b'\x00'+original,b'x'*257]:
        changed=copy.deepcopy(doc);changed['sent_base64']=base64.b64encode(raw).decode();cases.append((changed,False,b''))
    for encoded in ['!!!!','e31=','e30=AAAA','====','AA=A','e30_']:
        changed=copy.deepcopy(doc);changed['sent_base64']=encoded;cases.append((changed,False,b''))
    for index,(document,accepted,expected) in enumerate(cases):
        path=tmp_path/f'{index}.json';path.write_bytes(canonical(document))
        run=subprocess.run([str(exe),str(path),'yes' if accepted else 'no'],capture_output=True,timeout=10)
        assert run.returncode==0,(index,run.stderr)
        assert run.stdout==expected
    challenge=dict(schema='rocell.start_challenge.v1',boot_id='11'*16,nonce='22'*32,issued_us=1000,expires_us=11000)
    plan=SessionPlan(canonical(doc));token=sign_start(plan,challenge,bytes(range(32)))
    token_path=tmp_path/'start.bin';token_path.write_bytes(token)
    expected=[('STARTED',1,1),('ADMISSION_REJECTED',1,0),('EXPIRED_BEFORE_START',1,0),
              ('EVIDENCE_FAILURE',0,0),('START_NOT_VERIFIED',1,1)]
    for mode,(reason,admissions,starts) in enumerate(expected):
        run=subprocess.run([str(exe),str(token_path),'yes' if mode==0 else 'no',str(mode)],
            capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        lines=run.stdout.splitlines();assert lines[0]==f'{reason} {admissions} {starts}'
        if mode!=3:
            record=json.loads(lines[1])
            assert record['session_plan_sha256']==plan.sha256
            assert record['authentication_verified'] and not record['dispatch_attempted']
    for token_data,reason in [(token[:-1]+bytes([token[-1]^1]),'AUTHENTICATION_REJECTED'),
                             (sign_start(SessionPlan(canonical(cases[2][0])),challenge,bytes(range(32))),'PLAN_REJECTED')]:
        token_path.write_bytes(token_data)
        run=subprocess.run([str(exe),str(token_path),'no','0'],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,run.stderr
        assert run.stdout.strip()==f'{reason} 0 0'
    whole=dict(joints=[[1900,2200] for _ in range(7)],tracking_tolerance=2,
        maximum_pair_us=100,maximum_scan_us=1000,maximum_age_us=1000)
    v3=copy.deepcopy(doc);v3.update(schema='rocell.session_plan.v3',whole_arm_policy=whole)
    token=sign_start(SessionPlan(canonical(v3)),challenge,bytes(range(32)))
    token_path.write_bytes(token)
    for mode,accepted in [(0,True),(5,False),(6,True)]:
        run=subprocess.run([str(exe),str(token_path),'yes' if accepted else 'no',str(mode)],
            capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        assert run.stdout.splitlines()[0]==('STARTED 1 1' if accepted else 'PLAN_REJECTED 0 0')
    for field,value in [('tracking_tolerance',3),('maximum_pair_us',101),
                        ('maximum_scan_us',1001),('maximum_age_us',1001),('joints',[[0,2200] for _ in range(7)])]:
        changed=copy.deepcopy(v3);changed['whole_arm_policy'][field]=value
        token_path.write_bytes(sign_start(SessionPlan(canonical(changed)),challenge,bytes(range(32))))
        run=subprocess.run([str(exe),str(token_path),'no','0'],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,run.stderr
        assert run.stdout.strip()=='PLAN_REJECTED 0 0'
    # Complete authenticated native pipeline, with the real admission readers,
    # receipt/converter/write hook and sampling on an inert bus.
    token_path.write_bytes(token)
    for mode in range(10,20):
        run=subprocess.run([str(exe),str(token_path),'yes' if mode==10 else 'no',str(mode)],
            capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        status,*records=list(map(json.loads,run.stdout.splitlines()))
        assert status['state']==('CAPTURED' if mode==10 else 'FAULT')
        assert status['records']==len(records)
        assert not status['start_supported'] and not status['durable_export_verified']
        assert records[0]['session_plan_sha256']==SessionPlan(canonical(v3)).sha256
        assert records[1]['schema']=='rocell.whole_arm_baseline.v1'
        if mode in (12,13):
            assert records[-1]['status']=='PREWRITE_REJECTED' and not records[-1]['write_attempted']
        if mode!=10:continue
        def reader(path,**kwargs):
            if path.endswith('/status'):
                return canonical(status)
            index=int(path.split('index=')[1]);kinds=('authorization','whole_arm','receipt','baseline','converted','hook','dispatch','write')
            return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id='11'*16,index=index,
                kind=kinds[index] if index<len(kinds) else 'pair',record=records[index]))
        exported=collect_planned_run(tmp_path/'full-export',reader,v3['command'],v3['policy'],
            base64.b64decode(v3['sent_base64']),v3['schedule'],origin=v3['origin'],
            baseline_policy=v3['baseline_policy'],whole_arm_policy=v3['whole_arm_policy'])
        assessment=exported['outcome']['assessment']
        assert assessment['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
        assert assessment['whole_arm_baseline']['recomputed_accepted']
        assert assessment['whole_arm_baseline']['positions']==[2128]*7
        assert assessment['baseline']['requested_delta_counts']==4
        assert not assessment['physical_accuracy_verified'] and not assessment['progression_authority']
        assert replay_planned_run(tmp_path/'full-export',Path(exported['export_path']).name)['matches']
    for mode,reason in [(20,'STARTED'),(21,'BODY_LENGTH_MISMATCH'),(22,'BODY_LENGTH_MISMATCH'),
                        (23,'BODY_TIMEOUT_OR_CLOCK'),(24,'BODY_TIMEOUT_OR_CLOCK'),
                        (25,'BODY_DISCONNECTED'),(26,'BODY_TIMEOUT_OR_CLOCK'),
                        *[(mode,'INVALID_REQUEST_BODY') for mode in range(27,32)]]:
        run=subprocess.run([str(exe),str(token_path),'yes' if mode==20 else 'no',str(mode)],
            capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        assert run.stdout.strip()==reason
    headers=(b'POST /rocell/diagnostics/start HTTP/1.1\r\nHost: 192.168.0.225\r\n'
             b'Content-Type: application/octet-stream\r\nConnection: close\r\n'
             b'Content-Length: '+str(len(token)).encode()+b'\r\n\r\n')
    requests=[(headers+token,40,True),(headers+token,41,True)]
    for before,after in [(b'POST ',b'GET '),(b' HTTP/1.1',b' HTTP/1.0'),
                         (b'/start ',b'/start?x=1 '),(b'Connection: close',b'Connection: keep-alive'),
                         (b'application/octet-stream',b'application/json'),
                         (b'Host: 192.168.0.225\r\n',b''),
                         (b'Content-Length: ',b'Content-Length: +'),
                         (b'Content-Length: ',b'Content-Length: 0'),
                         (b'Content-Length: ',b'Content-Length : '),
                         (b'\r\n',b'\n')]:
        requests.append((headers.replace(before,after)+token,40,False))
    for extra in [b'Host: duplicate\r\n',b'content-length: '+str(len(token)).encode()+b'\r\n',
                  b'Transfer-Encoding: chunked\r\n',b'Expect: 100-continue\r\n',
                  b'X-Extra: '+b'a'*2048+b'\r\n',b' Folded: bad\r\n',b'X-Nul: \x00\r\n']:
        requests.append((headers[:-2]+extra+b'\r\n'+token,40,False))
    requests.extend([(headers+token[:-1],40,False),(headers+token+b'x',40,False),
                     (headers+token,42,False),(headers[:10],43,False),(headers[:10],44,False),
                     (headers+token[:-1]+bytes([token[-1]^1]),40,False)])
    # Rejection must not depend on TCP packet boundaries.
    requests.extend([(request,41,False) for request,mode,accepted in list(requests)
                     if mode==40 and not accepted])
    for index,(request,mode,accepted) in enumerate(requests):
        path=tmp_path/'request.bin';path.write_bytes(request)
        run=subprocess.run([str(exe),str(path),'yes' if accepted else 'no',str(mode)],
            capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(index,run.stderr)
        assert (run.stdout.strip()=='STARTED')==accepted
    path.write_bytes(headers+token)
    runtime_challenge=dict(challenge,issued_us=1001,expires_us=11001)
    runtime_token=sign_start(SessionPlan(canonical(v3)),runtime_challenge,bytes(reversed(range(32))))
    runtime_path=tmp_path/'runtime-request.bin';runtime_path.write_bytes(headers+runtime_token)
    for mode,reason in [(70,'NONE'),(71,'CONFIGURATION_REJECTED'),(72,'KEY_NOT_LOADED'),
                        (73,'LISTENER_START_FAILED'),(74,'OWNER_FAULT')]:
        run=subprocess.run([str(exe),str(runtime_path),'yes',str(mode)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        status,*runtime_records=map(json.loads,run.stdout.splitlines())
        assert status['state']==('CAPTURED' if mode==70 else 'FAULT')
        assert status['reason']==reason
        assert len(runtime_records)==(11 if mode==70 else 0)
        if mode==70:
            def runtime_reader(route,**kwargs):
                if route.endswith('/status'):return canonical(status)
                index=int(route.split('index=')[1])
                kinds=('authorization','whole_arm','receipt','baseline','converted','hook','dispatch','write')
                return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id='11'*16,index=index,
                    kind=kinds[index] if index<8 else 'pair',record=runtime_records[index]))
            exported=collect_planned_run(tmp_path/'runtime-export',runtime_reader,v3['command'],v3['policy'],
                base64.b64decode(v3['sent_base64']),v3['schedule'],origin=v3['origin'],
                baseline_policy=v3['baseline_policy'],whole_arm_policy=v3['whole_arm_policy'])
            assert exported['outcome']['assessment']['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
            assert replay_planned_run(tmp_path/'runtime-export',Path(exported['export_path']).name)['matches']
            linked_root=tmp_path/'linked-export'
            prepared=send_prepared_start(linked_root,Sender(linked_root),SessionPlan(canonical(v3)),
                runtime_challenge,bytes(reversed(range(32))))
            linked=collect_started_run(linked_root,Path(prepared['export_path']).name,runtime_reader)
            assert linked['outcome']['assessment']['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
            assert replay_started_run(linked_root,Path(linked['export_path']).name)['matches']
    for mode,reason in [(60,'CAPTURED'),(61,'LISTENER_START_FAILED'),
                        (62,'CHALLENGE_EXPIRED_OR_CLOCK'),(63,'CHALLENGE_EXPIRED_OR_CLOCK'),
                        (64,'INTERFERING_COMMAND')]:
        run=subprocess.run([str(exe),str(path),'yes',str(mode)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        assert run.stdout.strip()==reason
    for mode,reason in [(50,'STARTED'),(51,'RESPONSE_UNCERTAIN'),(52,'PEER_DISCONNECTED'),
                        (53,'SOCKET_READ_FAILED'),(54,'HTTP_TIMEOUT_OR_CLOCK'),
                        (55,'RESPONSE_UNCERTAIN'),(56,'RESPONSE_UNCERTAIN')]:
        run=subprocess.run([str(exe),str(path),'yes',str(mode)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        assert run.stdout.strip()==reason
