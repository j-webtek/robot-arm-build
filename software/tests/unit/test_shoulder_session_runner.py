import copy
import json
from pathlib import Path
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.shoulder_session_runner import run_shoulder_session
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError


@pytest.mark.parametrize('revision,scope',[(23,'POSE_PREPARATION'),(24,'POSE_PREPARATION'),
    (25,'POSE_PREPARATION'),(26,'MIXED_TARGET'),(26,'PAIR_HOLD'),(26,'SHOULDER_RISE'),
    (27,'PAIR_HOLD'),(27,'POSE_PREPARATION'),(27,'MIXED_TARGET')])
def test_pose_preparation_cannot_use_wrong_live_revision(tmp_path,revision,scope):
    def forbidden(*args):raise AssertionError('No network allowed before binding')
    with pytest.raises(ValueError,match='binding'):
        run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
            exchange=forbidden,authorized=True,origin='DEVICE_CAPTURE',revision=revision,experiment=scope)


class Transport:
    def __init__(self, failure=None):
        self.sequence=0;self.calls=[];self.failure=failure

    def __call__(self, method, path, body, timeout):
        route=path.rsplit('/',1)[1];self.calls.append(route)
        if self.failure==route: raise TimeoutError('Injected delivery uncertainty')
        if route=='prepare':
            return canonical(dict(schema='rocell.start_challenge.v1',boot_id='11'*16,
                nonce='00'*32,issued_us=1,expires_us=30_000_001))
        if route=='start': return canonical(dict(status='SESSION_ACTIVATED'))
        if route=='receipt':
            self.sequence+=1
            return canonical(dict(status='EXPORT_RECEIPT_ACCEPTED',movement_performed_by_handler=False))
        if route=='status':
            return canonical(dict(schema='rocell.shoulder_session_status.v1',boot_id='11'*16,
                command_id='r23-shoulder-hold',sequence=self.sequence,
                state='COMPLETE' if self.sequence==15 else 'WAITING_EXPORT',
                preload_writes=2,enable_delivery='SENT_UNACKNOWLEDGED'))
        s=self.sequence
        names=['BASELINE','PRELOAD_INTENT','PRELOAD_RESULT','PRELOAD_VERIFIED',
            'PRELOAD_INTENT','PRELOAD_RESULT','PRELOAD_VERIFIED','PAIR_ENABLE_INTENT',
            'PAIR_ENABLE_SENT_UNACKNOWLEDGED','PAIR_ENABLE_READBACK']
        rows=[]
        for i in range(7):
            position=2000+i
            goal=position if (i==1 and s>=3) or (i==2 and s>=6) else 0
            torque=int(i in (1,2) and s>=9)
            rows.append([11+i,position,goal,torque,(position.to_bytes(2,'little')+bytes(13)).hex()])
        sid=12 if s in (1,2,3) else 13 if s in (4,5,6) else 0
        record=dict(schema='rocell.shoulder_hold_event.v1',boot_id='11'*16,
            command_id='r23-shoulder-hold',sequence=s,event=names[s] if s<10 else 'TIMED_HOLD_SAMPLE',
            scan_started_us=1+s*500000,scan_finished_us=2+s*500000,
            servo_id=sid,result=int(s in (2,3,5,6) or s>=9),
            snapshot_role='PRE_ACTION' if s in (2,5,8) else 'OBSERVATION',joints=rows,
            physical_accuracy_verified=False)
        if s in (1,2,4,5):record.update(requested_target=rows[sid-11][1],speed=20,acceleration=1)
        if s in (2,5):record.update(action_started_us=3+s*500000,action_finished_us=4+s*500000,device_error=0)
        if self.failure=='bad_record' and s==1:record['requested_target']=0
        return canonical(record)


def test_r24_fault_snapshot_is_exported_without_ack_or_retry(tmp_path):
    class FaultTransport(Transport):
        def __call__(self, method, path, body, timeout):
            route=path.rsplit('/',1)[1]
            if self.sequence==3 and route in ('status','record'):
                self.calls.append(route)
                if route=='status':
                    return canonical(dict(schema='rocell.shoulder_session_status.v1',
                        boot_id='11'*16,command_id='r23-shoulder-hold',sequence=3,
                        state='FAULT',reason='STATE_CHANGED',record_available=True,
                        preload_writes=1,enable_delivery='NOT_ATTEMPTED'))
                return canonical(dict(event='STATE_MISMATCH',sequence=3,joints=[[12,2001,0,0]]))
            return super().__call__(method,path,body,timeout)
    transport=FaultTransport()
    result=run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
        exchange=transport,authorized=True,monotonic=lambda:0,revision=24)
    assert result['report']['state']=='STOPPED'
    assert result['report']['revision']==24
    assert transport.calls.count('receipt')==3
    assert transport.calls[-1]=='record'
    saved=json.loads((Path(result['export_path'])/'attachment-shoulder-run.json').read_text())
    assert saved['operations'][-1]['response']['event']=='STATE_MISMATCH'


def test_live_transport_cannot_bypass_origin_or_installation_binding(tmp_path):
    from rocell.application.shoulder_session_http import ShoulderSessionHTTP
    def forbidden(*args):raise AssertionError('No network permitted')
    live=ShoulderSessionHTTP('127.0.0.1',socket_factory=forbidden)
    for origin in ('SIMULATION','DEVICE_CAPTURE'):
        with pytest.raises(ValueError):
            run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
                exchange=live,authorized=True,origin=origin)


def test_mixed_scope_cannot_run_on_installed_r24(tmp_path):
    from rocell.application.shoulder_session_http import ShoulderSessionHTTP
    def forbidden(*args):raise AssertionError('No network permitted')
    live=ShoulderSessionHTTP('127.0.0.1',socket_factory=forbidden)
    with pytest.raises(ValueError,match='not released'):
        run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
            exchange=live,authorized=True,origin='DEVICE_CAPTURE',revision=24,experiment='MIXED_TARGET')
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('failure',[None,'prepare','start','receipt','bad_record'])
def test_finite_runner_exports_and_stops_without_retry(tmp_path,failure):
    transport=Transport(failure)
    result=run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
        exchange=transport,authorized=True,monotonic=lambda:0)
    assert result['report']['state']==('CONTROLLER_HOLD_OBSERVED' if failure is None else 'STOPPED')
    assert transport.calls.count('prepare')==1
    assert transport.calls.count('start')<=1
    if failure=='receipt':assert transport.calls.count('receipt')==1
    if failure=='bad_record':assert transport.calls.count('receipt')==1  # baseline only
    if failure is None:assert len(result['report']['records'])==15
    calls=copy.copy(transport.calls)
    with pytest.raises((ValueError,OSError,PhysicalOnboardingDurabilityError)):
        run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
            exchange=transport,authorized=True,monotonic=lambda:0)
    assert transport.calls==calls


def test_failed_receipt_intent_export_prevents_advancement(tmp_path,monkeypatch):
    from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
    original=WizardDiagnosticExporter.export
    failed=False

    def export(self,*args,**kwargs):
        nonlocal failed
        raw=kwargs.get('attachments',{}).get('shoulder-run.json')
        if raw:
            report=json.loads(raw)
            if report['operations']:
                last=report['operations'][-1]
                if not failed and last['path'].endswith('/receipt') and last['outcome']=='INTENT':
                    # The read evidence must already be part of this intent.
                    assert report['records']
                    assert any(op['path'].endswith('/record') and op['outcome']=='RECEIVED'
                               for op in report['operations'])
                    failed=True
                    raise ValueError('Injected receipt-intent persistence failure')
        return original(self,*args,**kwargs)

    monkeypatch.setattr(WizardDiagnosticExporter,'export',export)
    transport=Transport()
    result=run_shoulder_session(tmp_path,expected_boot='11'*16,key=bytes(range(32)),
        exchange=transport,authorized=True,monotonic=lambda:0)
    assert failed and result['report']['state']=='STOPPED'
    assert 'receipt' not in transport.calls
