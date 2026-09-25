import hashlib
import json
import pytest
from rocell.application.shoulder_session_runner import run_shoulder_session
from rocell.application.wizard_diagnostic_export import verify_export
from pathlib import Path

BOOT='11'*16
COMMAND='r23-shoulder-hold'


class Device:
    """Protocol-only fake: no sockets, no actuator operations."""
    def __init__(self, mode):
        self.mode=mode;self.calls=[];self.count=0
        self.original=json.dumps(dict(schema='rocell.shoulder_hold_event.v1',boot_id=BOOT,
            command_id=COMMAND,sequence=0,event='STATE_MISMATCH',scan_started_us=1,
            scan_finished_us=2)).encode()

    def __call__(self, method, path, body, timeout):
        self.calls.append((method,path))
        suffix=path.rsplit('/',1)[-1]
        if 'shoulder-session/' in path:
            if suffix=='prepare':
                doc=dict(schema='rocell.start_challenge.v1',boot_id=BOOT,nonce='00'*32,
                         issued_us=0,expires_us=30_000_000)
            elif suffix=='start':doc={'status':'SESSION_ACTIVATED'}
            elif suffix=='status':
                doc=dict(schema='rocell.shoulder_session_status.v1',boot_id=BOOT,
                         command_id=COMMAND,sequence=0,state='FAULT',record_available=True)
            elif suffix=='record':return self.original
            else:raise AssertionError('No parent fault receipt or follow-on movement allowed')
        elif suffix in ('start','receipt'):
            assert len(body)==248
            if suffix=='receipt':self.count+=1
            doc=dict(accepted=True,movement_performed_by_handler=False)
        elif suffix=='status':
            doc=dict(schema='rocell.shoulder_settling_status.v1',boot_id=BOOT,
                     command_id='settle-'+COMMAND,count=self.count if self.count==4 else self.count+1,
                     state='SETTLED' if self.count==4 else 'WAITING_EXPORT',
                     record_available=self.count<4,parent_fault_latched=True,movement_authorized=False)
        elif suffix=='record':
            feedback=(2429).to_bytes(2,'little')+bytes([1 if self.mode=='moving' else 0])+bytes(12)
            doc=dict(schema='rocell.shoulder_hold_event.v1',boot_id=BOOT,command_id='settle-'+COMMAND,
                sequence=self.count,event='FAULT_SETTLING_SAMPLE',parent_command_id=COMMAND,
                original_fault_sha256=hashlib.sha256(self.original).hexdigest(),parent_fault_latched=True,
                movement_authorized=False,physical_accuracy_verified=False,
                scan_started_us=1000+self.count*501000,scan_finished_us=2000+self.count*501000,
                joints=[[sid,2429,2419,1,feedback.hex()] for sid in range(11,18)])
            if self.mode=='invalid':doc['joints'][0][1]=1000
        else:raise AssertionError(path)
        return json.dumps(doc).encode()


@pytest.mark.parametrize('mode',['success','moving','invalid'])
def test_parent_runner_collects_without_clearing_motion_fault(tmp_path,mode):
    device=Device(mode)
    result=run_shoulder_session(tmp_path,expected_boot=BOOT,key=bytes(range(32)),
        exchange=device,authorized=True,fault_settling=True,pause=lambda _:None)
    report=result['report']
    assert report['state']=='STOPPED' and report['error_type']=='ControllerMotionFault'
    capture=report['settling']
    assert capture['state']==('SETTLED' if mode=='success' else 'STOPPED')
    assert capture['parent_motion_state']=='FAULT'
    assert verify_export(Path(result['export_path']))['valid']
    assert all(verify_export(Path(p))['valid'] for p in capture['raw_exports'])
    if mode=='invalid':
        assert capture['raw_exports'] and not capture['records']
        assert ('POST','/rocell/shoulder-settling/receipt') not in device.calls


def test_unreleased_live_capture_rejected_before_transport(tmp_path):
    def forbidden(*args):raise AssertionError('No live request allowed')
    with pytest.raises(ValueError,match='not released'):
        run_shoulder_session(tmp_path,expected_boot=BOOT,key=bytes(range(32)),exchange=forbidden,
            origin='DEVICE_CAPTURE',authorized=True,fault_settling=True)
