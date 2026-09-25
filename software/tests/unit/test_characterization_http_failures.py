"""Real loopback sockets only: no controller address or physical motion.

The server records received POSTs before failing, modeling the important case
where delivery occurred but its acknowledgement was lost.
"""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread, Event

import pytest

from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_request_auth import sign_request

KEY = bytes(range(32))
BOOT = '11'*16
PATH = '/rocell/characterization/start'


def response_signature(sequence, body):
    raw = (b'RCCRESPONSE01\0'+bytes.fromhex(BOOT)+sequence.to_bytes(4, 'big')
           +(200).to_bytes(2, 'big')+hashlib.sha256(body).digest())
    return hmac.digest(KEY, raw, 'sha256').hex()


class Server:
    def __init__(self, mode):
        self.calls = []
        self.errors = []
        self.stop = Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                sequence = int(self.headers['X-Rocell-Sequence'])
                owner.calls.append((self.path, sequence, body))
                expected = sign_request(key=KEY, boot=BOOT, sequence=sequence,
                                        method='POST', path=self.path, body=body).hex()
                if self.headers['X-Rocell-Signature'] != expected:
                    owner.errors.append('Request signature mismatch')
                reply = b'01'
                try:
                    if mode == 'disconnect':
                        self.close_connection = True
                        return
                    if mode in ('late_header', 'delayed_valid'):
                        owner.stop.wait(0.35)
                    if mode == 'cumulative_deadline':
                        owner.stop.wait(0.10)
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(reply)))
                    self.send_header('X-Rocell-Sequence', str(sequence))
                    signature = response_signature(sequence, reply)
                    self.send_header('X-Rocell-Signature', signature)
                    if mode == 'duplicate_cache':
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    if mode in ('late_body', 'cumulative_deadline'):
                        self.wfile.write(reply[:1]); self.wfile.flush()
                        owner.stop.wait(0.10 if mode == 'cumulative_deadline' else 0.35)
                    elif mode == 'truncated':
                        self.wfile.write(reply[:1]); self.wfile.flush()
                        self.close_connection = True
                        return
                    elif mode == 'bad_body':
                        reply = b'00'
                    if mode in ('late_body', 'cumulative_deadline'):
                        self.wfile.write(reply[1:])
                    else:
                        self.wfile.write(reply)
                except OSError:
                    # Expected when the client has already timed out and closed.
                    pass

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever,
                             kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()

    def client(self):
        return CharacterizationHTTP('127.0.0.1', self.server.server_port, key=KEY, boot=BOOT)

    def close(self):
        self.stop.set()
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        assert not self.thread.is_alive()
        assert not self.errors


@pytest.mark.parametrize('mode', ['disconnect', 'truncated', 'late_header', 'late_body', 'bad_body', 'cumulative_deadline'])
def test_received_post_with_unusable_ack_never_retries(mode):
    server = Server(mode)
    client = server.client()
    try:
        with pytest.raises((OSError, ValueError)):
            client('POST', PATH, b'00', timeout=0.15)
        assert client.session.stopped
        with pytest.raises(ValueError):
            client('POST', PATH, b'00', timeout=0.15)
        # Also reject a different follow-on operation, not just an identical retry.
        with pytest.raises(ValueError):
            client('GET', '/rocell/characterization/status')
        assert server.calls == [(PATH, 0, b'00')]
    finally:
        server.close()


def test_delay_beyond_250ms_accepted_within_explicit_budget():
    server = Server('delayed_valid')
    client = server.client()
    try:
        for sequence in range(2):
            assert client('POST', PATH, b'00', timeout=2) == b'01'
            assert not client.session.stopped
        assert [call[1] for call in server.calls] == [0, 1]
    finally:
        server.close()


def test_esp32_duplicate_no_store_does_not_break_authenticated_response():
    server = Server('duplicate_cache')
    try:
        assert server.client()('POST', PATH, b'00') == b'01'
        assert len(server.calls) == 1
    finally:
        server.close()
