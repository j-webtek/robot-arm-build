import copy
from pathlib import Path
import shutil
import subprocess

import pytest
from rocell.application.first_motion_contract import canonical
from test_servo_start_authorization import fixture


def test_native_plan_structure_and_limits(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'plan.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_start_plan_structure.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    plan,_=fixture();doc=plan.to_dict();doc['origin']='DEVICE_CAPTURE'
    doc['command'].update(boot_id='11'*16,conversion_version='test-reference')
    cases=[(canonical(doc),True)]
    mutations=[('origin','SIMULATION'),('extra',1),('command.joint',4),('command.servo_id',15),
        ('command.boot_id','22'*16),('command.command_id','bad/id'),('command.angle_units','deg'),
        ('command.position_units','mm'),('command.conversion_version','unknown'),
        ('command.wire_count',900),('command.wire_count',True),('command.desired_rad',-1),
        ('command.wire_rad',4),('command.payload.rad',1.8),('command.payload.spd',0),
        ('command.payload.acc',256),('schedule.sample_count',11),('schedule.maximum_lateness_us',1),
        ('policy.maximum_pair_us',10),('baseline_policy.maximum_delta_counts',65),
        ('baseline_policy.maximum_age_us',0),('baseline_policy.settled_tolerance_counts',17),
        ('command.payload_sha256','X'*64),('sent_base64','x')]
    for path,value in mutations:
        changed=copy.deepcopy(doc);target=changed;keys=path.split('.')
        for key in keys[:-1]:target=target[key]
        target[keys[-1]]=value;cases.append((canonical(changed),False))
    raw=canonical(doc)
    cases += [(raw+b'{}',False),(b' '+raw,False),
        (raw.replace(b'"joint":3',b'"joint":3,"joint":3',1),False),
        (raw.replace(b'"joint":3',b'"joint":03',1),False),
        (raw.replace(b'"joint":3',b'"joint":null',1),False),
        (raw.replace(b'"joint":3',b'"joint":[3]',1),False),
        (raw.replace(b'"joint":3',b'"jo\\u0069nt":3',1),False),
        (b'{"a":'*8+b'0'+b'}'*8,False), (b'x'*16385,False)]
    for index,(data,expected) in enumerate(cases):
        path=tmp_path/f'{index}.json';path.write_bytes(data)
        run=subprocess.run([str(exe),str(path),'yes' if expected else 'no'],capture_output=True,timeout=10)
        assert run.returncode==0,(index,run.stderr)
