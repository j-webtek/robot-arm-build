"""Reviewed-hover HTTP allowlist exercised only on loopback."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_request_auth import sign_request
from rocell.application.reviewed_hover_manifest import (
    decode_reviewed_hover_start, encode_reviewed_hover_start, ghost_key_manifest,
)
from rocell.application.reviewed_hover_live_admission import encode_live_admission


KEY = bytes(range(32))
BOOT = "ab" * 16
START = encode_reviewed_hover_start(ghost_key_manifest())
RELEASE = "12" * 32


def test_offline_start_cannot_be_sent_to_arm_address():
    client = CharacterizationHTTP("192.168.0.225", 80, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match="loopback-only"):
        client("POST", "/rocell/reviewed-hover/start", START)
    assert client.session.stopped


def test_live_start_requires_fresh_exact_boot_release_and_recipe(monkeypatch):
    calls = []
    def network_reached(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("fake network boundary")
    monkeypatch.setattr("rocell.application.characterization_http.socket.socket", network_reached)
    body = encode_live_admission(ghost_key_manifest(), boot=BOOT,
        release_sha256=RELEASE, authorize_noncontact_motion=True)
    for rejected in (START, body.replace(BOOT.encode(), ("cd" * 16).encode()),
                     body.replace(RELEASE.encode(), ("34" * 32).encode())):
        client = CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT,
            reviewed_hover_live_release_sha256=RELEASE)
        with pytest.raises(ValueError):
            client("POST", "/rocell/reviewed-hover/start", rejected)
    assert not calls
    with pytest.raises(ValueError, match="Fresh exact"):
        CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT,
            read_only_initial_sequence=1,
            reviewed_hover_live_release_sha256=RELEASE)
    client = CharacterizationHTTP("192.168.0.225", key=KEY, boot=BOOT,
        reviewed_hover_live_release_sha256=RELEASE)
    with pytest.raises(RuntimeError, match="fake network boundary"):
        client("POST", "/rocell/reviewed-hover/start", body)
    assert calls == [True]
    assert client.session.stopped


@pytest.mark.parametrize("path,method,body", [
    ("/rocell/reviewed-hover/start", "POST", b"RCHM1:01:01:" + b"0" * 64),
    ("/rocell/reviewed-hover/start", "POST", START[:-1]),
    ("/rocell/reviewed-hover/start", "POST", START.replace(b":10:", b":11:")),
    ("/rocell/reviewed-hover/next", "POST", b"17"),
    ("/rocell/reviewed-hover/receipt", "POST", b"17:" + b"a" * 64),
    ("/rocell/reviewed-hover/status", "GET", b"payload"),
    ("/rocell/reviewed-hover/delete", "POST", b"x"),
])
def test_invalid_reviewed_hover_requests_rejected_before_network(path, method, body):
    client = CharacterizationHTTP("127.0.0.1", 1, key=KEY, boot=BOOT)
    with pytest.raises(ValueError):
        client(method, path, body)
    assert client.session.stopped


def test_exact_start_decoder_rejects_digest_and_unreviewed_edges():
    assert decode_reviewed_hover_start(START) == ghost_key_manifest()
    with pytest.raises(ValueError, match="digest"):
        decode_reviewed_hover_start(START[:-1] + b"0")
    with pytest.raises(ValueError):
        decode_reviewed_hover_start(b"RCHM1:01:05:" + b"0" * 64)


def test_loopback_signed_start_status_record_and_receipt():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.respond()

        def do_GET(self):
            self.respond()

        def respond(self):
            method = self.command
            body = self.rfile.read(int(self.headers["Content-Length"]))
            sequence = len(calls)
            assert self.headers["X-Rocell-Sequence"] == str(sequence)
            assert self.headers["X-Rocell-Signature"] == sign_request(
                key=KEY, boot=BOOT, sequence=sequence, method=method,
                path=self.path, body=body).hex()
            calls.append((method, self.path, body))
            reply = {
                "start": b"CAPTURING_START",
                "status": b"AWAITING_EXPORT|1",
                "record": b"ab" * 1163,
                "receipt": b"READY|2",
                "next": b"CAPTURING_START",
            }[self.path.rsplit("/", 1)[-1]]
            unsigned = (b"RCCRESPONSE01\0" + bytes.fromhex(BOOT) +
                        sequence.to_bytes(4, "big") + (200).to_bytes(2, "big") +
                        hashlib.sha256(reply).digest())
            self.send_response(200)
            self.send_header("Content-Length", str(len(reply)))
            self.send_header("X-Rocell-Sequence", str(sequence))
            self.send_header("X-Rocell-Signature", hmac.digest(KEY, unsigned, "sha256").hex())
            self.end_headers()
            self.wfile.write(reply)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = CharacterizationHTTP("127.0.0.1", server.server_port,
                                  key=KEY, boot=BOOT)
    prefix = "/rocell/reviewed-hover/"
    try:
        assert client("POST", prefix + "start", START) == b"CAPTURING_START"
        assert client("GET", prefix + "status") == b"AWAITING_EXPORT|1"
        assert client("GET", prefix + "record") == b"ab" * 1163
        assert client("POST", prefix + "receipt", b"1:" + b"a" * 64) == b"READY|2"
        assert client("POST", prefix + "next", b"2") == b"CAPTURING_START"
        assert len(calls) == 5
        assert not client.session.stopped
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_loopback_lost_receipt_reply_latches_uncertain_continuation():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            calls.append(body)
            assert self.path == "/rocell/reviewed-hover/receipt"
            assert self.headers["X-Rocell-Signature"] == sign_request(
                key=KEY, boot=BOOT, sequence=0, method="POST",
                path=self.path, body=body).hex()
            self.close_connection = True

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = CharacterizationHTTP("127.0.0.1", server.server_port,
                                  key=KEY, boot=BOOT)
    receipt = b"1:" + b"a" * 64
    try:
        with pytest.raises((OSError, ValueError)):
            client("POST", "/rocell/reviewed-hover/receipt", receipt)
        assert calls == [receipt]
        assert client.session.stopped
        assert client.session.uncertainty["continuation_may_have_been_authorized"]
        assert not client.session.uncertainty["retry_allowed"]
        with pytest.raises(ValueError):
            client("POST", "/rocell/reviewed-hover/next", b"2")
        assert calls == [receipt]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
