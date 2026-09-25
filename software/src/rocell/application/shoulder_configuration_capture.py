"""Finite read-only shoulder capture. Caller binds installed image and idle boot.

No startup, reset, motion, settings writes, redirects or request retries.
"""
import base64
from pathlib import Path
import socket
import time

from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length
from .servo_start_authorization import _hex
from .shoulder_configuration_review import assess, export_review
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

MAX_RESPONSE = 8192


def shoulder_exchange(address, method, *, port=80):
    checked = DiagnosticHTTPReader(address, port)
    if method not in ('POST', 'GET'):
        raise ValueError('Unsupported shoulder operation')
    path = '/rocell/shoulder-configuration/' + ('capture' if method == 'POST' else 'result')
    deadline = time.monotonic() + 3

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('Shoulder exchange deadline')
        return value

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(remaining())
        connection.connect((checked.address, checked.port))
        request = (f'{method} {path} HTTP/1.1\r\nHost: {checked.address}:{checked.port}\r\n'
                   'Content-Length: 0\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n').encode('ascii')
        connection.settimeout(remaining())
        connection.sendall(request)

        def receive(count):
            connection.settimeout(remaining())
            raw = connection.recv(count)
            remaining()
            if not raw:
                raise ValueError('Truncated shoulder response')
            return raw

        header = bytearray()
        while not header.endswith(b'\r\n\r\n'):
            if len(header) >= 2048:
                raise ValueError('Shoulder header budget')
            header.extend(receive(1))
        length = _content_length(bytes(header), MAX_RESPONSE)
        body = bytearray()
        while len(body) < length:
            body.extend(receive(length - len(body)))
        return bytes(body)


def capture_shoulders(root, *, address, expected_boot, authorized=False,
                      origin='DEVICE_CAPTURE', exchange=shoulder_exchange):
    """Reserve before I/O; export raw bytes before parsing or a follow-on GET.

    An injected transport can exercise this function offline with SIMULATION
    origin. This API is not itself an installation/startup admission verifier.
    """
    if authorized is not True:
        raise ValueError('Explicit capture approval required')
    if origin not in ('SIMULATION', 'DEVICE_CAPTURE'):
        raise ValueError('Invalid evidence origin')
    if origin == 'SIMULATION' and exchange is shoulder_exchange:
        raise ValueError('Simulation must not use device transport')
    _hex(expected_boot, 16)
    DiagnosticHTTPReader(address)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    subject = dict(expected_boot=expected_boot, expected_capture='shoulder-config-1', origin=origin)
    publish_reservation_bytes(root, 'shoulder-configuration-'+expected_boot+'.json',
                              canonical(dict(subject, retry_allowed=False)), maximum_bytes=2048)
    report = dict(schema='rocell.shoulder_capture_transport.v1', subject=subject,
                  address=address, responses=[], category='INCONCLUSIVE', retry_allowed=False,
                  motion_authorized=False)

    def save():
        saved = exporter.export({'mode': 'shoulder-capture-transport'}, [], attachments={
            'shoulder-transport.json': canonical(report)})
        if not verify_export(Path(saved['path']))['valid']:
            raise ValueError('Shoulder transport export invalid')
        return saved['path']

    save()  # Durable intent before first network operation; failure prevents I/O.
    first = None
    for method in ('POST', 'GET'):
        try:
            raw = exchange(address, method)
            if type(raw) is not bytes or not 0 < len(raw) <= MAX_RESPONSE:
                raise ValueError('Shoulder response budget')
        except (OSError, ValueError, TypeError) as error:
            report['error_type'] = type(error).__name__
            return dict(export_path=save(), report=report)
        report['responses'].append(dict(method=method, raw_base64=base64.b64encode(raw).decode()))
        save()  # Export errors deliberately propagate: never send the next GET.
        try:
            document = decode_diagnostic_json(raw, maximum=MAX_RESPONSE)
            assessment = assess(document, **subject)
            if method == 'POST':
                first = raw
            elif raw != first:
                raise ValueError('Retained shoulder result changed')
            if assessment['category'] == 'INCONCLUSIVE':
                return dict(export_path=save(), report=report)
        except (ValueError, TypeError, KeyError) as error:
            report['error_type'] = type(error).__name__
            return dict(export_path=save(), report=report)
    saved = export_review(root, document, **subject)
    report.update(category=saved['assessment']['category'],
                  assessment_export_id=Path(saved['export_path']).name)
    return dict(export_path=save(), report=report)
