"""One bounded configuration acquisition; callers verify installed capability.

POST performs reads only, but consumes the controller's one-shot capture. GET is
archived-result retrieval. Neither path writes servo settings or starts motion.
"""
import base64
from pathlib import Path
import socket
import time
from .first_motion_contract import canonical
from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length
from .servo_start_authorization import _hex
from .physical_onboarding_durability import publish_reservation_bytes
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .elbow_configuration_review import assess_configuration, export_configuration


def configuration_exchange(address, method, *, port=80):
    checked=DiagnosticHTTPReader(address,port)
    if method not in ('POST','GET'):raise ValueError('Unsupported configuration operation')
    path='/rocell/elbow-configuration/'+('capture' if method=='POST' else 'result')
    deadline=time.monotonic()+3
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:raise TimeoutError('Configuration exchange deadline')
        return value
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
        connection.settimeout(remaining());connection.connect((checked.address,checked.port))
        request=(f'{method} {path} HTTP/1.1\r\nHost: {checked.address}:{checked.port}\r\n'
                 'Content-Length: 0\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n').encode('ascii')
        connection.settimeout(remaining());connection.sendall(request)
        def receive(count):
            connection.settimeout(remaining());data=connection.recv(count);remaining()
            if not data:raise ValueError('Truncated configuration response')
            return data
        header=bytearray()
        while not header.endswith(b'\r\n\r\n'):
            if len(header)>=2048:raise ValueError('Configuration header budget')
            header.extend(receive(1))
        length=_content_length(bytes(header),4095)
        body=bytearray()
        while len(body)<length:body.extend(receive(length-len(body)))
        return bytes(body)


def capture_configuration(root, *, address, expected_boot, exchange=configuration_exchange):
    """No retries, including on transport failure. Preserve response bytes first."""
    _hex(expected_boot,16);DiagnosticHTTPReader(address)
    root=Path(root);exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    subject=dict(expected_boot=expected_boot,expected_capture='elbow-config-1')
    publish_reservation_bytes(root,'elbow-configuration-'+expected_boot+'.json',
        canonical(dict(subject, retry_allowed=False)),maximum_bytes=2048)
    report=dict(schema='rocell.configuration_capture_transport.v1',subject=subject,
        address=address,responses=[],category='INCONCLUSIVE',retry_allowed=False)
    try:
        for method in ('POST','GET'):
            raw=exchange(address,method)
            if type(raw) is not bytes or not 0<len(raw)<=4095:raise ValueError('Response budget')
            report['responses'].append(dict(method=method,raw_base64=base64.b64encode(raw).decode()))
            document=decode_diagnostic_json(raw,maximum=4095)
            assess_configuration(document,**subject)
            if method=='POST':first=raw
            elif raw!=first:raise ValueError('Retained configuration changed')
        saved=export_configuration(root,document,**subject)
        report.update(category=saved['assessment']['category'],configuration_export=Path(saved['export_path']).name)
    except (OSError,ValueError,TypeError,KeyError) as error:
        report['error_type']=type(error).__name__
    saved=exporter.export({'mode':'configuration-capture-transport'},[],attachments={
        'configuration-transport.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Transport export invalid')
    return dict(export_path=saved['path'],report=report)
