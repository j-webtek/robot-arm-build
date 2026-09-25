import copy
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_session_plan import freeze_session_plan
from rocell.application.servo_start_authorization import issue_challenge,sign_start,StartAuthorizationGate
from rocell.application.startup_command_contract import freeze_startup_plan,sign_startup,StartupAuthorizationGate

KEY=b'k'*32
BOOT='0123456789abcdef0123456789abcdef'


def fixture():
    trace=simulate_trace('paired_arrival');trace['command'].update(boot_id=BOOT,servo_id=14)
    whole=dict(joints=[[1024,3071]]*7,tracking_tolerance=2,maximum_pair_us=1000,
               maximum_scan_us=100000,maximum_age_us=100000)
    normal=freeze_session_plan(trace['command'],trace['policy'],canonical(trace['command']['payload']),
        dict(sample_count=3,sample_interval_us=1000000,maximum_lateness_us=1000000,maximum_pair_us=1000),
        origin='SIMULATION',baseline_policy=dict(maximum_delta_counts=8,settled_tolerance_counts=2,
            maximum_pair_us=1000,maximum_age_us=100000),whole_arm_policy=whole)
    policy=dict(mode='ZERO_GOAL_TWO_SCAN',policy_id='test-only',joints=whole['joints'],
        drift_tolerance=2,minimum_separation_us=100000,maximum_wait_us=1000000,
        maximum_pair_us=1000,maximum_scan_us=100000,maximum_age_us=100000,reviewed_mode=0)
    return normal,policy,issue_challenge(BOOT,1000,lease_us=1000000)


def test_explicit_mode_and_one_use():
    normal,policy,challenge=fixture();plan=freeze_startup_plan(normal,policy)
    token=sign_startup(plan,challenge,KEY,policy)
    gate=StartupAuthorizationGate(challenge,KEY,policy,expected_origin='SIMULATION')
    result=gate.consume(token,now_us=1001)
    assert result['authenticated_request'] and not result['progression_authority']
    with pytest.raises(ValueError,match='consumed'):gate.consume(token,now_us=1002)


def test_no_cross_mode_interpretation():
    normal,policy,challenge=fixture();plan=freeze_startup_plan(normal,policy)
    with pytest.raises(ValueError):
        StartAuthorizationGate(challenge,KEY,expected_origin='SIMULATION').consume(
            sign_startup(plan,challenge,KEY,policy),now_us=1001)
    with pytest.raises(ValueError):
        StartupAuthorizationGate(challenge,KEY,policy,expected_origin='SIMULATION').consume(
            sign_start(normal,challenge,KEY),now_us=1001)


@pytest.mark.parametrize('fault',['policy','tamper','expiry','origin','key','boot'])
def test_failures_consume_without_retry(fault):
    normal,policy,challenge=fixture();plan=freeze_startup_plan(normal,policy)
    token=sign_startup(plan,challenge,KEY,policy);local=copy.deepcopy(policy);time=1001
    key=KEY;origin='SIMULATION';expected=copy.deepcopy(challenge)
    if fault=='policy':local['drift_tolerance']=3
    if fault=='tamper':token=token[:-1]+bytes([token[-1]^1])
    if fault=='expiry':time=challenge['expires_us']
    if fault=='origin':origin='DEVICE_CAPTURE'
    if fault=='key':key=b'x'*32
    if fault=='boot':expected['boot_id']='f'*32
    gate=StartupAuthorizationGate(expected,key,local,expected_origin=origin)
    with pytest.raises(ValueError):gate.consume(token,now_us=time)
    with pytest.raises(ValueError,match='consumed'):gate.consume(token,now_us=1001)


def test_native_parser_agrees_on_python_startup_contract(tmp_path):
    import json
    from pathlib import Path
    import shutil
    import subprocess
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'startup-parser.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_startup_plan_structure.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    normal,policy,_=fixture()
    from rocell.application.servo_session_plan import SessionPlan
    doc=normal.to_dict();doc['origin']='DEVICE_CAPTURE'
    normal=SessionPlan(canonical(doc));plan=freeze_startup_plan(normal,policy)
    conversion=normal.to_dict()['command']['conversion_version']
    cases=[(plan.encoded,True),(normal.encoded,False),(b'{}',False),(b' '+plan.encoded,False)]
    for key,value in [('mode','NORMAL'),('drift_tolerance',3),('reviewed_mode',1),
                      ('minimum_separation_us',True),('maximum_wait_us',0),('policy_id','wrong')]:
        doc=json.loads(plan.encoded);doc['startup_policy'][key]=value
        cases.append((canonical(doc),False))
    doc=json.loads(plan.encoded);doc['session_plan_base64']='!!!!';cases.append((canonical(doc),False))
    for index,(raw,accepted) in enumerate(cases):
        path=tmp_path/'request.json';path.write_bytes(raw)
        run=subprocess.run([str(exe),str(path),'yes' if accepted else 'no',conversion],
                           capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(index,run.stderr)
