"""Recovery transport and export fault tests, localhost only."""
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
import pytest
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from pathlib import Path

KEY=bytes(range(32)); BOOT='11'*16; CAMPAIGN='22'*32


@pytest.mark.parametrize('mode', ['valid','disconnect','truncated','duplicate','tamper',
    'deadline','identity','export_failure'])
def test_one_shot_recovery(mode, tmp_path, monkeypatch):
    calls=[]; stop=Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request=bytes.fromhex(self.rfile.read(int(self.headers['Content-Length'])).decode())
            calls.append(self.path)
            body=json.dumps(dict(boot=BOOT, campaign='33'*32 if mode=='identity' else CAMPAIGN)).encode()
            signature=hmac.digest(KEY,b'RCCRECOVERYRESPONSE01\0'+bytes.fromhex(BOOT)+request[:32]
                +(200).to_bytes(2,'big')+hashlib.sha256(body).digest(),'sha256').hex()
            try:
                if mode=='disconnect':
                    self.close_connection=True; return
                if mode=='deadline': stop.wait(0.35)
                self.send_response(200)
                self.send_header('Content-Length',str(len(body)))
                self.send_header('X-Rocell-Signature',signature)
                if mode=='duplicate': self.send_header('X-Rocell-Signature',signature)
                self.end_headers()
                if mode=='tamper': body=b'x'+body[1:]
                self.wfile.write(body[:-1] if mode=='truncated' else body)
            except OSError:
                pass

        def log_message(self, *args): pass

    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
    thread.start()
    reader=CharacterizationRecoveryHTTP('127.0.0.1',server.server_port,key=KEY,boot=BOOT,campaign=CAMPAIGN)
    if mode=='export_failure':
        def fail(*args, **kwargs): raise OSError('Injected disk failure')
        monkeypatch.setattr(WizardDiagnosticExporter,'export',fail)
    try:
        if mode=='valid':
            saved=reader.read_and_export(tmp_path/'exports')
            assert verify_export(Path(saved['export_path']))['valid']
            assert not saved['resume_allowed']
        else:
            with pytest.raises((ValueError,OSError)):
                reader.read_and_export(tmp_path/'exports',timeout=0.15 if mode=='deadline' else 3)
        with pytest.raises(ValueError): reader.read_and_export(tmp_path/'exports')
        assert calls==['/rocell/characterization/recovery-read']
    finally:
        stop.set(); server.shutdown(); server.server_close(); thread.join(timeout=2)
