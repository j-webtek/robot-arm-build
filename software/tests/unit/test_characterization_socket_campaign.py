"""Real loopback HTTP -> native routes -> fake servo bus -> real disk exports."""
import json
import hashlib
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from test_characterization_composition import binary
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_challenge import decode_challenge
from rocell.application.characterization_admission import sign_campaign
from rocell.application.characterization_host_session import CharacterizationHostSession
from rocell.application.characterization_record_transfer import RecordTransfer
from rocell.application.wizard_diagnostic_export import verify_export
from pathlib import Path

KEY = bytes(range(32))
BOOT = '11'*16
PREFIX = '/rocell/characterization/'


class NativeHTTPRelay:
    def __init__(self, binary, pattern, drop_receipt=False, hypothesis=None):
        args=[str(binary), pattern, 'rpc']+([hypothesis] if hypothesis else [])
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.calls = []
        self.errors = []
        self.writes_after_lost_ack = None
        self.receipt_digest = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.exchange()

            def do_POST(self):
                self.exchange()

            def exchange(self):
                try:
                    body = self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode()
                    owner.calls.append(self.path)
                    if self.path == PREFIX+'status':
                        owner.rpc('TICK 1')
                    sequence = self.headers['X-Rocell-Sequence']
                    signature = self.headers['X-Rocell-Signature']
                    response = owner.rpc(f'CALL {self.path} {sequence} {signature} {body or "-"}')
                    status, seq, sig, payload = response.split()
                    payload = b'' if payload == '-' else bytes.fromhex(payload)
                    if drop_receipt and self.path == PREFIX+'receipt' and status == '200':
                        owner.receipt_digest = hashlib.sha256(bytes.fromhex(body)).hexdigest()
                        # Controller accepted the receipt, but the host never sees its ACK.
                        owner.writes_after_lost_ack = int(owner.rpc('TICK 20'))
                        self.close_connection = True
                        return
                    self.send_response(int(status))
                    self.send_header('Content-Length', str(len(payload)))
                    if seq != '-': self.send_header('X-Rocell-Sequence', seq)
                    if sig != '-': self.send_header('X-Rocell-Signature', sig)
                    self.end_headers(); self.wfile.write(payload)
                except Exception as error:
                    owner.errors.append(repr(error))
                    self.close_connection = True

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever,
                             kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()

    def rpc(self, line):
        self.process.stdin.write(line+'\n'); self.process.stdin.flush()
        reply = self.process.stdout.readline().strip()
        if not reply:
            raise AssertionError(self.process.stderr.read())
        return reply

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        finally:
            if self.process.poll() is None:
                self.process.kill(); self.process.wait(timeout=5)
        assert not self.errors
        assert self.process.returncode == 0


def run_offline_campaign(client, root, expected_position=2414):
    """Test orchestration only. No hardware entry point or live release."""
    client('POST', PREFIX+'prepare')

    def until(expected):
        for _ in range(80):
            state = json.loads(client('GET', PREFIX+'status'))
            if state['state'] == expected:
                return state
            assert state['state'] != 'FAULT', state
        raise AssertionError('Bounded polling exhausted')

    until('AWAITING_AUTHORIZATION')
    decoded = decode_challenge(bytes.fromhex(client('GET', PREFIX+'challenge').decode()),
                               expected_boot=BOOT)
    from rocell.application.characterization_reference import export_reference
    reference=bytes.fromhex(client('GET',PREFIX+'reference').decode())
    saved_reference=export_reference(root.parent/'references',reference,expected_sha256=decoded['reference'])
    assert len(saved_reference['reference']['poses'])==3
    assert saved_reference['reference']['poses'][-1]['joints'][1]['position']==expected_position
    token = sign_campaign(decoded['manifest'], decoded['challenge'], KEY,
                          campaign=decoded['campaign'], reference=decoded['reference'])
    assert client('POST', PREFIX+'start', token.hex().encode()) == b'01'
    host = CharacterizationHostSession(root, decoded['manifest'], key=KEY, boot=BOOT,
                                      campaign=decoded['campaign'], reference=decoded['reference'])
    saved = []
    for leg in range(len(decoded['manifest']['goals'])):
        until('AWAITING_EXPORT')
        info = bytes.fromhex(client('GET', PREFIX+'record-info').decode())
        assert len(info) == 35 and info[0] == leg
        size = int.from_bytes(info[1:3], 'big')
        transfer = RecordTransfer(boot=BOOT, campaign=decoded['campaign'], leg=leg,
                                  size=size, sha256=info[3:].hex())
        offset = 0
        while offset < size:
            request = bytes([leg])+offset.to_bytes(2, 'big')+info[3:]
            chunk = bytes.fromhex(client('POST', PREFIX+'record-chunk', request.hex().encode()).decode())
            transfer.append(boot=BOOT, campaign=decoded['campaign'], leg=leg, offset=offset, data=chunk)
            offset += len(chunk)
        result = host.export_and_sign(transfer.finish(), source_boot=BOOT,
                                      source_campaign=decoded['campaign'])
        assert verify_export(Path(result['export_path']))['valid']
        saved.append(result['export_path'])
        assert client('POST', PREFIX+'receipt', result['receipt'].hex().encode()) == b'01'
    until('COMPLETE')
    return saved


@pytest.mark.parametrize('pattern', ['legacy', 'matched', 'smoke'])
def test_complete_campaign_through_real_socket(binary, tmp_path, pattern):
    relay = NativeHTTPRelay(binary, pattern)
    client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
    try:
        count = 1 if pattern == 'smoke' else 12
        assert len(run_offline_campaign(client, tmp_path/'exports')) == count
        assert relay.calls.count(PREFIX+'receipt') == count
        assert int(relay.rpc('TICK 100')) == count
    finally:
        relay.close()


def test_lost_receipt_ack_is_not_a_controller_stop(binary, tmp_path):
    relay = NativeHTTPRelay(binary, 'matched', drop_receipt=True)
    client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
    try:
        with pytest.raises((ValueError, OSError)):
            run_offline_campaign(client, tmp_path/'exports')
        assert client.session.stopped
        calls = len(relay.calls)
        with pytest.raises(ValueError):
            client('GET', PREFIX+'status')
        assert len(relay.calls) == calls
        assert relay.calls.count(PREFIX+'receipt') == 1
        assert len(list((tmp_path/'exports').glob('wizard-*'))) == 1
        # Exposure test: accepted receipt advances the controller despite lost ACK.
        # Never equate a stopped host session with cancellation of device motion.
        assert relay.writes_after_lost_ack == 2
        assert client.session.uncertainty['continuation_may_have_been_authorized']
        assert not client.session.uncertainty['controller_stop_confirmed']
        snapshot = json.loads(relay.rpc('SNAPSHOT'))
        assert snapshot['completed'] == 1
        assert snapshot['retained_leg'] == 1
        assert snapshot['phase'] == 'AWAITING_EXPORT'
        assert len(snapshot['last_receipt_sha256']) == 64
        assert snapshot['last_receipt_sha256'] == relay.receipt_digest
        assert snapshot['retained_size'] > 0
        # Let the native export deadline expire without another receipt. The
        # already admitted second leg must not become a third write.
        for _ in range(3):
            assert int(relay.rpc('TICK 100')) == 2
        fault_snapshot = json.loads(relay.rpc('SNAPSHOT'))
        assert fault_snapshot['phase'] == 'FAULT'
        assert fault_snapshot['completed'] == 1
        assert fault_snapshot['retained_sha256'] == snapshot['retained_sha256']
        assert fault_snapshot['last_receipt_sha256'] == snapshot['last_receipt_sha256']
        from rocell.application.characterization_reconciliation import assess_receipt_reconciliation
        review = assess_receipt_reconciliation(expected_boot=BOOT,
            expected_campaign=snapshot['campaign'], exported_leg=0,
            receipt_sha256=relay.receipt_digest, snapshot=fault_snapshot)
        assert review['state'] == 'RECEIPT_ACCEPTED_NEXT_LEG_POSSIBLE'
        assert not review['resume_allowed']
        # Independent authentication works despite the stopped command session.
        # This test-only transport is localhost; no live recovery client exists.
        import http.client
        from rocell.application.characterization_recovery_auth import RecoveryRead
        recovery = RecoveryRead(key=KEY, boot=BOOT)
        connection = http.client.HTTPConnection('127.0.0.1', relay.server.server_port, timeout=2)
        try:
            connection.request('POST', PREFIX+'recovery-read', recovery.request_body())
            response = connection.getresponse()
            raw = response.read()
            signature = response.getheader('X-Rocell-Signature')
            verified = recovery.verify(status=response.status, body=raw, signature=signature)
            assert json.loads(verified) == fault_snapshot
            with pytest.raises(ValueError):
                recovery.verify(status=response.status, body=raw, signature=signature)
            other = RecoveryRead(key=KEY, boot=BOOT)
            with pytest.raises(ValueError):
                other.verify(status=response.status, body=raw, signature=signature)
        finally:
            connection.close()
        assert client.session.stopped
        assert int(relay.rpc('TICK 1')) == 2
        from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
        reader = CharacterizationRecoveryHTTP('127.0.0.1', relay.server.server_port,
            key=KEY, boot=BOOT, campaign=snapshot['campaign'])
        saved = reader.read_and_export(tmp_path/'recovery-exports')
        assert saved['snapshot'] == fault_snapshot
        assert verify_export(Path(saved['export_path']))['valid']
        assert not saved['resume_allowed']
        calls = len(relay.calls)
        with pytest.raises(ValueError):
            reader.read_and_export(tmp_path/'recovery-exports')
        assert len(relay.calls) == calls
    finally:
        relay.close()


def test_invalid_recovery_requests_do_not_consume_command_sequence(binary, tmp_path):
    from rocell.application.characterization_recovery_auth import RecoveryRead
    relay = NativeHTTPRelay(binary, 'matched')
    try:
        wrong_boot = RecoveryRead(key=KEY, boot='22'*16).request_body().decode()
        wrong_key = RecoveryRead(key=bytes(reversed(KEY)), boot=BOOT).request_body().decode()
        valid = RecoveryRead(key=KEY, boot=BOOT).request_body().decode()
        tampered = ('0' if valid[0] != '0' else '1')+valid[1:]
        for body, expected in [('00', '400'), ('z'*128, '400'),
                               (wrong_boot, '403'), (wrong_key, '403'), (tampered, '403')]:
            response = relay.rpc(f'CALL {PREFIX}recovery-read - - {body}')
            assert response.split()[0] == expected
        # A valid read before preparation is unavailable, not an initialization.
        assert relay.rpc(f'CALL {PREFIX}recovery-read - - {valid}').split()[0] == '409'
        assert relay.rpc('TICK 1') == '0'
        client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
        assert len(run_offline_campaign(client, tmp_path/'exports')) == 12
    finally:
        relay.close()


def test_smoke_lost_final_ack_has_no_successor(binary, tmp_path):
    relay = NativeHTTPRelay(binary, 'smoke', drop_receipt=True)
    client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
    try:
        with pytest.raises((ValueError, OSError)):
            run_offline_campaign(client, tmp_path/'exports')
        assert client.session.stopped
        assert relay.writes_after_lost_ack == 1
        for _ in range(3):
            assert relay.rpc('TICK 100') == '1'
        snapshot = json.loads(relay.rpc('SNAPSHOT'))
        assert snapshot['completed'] == 1
        assert snapshot['phase'] == 'COMPLETE'
        assert snapshot['retained_leg'] is None
        from rocell.application.characterization_reconciliation import assess_receipt_reconciliation
        review = assess_receipt_reconciliation(expected_boot=BOOT,
            expected_campaign=snapshot['campaign'], exported_leg=0, expected_legs=1,
            receipt_sha256=relay.receipt_digest, snapshot=snapshot)
        assert review['state'] == 'CAMPAIGN_COMPLETE'
        assert not review['resume_allowed']
        assert len(list((tmp_path/'exports').glob('wizard-*'))) == 1
    finally:
        relay.close()
