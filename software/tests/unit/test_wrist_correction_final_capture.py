import base64
from threading import Event
import pytest
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_preview import preview_wrist_correction
from rocell.application.wrist_correction_final_capture import capture_final_readback,validate_final_capture
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.providers.windows.wrist_correction_native_protocol import digest
from rocell.arm.protocol import encode_line


def collect(fault=None):
    _,context,_,inputs=setup()
    request=WristCorrectionContextRequest(canonical(context));clock=[2_000_000_000]
    cancel=Event();calls=[]
    if fault=='cancelled': cancel.set()
    joints=inputs['samples'][-1]['joints_rad']
    line=encode_line(dict(T=1051,x=0,y=0,z=0,tit=0,**joints))
    def read(size,timeout):
        calls.append((size,timeout))
        clock[0]+=250_000_000 if fault=='late' else 20_000_000
        if fault=='clock': clock[0]=1
        if fault=='cancel_during': cancel.set()
        if fault=='oversized': return b'x'*(size+1)
        if fault=='empty': return b''
        if fault=='short_span' and clock[0]<2_140_000_000: return b''
        if fault=='exception': raise OSError('fixture read failure')
        return line
    capture=capture_final_readback(request,read_once=read,cancellation=cancel,
        clock_ns=lambda:clock[0],idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)))
    preview=preview_wrist_correction(inputs['originals'],expected_basis=inputs['expected_basis'],
        samples=inputs['samples'],now_ns=inputs['samples'][-1]['host_received_ns'],usb_identity=context['usb_identity'])
    args=dict(basis=inputs['expected_basis'],baseline_samples=inputs['samples'],selection_sha256=digest(canonical(preview)),now_ns=clock[0])
    return request,capture,inputs['originals'],args,calls


def test_final_window_feeds_readback_validator_without_commands():
    request,capture,originals,args,calls=collect()
    assert capture['status']=='WINDOW_COMPLETE'
    assert capture['window_deadline_ns']-capture['started_ns']==200_000_000
    assert capture['schema']=='rocell.wrist_correction_final_capture.v2'
    assert capture['started_ns']+170_000_000<=capture['observation_end_ns']==capture['finished_ns']<capture['window_deadline_ns']
    assert len(calls)<=16 and all(size<=256 and timeout<=100 for size,timeout in calls)
    report=validate_final_capture(request,capture,originals,**args)
    assert report['host_age_ns']<=100_000_000 and not report['motion_authorized']


@pytest.mark.parametrize('fault',['cancelled','cancel_during','late','clock','oversized','empty','exception','short_span'])
def test_capture_faults_preserved_and_cannot_validate(fault):
    request,capture,originals,args,calls=collect(fault)
    assert len(calls)<=16
    if fault=='cancelled': assert not calls
    if fault=='late':
        assert capture['late_completion_bytes']>0
        assert b''.join(base64.b64decode(c) for c in capture['raw']['base64_chunks'])
    if fault=='oversized': assert capture['abnormal_completion']['returned_bytes']==257
    if fault=='clock': assert capture['untimed_completion'] is not None
    with pytest.raises(ValueError): validate_final_capture(request,capture,originals,**args)


@pytest.mark.parametrize('fault',['too_early','after_finish','late_finish','missing','downgrade'])
def test_actual_end_cannot_invent_observation_or_extend_limit(fault):
    request,capture,originals,args,_=collect()
    if fault=='too_early': capture['observation_end_ns']=capture['started_ns']+160_000_000
    elif fault=='after_finish': capture['observation_end_ns']=capture['finished_ns']+1
    elif fault=='late_finish': capture['finished_ns']=capture['window_deadline_ns']+1
    elif fault=='missing': del capture['observation_end_ns']
    else: capture['schema']='rocell.wrist_correction_final_capture.v1'
    with pytest.raises(ValueError): validate_final_capture(request,capture,originals,**args)


def test_legacy_fixed_window_remains_valid_and_observes_same_frames(monkeypatch):
    from rocell.application import wrist_correction_final_capture as module
    _,early,_,_,_=collect()
    collector=module._capture_owned_window
    def legacy(*args,**kwargs):
        kwargs.update(schema=module.LEGACY_SCHEMA,finish_at_read_guard=False)
        return collector(*args,**kwargs)
    monkeypatch.setattr(module,'_capture_owned_window',legacy)
    request,capture,originals,args,_=collect()
    assert 'observation_end_ns' not in capture
    assert capture['finished_ns']==capture['window_deadline_ns']
    assert capture['read_windows']==early['read_windows'] and capture['raw']==early['raw']
    assert validate_final_capture(request,capture,originals,**args)['host_age_ns']<=100_000_000


@pytest.mark.parametrize('fault',['request','count','deadline','digest','authority'])
def test_changed_collector_envelope_rejected(fault):
    request,capture,originals,args,_=collect()
    if fault=='request': capture['request_sha256']='0'*64
    elif fault=='count': capture['read_calls']+=1
    elif fault=='deadline': capture['window_deadline_ns']+=1
    elif fault=='digest': capture['raw']['sha256']='0'*64
    else: capture['physical_stop_verified']=True
    with pytest.raises(ValueError): validate_final_capture(request,capture,originals,**args)
