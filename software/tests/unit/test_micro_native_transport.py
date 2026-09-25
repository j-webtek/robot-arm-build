import pytest
from test_micro_control_session import build,bind
from test_micro_command_admission import consume
from test_arm_wifi_deadline import wire
from rocell.providers.windows import micro_native_transport as native
from rocell.application.first_motion_contract import canonical


def test_exact_micro_dispatch_one_socket_attempt(tmp_path,monkeypatch,wire):
    admission,session,ticks,_=build(tmp_path,monkeypatch)
    clock,sent,sock,_=wire
    monkeypatch.setattr(native,'neighbor_mac',lambda:native.MAC)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:ticks[0])
    with session.scope():
        bind(admission,session,ticks);consume(admission);ticks[0]=1_400_000_000
        binding=native.MicroNativeBinding(admission,session,root=tmp_path)
        connection=native._MicroConnection(native.ADDRESS,clock=lambda:clock[0])
        payload=canonical(admission.snapshot()['command'])
        connection.dispatch(binding,payload)
        assert len(sent)==1 and b'%22T%22%3A101' in sent[0]
        with pytest.raises(ValueError):connection.dispatch(binding,payload)
        connection.close()
    assert sock.closed and len(list(tmp_path.glob('*-micro-native-send.json')))==1


@pytest.mark.parametrize('fault',['unconsumed','identity','expired_write'])
def test_boundary_fault_never_opens_socket(tmp_path,monkeypatch,wire,fault):
    admission,session,ticks,_=build(tmp_path,monkeypatch)
    clock,sent,_,_=wire
    monkeypatch.setattr(native,'neighbor_mac',lambda:'wrong' if fault=='identity' else native.MAC)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:ticks[0])
    with session.scope():
        bind(admission,session,ticks)
        if fault!='unconsumed':consume(admission)
        ticks[0]=1_400_000_000
        if fault=='expired_write':
            original=native.publish_reservation_bytes
            def slow(*a,**k):
                result=original(*a,**k);ticks[0]=3_000_000_000;return result
            monkeypatch.setattr(native,'publish_reservation_bytes',slow)
        binding=native.MicroNativeBinding(admission,session,root=tmp_path)
        connection=native._MicroConnection(native.ADDRESS,clock=lambda:clock[0])
        with pytest.raises(ValueError):connection.dispatch(binding,canonical(admission.snapshot()['command']))
        assert not sent
        connection.close()


@pytest.mark.parametrize('body,accepted',[(b'',True),(b'{"ok":1}',True),
    (b'{"ok":true}',False),(b'{"error":"x"}',False),(b'{"T":1051}',False)])
def test_receipt_never_counts_as_endpoint(tmp_path,monkeypatch,body,accepted):
    admission,session,_,_=build(tmp_path,monkeypatch);closed=[]
    binding=native.MicroNativeBinding(admission,session,root=tmp_path)
    class Connection:
        status=200
        def __init__(self,*a,**k):pass
        def dispatch(self,*a):pass  # Socket boundary tested separately above.
        def getresponse(self):return self
        def read1(self,n):return body
        def close(self):closed.append(True)
    monkeypatch.setattr(native,'_MicroConnection',Connection)
    monkeypatch.setattr(native,'neighbor_mac',lambda:native.MAC)
    transport=native.NativeMicroTransport(binding)
    if accepted:assert transport.send_once(b'{}',deadline_ns=99,cancelled=lambda:False)
    else:
        with pytest.raises(ValueError):transport.send_once(b'{}',deadline_ns=99,cancelled=lambda:False)
    assert closed==[True] and not transport.receipt['receipt_used_as_endpoint']


def test_existing_sender_still_rejects_micro_binding(tmp_path,monkeypatch):
    from rocell.providers.windows.wifi_discrete_native import NativeDiscreteTransport
    admission,session,_,_=build(tmp_path,monkeypatch)
    binding=native.MicroNativeBinding(admission,session,root=tmp_path)
    with pytest.raises(ValueError):NativeDiscreteTransport(binding)
