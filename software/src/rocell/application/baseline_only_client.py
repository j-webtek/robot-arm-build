"""Explicit one-shot baseline acquisition; never a motion command or retry path."""
import hashlib
import socket
import time
from pathlib import Path

from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length
from .servo_diagnostic_contract import _identifier
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .baseline_only_review import assess_baseline_only

ROUTE = '/rocell/diagnostics/baseline'


class BaselineOnlyClient:
    def __init__(self, address, port=80):
        checked = DiagnosticHTTPReader(address, port)
        self.address, self.port = checked.address, checked.port
        self.attempted = False
        self.acknowledged = False
        self.collection_attempted = False

    def request(self, body):
        if self.attempted:
            raise ValueError('Baseline request consumed; do not resend')
        self.attempted = True
        value = decode_diagnostic_json(body, maximum=512)
        if type(value) is not dict or set(value) != {'boot_id', 'scan_id'}:
            raise ValueError('Exact baseline request required')
        _identifier(value['boot_id']); _identifier(value['scan_id'])
        response = self._exchange('POST', body, 202, 256)
        if decode_diagnostic_json(response, maximum=256) != {'status': 'BASELINE_QUEUED'}:
            raise ValueError('Unexpected baseline acceptance')
        self.acknowledged = True
        return response

    def collect(self):
        if not self.acknowledged or self.collection_attempted:
            raise ValueError('Collection requires acknowledged, uncollected baseline attempt')
        self.collection_attempted = True
        return self._exchange('GET', b'', 200, 2304)

    def _exchange(self, method, body, status, maximum):
        deadline = time.monotonic() + 10  # Includes bounded controller scan time.
        def remaining():
            left = deadline-time.monotonic()
            if left <= 0: raise TimeoutError('Baseline exchange deadline exceeded')
            return left
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(remaining()); connection.connect((self.address, self.port))
            headers = (f'{method} {ROUTE} HTTP/1.0\r\nHost: {self.address}:{self.port}\r\n'
                       'Content-Type: application/json\r\nAccept: application/json\r\n'
                       f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n').encode('ascii')
            connection.settimeout(remaining()); connection.sendall(headers+body)
            def receive(count):
                connection.settimeout(remaining()); data=connection.recv(count); remaining()
                if not data: raise ValueError('Truncated baseline response')
                return data
            header=bytearray()
            while not header.endswith(b'\r\n\r\n'):
                if len(header)>=2048: raise ValueError('Baseline header limit exceeded')
                header.extend(receive(1))
            length=_content_length(bytes(header),maximum,expected_status=status)
            result=bytearray()
            while len(result)<length: result.extend(receive(length-len(result)))
            return bytes(result)


def run_baseline_only(client, *, boot_id, scan_id, claim_root, export_root):
    """Requires reviewed installed capability; persist attempt before any POST.

    A claim is keyed by endpoint and boot, not caller-selected scan ID. A restart
    of the host therefore cannot silently repeat acquisition on the same boot.
    Failed exports raise and never release the claim. No recovery/device reset.
    """
    _identifier(boot_id); _identifier(scan_id)
    request=canonical(dict(boot_id=boot_id,scan_id=scan_id))
    exporter=WizardDiagnosticExporter(Path(export_root).resolve()); exporter.prepare(create=True)
    prepared=exporter.export({'mode':'baseline-only-prepared'},[],attachments={'request.json':request})
    if not verify_export(Path(prepared['path']))['valid']: raise ValueError('Prepared export failed')
    claim_name=hashlib.sha256(canonical([client.address,client.port,boot_id])).hexdigest()+'.json'
    publish_reservation_bytes(Path(claim_root),claim_name,request,maximum_bytes=512)
    attachments={'request.json':request}; assessment=None; status='DELIVERY_UNCERTAIN'
    try:
        raw=client.request(request); attachments['acceptance.json']=raw
        if decode_diagnostic_json(raw,maximum=256)!={'status':'BASELINE_QUEUED'}:
            raise ValueError('Unexpected baseline acceptance')
        status='COLLECTION_INCONCLUSIVE'
        raw=client.collect(); attachments['baseline.json']=raw
        record=decode_diagnostic_json(raw,maximum=2304)
        assessment=assess_baseline_only(record,boot_id=boot_id,scan_id=scan_id)
        status=assessment['status']
    except (OSError,ValueError,TypeError,KeyError):
        # Preserve the known stage and received evidence, never infer no delivery.
        pass
    receipt=exporter.export({'mode':'baseline-only-result','status':status,
        'assessment':assessment,'prepared_export':prepared['export_id'],
        'retry_allowed':False,'motion_authority':False},[],attachments=attachments)
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Baseline export verification failed')
    return {'status':status,'assessment':assessment,'export':receipt['path'],'retry_allowed':False}
