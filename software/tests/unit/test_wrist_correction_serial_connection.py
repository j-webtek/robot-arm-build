import ctypes
from threading import Event
import pytest
from test_wrist_correction_current_context import fixture
from test_endpoint_serial_connection import OwnerKernel
from rocell.arm.protocol import encode_line
from rocell.safety.wrist_correction_admission import admit_wrist_correction
from rocell.providers.windows.wrist_correction_serial_api import WindowsWristCorrectionSerialApi
from rocell.providers.windows.wrist_correction_serial_connection import WristCorrectionSerialConnection
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi


def owner(tmp_path,monkeypatch):
    reader,clock,*_=fixture(tmp_path)
    request=reader.request
    permit=admit_wrist_correction(request,reader=reader,root=tmp_path,cancellation=Event())
    kernel=OwnerKernel()
    def load(api): api._dll=kernel;return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    monkeypatch.setattr(ctypes,'get_last_error',lambda:kernel.last_error,raising=False)
    api=WindowsWristCorrectionSerialApi.from_correction_permit(request,permit,
        port_name=permit._binding._port,connection_id=request.to_dict()['attempt_id'])
    connection=WristCorrectionSerialConnection(request,api,clock_ns=lambda:clock[0])
    return connection,kernel,permit,request,reader,clock


def select(connection,permit,request,reader,clock):
    raw=b'';windows=[]
    joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
    for i in range(10):
        line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
        stamp=2_000_000_000+i*50_000_000
        windows.append([len(raw),len(raw)+len(line),stamp,stamp]);raw+=line
    clock[0]=2_500_000_000
    permit.bind_owned_baseline(request,request.to_dict()['attempt_id'],permit._binding._port,
        raw,windows,started_ns=2_000_000_000,finished_ns=clock[0])


def test_open_read_write_post_and_reverse_cleanup(tmp_path,monkeypatch):
    c,k,p,r,reader,clock=owner(tmp_path,monkeypatch)
    c.open();assert c.read(256,100)==k.input
    select(c,p,r,reader,clock)
    payload=p.selected_payload()
    assert c.write_once(payload)==len(payload)
    assert c.read(256,100)==k.input
    assert c.close(2000).all_handles_closed
    assert k.closed==[202,201,101] and k.writes==[payload]
    assert c.snapshot()['confirmed_write_bytes']==len(payload)
    with pytest.raises(ValueError): c.open()
    with pytest.raises(ValueError): c.write_once(payload)


@pytest.mark.parametrize('fault',['bad_settings','fail_setup'])
def test_setup_failure_closes_without_command(tmp_path,monkeypatch,fault):
    c,k,*_=owner(tmp_path,monkeypatch)
    setattr(k,fault,True)
    with pytest.raises(Exception): c.open()
    assert k.closed==[202,201,101] and not k.writes


def test_pending_read_cancellation_retains_late_bytes(tmp_path,monkeypatch):
    import base64
    c,k,*_=owner(tmp_path,monkeypatch)
    c.open();k.pending=True;k.completion_ready=False
    with pytest.raises(Exception): c.read(256,100)
    assert c.close(2000).all_handles_closed
    assert base64.b64decode(c.snapshot()['late_cleanup_read_base64'])==k.input
    assert k.cancel_calls==1 and not k.writes


def test_no_baseline_no_write_and_cleanup_still_available(tmp_path,monkeypatch):
    c,k,*_=owner(tmp_path,monkeypatch)
    c.open()
    with pytest.raises(ValueError): c.write_once(b'{}\n')
    assert c.close(2000).all_handles_closed and not k.writes
