from pathlib import Path
import shutil
import subprocess
import pytest
import json
import copy
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_transport_snapshot import collect_snapshot
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_session_plan import freeze_session_plan, assess_planned_session
from rocell.application.servo_planned_run import collect_planned_run, replay_planned_run
from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render


def test_actual_native_owner_with_inert_io(tmp_path,make_service):
    root=Path(__file__).resolve().parents[2];firmware=root/'firmware/diagnostics'
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    executable=tmp_path/'native-owner-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(firmware/'test_stubs'),'-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(firmware/'test_native_diagnostic_owner.cpp'),'-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    for scenario in range(7):
        run=subprocess.run([str(executable),str(scenario)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(scenario,run.stderr)
        if scenario in (5,6):
            check_partial_capture(list(map(json.loads,run.stdout.splitlines())),make_service)
        if scenario in (2,3):
            records=list(map(json.loads,run.stdout.splitlines()))
            assert records[1]['schema']=='rocell.elbow_baseline.v1' and records[1]['accepted']
            def get(path,**kwargs):
                if path.endswith('/status'):
                    return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='a'*32,
                        state='FAULT',reason='INTERFERING_COMMAND',records=len(records),storage_fault=False,
                        start_supported=False,durable_export_verified=False))
                index=int(path.split('index=')[1]);kinds=('receipt','baseline','converted','hook','dispatch','write')
                return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id='a'*32,index=index,
                    kind=kinds[index] if index<6 else 'pair',record=records[index]))
            snapshot=collect_snapshot(get)
            assert snapshot['records'][1]['record']==records[1]
            assert not snapshot['progression_authority']
            expected=simulate_trace('paired_arrival')
            expected['command'].update(boot_id=records[0]['boot_id'],command_id='command',
                servo_id=14,desired_count=2132,wire_count=2132)
            expected['policy']['maximum_pair_us']=100
            sent=b'{"T":101,"joint":3,"rad":1.7,"spd":20,"acc":1}'
            schedule=dict(sample_count=2,sample_interval_us=1000000,
                maximum_lateness_us=1000000,maximum_pair_us=100)
            baseline=dict(maximum_delta_counts=16,settled_tolerance_counts=2,
                maximum_pair_us=100,maximum_age_us=100)
            plan=freeze_session_plan(expected['command'],expected['policy'],sent,schedule,
                origin='SIMULATION',baseline_policy=baseline)
            assessed=assess_planned_session(snapshot,plan)
            assert assessed['category']=='SESSION_FAULT'
            assert assessed['baseline']['recomputed_accepted']
            assert assessed['baseline']['position_count']==2132
            assert not assessed['baseline']['physical_clearance_verified']
            for key,value in [('accepted',False),('maximum_delta_counts',17),
                              ('reason','UNVERIFIED')]:
                corrupt=copy.deepcopy(snapshot)
                corrupt['records'][1]['record'][key]=value
                with pytest.raises(ValueError):assess_planned_session(corrupt,plan)
            # Frozen policy is independently checked, not replaced by captured limits.
            stricter=dict(baseline,maximum_age_us=1)
            stale_plan=freeze_session_plan(expected['command'],expected['policy'],sent,schedule,
                origin='SIMULATION',baseline_policy=stricter)
            corrupt=copy.deepcopy(snapshot)
            corrupt['records'][1]['record']['maximum_age_us']=1
            with pytest.raises(ValueError,match='stale'):assess_planned_session(corrupt,stale_plan)
            # A forged accepted flag cannot hide motion, tracking error, or a
            # too-large requested displacement in the underlying register bytes.
            for position,moving in [(2132,1),(2100,0)]:
                corrupt=copy.deepcopy(snapshot)
                pair=corrupt['records'][1]['record']['acquisition']
                raw=bytearray.fromhex(pair['feedback']['raw_hex'])
                raw[:2]=position.to_bytes(2,'little');raw[10]=moving
                pair['feedback']['raw_hex']=raw.hex()
                if position==2100:pair['target']['raw_hex']=position.to_bytes(2,'little').hex()
                with pytest.raises(ValueError,match='does not support'):assess_planned_session(corrupt,plan)
            result=collect_planned_run(tmp_path/str(scenario),get,expected['command'],
                expected['policy'],sent,schedule,origin='SIMULATION',baseline_policy=baseline)
            assert result['outcome']['assessment']['baseline']['recomputed_accepted']
            assert replay_planned_run(tmp_path/str(scenario),Path(result['export_path']).name)['matches']
            service,runner,_=make_service(mode='physical')
            wizard_run=collect_planned_run(service.export_directory,get,expected['command'],
                expected['policy'],sent,schedule,origin='SIMULATION',baseline_policy=baseline)
            operation=_run(service,'review_planned_servo_run',{'export_id':Path(wizard_run['export_path']).name})
            assert operation['status']=='SUCCEEDED'
            page=render(operation)
            assert 'Independently checked' in page and 'SESSION_FAULT' in page
            assert 'NOT QUALIFIED' in page and not runner.calls
            check_authorized_capture(records,plan,expected,sent,schedule,baseline,make_service)


def test_generated_ingress_and_background_guards():
    root=Path(__file__).resolve().parents[2]/'.firmware-tools/baseline-candidate/RoArm-M3_example'
    loop=(root/'RoArm-M3_example.ino').read_text().split('void loop() {',1)[1]
    assert loop.index('pollReceivedDiagnostic(); return;')<loop.index('constantHandle();')
    assert loop.index('pollReceivedDiagnostic(); return;')<loop.index('RoArmM3_getPosByServoFeedback();')
    uart=(root/'uart_ctrl.h').read_text()
    assert 'rocellRejectDiagnosticInterference() && cmdType!=CMD_EMERGENCY_STOP' in uart
    esp=(root/'espnow_owner.h').read_text()
    assert esp.index('rocellRejectDiagnosticInterference()')<esp.index('RoArmM3_allJointAbsCtrl(')


def check_partial_capture(records,make_service):
    """Native failed admission -> retained export -> replay -> actual wizard UI."""
    expected=simulate_trace('paired_arrival')
    expected['command'].update(boot_id=records[0]['boot_id'],command_id='command',
        servo_id=14,desired_count=2132,wire_count=2132)
    expected['policy']['maximum_pair_us']=100
    sent=b'{"T":101,"joint":3,"rad":1.7,"spd":20,"acc":1}'
    schedule=dict(sample_count=2,sample_interval_us=1000000,maximum_lateness_us=1000000,maximum_pair_us=100)
    baseline=dict(maximum_delta_counts=16,settled_tolerance_counts=2,maximum_pair_us=100,maximum_age_us=100)
    def get(path,**kwargs):
        if path.endswith('/status'):
            return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='a'*32,
                state='FAULT',reason='ADMISSION_REJECTED',records=2,storage_fault=False,
                start_supported=False,durable_export_verified=False))
        index=int(path.split('index=')[1])
        return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id='a'*32,index=index,
            kind=('receipt','baseline')[index],record=records[index]))
    service,runner,_=make_service(mode='physical')
    result=collect_planned_run(service.export_directory,get,expected['command'],expected['policy'],
        sent,schedule,origin='SIMULATION',baseline_policy=baseline)
    assert result['outcome']['status']=='PARTIAL_FAILURE_ASSESSED'
    assessment=result['outcome']['assessment']
    assert assessment['supported_reason']==records[1]['reason']
    assert not assessment['no_motion_proven'] and not assessment['progression_authority']
    assert replay_planned_run(service.export_directory,Path(result['export_path']).name)['matches']
    operation=_run(service,'review_planned_servo_run',{'export_id':Path(result['export_path']).name})
    assert operation['status']=='SUCCEEDED'
    page=render(operation)
    assert records[1]['reason'] in page and 'does not prove no physical motion' in page
    assert not runner.calls
    from rocell.application.servo_planned_run import _outcome
    plan=freeze_session_plan(expected['command'],expected['policy'],sent,schedule,
        origin='SIMULATION',baseline_policy=baseline)
    snapshot=collect_snapshot(get)
    assert _outcome(snapshot,plan,allow_partial=False)==dict(status='EVIDENCE_REJECTED',assessment=None)
    authorization=dict(schema='rocell.start_authorization.v1',boot_id=records[0]['boot_id'],
        command_id=records[0]['command_id'],session_plan_sha256=plan.sha256,
        received_us=1000,expires_us=11000,authentication_verified=True,
        phase='BEFORE_ADMISSION',dispatch_attempted=False)
    prefixed=copy.deepcopy(snapshot)
    prefixed['records'].insert(0,dict(kind='authorization',record=authorization))
    assessed=_outcome(prefixed,plan)
    assert assessed['status']=='PARTIAL_FAILURE_ASSESSED'
    assert assessed['assessment']['start_record']['plan_identity_matched']
    for key,value in [('accepted',True),('reason','BASELINE_ACCEPTED'),('maximum_age_us',99)]:
        corrupt=copy.deepcopy(snapshot);corrupt['records'][1]['record'][key]=value
        assert _outcome(corrupt,plan)['status']=='EVIDENCE_REJECTED'


def check_authorized_capture(records,plan,expected,sent,schedule,baseline,make_service):
    # Add a simulated authorization prefix to real inert native session output.
    # This tests correlation, never authenticates the HTTP response itself.
    authorization=dict(schema='rocell.start_authorization.v1',boot_id=records[0]['boot_id'],
        command_id=records[0]['command_id'],session_plan_sha256=plan.sha256,
        received_us=1000,expires_us=11000,authentication_verified=True,
        phase='BEFORE_ADMISSION',dispatch_attempted=False)
    combined=[authorization,*records]
    def get(path,**kwargs):
        if path.endswith('/status'):
            return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id=authorization['boot_id'],
                state='FAULT',reason='INTERFERING_COMMAND',records=len(combined),storage_fault=False,
                start_supported=False,durable_export_verified=False))
        index=int(path.split('index=')[1]);kinds=('authorization','receipt','baseline','converted','hook','dispatch','write')
        if len(combined)>1 and combined[1].get('schema')=='rocell.whole_arm_baseline.v1':
            kinds=('authorization','whole_arm','receipt','baseline','converted','hook','dispatch','write')
        return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id=authorization['boot_id'],index=index,
            kind=kinds[index] if index<len(kinds) else 'pair',record=combined[index]))
    snapshot=collect_snapshot(get)
    result=assess_planned_session(snapshot,plan)
    assert result['category']=='SESSION_FAULT'
    assert result['start_record']['plan_identity_matched']
    assert not result['start_record']['authenticated_provenance_verified']
    for field,value in [('session_plan_sha256','0'*64),('command_id','different'),
                        ('authentication_verified',False),('dispatch_attempted',True),
                        ('phase','AFTER_DISPATCH'),('expires_us',1002),('received_us',True)]:
        corrupt=copy.deepcopy(snapshot);corrupt['records'][0]['record'][field]=value
        with pytest.raises(ValueError):assess_planned_session(corrupt,plan)
    service,runner,_=make_service(mode='physical')
    run=collect_planned_run(service.export_directory,get,expected['command'],expected['policy'],sent,schedule,
        origin='SIMULATION',baseline_policy=baseline)
    assert run['outcome']['assessment']['start_record']['plan_identity_matched']
    assert replay_planned_run(service.export_directory,Path(run['export_path']).name)['matches']
    operation=_run(service,'review_planned_servo_run',{'export_id':Path(run['export_path']).name})
    page=render(operation)
    assert 'controller-reported authorization' in page and 'SESSION_FAULT' in page
    assert 'Not verified' in page and not runner.calls
    from rocell.application.servo_register_reference import PROFILE_ID
    whole_policy=dict(joints=[[2122,2142] for _ in range(7)],tracking_tolerance=2,
        maximum_pair_us=100,maximum_scan_us=1000,maximum_age_us=1000)
    whole_plan=freeze_session_plan(expected['command'],expected['policy'],sent,schedule,
        origin='SIMULATION',baseline_policy=baseline,whole_arm_policy=whole_policy)
    raw=(2132).to_bytes(2,'little').hex()
    whole=dict(schema='rocell.whole_arm_baseline.v1',boot_id=authorization['boot_id'],
        command_id=authorization['command_id'],profile_id=PROFILE_ID,byte_order='little',
        accepted=True,reason='WHOLE_ARM_BASELINE_ACCEPTED',checked_us=929,policy=copy.deepcopy(whole_policy),reads=[])
    for i in range(7):
        start=900+i*4
        whole['reads'].append([[i*2,start,start+1,2,0,True,raw],
                              [i*2+1,start+2,start+3,15,0,True,raw+'00'*13]])
    authorization.update(received_us=800,session_plan_sha256=whole_plan.sha256)
    combined.insert(1,whole)
    snapshot=collect_snapshot(get)
    assessed=assess_planned_session(snapshot,whole_plan)
    assert assessed['whole_arm_baseline']['recomputed_accepted']
    assert assessed['category']=='SESSION_FAULT'
    for key,value in [('accepted',False),('checked_us',1100)]:
        corrupt=copy.deepcopy(snapshot);corrupt['records'][1]['record'][key]=value
        with pytest.raises(ValueError):assess_planned_session(corrupt,whole_plan)
    corrupt=copy.deepcopy(snapshot);corrupt['records'].pop(1)
    with pytest.raises(ValueError):assess_planned_session(corrupt,whole_plan)
    whole_policy['tracking_tolerance']=3
    assert whole_plan.to_dict()['whole_arm_policy']['tracking_tolerance']==2
    whole_policy['tracking_tolerance']=2
    run=collect_planned_run(service.export_directory,get,expected['command'],expected['policy'],sent,schedule,
        origin='SIMULATION',baseline_policy=baseline,whole_arm_policy=whole_policy)
    assert replay_planned_run(service.export_directory,Path(run['export_path']).name)['matches']
    operation=_run(service,'review_planned_servo_run',{'export_id':Path(run['export_path']).name})
    page=render(operation)
    assert 'Seven servo reads independently checked' in page and 'SESSION_FAULT' in page
    authorization['boot_id']='f'*32
    with pytest.raises(ValueError,match='identity mismatch'):collect_snapshot(get)
