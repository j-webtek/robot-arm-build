"""Real commissioning composition down to a fake kernel; never actual Win32."""
import ctypes
import json

import pytest

from rocell.application.first_motion_owned_trial import run_owned_first_motion_trial, FirstMotionCleanupResult
from rocell.providers.windows.first_motion_serial_api import WindowsFirstMotionSerialApi
from rocell.providers.windows.first_motion_serial_connection import FirstMotionSerialConnection
from rocell.providers.windows.endpoint_serial_connection import EndpointSerialConnection
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from test_first_motion_admission import setup, admit
from test_endpoint_serial_connection import OwnerKernel
from threading import Event


def owner(tmp_path,monkeypatch):
    request, reader, clock, _ = setup(tmp_path)
    permit = admit(tmp_path,request,reader,clock)
    kernel = OwnerKernel()
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    monkeypatch.setattr(ctypes,'get_last_error',lambda:kernel.last_error,raising=False)
    api = WindowsFirstMotionSerialApi.from_first_motion_permit(request,permit,
        port_name='COM7',connection_id=request.to_dict()['attempt_id'])
    connection = FirstMotionSerialConnection(request,api,clock_ns=lambda:clock[0])
    return request,permit,connection,kernel,clock,api


def test_owned_runner_to_fake_driver_roundtrip(tmp_path,monkeypatch):
    request,permit,connection,kernel,clock,_ = owner(tmp_path,monkeypatch)
    def frame(value):
        return json.dumps(dict(T=1051,x=1,y=2,z=3,tit=0,b=0,s=0,e=0,t=value,r=0,g=0),
                          separators=(',',':')).encode()+b'\n'
    kernel.input = frame(0)
    original_read, original_write = kernel.ReadFile,kernel.WriteFile
    def read(*args):
        clock[0] += 50_000_000
        return original_read(*args)
    def write(*args):
        clock[0] += 1
        kernel.input = frame(request.to_dict()['command']['rad'])
        return original_write(*args)
    kernel.ReadFile,kernel.WriteFile = read,write
    connection.open()
    result = run_owned_first_motion_trial(request,permit,
        connection_id=request.to_dict()['attempt_id'],read_once=connection.read,
        write_once=connection.write_once,close_once=connection.close,cancellation=Event(),
        basis='SYNTHETIC_WIRE_REHEARSAL',clock_ns=lambda:clock[0])
    assert result['status']=='REPORTED_WRIST_RESPONSE_REVIEW_REQUIRED'
    assert len(kernel.writes)==1 and json.loads(kernel.writes[0])==request.to_dict()['command']
    assert kernel.closed==[202,201,101]
    snapshot = connection.snapshot()
    assert snapshot['schema']=='rocell.first_motion_connection_lifecycle.v1'
    assert snapshot['phase']=='CLOSED' and snapshot['owned_handle_count']==0
    assert snapshot['confirmed_write_bytes']==len(kernel.writes[0])
    assert snapshot['read_calls']=={'baseline':20,'post':100}
    with pytest.raises(ValueError): connection.open()


@pytest.mark.parametrize('fault',['bad_settings','fail_setup'])
def test_setup_failure_closes_without_write(tmp_path,monkeypatch,fault):
    _,_,connection,kernel,_,_ = owner(tmp_path,monkeypatch)
    setattr(kernel,fault,True)
    with pytest.raises(Exception): connection.open()
    assert kernel.closed==[202,201,101] and kernel.writes==[]
    assert type(connection.close(2000)) is FirstMotionCleanupResult
    assert len(kernel.closed)==3
    with pytest.raises(ValueError): connection.open()


def test_endpoint_owner_rejects_commissioning_facade(tmp_path,monkeypatch):
    request,_,connection,kernel,_,api = owner(tmp_path,monkeypatch)
    with pytest.raises(ValueError): EndpointSerialConnection(request,api)
    assert kernel.closed==[] and kernel.writes==[]


def test_wrong_payload_consumes_connection_write_slot(tmp_path,monkeypatch):
    _,_,connection,kernel,_,_ = owner(tmp_path,monkeypatch)
    connection.open()
    with pytest.raises(ValueError): connection.write_once(b'{"T":999}\n')
    with pytest.raises(ValueError): connection.write_once(b'{"T":999}\n')
    assert kernel.writes==[]
    assert connection.close(2000).all_handles_closed
