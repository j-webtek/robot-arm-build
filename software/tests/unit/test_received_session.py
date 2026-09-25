import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_transport_export import capture_transport_export
from rocell.application.servo_controller_receipt import assess_controller_receipt
from rocell.application.servo_session_assessment import assess_session
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_session_plan import freeze_session_plan,assess_planned_session
from rocell.application.servo_planned_run import collect_planned_run,replay_planned_run
from test_arrival_wizard_service import make_service,_run
from test_movement_campaign_ui import render


def test_receipt_conversion_and_write_are_one_sequence(tmp_path,make_service):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    source=root/'firmware/diagnostics/test_received_session.cpp'
    executable=tmp_path/'received-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),str(source),'-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    receipt,converted,hook,dispatch,write,*pairs=map(json.loads,run.stdout.splitlines())
    assert receipt['command_id']==converted['command_id']==dispatch['command_id']==write['command_id']
    assert receipt['received_us']<dispatch['device_us']
    sent=b'{"T":101,"joint":3,"rad":1.7,"spd":20,"acc":1}'
    assert assess_controller_receipt(receipt,sent,dispatch)['exact_payload_match']
    assert converted['wire_count']==dispatch['wire_count']==2100
    assert len(pairs)==3 and hook['status']=='WRITE_VERIFIED'
    records=[receipt,converted,hook,dispatch,write,*pairs]
    def get(path,**kwargs):
        if path.endswith('/status'):
            return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='b'*32,
                state='CAPTURED',reason='NONE',records=len(records),storage_fault=False,
                start_supported=False,durable_export_verified=False))
        index=int(path.split('index=')[1])
        kinds=('receipt','converted','hook','dispatch','write')
        return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id='b'*32,
            index=index,kind=kinds[index] if index<5 else 'pair',record=records[index]))
    result=capture_transport_export(tmp_path/'exports',get)
    assert result['export_verified'] and result['replay_verified']
    expected=simulate_trace('paired_arrival')
    expected['command'].update(boot_id='boot',command_id='command',servo_id=14)
    expected['policy']['maximum_pair_us']=100
    assessed=assess_session(result['summary'],sent,expected['command'],expected['policy'],origin='SIMULATION')
    assert assessed['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
    assert assessed['receipt']['exact_payload_match'] and assessed['write']['acknowledgment_verified']
    assert not assessed['progression_authority']
    plan=freeze_session_plan(expected['command'],expected['policy'],sent,
        dict(sample_count=3,sample_interval_us=1000000,maximum_lateness_us=1000000,maximum_pair_us=100),
        origin='SIMULATION')
    assert assess_planned_session(result['summary'],plan)['session_plan_sha256']==plan.sha256
    service,runner,_=make_service(mode='physical')
    planned_root=service.export_directory
    observed=[]
    import copy
    mutable_command=copy.deepcopy(expected['command'])
    mutable_policy=copy.deepcopy(expected['policy'])
    mutable_schedule=plan.to_dict()['schedule']
    def planned_reader(path,**kwargs):
        plans=list(planned_root.glob('*/attachment-session-plan.json'))
        assert len(plans)==1 # Verified plan must exist before even the status GET.
        mutable_command['desired_count']=999
        mutable_policy['tolerance_counts']=90
        mutable_schedule['sample_count']=1
        observed.append(path)
        return get(path,**kwargs)
    run_result=collect_planned_run(planned_root,planned_reader,mutable_command,mutable_policy,sent,
        mutable_schedule,origin='SIMULATION')
    assert observed and run_result['outcome']['assessment']['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
    assert replay_planned_run(planned_root,Path(run_result['export_path']).name)['matches']
    operation=_run(service,'review_planned_servo_run',{'export_id':Path(run_result['export_path']).name})
    assert operation['status']=='SUCCEEDED',operation
    page=render(operation)
    assert 'exact controller receipt' in page and 'bus acknowledgment' in page
    assert 'DIAGNOSTIC_ENDPOINT_CRITERIA_MET' in page and 'NOT QUALIFIED' in page
    assert not runner.calls
    faulted=copy.deepcopy(result['summary']);faulted['status']['state']='FAULT'
    assert assess_session(faulted,sent,expected['command'],expected['policy'],origin='SIMULATION')['category']=='SESSION_FAULT'
    for index,key,value in [(1,'wire_count',2101),(1,'sample_count',4),
                            (2,'status','INVALID_CLOCK'),(2,'finished_us_raw','1'),
                            (4,'ack_policy','DISABLED')]:
        corrupt=copy.deepcopy(result['summary']);corrupt['records'][index]['record'][key]=value
        with pytest.raises(ValueError):assess_session(corrupt,sent,expected['command'],expected['policy'],origin='SIMULATION')
