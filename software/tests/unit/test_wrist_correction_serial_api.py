from threading import Event
import pytest
from test_wrist_correction_current_context import fixture
from test_endpoint_serial_api import FakeKernel
from rocell.arm.protocol import encode_line
from rocell.providers.windows.wrist_correction_serial_api import WindowsWristCorrectionSerialApi
from rocell.providers.windows.absolute_wrist_serial_api import WindowsAbsoluteWristSerialApi
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi,IoToken,NativeSerialError
from rocell.safety.wrist_correction_admission import admit_wrist_correction


def admitted(tmp_path,monkeypatch,select=True):
    reader,clock,refs,*_=fixture(tmp_path)
    request=reader.request;cancel=Event()
    permit=admit_wrist_correction(request,reader=reader,root=tmp_path,cancellation=cancel)
    kernel=FakeKernel()
    def load(api): api._dll=kernel;return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    port=permit._binding._port
    api=WindowsWristCorrectionSerialApi.from_correction_permit(request,permit,port_name=port,connection_id=request.to_dict()['attempt_id'])
    handle=api.create_file('\\\\.\\'+port);event=api.create_event()
    if select:
        joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
        raw=b'';windows=[]
        for i in range(10):
            line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
            stamp=2_000_000_000+i*50_000_000
            windows.append([len(raw),len(raw)+len(line),stamp,stamp]);raw+=line
        clock[0]=2_500_000_000
        permit.bind_owned_baseline(request,api.connection_id,port,raw,windows,started_ns=2_000_000_000,finished_ns=clock[0])
    return request,permit,api,handle,event,kernel,clock,cancel,refs


def test_exact_correction_once_with_fake_kernel(tmp_path,monkeypatch):
    request,permit,api,handle,event,kernel,*_=admitted(tmp_path,monkeypatch)
    payload=permit.selected_payload()
    token=IoToken(event,'write',len(payload),payload)
    result=api.submit_io(handle,token)
    assert result.state=='COMPLETE' and kernel.writes==[payload]
    with pytest.raises(NativeSerialError): api.submit_io(handle,token)
    with pytest.raises(NativeSerialError): api.create_file(api.expected_path)
    api.close_handle(event);api.close_handle(handle)


@pytest.mark.parametrize('payload',[b'{"T":0}\n',b'{"T":999}\n',b'{"T":101,"joint":4,"rad":0,"spd":20,"acc":1}\n'])
def test_changed_payload_burns_native_write(tmp_path,monkeypatch,payload):
    _,permit,api,handle,event,kernel,*_=admitted(tmp_path,monkeypatch)
    with pytest.raises(NativeSerialError): api.submit_io(handle,IoToken(event,'write',len(payload),payload))
    correct=permit.selected_payload()
    with pytest.raises(NativeSerialError): api.submit_io(handle,IoToken(event,'write',len(correct),correct))
    assert not kernel.writes
    api.close_handle(event);api.close_handle(handle)


@pytest.mark.parametrize('fault',['stale','cancel','references'])
def test_current_context_failure_before_syscall(tmp_path,monkeypatch,fault):
    _,permit,api,handle,event,kernel,clock,cancel,refs=admitted(tmp_path,monkeypatch)
    payload=permit.selected_payload()
    if fault=='stale': clock[0]+=101_000_000
    if fault=='cancel': cancel.set()
    if fault=='references': refs[0]=()
    with pytest.raises(ValueError): api.submit_io(handle,IoToken(event,'write',len(payload),payload))
    assert not kernel.writes
    api.close_handle(event);api.close_handle(handle)


def test_old_facade_rejects_correction_permit(tmp_path,monkeypatch):
    request,permit,api,handle,event,kernel,*_=admitted(tmp_path,monkeypatch,False)
    with pytest.raises(ValueError):
        WindowsAbsoluteWristSerialApi.from_absolute_wrist_permit(request,permit,port_name=api._port_name,connection_id=api.connection_id)
    with pytest.raises(ValueError): permit.selected_payload()
    assert not kernel.writes
    api.close_handle(event);api.close_handle(handle)


def test_unadmitted_facade_cannot_load_native_kernel(monkeypatch):
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',lambda *_:pytest.fail('Unexpected native load'))
    api=WindowsWristCorrectionSerialApi('COM7')
    with pytest.raises(NativeSerialError): api.create_file(api.expected_path)
