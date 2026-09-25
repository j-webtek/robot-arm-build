"""Actual loopback HTTP and real coordinator; incapable owner, no device IO."""
import base64
import ctypes
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import time

import pytest
from test_arrival_wizard_service import make_service
from test_arrival_wizard_integration import request,prepare,execute
from test_endpoint_current_context import fixture as controller_fixture
from test_wrist_correction_saved_sources import saved
from rocell.application.first_motion_contract import canonical
from rocell.application import wizard_wrist_correction_coordinator as coordinator
from rocell.application.wrist_correction_process_finalization import finalize_correction_process
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult,owned_request_wire
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.observational_review_authority import CHECKS
from rocell.ui.server import create_wizard_server


def complete(server,operation):
    # The composed real capture/review path does more work than the generic
    # four-second pure-service fixture. Poll the same operation; never restart.
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        status,result=request(server,'/api/operations/'+operation['operation_id'])
        assert status==200
        if result['status'] in ('SUCCEEDED','FAILED','CANCELLED','TIMED_OUT'):
            return result
        time.sleep(.02)
    pytest.fail('Composed correction rehearsal did not finish in 20 seconds')


@pytest.mark.parametrize('fault',['timeout','cancel_after_worker','settled','miss','wall_clock'])
def test_http_real_review_child_verification_and_export(make_service,monkeypatch,fault,record_property):
    # There is no native escape path in this rehearsal. The only replaced
    # execution component is the process owner; signing/preparation/export run.
    from rocell.providers.windows import wrist_correction_child_execution
    def forbidden(*args,**kwargs):
        raise AssertionError('Native correction child forbidden in HTTP rehearsal')
    endpoint_case=fault in ('settled','miss','wall_clock')
    timings=[]
    if fault=='wall_clock':
        from rocell.application.wrist_correction_command_binding import WristCorrectionCommandBinding
        from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority
        # Instrument existing methods without replacing their checks or clocks.
        def instrument(cls,name):
            original=getattr(cls,name)
            def measured(self,*args,**kwargs):
                start=time.monotonic_ns();error=None
                acquired=getattr(self,'_acquired',None)
                try: return original(self,*args,**kwargs)
                except Exception as caught:
                    error=str(caught);raise
                finally:
                    end=time.monotonic_ns()
                    row=dict(method=cls.__name__+'.'+name,elapsed_ns=end-start,error=error)
                    if acquired is not None:
                        row.update(baseline_age_start_ns=start-acquired,baseline_age_end_ns=end-acquired)
                    if name=='bind_baseline':
                        row.update(capture_end_age_start_ns=start-kwargs['finished_ns'],
                            capture_end_age_end_ns=end-kwargs['finished_ns'])
                        last_sample=getattr(self,'_acquired',None)
                        if last_sample is not None:
                            row['last_sample_age_end_ns']=end-last_sample
                    if name=='_save' and args:
                        row['record_suffix']=args[0]
                    timings.append(row)
            monkeypatch.setattr(cls,name,measured)
        for name in ('bind_baseline','prepare_final_dispatch','consume_command'):
            instrument(WristCorrectionCommandBinding,name)
        for name in ('verify_plan','bind_review_from_capture','verify','seal_final_readback','verify_final_readback'):
            instrument(WristCorrectionReviewAuthority,name)
        from rocell.application.wrist_correction_consumption import WristCorrectionConsumption
        for cls in (WristCorrectionCommandBinding,WristCorrectionConsumption):
            instrument(cls,'_save')
        from rocell.application.wrist_correction_final_consumption import FinalReadbackConsumption
        for name in ('_verify','consume'):
            instrument(FinalReadbackConsumption,name)
        from rocell.application import wrist_correction_process_finalization as finalization
        parent_review=finalization.review_correction_child_result
        def reviewed(*args,**kwargs):
            try: return parent_review(*args,**kwargs)
            except Exception as error:
                record_property('parent_reconstruction_error',str(error))
                raise
        monkeypatch.setattr(finalization,'review_correction_child_result',reviewed)
    if not endpoint_case:
        monkeypatch.setattr(wrist_correction_child_execution,'execute_correction_child',forbidden)
    authority=BenchReviewAuthority(b'F'*32).for_wrist_correction_review()
    monkeypatch.setattr(bench_review_key,'load_host_wrist_correction_review_authority',lambda _:authority)
    monkeypatch.setattr(wrist_correction_child_execution,'load_host_wrist_correction_review_authority',lambda _:authority)
    from rocell.providers.windows import wrist_correction_prelaunch
    monkeypatch.setattr(wrist_correction_prelaunch,'load_host_wrist_correction_review_authority',lambda _:authority)
    service,runner,_=make_service(mode='physical')
    service.export_directory.mkdir(exist_ok=True)
    _,snapshots,_,controller=controller_fixture()
    source=service.retain_reviewed_observational_sources(controller_binding=controller,
        protocol_original=canonical({'fixture':'protocol'}),label='Synthetic HTTP controller')
    attempts=saved(service.export_directory,monkeypatch,fault='miss')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:{'fixture':'powered-not-physical-evidence'})
    calls=[]
    kernels=[]
    class IncapableOwner:
        def __init__(self,registration,*,authorizer,_clock):
            self.registration=registration;self.authorize=authorizer
        def run(self,outer,*,cancellation,deadline_ns):
            raw,digest=owned_request_wire(self.registration,outer,deadline_ns=deadline_ns)
            self.authorize(self.registration,outer,digest)
            calls.append(raw)
            now=time.monotonic_ns()
            if endpoint_case:
                from test_endpoint_serial_connection import OwnerKernel
                from rocell.arm.protocol import encode_line
                from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
                from rocell.providers.windows.wrist_correction_native_result import encode_result
                from rocell.providers.windows.wrist_correction_evidence_store import load_evidence
                payload=json.loads(raw)['payload']
                clock=[now]
                def tick(): return time.monotonic_ns() if fault=='wall_clock' else clock[0]
                # Use one deterministic clock for reads AND idle guards. Real
                # filesystem scheduling is not simulated acquisition freshness.
                from rocell.providers.windows.wrist_correction_trial_execution import _execute_claimed_correction_trial
                def execute_with_virtual_idle(*args,**kwargs):
                    return _execute_claimed_correction_trial(*args,**kwargs,
                        idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)))
                if fault!='wall_clock':
                    monkeypatch.setattr(wrist_correction_child_execution,'_execute_claimed_correction_trial',execute_with_virtual_idle)
                evidence=load_evidence(payload,assigned_root=service._log.root)
                joints=evidence.originals[0][0].to_dict()['draft']['expected_start_joints_rad']
                kernel=OwnerKernel();kernels.append(kernel)
                kernel.input=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
                read,write=kernel.ReadFile,kernel.WriteFile
                def timed_read(*args):
                    clock[0]+=20_000_000
                    return read(*args)
                def timed_write(*args):
                    clock[0]+=1_000_000
                    value=write(*args)
                    kernel.input=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,
                        **dict(joints,t=math.radians(1 if fault=='miss' else 0))))
                    return value
                kernel.ReadFile,kernel.WriteFile=timed_read,timed_write
                def load(api):
                    api._dll=kernel
                    return kernel
                monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
                monkeypatch.setattr(ctypes,'get_last_error',lambda:kernel.last_error,raising=False)
                def metadata(**kwargs):
                    assert kwargs['maximum_acquisitions']==8
                    def snapshot():
                        stamp=tick()
                        return replace(snapshots[0],started_monotonic_ns=stamp,finished_monotonic_ns=stamp)
                    return snapshot
                monkeypatch.setattr(wrist_correction_child_execution,'WindowsControllerMetadataAcquirer',metadata)
                child=wrist_correction_child_execution.execute_correction_child(service.workspace,raw,
                    cancellation=cancellation,clock_ns=tick)
                if fault=='wall_clock':
                    record_property('wall_clock_diagnostics',json.dumps(dict(timings=timings,
                        child_status=child['status'],fake_writes=len(kernel.writes),
                        final_capture=child['result'].get('capture_envelopes',{}).get('final',{}).get('validation')),
                        sort_keys=True))
                stdout=encode_result(child,request_raw=raw)
                simulated=OwnedWorkerResult(status='SUCCEEDED',primary_error=None,cleanup_errors=(),
                    request_sha256=digest,attempt_id=outer.attempt_id,process_created=True,
                    initial_thread_resumed=True,tree_exit_confirmed=True,returncode=0,elapsed_ns=tick()-now,
                    stdin_bytes_written=len(raw),peak_observed_handles=3,peak_active_processes=1,
                    stdout=stdout,stderr=b'',owned_process_id=os.getpid(),finished_monotonic_ns=tick())
                verdict=finalize_correction_process(raw,simulated,assigned_root=service._log.root,
                    authority=authority,process_started_ns=now)
                return replace(simulated,parsed_result=verdict)
            failed=OwnedWorkerResult(status='FAILED',primary_error='TIMED_OUT',cleanup_errors=(),
                request_sha256=digest,attempt_id=outer.attempt_id,process_created=False,
                initial_thread_resumed=False,tree_exit_confirmed=True,returncode=None,elapsed_ns=0,
                stdin_bytes_written=0,peak_observed_handles=0,peak_active_processes=0,
                stdout=b'fixture partial output',stderr=b'fixture timeout',owned_process_id=0,
                finished_monotonic_ns=now)
            final=finalize_correction_process(raw,failed,assigned_root=service._log.root,
                authority=authority,process_started_ns=now)
            if fault=='cancel_after_worker': cancellation.set()
            return replace(failed,parsed_result=final)
    monkeypatch.setattr(coordinator,'OwnedWindowsWorker',IncapableOwner)
    server=create_wizard_server(service);thread=server.start_in_thread()
    def run(action,values=None):
        return complete(server,execute(server,prepare(server,action,values)))
    try:
        assessed=run('assess_saved_wrist_correction',dict(attempt_ids='\n'.join(attempts)))
        assert assessed['status']=='SUCCEEDED',assessed
        bound=run('bind_saved_wrist_correction',dict(assessment_operation_id=assessed['operation_id'],source_id=source['source_id']))
        assert bound['status']=='SUCCEEDED',bound
        staged=run('stage_wrist_correction',dict(binding_operation_id=bound['operation_id']))
        assert staged['status']=='SUCCEEDED',staged
        values=dict(operator_id='synthetic-http-operator',**{name:True for name in CHECKS})
        ticket=prepare(server,'run_wrist_correction',values)
        assert 'experimental motor target' in ' '.join(ticket['effects'])
        result=complete(server,execute(server,ticket))
        allowed=('SUCCEEDED',) if fault in ('wall_clock','settled') else ('FAILED','CANCELLED')
        assert result['status'] in allowed,json.dumps(result,indent=2)
        assert len(calls)==1 and not runner.calls,json.dumps(result,indent=2)
        outcome=service._wrist_correction_outcome
        assert outcome.stage=='EXPORTED',outcome
        expected='REPORTED_SETTLED' if fault in ('wall_clock','settled') else 'WRIST_EXCURSION' if fault=='miss' else 'HELD_PROCESS_FAILURE'
        if fault=='wall_clock':
            assert timings
        # Timing regression is a failure, not a successful fail-closed rehearsal.
        # Dedicated fault cases separately test holds and absence of retries.
        assert outcome.owned.parsed_result['status']==expected,outcome.owned.parsed_result
        assert outcome.report['artifact_roster_complete'] is endpoint_case
        if endpoint_case:
            assert len(kernels)==1
            assert len(kernels[0].writes)==1
            assert kernels[0].closed==[202,201,101]
        # Verify export copies against original bytes, not a success label.
        manifest=json.loads(outcome.report_path.read_bytes())
        from rocell.application.wrist_correction_export_validation import validate_correction_export
        portable=validate_correction_export(outcome.report_path.parent)
        assert portable['integrity_valid']
        assert portable['artifact_roster_complete']==outcome.report['artifact_roster_complete']
        assert not portable['endpoint_verified'] and not portable['replay_allowed']
        assert base64.b64decode(manifest['request']['base64'])==calls[0]
        assert base64.b64decode(manifest['stdout']['base64'])==outcome.owned.stdout
        retained=[row for row in manifest['artifacts'] if row['status']=='RETAINED']
        assert any('parent-verdict.original' in row['source_relative'] for row in retained)
        for row in retained:
            raw=(outcome.report_path.parent/row['file']).read_bytes()
            assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
            assert raw==(service._log.root/row['source_relative']).read_bytes()
        status,repeated= request(server,'/api/execute',body={'ticket_id':ticket['ticket_id']})
        # HTTP retry is idempotent: it may return the original receipt, never
        # create a second execution or renew the accepted plan.
        assert status==200 and repeated['operation_id']==result['operation_id'] and len(calls)==1
        exported=run('export_logs')
        assert exported['status']=='SUCCEEDED',exported
        assert verify_export(Path(exported['result']['receipt']['path']))['valid']
    finally:
        server.close();thread.join(timeout=3)
        assert not thread.is_alive()
