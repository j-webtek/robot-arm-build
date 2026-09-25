import pytest
from rocell.application.shoulder_session_http import ShoulderSessionHTTP


class Socket:
    def __init__(self,reply,fail=False):self.reply=reply;self.fail=fail;self.sent=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def settimeout(self,t):assert 0<t<=3
    def connect(self,address):assert address==('127.0.0.1',80)
    def sendall(self,data):
        self.sent.append(data)
        if self.fail:raise TimeoutError('Uncertain send')
    def recv(self,n):data=self.reply[:n];self.reply=self.reply[n:];return data


@pytest.mark.parametrize('failure',[None,'send','redirect','truncated','encoding'])
def test_fixed_transport_latches_failures_without_retry(failure):
    reply=b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}'
    if failure=='redirect':reply=reply.replace(b'200 OK',b'302 Found')
    if failure=='truncated':reply=reply[:-1]
    if failure=='encoding':reply=reply.replace(b'Content-Length',b'Transfer-Encoding: chunked\r\nContent-Length')
    sock=Socket(reply,failure=='send');opened=[]
    def factory(*args):opened.append(1);return sock
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=factory)
    if failure:
        with pytest.raises((OSError,ValueError)):adapter('POST','/rocell/shoulder-session/prepare',b'',1)
    else:assert adapter('POST','/rocell/shoulder-session/prepare',b'',1)==b'{}'
    with pytest.raises(ValueError):adapter('POST','/rocell/shoulder-session/prepare',b'',1)
    assert len(opened)==1 and len(sock.sent)==1


def test_arbitrary_command_route_cannot_open_socket():
    def forbidden(*args):raise AssertionError('Must not open socket')
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=forbidden)
    with pytest.raises(ValueError):adapter('POST','/js',b'{}',1)


def test_settling_routes_require_explicit_capability():
    def forbidden(*args):raise AssertionError('Must not open socket')
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=forbidden)
    with pytest.raises(ValueError):adapter('GET','/rocell/shoulder-settling/status',b'',1)


def test_local_routes_require_explicit_capability():
    def forbidden(*args):raise AssertionError('Must not open socket')
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=forbidden)
    with pytest.raises(ValueError):adapter('GET','/rocell/local-step/status',b'',1)


def test_local_authorization_has_distinct_bounded_body_budget():
    reply=b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}'
    sock=Socket(reply)
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=lambda *args:sock,local_step_capability=True)
    assert adapter('POST','/rocell/local-step/authorize',b'0'*2000,1)==b'{}'
    def forbidden(*args):raise AssertionError('No oversized request')
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=forbidden,local_step_capability=True)
    with pytest.raises(ValueError):adapter('POST','/rocell/local-step/authorize',b'0'*4402,1)


def test_parent_and_settling_start_have_separate_one_use_slots():
    opened=[]
    def factory(*args):
        sock=Socket(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}')
        opened.append(sock);return sock
    adapter=ShoulderSessionHTTP('127.0.0.1',socket_factory=factory,settling_capability=True)
    for path in ('/rocell/shoulder-session/start','/rocell/shoulder-settling/start'):
        assert adapter('POST',path,b'0'*248,1)==b'{}'
    with pytest.raises(ValueError):adapter('POST','/rocell/shoulder-settling/start',b'0'*248,1)
    assert len(opened)==2
