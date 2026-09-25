import json
import pytest
from rocell.providers.windows import arm_wifi_deadline as native
from rocell.providers.windows.arm_wifi_feedback import ADDRESS,PATH,MAC,probe
from test_arrival_wizard_service import make_service,_run,_ticket


@pytest.fixture
def wire(monkeypatch):
    now=[1.];sent=[]
    body=json.dumps(dict(T=1051,b=0,s=0,e=1,t=0,r=0,g=3)).encode()
    response=b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
    class Socket:
        chunks=[response];closed=False
        def setblocking(self,value):assert value is False
        def connect_ex(self,address):assert address==(ADDRESS,80);return 0
        def getsockopt(self,*args):return 0
        def send(self,value):sent.append(bytes(value));return len(value)
        def recv(self,count):return self.chunks.pop(0) if self.chunks else b''
        def close(self):self.closed=True
    sock=Socket()
    def ready(r,w,e,timeout):now[0]+=.01;return r,w,[]
    monkeypatch.setattr(native.socket,'socket',lambda *a:sock)
    monkeypatch.setattr(native.select,'select',ready)
    def connection():return native.DeadlineFeedbackConnection(ADDRESS,clock=lambda:now[0])
    return now,sent,sock,connection


def test_bounded_original_feedback_and_cleanup(wire):
    now,sent,sock,factory=wire
    report=probe(identity=lambda:MAC,connection_factory=lambda *a,**k:factory(),
        clock=lambda:now[0],retain_response=True)
    assert report['status']=='SUCCEEDED' and sock.closed and len(sent)==1
    assert sent[0].startswith(('GET '+PATH+' HTTP/1.1').encode())


def test_trickled_headers_cannot_extend_absolute_deadline(wire):
    now,sent,sock,factory=wire
    sock.chunks=[b'H']*200
    c=factory()
    try:
        c.request('GET',PATH)
        with pytest.raises(TimeoutError):c.getresponse()
        assert now[0]<1.82
        assert len(sent)==1
    finally:c.close()


@pytest.mark.parametrize('response',[
    b'HTTP/1.1 302 Found\r\nContent-Length: 1\r\n\r\nx',
    b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\nx',
    b'HTTP/1.1 200 OK\r\nContent-Length: 9999\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nx',
])
def test_framing_failures_no_retry(wire,response):
    now,sent,sock,factory=wire;sock.chunks=[response]
    report=probe(identity=lambda:MAC,connection_factory=lambda *a,**k:factory())
    assert report['status']=='FAILED' and len(sent)==1 and sock.closed


def test_motion_path_and_repeated_request_rejected(wire):
    now,sent,sock,factory=wire;c=factory()
    with pytest.raises(ValueError):c.request('GET','/js?json={"T":101}')
    assert not sent
    c.request('GET',PATH)
    with pytest.raises(ValueError):c.request('GET',PATH)
    c.close()


def test_cancel_before_connect(wire):
    now,sent,sock,factory=wire
    c=native.DeadlineFeedbackConnection(ADDRESS,cancelled=lambda:True)
    with pytest.raises(ValueError,match='CANCELLED'):c.request('GET',PATH)
    assert not sent


def test_trickled_body_uses_same_deadline(wire):
    now,sent,sock,factory=wire
    sock.chunks=[b'HTTP/1.1 200 OK\r\nContent-Length: 200\r\n\r\n']+[b'x']*200
    c=factory()
    try:
        c.request('GET',PATH)
        with pytest.raises(TimeoutError):c.getresponse()
        assert now[0]<1.82
    finally:c.close()


def test_connect_stall_is_bounded(wire,monkeypatch):
    now,sent,sock,factory=wire
    def idle(r,w,e,timeout):now[0]+=timeout;return [],[],[]
    monkeypatch.setattr(native.select,'select',idle)
    c=factory()
    try:
        with pytest.raises(TimeoutError):c.request('GET',PATH)
        assert not sent and now[0]<1.83
    finally:c.close()


def test_expired_or_invalid_deadline_never_sends(wire):
    now,sent,sock,factory=wire
    with pytest.raises(ValueError):native.DeadlineFeedbackConnection(ADDRESS,deadline=float('nan'))
    c=native.DeadlineFeedbackConnection(ADDRESS,deadline=.9,clock=lambda:now[0])
    with pytest.raises(TimeoutError):c.request('GET',PATH)
    assert not sent


def test_wizard_preview_is_inert_and_result_exports(make_service,monkeypatch):
    from test_arm_wifi_spaced import simulate
    report,_=simulate(intermediate=True);calls=[]
    def run(**kw):calls.append(1);return report
    monkeypatch.setattr(native,'observe_bounded',run)
    service,runner,_=make_service(mode='physical')
    _ticket(service,'observe_arm_wifi_bounded',{})
    assert not calls
    assert _run(service,'observe_arm_wifi_bounded')['status']=='SUCCEEDED'
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert calls==[1] and not runner.calls
