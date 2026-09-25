from threading import Event
import pytest
from test_wrist_correction_review_authority import setup
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_capture import capture_wrist_correction_window,correction_capture_original
from rocell.arm.protocol import encode_line


def collect(phase,cancelled=False):
    _,ctx,_,_=setup()
    request=WristCorrectionContextRequest(canonical(ctx));clock=[2_000_000_000]
    cancel=Event()
    if cancelled: cancel.set()
    def read(size,timeout):
        clock[0]+=20_000_000
        return encode_line(dict(T=1051,x=0,y=0,z=0,tit=0,b=0,s=0,e=0,t=0,r=0,g=0))
    completed=clock[0] if phase=='post' else None
    result=capture_wrist_correction_window(request,phase,read_once=read,cancellation=cancel,
        clock_ns=lambda:clock[0],idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)),command_completed_ns=completed)
    return request,result,completed


@pytest.mark.parametrize('phase,seconds',[('baseline',1),('post',5)])
def test_bounded_capture_projects_validated_originals(phase,seconds):
    request,capture,completed=collect(phase)
    original=correction_capture_original(request,capture,phase=phase,command_completed_ns=completed)
    assert original['finished_ns']-original['started_ns']==seconds*1_000_000_000
    assert original['raw_base64'] and len(original['read_windows'])<=512


def test_cancelled_capture_cannot_be_projected_as_complete():
    request,capture,completed=collect('post',True)
    with pytest.raises(ValueError): correction_capture_original(request,capture,phase='post',command_completed_ns=completed)


def test_changed_capture_association_rejected():
    request,capture,completed=collect('baseline')
    capture['request_sha256']='a'*64
    with pytest.raises(ValueError): correction_capture_original(request,capture,phase='baseline')
