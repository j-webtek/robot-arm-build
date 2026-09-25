import json
import subprocess
from pathlib import Path
import pytest
from test_compensated_shoulder_session import session_bridge
from rocell.application.compensated_shoulder_runner import run_compensated_step
from rocell.application.wizard_diagnostic_export import verify_export


class NativeInterface:
    """Adapt exact route operations to the existing real-native process bridge."""
    def __init__(self,binary,mode):
        self.mode=mode;self.sequence=0;self.settle_count=0;self.pending=None;self.raw=None;self.calls=[]
        self.process=subprocess.Popen([str(binary),mode if mode in ('short','neighbor','prewrite','overshoot','wrong_goal','at_command') else 'success'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    def read(self):
        line=self.process.stdout.readline();assert line,self.process.stderr.read()
        self.raw=line.rstrip().encode();self.pending=json.loads(self.raw)

    def __call__(self,method,path,body,timeout):
        self.calls.append((method,path));suffix=path.rsplit('/',1)[-1];settling='shoulder-settling/' in path
        if method=='POST':
            if suffix=='prepare':
                self.read()
                return json.dumps(dict(schema='rocell.start_challenge.v1',boot_id='11'*16,nonce='00'*32,
                                       issued_us=1,expires_us=30000001)).encode()
            self.process.stdin.write(body.decode()+'\n');self.process.stdin.flush()
            if suffix=='receipt':
                if settling:self.settle_count+=1
                else:self.sequence+=1
            self.read()
            return b'{"accepted":true,"movement_performed_by_handler":false}'
        doc=self.pending
        if suffix=='record':
            raw=doc['original'].encode() if doc.get('terminal') else self.raw
            if self.mode=='bad_raw' and not settling:
                changed=json.loads(raw);changed['joints'][0][1]+=1;return json.dumps(changed).encode()
            if self.mode in ('false_error','false_success','wrong_desired','forged_arrival') and not settling and self.sequence>=5:
                changed=json.loads(raw)
                if self.mode=='false_error':changed['desired_error_counts'][0]+=1
                if self.mode=='false_success':changed['result']=0
                if self.mode=='wrong_desired':changed['desired_positions'][0]+=1
                if self.mode=='forged_arrival':
                    # Internally consistent position/error fields, but the claimed
                    # success contradicts a measured five-count shortfall.
                    changed['joints'][1][1]+=5
                    changed['joints'][1][4]=changed['joints'][1][1].to_bytes(2,'little').hex()+changed['joints'][1][4][4:]
                    changed['desired_error_counts'][0]+=5
                    changed['goal_residual_counts'][0]+=5
                return json.dumps(changed).encode()
            return raw
        if settling:
            return json.dumps(dict(schema='rocell.shoulder_settling_status.v1',boot_id='11'*16,
                command_id='settle-compensated-step-1',count=self.settle_count if doc.get('settling_terminal') else self.settle_count+1,
                state='SETTLED' if doc.get('settling_terminal') else 'WAITING_EXPORT',
                parent_fault_latched=True,movement_authorized=False,
                record_available=not doc.get('settling_terminal',False))).encode()
        state=('AUTHORIZATION' if doc.get('authorize') else 'FAULT' if doc.get('fault') else
               'COMPLETE' if doc.get('terminal') else 'WAITING_EXPORT')
        if self.mode=='premature' and self.sequence==3:state='COMPLETE'
        return json.dumps(dict(schema='rocell.compensated_step_status.v1',boot_id='11'*16,command_id='compensated-step-1',
            sequence=self.sequence,state=state,controller_now_us=doc.get('now_us'),
            target_packets=doc.get('writes',0),reason=doc.get('reason'),record_available=bool(doc.get('original')))).encode()

    def close(self):
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=5)


@pytest.mark.parametrize('mode',['success','short','neighbor','prewrite','bad_raw','premature','overshoot','wrong_goal','at_command','false_error','false_success','wrong_desired','forged_arrival'])
def test_host_runner_drives_native_interface(session_bridge,tmp_path,mode):
    interface=NativeInterface(session_bridge,mode)
    try:
        result=run_compensated_step(tmp_path,boot='11'*16,key=bytes(range(32)),exchange=interface,
                             authorized=True,pause=lambda _:None)
        report=result['report']
        assert report['state']==('COMPENSATED_STEP_OBSERVED' if mode=='success' else 'STOPPED'),report
        assert verify_export(Path(result['export_path']))['valid']
        if mode in ('short','neighbor','overshoot','wrong_goal','at_command'):
            assert report['settling']['state']=='SETTLED',report
        if mode in ('bad_raw','premature'):
            assert ('POST','/rocell/compensated-step/authorize') not in interface.calls
        if mode in ('false_error','false_success','wrong_desired','forged_arrival'):
            assert interface.sequence==5  # No receipt sent for the rejected sample.
        assert all(verify_export(Path(path))['valid'] for path in report['raw_exports'])
    finally:interface.close()


def test_live_operation_not_released(tmp_path):
    with pytest.raises(ValueError,match='release binding'):
        run_compensated_step(tmp_path,boot='11'*16,key=bytes(range(32)),authorized=True,
                       origin='DEVICE_CAPTURE',exchange=lambda *args:pytest.fail('No network allowed'))


def test_initial_export_failure_prevents_any_transport(tmp_path,monkeypatch):
    from rocell.application import compensated_shoulder_runner as module
    def fail(*args,**kwargs):raise OSError('Simulated export storage failure')
    monkeypatch.setattr(module.WizardDiagnosticExporter,'export',fail)
    with pytest.raises(OSError):
        module.run_compensated_step(tmp_path,boot='11'*16,key=bytes(range(32)),authorized=True,
                                   exchange=lambda *args:pytest.fail('No request before durable intent'))
