"""Real exchange implementation over an inert socket; no network access."""
import pytest
from rocell.application import elbow_gain_capture as capture


@pytest.mark.parametrize('method',['POST','GET'])
@pytest.mark.parametrize('fault',[None,'truncated','status','oversize','duplicate','encoded','slow'])
def test_bounded_gain_exchange(monkeypatch,method,fault):
    response=b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}'
    if fault=='truncated':response=response[:-1]
    if fault=='status':response=response.replace(b'200 OK',b'409 Conflict')
    if fault=='oversize':response=response.replace(b'Length: 2',b'Length: 4096')
    if fault=='duplicate':response=response.replace(b'Length: 2',b'Length: 2\r\nContent-Length: 2')
    if fault=='encoded':response=response.replace(b'Length: 2',b'Length: 2\r\nTransfer-Encoding: chunked')
    tick=[0.0]
    class Socket:
        connects=0;sends=[];closed=False;offset=0
        def __enter__(self):return self
        def __exit__(self,*args):self.closed=True
        def settimeout(self,seconds):assert 0<seconds<=3
        def connect(self,target):
            assert target==('192.168.0.225',80);self.connects+=1
        def sendall(self,request):self.sends.append(request)
        def recv(self,count):
            tick[0]+=1.0 if fault=='slow' else 0.001
            raw=response[self.offset:self.offset+count];self.offset+=len(raw);return raw
    sock=Socket();created=[]
    def factory(*args):created.append(args);return sock
    monkeypatch.setattr(capture.socket,'socket',factory)
    monkeypatch.setattr(capture.time,'monotonic',lambda:tick[0])
    if fault:
        with pytest.raises((ValueError,OSError)) as raised:capture.gain_exchange('192.168.0.225',method)
        trace=raised.value.gain_exchange_diagnostic
        assert trace['method']==method and trace['deadline_seconds']==3
        assert trace['phase'] in ('response_header','validate_header','response_body')
        assert 0<=trace['header_bytes']<=2048 and 0<=trace['body_bytes']<=4095
        assert trace['elapsed_seconds']>=0
        if fault=='truncated':
            assert trace['phase']=='response_body' and trace['expected_body_bytes']==2
    else:assert capture.gain_exchange('192.168.0.225',method)==b'{}'
    assert len(created)==sock.connects==len(sock.sends)==1 and sock.closed
    path='capture' if method=='POST' else 'result'
    assert sock.sends[0].startswith(f'{method} /rocell/elbow-gain/{path} HTTP/1.1\r\n'.encode())
    assert sock.sends[0].endswith(b'\r\n\r\n') and b'Content-Length: 0\r\n' in sock.sends[0]


def test_invalid_operation_never_creates_socket(monkeypatch):
    def forbidden(*args):raise AssertionError('Socket must not be created')
    monkeypatch.setattr(capture.socket,'socket',forbidden)
    for method in ('PUT','DELETE','POST /js'):
        with pytest.raises(ValueError):capture.gain_exchange('192.168.0.225',method)
