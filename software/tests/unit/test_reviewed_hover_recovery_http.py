"""The recovery route cannot bypass the authenticated exact-body allowlist."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import hashlib
import hmac

import pytest

from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_request_auth import sign_request
from rocell.application.reviewed_hover_recovery_admission import (
    encode_recovery_admission, recovery_manifest,
)


KEY = bytes(range(32))
BOOT = "ab" * 16
RELEASE = "12" * 32
START = encode_recovery_admission(recovery_manifest(), boot=BOOT,
    release_sha256=RELEASE, authorize_noncontact_motion=True)
PREFIX = "/rocell/recovery-hover/"


def test_recovery_start_requires_fresh_exclusive_release_and_exact_body(monkeypatch):
    calls = []

    def network_reached(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("fake network boundary")

    monkeypatch.setattr("rocell.application.characterization_http.socket.socket",
                        network_reached)
    for rejected in (START[:-1],
                     START.replace(BOOT.encode(), ("cd" * 16).encode()),
                     START.replace(RELEASE.encode(), ("34" * 32).encode())):
        client = CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT,
            recovery_hover_live_release_sha256=RELEASE)
        with pytest.raises(ValueError):
            client("POST", PREFIX + "start", rejected)
        assert client.session.stopped
    assert calls == []
    for options in (dict(), dict(read_only_initial_sequence=1,
                                recovery_hover_live_release_sha256=RELEASE),
                    dict(recovery_hover_live_release_sha256=RELEASE,
                         reviewed_hover_live_release_sha256=RELEASE)):
        client_args = dict(options)
        if "recovery_hover_live_release_sha256" not in client_args:
            client = CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT)
            with pytest.raises(ValueError):
                client("POST", PREFIX + "start", START)
        else:
            with pytest.raises(ValueError):
                CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT,
                                     **client_args)
    assert calls == []
    client = CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT,
        recovery_hover_live_release_sha256=RELEASE)
    with pytest.raises(RuntimeError, match="fake network boundary"):
        client("POST", PREFIX + "start", START)
    assert calls == [True]


@pytest.mark.parametrize("path,method,body", [
    ("start", "POST", b"RCHR1:" + b"0" * 176),
    ("next", "POST", b"1"),
    ("next", "POST", b"6"),
    ("receipt", "POST", b"6:" + b"a" * 64),
    ("status", "GET", b"payload"),
    ("delete", "POST", b"x"),
])
def test_invalid_recovery_requests_rejected_before_network(path, method, body):
    client = CharacterizationHTTP("127.0.0.1", 1, key=KEY, boot=BOOT,
        recovery_hover_live_release_sha256=RELEASE)
    with pytest.raises(ValueError):
        client(method, PREFIX + path, body)
    assert client.session.stopped


def test_loopback_signed_recovery_exchange():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.respond()

        def do_GET(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            sequence = len(calls)
            assert self.headers["X-Rocell-Sequence"] == str(sequence)
            assert self.headers["X-Rocell-Signature"] == sign_request(
                key=KEY, boot=BOOT, sequence=sequence, method=self.command,
                path=self.path, body=body).hex()
            calls.append((self.command, self.path, body))
            reply = {"start": b"CAPTURING_START", "status": b"AWAITING_EXPORT|1",
                     "record": b"ab" * 1163, "receipt": b"READY|2",
                     "next": b"CAPTURING_START"}[self.path.rsplit("/", 1)[-1]]
            unsigned = (b"RCCRESPONSE01\0" + bytes.fromhex(BOOT) +
                        sequence.to_bytes(4, "big") + (200).to_bytes(2, "big") +
                        hashlib.sha256(reply).digest())
            self.send_response(200)
            self.send_header("Content-Length", str(len(reply)))
            self.send_header("X-Rocell-Sequence", str(sequence))
            self.send_header("X-Rocell-Signature",
                             hmac.digest(KEY, unsigned, "sha256").hex())
            self.end_headers()
            self.wfile.write(reply)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = CharacterizationHTTP("127.0.0.1", server.server_port,
        key=KEY, boot=BOOT, recovery_hover_live_release_sha256=RELEASE)
    try:
        assert client("POST", PREFIX + "start", START) == b"CAPTURING_START"
        assert client("GET", PREFIX + "status") == b"AWAITING_EXPORT|1"
        assert client("GET", PREFIX + "record") == b"ab" * 1163
        assert client("POST", PREFIX + "receipt", b"1:" + b"a" * 64) == b"READY|2"
        assert client("POST", PREFIX + "next", b"2") == b"CAPTURING_START"
        assert len(calls) == 5
        assert not client.session.stopped
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
