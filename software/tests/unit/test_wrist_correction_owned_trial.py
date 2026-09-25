import math
import json
import hashlib
import pytest
from test_wrist_correction_serial_connection import owner
from rocell.arm.protocol import encode_line
from rocell.application.wrist_correction_owned_trial import _run_wrist_correction_trial


def run(tmp_path,monkeypatch,*,cancel=False,setup_failure=False,bias=.87,write_fault=None):
    connection,kernel,permit,request,reader,clock=owner(tmp_path,monkeypatch)
    joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
    kernel.input=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
    real_read=kernel.ReadFile;real_write=kernel.WriteFile
    def read(*args):
        clock[0]+=20_000_000
        return real_read(*args)
    def write(*args):
        clock[0]+=1_000_000
        result=real_write(*args)
        if write_fault=='interrupt': raise KeyboardInterrupt()
        if write_fault=='exception': raise OSError('synthetic uncertain write')
        if write_fault=='short': kernel.size-=1
        target=-math.radians(.87890625)+math.radians(bias)
        kernel.input=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**dict(joints,t=target)))
        return result
    kernel.ReadFile=read;kernel.WriteFile=write
    kernel.fail_setup=setup_failure
    cancellation=permit._binding._cancel
    if cancel: cancellation.set()
    result=_run_wrist_correction_trial(connection,permit,cancellation=cancellation,
        clock_ns=lambda:clock[0],idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)))
    return result,kernel


def test_complete_owned_fake_trial_publishes_nominal_endpoint(tmp_path,monkeypatch):
    result,kernel=run(tmp_path,monkeypatch)
    assert result['status']=='REPORTED_SETTLED',result['errors']
    assert len(kernel.writes)==1 and kernel.closed==[202,201,101]
    assert result['publication']['records_consistent']
    assert not result['owned_process_verified']


def test_nominal_miss_stops_without_return(tmp_path,monkeypatch):
    result,kernel=run(tmp_path,monkeypatch,bias=0)
    assert result['status']=='WRIST_EXCURSION',result['errors']
    assert len(kernel.writes)==1


def test_cancel_before_open_no_write(tmp_path,monkeypatch):
    result,kernel=run(tmp_path,monkeypatch,cancel=True)
    assert result['status']=='CANCELLED_BEFORE_OPEN'
    assert not kernel.writes and not kernel.closed


def test_setup_failure_closes_without_write(tmp_path,monkeypatch):
    result,kernel=run(tmp_path,monkeypatch,setup_failure=True)
    assert result['status']=='HELD_BEFORE_WRITE'
    assert not kernel.writes and kernel.closed==[202,201,101]


def test_short_write_not_accepted_even_if_reported_position_settles(tmp_path,monkeypatch):
    result,kernel=run(tmp_path,monkeypatch,write_fault='short')
    assert result['status']=='TRANSPORT_FAULT',result['errors']
    assert len(kernel.writes)==1


def test_uncertain_submission_retains_failure_without_retry(tmp_path,monkeypatch):
    result,kernel=run(tmp_path,monkeypatch,write_fault='exception')
    assert result['status']!='REPORTED_SETTLED'
    assert result['trial']['write']['completion_uncertain']
    assert len(kernel.writes)==1 and result['lifecycle'] is not None


@pytest.mark.parametrize('options',[{},dict(cancel=True),dict(setup_failure=True),dict(write_fault='exception'),dict(bias=0)])
def test_every_completed_runner_return_has_durable_original(tmp_path,monkeypatch,options):
    result,_=run(tmp_path,monkeypatch,**options)
    receipt=result['outcome_retention']
    assert receipt['status']=='RETAINED'
    raw=(tmp_path/receipt['file']).read_bytes()
    assert len(raw)==receipt['bytes'] and hashlib.sha256(raw).hexdigest()==receipt['sha256']
    saved=json.loads(raw)
    assert saved['status']==result['status'] and saved['lifecycle']==result['lifecycle']
    assert saved['capture_envelopes']==result['capture_envelopes']


def test_keyboard_interrupt_is_retained_then_propagated(tmp_path,monkeypatch):
    with pytest.raises(KeyboardInterrupt): run(tmp_path,monkeypatch,write_fault='interrupt')
    raw=next(tmp_path.glob('*outcome.original.json')).read_bytes()
    saved=json.loads(raw)
    assert saved['status']=='INTERRUPTED_AFTER_WRITE_ATTEMPT'
    assert saved['trial']['write']['completion_uncertain']
    assert saved['lifecycle']['owned_handle_count']==0


def test_outcome_storage_error_is_explicit_and_not_motion_success(tmp_path,monkeypatch):
    import rocell.application.wrist_correction_owned_trial as module
    def fail(*a,**kw): raise OSError('synthetic storage error')
    monkeypatch.setattr(module,'publish_reservation_bytes',fail)
    result,kernel=run(tmp_path,monkeypatch,cancel=True)
    assert result['outcome_retention']==dict(status='FAILED',error='OSError')
    assert not kernel.writes and not list(tmp_path.glob('*outcome.original.json'))


@pytest.mark.parametrize('fault',['capture','cancel','stale'])
def test_final_readback_failure_never_falls_back_to_old_baseline(tmp_path,monkeypatch,fault):
    import rocell.application.wrist_correction_owned_trial as module
    retain=module.retain_owned_final_capture
    def injected(connection,permit,**kwargs):
        if fault=='capture': raise OSError('synthetic final capture failure')
        final=retain(connection,permit,**kwargs)
        if fault=='cancel': permit._binding._cancel.set()
        else:
            clock=permit._binding._reader._clock
            permit._binding._reader._clock=lambda:clock()+200_000_000
        return final
    monkeypatch.setattr(module,'retain_owned_final_capture',injected)
    result,kernel=run(tmp_path,monkeypatch)
    assert result['status']=='HELD_BEFORE_WRITE'
    assert not kernel.writes and kernel.closed==[202,201,101]
    assert result['trial']['write'] is None
    assert result['outcome_retention']['status']=='RETAINED'
