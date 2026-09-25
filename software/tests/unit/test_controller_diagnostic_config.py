import copy
from pathlib import Path
import shutil
import subprocess

import pytest
from rocell.application.first_motion_contract import canonical


def test_native_controller_config_and_key_loading(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'config.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_controller_diagnostic_config.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    doc=dict(schema='rocell.controller_diagnostics.v1',policy_id='inert-only',
        conversion_version='test-reference',start_port=8081,challenge_lifetime_us=30000000,
        elbow_bounds=dict(minimum_rad=1.6,maximum_rad=1.9,maximum_speed=40,maximum_acceleration=1),
        whole_arm_policy=dict(joints=[[1900,2200] for _ in range(7)],tracking_tolerance=2,
            maximum_pair_us=100,maximum_scan_us=1000,maximum_age_us=1000))
    cases=[(canonical(doc),True)]
    for path,value in [('schema','wrong'),('policy_id','bad/id'),('conversion_version','wrong'),
                       ('start_port',80),('start_port',65536),('start_port',True),
                       ('challenge_lifetime_us',0),('challenge_lifetime_us',30000001),
                       ('elbow_bounds.minimum_rad',2),('elbow_bounds.maximum_rad',4),
                       ('elbow_bounds.maximum_speed',0),('elbow_bounds.maximum_acceleration',256),
                       ('whole_arm_policy.joints',[[2200,1900]]*7),
                       ('whole_arm_policy.joints',[[1900,2200]]*6),
                       ('whole_arm_policy.tracking_tolerance',17),('whole_arm_policy.maximum_age_us',0),
                       ('authorization_key','must-not-be-in-policy')]:
        changed=copy.deepcopy(doc);target=changed;keys=path.split('.')
        for key in keys[:-1]:target=target[key]
        target[keys[-1]]=value;cases.append((canonical(changed),False))
    raw=canonical(doc)
    cases.extend([(raw+b'{}',False),(b' '+raw,False),(b'x'*4097,False),
                  (raw.replace(b'"start_port":8081',b'"start_port":8081,"start_port":8081'),False)])
    for i,(data,accepted) in enumerate(cases):
        path=tmp_path/'policy.json';path.write_bytes(data)
        run=subprocess.run([str(exe),str(path),'yes' if accepted else 'no'],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(i,run.stderr)
