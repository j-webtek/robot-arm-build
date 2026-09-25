"""Wizard -> real host exports/HMAC -> persistent native synthetic servo runtime.

Only trusted admission, capability observation and device transport are synthetic.
Both legs share one native process, bus, hold handoff and evidence owner.
"""
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

import pytest

from test_arrival_wizard_service import make_service, _run
from test_held_pair_command_contract import inputs
from held_pair_test_support import prepare_native_pair_source
from test_servo_diagnostic_start_http import once_server
from test_servo_diagnostic_http import response
from test_movement_campaign_ui import render
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_command_contract import freeze_hold_plan, sign_hold
from rocell.application import held_pair_trial as trial
from rocell.application import wizard_held_pair as wizard
from rocell.application.held_pair_capabilities import validate_pair_capabilities
from rocell.application.held_pair_transport import HeldPairHTTPReader, STATUS, RECORD
from rocell.application.held_pair_observed_return import replay_observed_pair_return


@pytest.mark.parametrize('lose_forward_telemetry',[False,True])
def test_wizard_to_persistent_native_pair(tmp_path,monkeypatch,make_service,lose_forward_telemetry):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:pytest.skip('Windows native crypto/compiler required')
    root,policy,challenge=inputs();exe=tmp_path/'interactive-pair.exe'
    build=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_pair_authenticated_runtime.cpp'),
        '-lbcrypt','-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    hold=freeze_hold_plan(policy,boot_id=challenge['boot_id'],command_id='verified-hold')
    hold_path=tmp_path/'hold.bin'
    hold_path.write_bytes(sign_hold(hold,dict(challenge,nonce='44'*32),b'k'*32,approved_policy=policy))
    process=subprocess.Popen([str(exe),'-','-','1','1',str(hold_path),'interactive'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    lines=queue.Queue()
    def read_lines():
        for line in process.stdout:lines.put(line)
        lines.put(None)
    reader=threading.Thread(target=read_lines,daemon=True);reader.start()
    def next_meta():
        line=lines.get(timeout=20)
        assert line is not None,'Native runtime ended without expected evidence'
        return json.loads(line)
    try:
        hold_meta=next_meta()
        service,runner,_=make_service(mode='physical')
        exports=service.export_directory
        preparation=prepare_native_pair_source(exports,hold,policy,challenge,hold_meta,
            monkeypatch,prepare_only=True)
        def admission(subject):
            return dict(schema='rocell.held_pair_admission.v1',subject=subject,
                approval_reference='SYNTHETIC-NATIVE-TEST-NOT-LIVE',
                expires_ns=time.monotonic_ns()+120_000_000_000,
                installed_image_verified=True,pair_configuration_verified=True,
                powered_trial_approved=True,supported_and_clear=True,exclusive_controller=True)
        service._held_pair_binding=wizard.HeldPairWizardBinding(
            Path(preparation['export_path']).name,preparation['preparation_sha256'],
            '127.0.0.1',admission,lambda:b'k'*32)
        capabilities=dict(schema='rocell.held_pair_capabilities.v1',boot_id=challenge['boot_id'],
            protocol='hold-first-pair-v1',servo_id=14,max_offset_counts=16,
            free_internal_heap_bytes=200000,minimum_free_internal_heap_bytes=180000,
            largest_internal_block_bytes=150000,stack_measured=False,physical_accuracy_verified=False)
        monkeypatch.setattr(trial,'read_pair_capabilities',lambda **kwargs:
            validate_pair_capabilities(canonical(capabilities),expected_boot=kwargs['expected_boot']))
        real_challenge=trial.request_pair_challenge
        operations=[];wire_tokens=[];current={}
        def request(root,**kwargs):
            operations.append(kwargs['operation'])
            value=challenge if kwargs['operation']=='prepare' else dict(challenge,
                nonce='33'*32,issued_us=2000,expires_us=10002000)
            with once_server(response(canonical(value))) as (port,requests):
                result=real_challenge(root,**dict(kwargs,port=port))
            assert len(requests)==1
            return result
        monkeypatch.setattr(trial,'request_pair_challenge',request)
        real_send=trial.send_authorized_pair
        def send(root,authorization,**kwargs):
            reply=response(canonical(dict(accepted=True,retry_allowed=False)),status=b'202 Accepted')
            with once_server(reply) as (port,requests):
                result=real_send(root,authorization,**dict(kwargs,port=port))
            assert len(requests)==1
            token=requests[0][2];wire_tokens.append(token)
            # Feed exactly the wire body, not a separately generated token.
            token_path=tmp_path/(kwargs['leg']+'.bin');token_path.write_bytes(token)
            process.stdin.write(str(token_path)+'\n');process.stdin.flush()
            current.clear();current.update(next_meta())
            return result
        monkeypatch.setattr(trial,'send_authorized_pair',send)
        def get(self,path,**kwargs):
            if path==STATUS:return current['transport_status_json'].encode()
            if lose_forward_telemetry and len(wire_tokens)==1:
                raise OSError('Synthetic forward telemetry loss')
            return current['transport_records'][int(path.removeprefix(RECORD))].encode()
        monkeypatch.setattr(HeldPairHTTPReader,'_get',get)
        operation=_run(service,'run_held_pair',{'acknowledge':True},timeout_s=120)
        if lose_forward_telemetry:
            assert operation['status']=='FAILED',operation
            assert operations==['prepare'] and len(wire_tokens)==1
            report=operation['result']['steps'][0]['report']
            assert report['phase']=='STOPPED' and report['reason']=='FORWARD_ENDPOINT_NOT_ELIGIBLE'
            assert process.poll() is None  # Still awaiting return; host did not send it.
            assert not runner.calls
            return
        assert operation['status']=='SUCCEEDED',operation
        assert operations==['prepare','return'] and len(wire_tokens)==2
        assert process.wait(timeout=10)==0,process.stderr.read()
        report=operation['result']['steps'][0]['report']
        assert report['phase']=='CONTROLLER_REPORTED_PAIR_ARRIVAL'
        final_id=report['steps'][-1]['export_id']
        review=replay_observed_pair_return(exports,final_id)['review']
        assert review['forward']['position_change_counts']==6
        assert review['reverse']['position_change_counts']==-6
        assert review['reverse']['final_position']==2723
        assert review['endpoint_continuity_verified']
        assert not review['physical_tip_accuracy_verified']
        assert 'NOT QUALIFIED' in render(operation)
        assert not runner.calls
    finally:
        if process.poll() is None:process.kill()
        process.wait(timeout=10)
        for stream in (process.stdin,process.stdout,process.stderr):stream.close()
        reader.join(timeout=2)
