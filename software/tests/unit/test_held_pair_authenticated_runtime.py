"""Complete native hold/start/forward/return with synthetic bus and real HMAC."""
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import pytest
from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render
from test_held_pair_command_contract import inputs
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_command_contract import freeze_held_pair_plan, sign_held_pair
from rocell.application.held_evidence_digest import held_evidence_digest
from rocell.application.servo_start_authorization import DOMAIN, _challenge_bytes
from rocell.application.held_pair_transport import collect_held_pair_snapshot, STATUS, RECORD
from rocell.application.hold_command_contract import freeze_hold_plan, sign_hold


@pytest.mark.parametrize('socket_mode',[False,True,'powered','observed-pose'])
def test_authenticated_pair_runtime(tmp_path,socket_mode,monkeypatch,make_service):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root,policy,challenge=inputs();exe=tmp_path/'runtime.exe'
    observed_pose = socket_mode == 'observed-pose'
    anchor, offset = (2899, 10) if observed_pose else (2723, 6)
    forward_id, return_id, hold_id = 'forward', 'return', 'verified-hold'
    if observed_pose:
        from test_observed_pose_candidate import inputs as observed_inputs
        from rocell.application.observed_pose_candidate import draft_settings
        hold_settings, pair_settings = draft_settings(*observed_inputs())
        policy = hold_settings['hold_policy']; hold_id = hold_settings['command_id']
        forward_id = pair_settings['forward_command_id']; return_id = pair_settings['return_command_id']
    built=subprocess.run([compiler,'-std=c++17',
        *(['-DOBSERVED_POSE_PLUS10'] if observed_pose else []),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_pair_authenticated_runtime.cpp'),
        '-lbcrypt','-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stderr
    hold_plan=freeze_hold_plan(policy,boot_id=challenge['boot_id'],command_id=hold_id)
    hold_hash=hashlib.sha256(hold_plan.encoded).hexdigest()
    hold_path=tmp_path/'hold.bin'
    hold_path.write_bytes(sign_hold(hold_plan,dict(challenge,nonce='44'*32),b'k'*32,approved_policy=policy))
    plan=freeze_held_pair_plan(policy,boot_id=challenge['boot_id'],hold_plan_sha256=hold_hash,
                              forward_command_id=forward_id,return_command_id=return_id,offset_counts=offset)
    token=sign_held_pair(plan,challenge,b'k'*32,approved_policy=policy,expected_hold_plan_sha256=hold_hash)
    start=tmp_path/'start.bin';start.write_bytes(token)
    stopped=subprocess.run([str(exe),str(start),'-','1','0',str(hold_path),'nonarrival'],
        capture_output=True,timeout=20)
    assert stopped.returncode==0,stopped.stderr
    assert stopped.stdout.strip()==b'NONARRIVAL_REASON_PRESERVED'
    extra=['socket-powered' if socket_mode=='powered' else 'socket'] if socket_mode else []
    dump=subprocess.run([str(exe),str(start),'-','1','0',str(hold_path),*extra],capture_output=True,timeout=20)
    assert dump.returncode==0,dump.stderr
    lines=dump.stdout.splitlines();meta=json.loads(lines[0])
    assert meta['session_sha256']==hashlib.sha256(plan.encoded).hexdigest()
    assert meta['forward_plan_sha256']==hashlib.sha256(meta['forward_plan_json'].encode()).hexdigest()
    leg=json.loads(meta['forward_plan_json']);assert leg['target_count']==anchor+offset
    assert leg['policy_sha256']==hashlib.sha256(canonical(policy)).hexdigest()
    rows=[(kind.decode(),raw) for kind,raw in (line.split(b'\t',1) for line in lines[1:])]
    for fault in (None,'active','changed','wrong_plan','wrong_index','missing','bad_raw'):
        calls=[]
        def get(path,**limits):
            calls.append(path)
            if path==STATUS:
                value=json.loads(meta['transport_status_json'])
                if fault=='active':value['state']='FORWARD'
                if fault=='changed' and len(calls)>1:value['state']='STOPPED'
            else:
                index=int(path.removeprefix(RECORD))
                if fault=='missing' and index==2:raise OSError('synthetic disconnection')
                value=json.loads(meta['transport_records'][index])
                if fault=='wrong_index':value['index']=99
                if fault=='wrong_plan':value['plan_sha256']='0'*64
                if fault=='bad_raw':value['raw_json']='{}'
            raw=canonical(value);assert len(raw)<=limits['maximum_bytes'];return raw
        captured=collect_held_pair_snapshot(get,expected_boot='11'*16,
            expected_session=meta['session_sha256'],expected_plan=meta['forward_plan_sha256'],leg='forward')
        assert len(calls)<=9
        if fault is None:
            assert captured['category']=='TRANSPORT_CAPTURED' and captured['records']==rows
            assert captured['evidence_sha256']==held_evidence_digest(rows)
            assert captured['stable_status_observed'] and not captured['progression_authority']
        else:
            assert captured['category']=='INCONCLUSIVE' and not captured['stable_status_observed']
            assert captured['responses']
    # Native bytes exercise the complete saved hold -> pair -> forward -> return
    # chain. Only sender/HTTP hardware boundaries are synthetic, not replay.
    from rocell.application import held_pair_observed_forward as observed
    from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
    from held_pair_test_support import prepare_native_pair_source
    service,runner,_=make_service(mode='physical')
    export_root=service.export_directory
    initial_auth=prepare_native_pair_source(export_root,hold_plan,policy,challenge,meta,monkeypatch,
        forward_command_id=forward_id,return_command_id=return_id,offset_counts=offset)
    assert initial_auth.token==token
    context_id=initial_auth.context_export_id
    from rocell.application.held_pair_delivery import send_authorized_pair, replay_pair_delivery
    from test_servo_diagnostic_start_http import once_server
    from test_servo_diagnostic_http import response
    from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
    accepted_reply=response(canonical(dict(accepted=True,retry_allowed=False)),status=b'202 Accepted')
    with once_server(accepted_reply) as (port,requests):
        delivered=send_authorized_pair(export_root,initial_auth,leg='forward',address='127.0.0.1',port=port)
    assert len(requests)==1 and requests[0][2]==initial_auth.token
    assert replay_pair_delivery(export_root,Path(delivered['export_path']).name)['replay_verified']
    with pytest.raises(PhysicalOnboardingDurabilityError):
        send_authorized_pair(export_root,initial_auth,leg='forward',address='127.0.0.1',port=port)
    def native_get(self,path,**kwargs):
        if path==STATUS:return meta['transport_status_json'].encode()
        return meta['transport_records'][int(path.removeprefix(RECORD))].encode()
    with monkeypatch.context() as patch:
        patch.setattr(observed.HeldPairHTTPReader,'_get',native_get)
        saved=observed.collect_authorized_pair_forward(export_root,context_id,address='127.0.0.1')
        assessment=saved['assessment']
        assert assessment['category']=='CONTROLLER_REPORTED_ARRIVAL'
        assert assessment['start_position']==anchor and assessment['final_position']==anchor+offset
        assert assessment['historical_anchor_matches'] and assessment['stable_status_observed']
        assert not assessment['progression_authority'] and not assessment['provenance_verified']
        assert assessment['evidence_sha256']==held_evidence_digest(rows)
        patch.setattr(observed.HeldPairHTTPReader,'_get',lambda *a,**kw:pytest.fail('Replay contacted hardware'))
        export_id=Path(saved['export_path']).name
        assert observed.replay_observed_pair_forward(export_root,export_id)['assessment']==assessment
        bundle=json.loads((export_root/export_id/'attachment-observed-pair-forward.json').read_bytes())
        exporter=WizardDiagnosticExporter(export_root);exporter.prepare(create=True)
        import copy
        for mutate in (
            lambda b:b.update(context_sha256='b'*64),
            lambda b:b.update(progression_authority=True),
            lambda b:b['assessment'].update(final_position=anchor+offset+1),
            lambda b:b['responses'][1].update(sha256='0'*64),
            lambda b:b['responses'].append(b['responses'][-1]),
            lambda b:b['responses'][1].update(path=STATUS),
        ):
            altered=copy.deepcopy(bundle);mutate(altered)
            bad=exporter.export({'mode':'test'},[],attachments={'observed-pair-forward.json':canonical(altered)})
            with pytest.raises(ValueError):
                observed.replay_observed_pair_forward(export_root,Path(bad['path']).name)
        def disconnected(*args,**kwargs):raise OSError('Synthetic disconnection')
        patch.setattr(observed.HeldPairHTTPReader,'_get',disconnected)
        incomplete=observed.collect_authorized_pair_forward(export_root,context_id,address='127.0.0.1')
        assert incomplete['replay_verified'] and incomplete['assessment']['category']=='INCONCLUSIVE'
        def partial(self,path,**kwargs):
            if path==RECORD+'2':raise OSError('Synthetic partial capture')
            return native_get(self,path,**kwargs)
        patch.setattr(observed.HeldPairHTTPReader,'_get',partial)
        partial_saved=observed.collect_authorized_pair_forward(export_root,context_id,address='127.0.0.1')
        assert partial_saved['replay_verified'] and partial_saved['assessment']['category']=='INCONCLUSIVE'
        def stopped(self,path,**kwargs):
            if path==STATUS:
                status=json.loads(meta['transport_status_json']);status['state']='STOPPED'
                return canonical(status)
            return native_get(self,path,**kwargs)
        patch.setattr(observed.HeldPairHTTPReader,'_get',stopped)
        stopped_saved=observed.collect_authorized_pair_forward(export_root,context_id,address='127.0.0.1')
        assert stopped_saved['assessment']['controller_state']=='STOPPED'
        assert not stopped_saved['assessment']['progression_authority']
        from rocell.application import held_pair_return_authorization as returns
        from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
        return_challenge=dict(challenge,nonce='33'*32,issued_us=2000,expires_us=10002000)
        from functools import partial
        authorize_return=partial(returns.authorize_observed_pair_return,
            forward_delivery_export_id=Path(delivered['export_path']).name)
        # Arrival alone never overrides uncertain/rejected command delivery.
        for delivery_result in ('DELIVERY_UNCERTAIN','CONTROLLER_REPORTED_REJECTION'):
            rejected=copy.deepcopy(delivered['report'])
            rejected['delivery']['result']=delivery_result
            if delivery_result=='CONTROLLER_REPORTED_REJECTION':
                raw=canonical(dict(accepted=False,retry_allowed=False))
                rejected['delivery'].update(response_body=raw.decode(),response_sha256=hashlib.sha256(raw).hexdigest())
            rejected_export=exporter.export({'mode':'test'},[],attachments={'pair-delivery-result.json':canonical(rejected)})
            with pytest.raises(ValueError,match='accepted delivery'):
                returns.authorize_observed_pair_return(export_root,export_id,return_challenge,b'k'*32,
                    forward_delivery_export_id=Path(rejected_export['path']).name)
        from rocell.application.held_pair_challenge_http import request_pair_challenge
        from rocell.application.held_pair_receipt_workflow import authorize_pair_from_receipt,replay_pair_receipt_workflow
        with once_server(response(canonical(return_challenge))) as (port,requests):
            receipt=request_pair_challenge(export_root,operation='return',expected_boot=return_challenge['boot_id'],
                                           address='127.0.0.1',port=port)
        workflow=authorize_pair_from_receipt(export_root,Path(receipt['export_path']).name,export_id,b'k'*32,
            leg='return',forward_delivery_export_id=Path(delivered['export_path']).name)
        authorization=workflow['authorization']
        assert replay_pair_receipt_workflow(export_root,Path(workflow['export_path']).name)['replay_verified']
        altered=copy.deepcopy(workflow['report']);altered['receipt_sha256']='0'*64
        forged=exporter.export({'mode':'test'},[],attachments={'pair-receipt-workflow.json':canonical(altered)})
        with pytest.raises(ValueError):replay_pair_receipt_workflow(export_root,Path(forged['path']).name)
        with once_server(accepted_reply) as (port,requests):
            return_delivery=send_authorized_pair(export_root,authorization,leg='return',address='127.0.0.1',port=port)
        assert len(requests)==1 and requests[0][2]==authorization.token
        assert return_delivery['report']['delivery']['result']=='CONTROLLER_REPORTED_ACCEPTANCE'
        with pytest.raises(ValueError,match='Unexpected delivery leg'):
            returns.authorize_observed_pair_return(export_root,export_id,return_challenge,b'k'*32,
                forward_delivery_export_id=Path(return_delivery['export_path']).name)
        return_replay=returns.replay_pair_return_authorization(export_root,authorization.context_export_id)
        payload=return_replay['context']['payload']
        assert payload['export_sha256']==saved['export_sha256']
        assert payload['evidence_sha256']==held_evidence_digest(rows)
        assert payload['return_target_count']==anchor
        assert return_replay['replay_verified'] and not return_replay['delivery_verified']
        assert 'token=' not in repr(authorization)
        assert authorization.token.endswith(hmac.digest(b'k'*32,authorization.token[:-32],'sha256'))
        assert authorization.token not in (export_root/authorization.context_export_id/'attachment-held-return-signing-context.json').read_bytes()
        with pytest.raises(PhysicalOnboardingDurabilityError):
            authorize_return(export_root,export_id,return_challenge,b'k'*32)
        # A previously consumed hold nonce shares this same reservation namespace.
        with pytest.raises(PhysicalOnboardingDurabilityError):
            authorize_return(export_root,export_id,
                                                   dict(return_challenge,nonce='44'*32),b'k'*32)
        for mutate in (
            lambda c:c['payload'].update(return_target_count=anchor+1),
            lambda c:c['payload'].update(export_sha256='0'*64),
            lambda c:c.update(delivery_attempted=True),
            lambda c:c.update(forward_delivery_sha256='0'*64),
        ):
            changed=copy.deepcopy(return_replay['context']);mutate(changed)
            forged=exporter.export({'mode':'test'},[],attachments={'held-return-signing-context.json':canonical(changed)})
            with pytest.raises(ValueError):
                returns.replay_pair_return_authorization(export_root,Path(forged['path']).name)
        for bad_challenge in (dict(return_challenge,boot_id='99'*16),
                              dict(return_challenge,nonce=challenge['nonce']),
                              dict(return_challenge,issued_us=1000)):
            with pytest.raises(ValueError):
                authorize_return(export_root,export_id,bad_challenge,b'k'*32)
        for bad_export in (incomplete,partial_saved,stopped_saved):
            with pytest.raises(ValueError,match='stable arrived'):
                authorize_return(export_root,Path(bad_export['export_path']).name,
                                                       return_challenge,b'k'*32)
        def fail_storage(*args,**kwargs):raise OSError('Synthetic storage failure')
        failing_challenge=dict(return_challenge,nonce='88'*32)
        identity=canonical(dict(boot_id=failing_challenge['boot_id'],nonce=failing_challenge['nonce']))
        claim_path=export_root/('diagnostic-start-'+hashlib.sha256(identity).hexdigest()+'.json')
        with monkeypatch.context() as failed:
            failed.setattr(returns.WizardDiagnosticExporter,'export',fail_storage)
            with pytest.raises(OSError):
                authorize_return(export_root,export_id,failing_challenge,b'k'*32)
        assert not claim_path.exists()
        with monkeypatch.context() as failed:
            failed.setattr(returns,'read_bounded_regular_file',fail_storage)
            with pytest.raises(OSError):
                authorize_return(export_root,export_id,failing_challenge,b'k'*32)
        assert claim_path.exists()
        with pytest.raises(PhysicalOnboardingDurabilityError):
            authorize_return(export_root,export_id,failing_challenge,b'k'*32)
    body=authorization.token[:-32]
    back=tmp_path/'return.bin';back.write_bytes(authorization.token)
    for start_ok,return_ok in [(True,True),(True,False),(False,False)]:
        start.write_bytes(token if start_ok else token[:-1]+bytes([token[-1]^1]))
        if not return_ok:
            back.write_bytes(body+bytes(32))
        run=subprocess.run([str(exe),str(start),str(back),str(int(start_ok)),str(int(return_ok)),str(hold_path),*extra],
                           capture_output=True,text=True,timeout=20)
        assert run.returncode==0,run.stderr
        if start_ok and return_ok:
            from rocell.application import held_pair_observed_return as observed_return
            return_meta=json.loads(run.stdout)
            def return_get(self,path,**kwargs):
                if path==STATUS:return return_meta['transport_status_json'].encode()
                return return_meta['transport_records'][int(path.removeprefix(RECORD))].encode()
            with monkeypatch.context() as patch:
                patch.setattr(observed_return.HeldPairHTTPReader,'_get',return_get)
                paired=observed_return.collect_authorized_pair_return(export_root,
                    authorization.context_export_id,address='127.0.0.1')
                review=paired['review']
                assert review['category']=='CONTROLLER_REPORTED_PAIR_ARRIVAL'
                assert review['forward']['position_change_counts']==offset
                assert review['reverse']['position_change_counts']==-offset
                assert review['reverse']['final_position']==anchor
                assert review['endpoint_continuity_verified'] and review['between_leg_delta_counts']==0
                assert not review['physical_tip_accuracy_verified'] and not review['progression_authority']
                pair_id=Path(paired['export_path']).name
                patch.setattr(observed_return.HeldPairHTTPReader,'_get',lambda *a,**kw:pytest.fail('Replay contacted hardware'))
                assert observed_return.replay_observed_pair_return(export_root,pair_id)['review']==review
                operation=_run(service,'review_observed_pair',{'export_id':pair_id})
                assert operation['status']=='SUCCEEDED',operation
                page=render(operation)
                assert 'CONTROLLER_REPORTED_PAIR_ARRIVAL' in page
                assert str(anchor) in page and str(anchor+offset) in page and 'NOT QUALIFIED' in page
                assert 'Stylus-tip accuracy is not measured' in page
                malformed=copy.deepcopy(operation)
                malformed['result']['steps'][0]['report']['review']['reverse']['controller_state']='STOPPED'
                assert 'Pair review unavailable or inconsistent' in render(malformed)
                assert not runner.calls and service.view()['arm']['status']=='NOT_CONNECTED'
                archived=json.loads((export_root/pair_id/'attachment-observed-pair-return.json').read_bytes())
                for mutate in (
                    lambda b:b['review'].update(category='INCONCLUSIVE'),
                    lambda b:b.update(context_sha256='0'*64),
                    lambda b:b['responses'][1].update(sha256='0'*64),
                ):
                    changed=copy.deepcopy(archived);mutate(changed)
                    bad=exporter.export({'mode':'test'},[],attachments={'observed-pair-return.json':canonical(changed)})
                    with pytest.raises(ValueError):
                        observed_return.replay_observed_pair_return(export_root,Path(bad['path']).name)
                def missing(*a,**kw):raise OSError('Synthetic return transport loss')
                patch.setattr(observed_return.HeldPairHTTPReader,'_get',missing)
                lost=observed_return.collect_authorized_pair_return(export_root,
                    authorization.context_export_id,address='127.0.0.1')
                assert lost['replay_verified'] and lost['review']['category']=='INCONCLUSIVE'
                lost_operation=_run(service,'review_observed_pair',{'export_id':Path(lost['export_path']).name})
                assert lost_operation['status']=='SUCCEEDED'
                assert 'INCONCLUSIVE' in render(lost_operation)
                # A valid forward archive must never be mistaken for return evidence.
                patch.setattr(observed_return.HeldPairHTTPReader,'_get',native_get)
                wrong_leg=observed_return.collect_authorized_pair_return(export_root,
                    authorization.context_export_id,address='127.0.0.1')
                assert wrong_leg['review']['category']=='INCONCLUSIVE'
                def stopped_return(self,path,**kwargs):
                    if path==STATUS:
                        value=json.loads(return_meta['transport_status_json']);value['state']='STOPPED'
                        return canonical(value)
                    return return_get(self,path,**kwargs)
                patch.setattr(observed_return.HeldPairHTTPReader,'_get',stopped_return)
                stopped_pair=observed_return.collect_authorized_pair_return(export_root,
                    authorization.context_export_id,address='127.0.0.1')
                assert stopped_pair['review']['reverse']['category']=='CONTROLLER_REPORTED_ARRIVAL'
                assert stopped_pair['review']['category']=='INCONCLUSIVE'
    print('Host ABI runtime bytes:',meta['runtime_bytes'])
    if socket_mode:
        start.write_bytes(token)
        back.write_bytes(body+hmac.digest(b'k'*32,body,'sha256'))
        for mode,start_ok in [('shortstart',False),('shortreturn',True)]:
            run=subprocess.run([str(exe),str(start),str(back),str(int(start_ok)),'0',str(hold_path),mode],
                               capture_output=True,text=True,timeout=20)
            assert run.returncode==0,run.stderr
        for mode in ('handoff_boot','handoff_plan','handoff_policy','handoff_used','handoff_empty'):
            run=subprocess.run([str(exe),str(start),str(back),'0','0',str(hold_path),mode],
                               capture_output=True,text=True,timeout=20)
            assert run.returncode==0,run.stderr
