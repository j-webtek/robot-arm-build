"""Explicit one-use authenticated start client. Construction performs no I/O.

Not wired to wizard startup or legacy motion paths. Deployment compatibility and
reviewed local policy/key provisioning must precede use. Never retry a lost reply.
"""
import hashlib
import math
import socket
import time

from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length
from .servo_start_authorization import sign_start
from .wizard_diagnostic_coordinator import decode_diagnostic_json


class DiagnosticStartError(RuntimeError):
    def __init__(self, report):
        super().__init__('Diagnostic start unverified; do not resend; inspect retained telemetry')
        self.report = report


class DiagnosticStartSender:
    """One object, one attempt, no redirects/reconnects/legacy fallback."""
    delivery_schema = 'rocell.host_start_delivery.v1'

    def __init__(self, address, port):
        checked = DiagnosticHTTPReader(address, port)  # Pure address validation.
        self.address, self.port = checked.address, checked.port
        self.attempted = False

    def _prepare_request(self, plan, challenge, key):
        document = plan.to_dict()
        if document.get('schema') != 'rocell.session_plan.v3' or document.get('origin') != 'DEVICE_CAPTURE':
            raise ValueError('Native whole-arm baseline-bound plan required')
        return sign_start(plan, challenge, key), dict(session_plan_sha256=plan.sha256,
            command_id=document['command']['command_id'], boot_id=document['command']['boot_id'])

    def send(self, plan, challenge, key, *, timeout_seconds=10):
        if self.attempted:
            raise ValueError('Start attempt consumed; no automatic retry')
        self.attempted = True
        report = dict(schema=self.delivery_schema, connection_attempted=False,
            transmission_attempted=False, retry_allowed=False, progression_authority=False,
            endpoint_verified=False, result='PREPARATION_REJECTED')
        try:
            if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                    or not 0 < timeout_seconds <= 10):
                raise ValueError('Invalid start deadline')
            token, identity = self._prepare_request(plan, challenge, key)
            report.update(identity)
            header = (f'POST /rocell/diagnostics/start HTTP/1.1\r\n'
                      f'Host: {self.address}:{self.port}\r\nContent-Type: application/octet-stream\r\n'
                      f'Connection: close\r\nContent-Length: {len(token)}\r\n\r\n').encode('ascii')
            deadline = time.monotonic() + timeout_seconds

            def remaining():
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError('Start deadline exceeded')
                return left

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                report['connection_attempted'] = True
                report['result'] = 'CONNECTION_UNVERIFIED'
                connection.settimeout(remaining())
                connection.connect((self.address, self.port))
                connection.settimeout(remaining())
                # Set before sendall: an exception can follow partial delivery.
                report['transmission_attempted'] = True
                report['result'] = 'DELIVERY_UNCERTAIN'
                connection.sendall(header + token)

                def receive(count):
                    connection.settimeout(remaining())
                    data = connection.recv(count)
                    remaining()
                    if not data:
                        raise ValueError('Truncated start response')
                    return data

                response_header = bytearray()
                while not response_header.endswith(b'\r\n\r\n'):
                    if len(response_header) >= 2048:
                        raise ValueError('Start response header limit')
                    response_header.extend(receive(1))
                status_line = bytes(response_header).split(b'\r\n', 1)[0]
                status = 202 if status_line.startswith(b'HTTP/1.1 202 ') else 400
                length = _content_length(bytes(response_header), 256, expected_status=status)
                body = bytearray()
                while len(body) < length:
                    body.extend(receive(length-len(body)))
                result = decode_diagnostic_json(bytes(body), maximum=256)
                if (type(result) is not dict or set(result) != {'accepted', 'retry_allowed'}
                        or result['accepted'] is not (status == 202) or result['retry_allowed'] is not False):
                    raise ValueError('Contradictory start response')
                report.update(result='CONTROLLER_REPORTED_ACCEPTANCE' if status == 202 else 'CONTROLLER_REPORTED_REJECTION',
                    response_body=bytes(body).decode('ascii'), response_sha256=hashlib.sha256(body).hexdigest())
                return report
        except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError):
            # No raw exception, key, token, or request body is exposed in reports.
            raise DiagnosticStartError(report) from None
