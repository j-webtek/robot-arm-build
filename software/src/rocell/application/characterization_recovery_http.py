"""One-shot recovery read/export. No command, admission or retry API.

Not exposed as a live CLI or wizard action until installed compatibility is
reviewed. A snapshot describes controller evidence, not freshly measured pose.
"""
import json
import math
import re
import socket
import time
from pathlib import Path

from .characterization_recovery_auth import RecoveryRead
from .servo_diagnostic_http import DiagnosticHTTPReader
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class CharacterizationRecoveryHTTP:
    def __init__(self, address, port=80, *, key, boot, campaign):
        checked = DiagnosticHTTPReader(address, port)
        from .servo_start_authorization import _hex
        _hex(campaign, 32)
        self.address, self.port = checked.address, checked.port
        self.boot, self.campaign = boot, campaign
        self._auth = RecoveryRead(key=key, boot=boot)
        self._used = False

    def read_and_export(self, root, *, timeout=3):
        if self._used:
            raise ValueError('Recovery attempt consumed; no automatic retry')
        self._used = True
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3:
            raise ValueError('Invalid recovery deadline')
        # Verify destination before issuing even a read. Export failure never
        # triggers another request or changes command-session state.
        exporter = WizardDiagnosticExporter(Path(root).resolve())
        exporter.prepare(create=True)
        body = self._auth.request_body()
        deadline = time.monotonic()+timeout

        def remaining():
            value = deadline-time.monotonic()
            if value <= 0:
                raise TimeoutError('Total recovery deadline')
            return value

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(remaining())
            connection.connect((self.address, self.port))
            wire = (f'POST /rocell/characterization/recovery-read HTTP/1.1\r\n'
                    f'Host: {self.address}:{self.port}\r\nContent-Length: {len(body)}\r\n'
                    'Content-Type: text/plain\r\nAccept-Encoding: identity\r\n'
                    'Connection: close\r\n\r\n').encode('ascii')+body
            connection.settimeout(remaining())
            connection.sendall(wire)

            def receive(count):
                connection.settimeout(remaining())
                data = connection.recv(count)
                remaining()
                if not data:
                    raise ValueError('Truncated recovery response')
                return data

            header = bytearray()
            while not header.endswith(b'\r\n\r\n'):
                if len(header) >= 4096:
                    raise ValueError('Recovery header budget')
                header.extend(receive(1))
            lines = bytes(header).decode('ascii').split('\r\n')
            match = re.fullmatch(r'HTTP/1\.[01] ([0-9]{3})(?: .*|)', lines[0])
            if not match:
                raise ValueError('Invalid recovery status')
            fields = {}
            for line in lines[1:-2]:
                name, separator, value = line.partition(':')
                name = name.lower()
                if not separator or name in fields or name.strip() != name:
                    raise ValueError('Invalid or duplicate recovery headers')
                fields[name] = value.strip()
            if 'transfer-encoding' in fields or fields.get('content-encoding', 'identity') != 'identity':
                raise ValueError('Unsupported recovery encoding')
            length = fields.get('content-length', '')
            if not re.fullmatch(r'0|[1-9][0-9]{0,2}', length) or int(length) > 639:
                raise ValueError('Invalid recovery length')
            raw = bytearray()
            while len(raw) < int(length):
                raw.extend(receive(int(length)-len(raw)))
        verified = self._auth.verify(status=int(match[1]), body=bytes(raw),
                                     signature=fields.get('x-rocell-signature'))
        remaining()
        snapshot = json.loads(verified)
        if (type(snapshot) is not dict or snapshot.get('boot') != self.boot
                or snapshot.get('campaign') != self.campaign):
            raise ValueError('Recovery identity mismatch')
        saved = exporter.export({'mode': 'authenticated-recovery-read',
            'resume_allowed': False, 'physical_pose_verified': False}, [], attachments={
                'recovery-snapshot.json': verified,
                'recovery-snapshot.hex.txt': verified.hex().encode('ascii'),
                'recovery-framing.json': json.dumps(dict(
                    request_hex=body.hex(), response_signature=fields['x-rocell-signature'],
                    status=int(match[1]), boot=self.boot, deadline_seconds=timeout)).encode()})
        path = Path(saved['path'])
        if (not verify_export(path)['valid']
                or (path/'attachment-recovery-snapshot.hex.txt').read_text() != verified.hex()):
            raise ValueError('Recovery export verification failed')
        return dict(snapshot=snapshot, export_path=str(path), resume_allowed=False,
                    physical_pose_verified=False)
