"""Loopback only: no discovery, live device access, or wizard startup changes."""
from contextlib import contextmanager
import socket
import threading

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_session_plan import SessionPlan
from rocell.application.servo_start_authorization import sign_start
from rocell.application.servo_diagnostic_start_http import DiagnosticStartSender, DiagnosticStartError
from test_servo_start_authorization import fixture
from test_servo_diagnostic_http import response

KEY=bytes(reversed(range(32)))  # Public test fixture, not provisioned anywhere.


def native_plan():
    plan,challenge=fixture();doc=plan.to_dict()
    doc.update(schema='rocell.session_plan.v3',origin='DEVICE_CAPTURE',whole_arm_policy=dict(
        joints=[[1900,2200]]*7,tracking_tolerance=2,maximum_pair_us=1000,
        maximum_scan_us=10000,maximum_age_us=10000))
    return SessionPlan(canonical(doc)),challenge


@contextmanager
def once_server(reply):
    requests=[];errors=[]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(2)
        port=listener.getsockname()[1]
        def serve():
            try:
                connection,_=listener.accept()
                with connection:
                    connection.settimeout(2);header=b''
                    while not header.endswith(b'\r\n\r\n'):
                        part=connection.recv(1)
                        if not part:raise AssertionError('Truncated request header')
                        header+=part
                        assert len(header)<=2048
                    lines=header[:-4].split(b'\r\n')
                    fields=dict(line.split(b': ',1) for line in lines[1:])
                    length=int(fields[b'Content-Length']);body=b''
                    while len(body)<length:
                        part=connection.recv(length-len(body))
                        if not part:raise AssertionError('Truncated request body')
                        body+=part
                    requests.append((lines,fields,body))
                    if reply:connection.sendall(reply)
            except Exception as error:errors.append(error)
        worker=threading.Thread(target=serve,daemon=True);worker.start()
        yield port,requests
        worker.join(3)
        assert not worker.is_alive() and not errors,errors


@pytest.mark.parametrize('status,accepted',[(b'202 Accepted',True),(b'400 Bad Request',False)])
def test_exact_signed_post_and_no_retry(status,accepted):
    plan,challenge=native_plan();body=canonical(dict(accepted=accepted,retry_allowed=False))
    with once_server(response(body,status=status)) as (port,requests):
        sender=DiagnosticStartSender('127.0.0.1',port)
        report=sender.send(plan,challenge,KEY)
        with pytest.raises(ValueError,match='consumed'):sender.send(plan,challenge,KEY)
    assert len(requests)==1
    lines,fields,token=requests[0]
    assert lines[0]==b'POST /rocell/diagnostics/start HTTP/1.1'
    assert set(fields)=={b'Host',b'Content-Length',b'Content-Type',b'Connection'}
    assert fields[b'Content-Type']==b'application/octet-stream' and fields[b'Connection']==b'close'
    assert token==sign_start(plan,challenge,KEY)
    assert report['result']==('CONTROLLER_REPORTED_ACCEPTANCE' if accepted else 'CONTROLLER_REPORTED_REJECTION')
    assert report['transmission_attempted'] and not report['retry_allowed']
    assert not report['progression_authority'] and not report['endpoint_verified']
    assert token.hex() not in str(report) and KEY.hex() not in str(report)


@pytest.mark.parametrize('reply',[
    b'',b'HTTP/1.1 202 Accepted\r\n',
    response(b'{}',status=b'302 Found'),
    response(b'{"accepted":false,"retry_allowed":false}',status=b'202 Accepted'),
    response(b'{"accepted":true,"retry_allowed":true}',status=b'202 Accepted'),
    response(b'{"accepted":true,"accepted":true,"retry_allowed":false}',status=b'202 Accepted'),
    response(b'{}',headers=b'Content-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2',status=b'202 Accepted'),
    response(b'{}',headers=b'Content-Type: application/json\r\nTransfer-Encoding: chunked',status=b'202 Accepted'),
])
def test_uncertain_responses_never_resend(reply):
    plan,challenge=native_plan()
    with once_server(reply) as (port,requests):
        sender=DiagnosticStartSender('127.0.0.1',port)
        with pytest.raises(DiagnosticStartError) as error:sender.send(plan,challenge,KEY)
        assert error.value.report['result']=='DELIVERY_UNCERTAIN'
        assert error.value.report['transmission_attempted']
        with pytest.raises(ValueError,match='consumed'):sender.send(plan,challenge,KEY)
    assert len(requests)==1


def test_invalid_preparation_has_no_network(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected socket')
    monkeypatch.setattr(socket,'socket',forbidden)
    plan,challenge=fixture()  # Simulation plan cannot enter the native sender.
    sender=DiagnosticStartSender('127.0.0.1',8081)
    with pytest.raises(DiagnosticStartError) as error:sender.send(plan,challenge,KEY)
    assert error.value.report['result']=='PREPARATION_REJECTED'
    assert not error.value.report['connection_attempted']
    with pytest.raises(ValueError,match='consumed'):sender.send(plan,challenge,KEY)


@pytest.mark.parametrize('stage',['connect','send'])
def test_connection_and_partial_send_failures_are_one_attempt(monkeypatch,stage):
    calls=[]
    class BrokenSocket:
        def __enter__(self):return self
        def __exit__(self,*args):calls.append('closed')
        def settimeout(self,value):assert 0<value<=10
        def connect(self,address):
            calls.append('connect')
            if stage=='connect':raise ConnectionRefusedError()
        def sendall(self,data):
            calls.append('send')
            raise TimeoutError()  # Could occur after only part of the token left.
    monkeypatch.setattr(socket,'socket',lambda *args:BrokenSocket())
    plan,challenge=native_plan();sender=DiagnosticStartSender('127.0.0.1',8081)
    with pytest.raises(DiagnosticStartError) as error:sender.send(plan,challenge,KEY)
    assert error.value.report['transmission_attempted']==(stage=='send')
    assert error.value.report['connection_attempted']
    with pytest.raises(ValueError,match='consumed'):sender.send(plan,challenge,KEY)
    assert calls==(['connect','closed'] if stage=='connect' else ['connect','send','closed'])
