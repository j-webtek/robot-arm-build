import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import pytest
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_request_auth import sign_request

KEY=bytes(range(32));BOOT='11'*16


@pytest.mark.parametrize('mode',['valid','duplicate','tamper','redirect','missing'])
def test_real_loopback_exchange(mode):
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            expected=sign_request(key=KEY,boot=BOOT,sequence=0,method='GET',path=self.path).hex()
            assert self.headers['X-Rocell-Signature']==expected
            body=b'{}';status=302 if mode=='redirect' else 200
            unsigned=b'RCCRESPONSE01\0'+bytes.fromhex(BOOT)+bytes(4)+status.to_bytes(2,'big')+hashlib.sha256(body).digest()
            signature=hmac.digest(KEY,unsigned,'sha256').hex()
            self.send_response(status);self.send_header('Content-Length','2')
            if mode!='missing':self.send_header('X-Rocell-Sequence','0')
            if mode=='duplicate':self.send_header('X-Rocell-Sequence','0')
            self.send_header('X-Rocell-Signature','00'*32 if mode=='tamper' else signature)
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    client=CharacterizationHTTP('127.0.0.1',server.server_port,key=KEY,boot=BOOT)
    try:
        if mode=='valid':assert client('GET','/rocell/characterization/status')==b'{}'
        else:
            with pytest.raises(ValueError):client('GET','/rocell/characterization/status')
            with pytest.raises(ValueError):client('GET','/rocell/characterization/status')
        assert len(calls)==1
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_reanchor_transport_rejects_caller_targets_before_network():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Body not allowed'):
        client('POST', '/rocell/reanchor/start', b'2389,1725')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Invalid receipt length'):
        client('POST', '/rocell/reanchor/receipt', b'00')


def test_park_return_transport_rejects_caller_targets_before_network():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Body not allowed'):
        client('POST', '/rocell/park-return/start', b'2389,1725')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Invalid receipt length'):
        client('POST', '/rocell/park-return/receipt', b'00')


def test_sequence_resumed_client_cannot_send_movement():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT,
                                  read_only_initial_sequence=1)
    with pytest.raises(ValueError, match='read-only'):
        client('POST', '/rocell/park-step/start', b'2377,1737')
    assert client.session.stopped is True


def test_b_hover_transport_has_no_next_leg_or_caller_target():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-type-b-hover/next', b'2')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIRB1'):
        client('POST', '/rocell/air-type-b-hover/start', b'2098,2016,2609,2201')


def test_finale_transport_rejects_unreviewed_ordinal_and_target():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIR7'):
        client('POST', '/rocell/air-type-final/start', b'2111,2003')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-type-final/next', b'8')


def test_last_four_transport_rejects_unreviewed_ordinal_target_and_fault_write():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIR4'):
        client('POST', '/rocell/air-type-last/start', b'2047,2075')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-type-last/next', b'5')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-type-last/source-fault', b'anything')


def test_repeat_six_transport_rejects_unreviewed_selector_ordinal_and_fault_write():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIR6'):
        client('POST', '/rocell/air-type-repeat/start', b'2093,2021')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-type-repeat/next', b'7')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-type-repeat/source-fault', b'anything')


def test_elbow_direction_transport_rejects_unreviewed_selector_ordinal_and_fault_write():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIRE8'):
        client('POST', '/rocell/air-elbow-direction/start', b'2600')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-elbow-direction/next', b'9')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact leg'):
        client('POST', '/rocell/air-elbow-direction/receipt', b'9:'+b'ab'*32)
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-elbow-direction/source-fault', b'anything')


def test_elbow_shift_transport_rejects_unreviewed_selector_ordinal_and_fault_write():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIRH8'):
        client('POST', '/rocell/air-elbow-shift/start', b'2610')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-elbow-shift/next', b'9')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact leg'):
        client('POST', '/rocell/air-elbow-shift/receipt', b'9:'+b'ab'*32)
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-elbow-shift/source-fault', b'anything')


def test_elbow_grid_transport_rejects_unreviewed_selector_ordinal_and_fault_write():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIRG16'):
        client('POST', '/rocell/air-elbow-grid/start', b'2590')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-elbow-grid/next', b'17')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact leg'):
        client('POST', '/rocell/air-elbow-grid/receipt', b'17:'+b'ab'*32)
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-elbow-grid/source-fault', b'anything')


def test_multi_hover_transport_rejects_unreviewed_selector_ordinal_and_fault_write():
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact AIRM5'):
        client('POST', '/rocell/air-multi-hover/start', b'1994')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact next'):
        client('POST', '/rocell/air-multi-hover/next', b'6')
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Exact leg'):
        client('POST', '/rocell/air-multi-hover/receipt', b'6:'+b'ab'*32)
    client = CharacterizationHTTP('127.0.0.1', 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match='Unsupported'):
        client('POST', '/rocell/air-multi-hover/source-fault', b'anything')


@pytest.mark.parametrize('route,selector,invalid',[('/rocell/large-pose-lift/start',b'T1',b'P1'),
                                                   ('/rocell/large-pose-relief/start',b'P1',b'T1'),
                                                   ('/rocell/large-pose-relief/start',b'T4L',b'T5'),
                                                   ('/rocell/large-pose-relief/start',b'T4',b'T5'),
                                                   ('/rocell/large-pose-relief/start',b'P4E',b'P5'),
                                                   ('/rocell/large-pose-relief/start',b'P4',b'P5'),
                                                   ('/rocell/p4-repeat/start',b'P4R12',b'P4'),
                                                   ('/rocell/p4-repeat/next',b'2',b'13'),
                                                   ('/rocell/p4-repeat/receipt',b'1:'+b'ab'*32,b'00'),
                                                   ('/rocell/p4-correction/start',b'P4C16',b'P4R12'),
                                                   ('/rocell/p4-correction/next',b'16',b'17'),
                                                   ('/rocell/p4-correction/receipt',b'16:'+b'ab'*32,b'17:'+b'ab'*32),
                                                   ('/rocell/p4-midpoint/start',b'P4M16',b'P4C16'),
                                                   ('/rocell/p4-midpoint/next',b'16',b'17'),
                                                   ('/rocell/p4-midpoint/receipt',b'16:'+b'ab'*32,b'17:'+b'ab'*32),
                                                   ('/rocell/air-type-b-hover/start',b'AIRB1',b'AIR17'),
                                                   ('/rocell/air-type-b-hover/receipt',b'1:'+b'ab'*32,b'2:'+b'ab'*32),
                                                   ('/rocell/air-type-final/start',b'AIR7',b'AIRB1'),
                                                   ('/rocell/air-type-final/next',b'7',b'8'),
                                                   ('/rocell/air-type-final/receipt',b'7:'+b'ab'*32,b'8:'+b'ab'*32),
                                                   ('/rocell/air-type-last/start',b'AIR4',b'AIR7'),
                                                   ('/rocell/air-type-last/next',b'4',b'5'),
                                                   ('/rocell/air-type-last/receipt',b'4:'+b'ab'*32,b'5:'+b'ab'*32),
                                                   ('/rocell/air-type-repeat/start',b'AIR6',b'AIR4'),
                                                   ('/rocell/air-type-repeat/next',b'6',b'7'),
                                                   ('/rocell/air-type-repeat/receipt',b'6:'+b'ab'*32,b'7:'+b'ab'*32)])
def test_large_pose_start_is_exact_and_signed_over_loopback(route,selector,invalid):
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']))
            calls.append((self.path, body))
            assert body==selector
            assert self.headers['X-Rocell-Signature']==sign_request(
                key=KEY, boot=BOOT, sequence=0, method='POST', path=self.path,
                body=body).hex()
            answer=b'CAPTURING_START';status=200
            unsigned=(b'RCCRESPONSE01\0'+bytes.fromhex(BOOT)+bytes(4)
                      +status.to_bytes(2,'big')+hashlib.sha256(answer).digest())
            signature=hmac.digest(KEY,unsigned,'sha256').hex()
            self.send_response(status)
            self.send_header('Content-Length',str(len(answer)))
            self.send_header('X-Rocell-Sequence','0')
            self.send_header('X-Rocell-Signature',signature)
            self.end_headers();self.wfile.write(answer)
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        for bad in (b'',invalid,selector+b'\n'):
            client=CharacterizationHTTP('127.0.0.1',server.server_port,key=KEY,boot=BOOT)
            with pytest.raises(ValueError,match='Exact '):
                client('POST',route,bad)
        assert not calls
        client=CharacterizationHTTP('127.0.0.1',server.server_port,key=KEY,boot=BOOT)
        assert client('POST',route,selector)==b'CAPTURING_START'
        assert calls==[(route,selector)]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
