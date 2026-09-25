"""Loopback-only integration tests; never contact the arm or open serial ports."""
from contextlib import contextmanager
from pathlib import Path
import socket
import threading
import time

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
from rocell.application.servo_transport_export import capture_transport_export, replay_transport_export
from rocell.application.servo_transport_snapshot import STATUS


def response(body=b'{}', headers=None, status=b'200 OK'):
    if headers is None:
        headers=b'Content-Type: application/json\r\nContent-Length: '+str(len(body)).encode()
    return b'HTTP/1.1 '+status+b'\r\n'+headers+b'\r\n\r\n'+body


@contextmanager
def server(responses, *, delay=0):
    requests=[];errors=[]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(2)
        port=listener.getsockname()[1]
        def serve():
            try:
                for raw in responses:
                    connection,_=listener.accept()
                    with connection:
                        connection.settimeout(2);request=b''
                        while not request.endswith(b'\r\n\r\n'):
                            chunk=connection.recv(1024)
                            if not chunk:raise AssertionError('Incomplete test request')
                            request+=chunk
                        requests.append(request)
                        if delay:
                            for byte in raw:
                                connection.sendall(bytes([byte]));time.sleep(delay)
                        else:connection.sendall(raw)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
                pass  # Expected when the bounded client aborts a response.
            except Exception as error:errors.append(error)
        worker=threading.Thread(target=serve,daemon=True);worker.start()
        yield port,requests
        worker.join(3)
        assert not worker.is_alive() and not errors,errors


def read(reader,**kwargs):
    return reader(STATUS,maximum_bytes=512,timeout_seconds=kwargs.get('timeout',1))


def test_real_socket_collection_export_and_replay(tmp_path,monkeypatch):
    body=canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='a'*32,
        state='IDLE',reason='NONE',records=0,storage_fault=False,start_supported=False,
        durable_export_verified=False))
    # Proxy environment variables must never route the evidence elsewhere.
    monkeypatch.setenv('HTTP_PROXY','http://127.0.0.1:1')
    with server([response(body),response(body)]) as (port,requests):
        reader=DiagnosticHTTPReader('127.0.0.1',port)
        result=capture_transport_export(tmp_path,reader)
        assert result['export_verified'] and result['replay_verified']
        assert replay_transport_export(tmp_path,Path(result['export_path']).name)['matches']
        assert len(requests)==2 and not reader.failed
        assert all(request.startswith(b'GET '+STATUS.encode()+b' HTTP/1.0\r\n') for request in requests)
        assert not result['progression_authority']


@pytest.mark.parametrize('raw',[
    response(status=b'302 Found',headers=b'Location: http://127.0.0.1/js'),
    response(status=b'404 Not Found'),
    response(headers=b'Content-Type: text/html\r\nContent-Length: 2'),
    response(headers=b'Content-Type: application/json\r\nContent-Length: 513'),
    response(headers=b'Content-Type: application/json'),
    response(headers=b'Content-Type: application/json\r\nContent-Length: 5'),
    response(headers=b'Content-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2'),
    response(headers=b'Content-Type: application/json\r\nContent-Length: 2\r\nTransfer-Encoding: chunked'),
    response(headers=b'Content-Type: application/json\r\nContent-Length: 2\r\nContent-Encoding: gzip'),
    response(headers=b'Content-Type: application/json\r\nContent-Length: 2\r\n folded'),
    b'HTTP/1.1 200 OK\r\nX-Huge: '+b'x'*8192,
])
def test_protocol_failures_latch_without_retry_or_redirect(raw):
    with server([raw]) as (port,requests):
        reader=DiagnosticHTTPReader('127.0.0.1',port)
        with pytest.raises(ValueError):read(reader)
        assert reader.failed
        with pytest.raises(ValueError,match='faulted'):read(reader)
        assert len(requests)==1


def test_total_deadline_rejects_slow_trickle():
    with server([response()],delay=.015) as (port,requests):
        reader=DiagnosticHTTPReader('127.0.0.1',port)
        start=time.monotonic()
        with pytest.raises(TimeoutError):read(reader,timeout=.08)
        assert time.monotonic()-start<.6
        assert reader.failed and len(requests)==1


@pytest.mark.parametrize('address',['example.com','http://192.168.0.225','8.8.8.8','::1','0.0.0.0','224.0.0.1'])
def test_non_lan_or_non_numeric_destinations_rejected(address):
    with pytest.raises(ValueError):DiagnosticHTTPReader(address)


@pytest.mark.parametrize('path',['/js','/rocell/diagnostics/start','/rocell/diagnostics/record?index=16',
                                 '/rocell/diagnostics/record?index=01',STATUS+'\r\nPOST /js'])
def test_no_command_routes_or_request_injection(path,monkeypatch):
    monkeypatch.setattr(socket,'socket',lambda *a,**k:pytest.fail('Unexpected connection'))
    reader=DiagnosticHTTPReader('192.168.0.225')
    with pytest.raises(ValueError):reader(path,maximum_bytes=512,timeout_seconds=1)
    assert reader.failed
