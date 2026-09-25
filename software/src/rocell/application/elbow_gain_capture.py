"""One bounded gain acquisition; callers verify installed capability.

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
from .elbow_gain_review import assess_gain, export_gain


def gain_exchange(address, method, *, port=80):
    """One exchange, retaining bounded phase/byte metadata if it fails."""
    started=time.monotonic()
    trace=dict(method=method,phase='validation',header_bytes=0,body_bytes=0,
               expected_body_bytes=None,deadline_seconds=3)
    try:
        return _gain_exchange(address,method,port=port,trace=trace)
    except (OSError,ValueError) as error:
        # Deliberately no response bodies, credentials or arbitrary exception text.
        trace['elapsed_seconds']=max(0.0,time.monotonic()-started)
        error.gain_exchange_diagnostic=trace
        raise


def _gain_exchange(address, method, *, port, trace):
    checked=DiagnosticHTTPReader(address,port)
    if method not in ('POST','GET'):raise ValueError('Unsupported gain operation')
    path='/rocell/elbow-gain/'+('capture' if method=='POST' else 'result')
    deadline=time.monotonic()+3
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:raise TimeoutError('Gain exchange deadline')
        return value
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
        trace['phase']='connect'
        connection.settimeout(remaining());connection.connect((checked.address,checked.port))
        request=(f'{method} {path} HTTP/1.1\r\nHost: {checked.address}:{checked.port}\r\n'
                 'Content-Length: 0\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n').encode('ascii')
        trace['phase']='send'
        connection.settimeout(remaining());connection.sendall(request)
        def receive(count):
            connection.settimeout(remaining());data=connection.recv(count);remaining()
            if not data:raise ValueError('Truncated gain response')
            return data
        header=bytearray()
        trace['phase']='response_header'
        while not header.endswith(b'\r\n\r\n'):
            if len(header)>=2048:raise ValueError('Gain header budget')
            header.extend(receive(1))
            trace['header_bytes']=len(header)
        trace['phase']='validate_header'
        length=_content_length(bytes(header),4095)
        trace['expected_body_bytes']=length
        body=bytearray()
        trace['phase']='response_body'
        while len(body)<length:
            body.extend(receive(length-len(body)))
            trace['body_bytes']=len(body)
        return bytes(body)


def capture_gain(root, *, address, expected_boot, exchange=gain_exchange):
    """No retries, including on transport failure. Preserve response bytes first."""
    _hex(expected_boot,16);DiagnosticHTTPReader(address)
    root=Path(root);exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    subject=dict(expected_boot=expected_boot,expected_capture='elbow-gain-1')
    publish_reservation_bytes(root,'elbow-gain-'+expected_boot+'.json',
        canonical(dict(subject, retry_allowed=False)),maximum_bytes=2048)
    report=dict(schema='rocell.gain_capture_transport.v1',subject=subject,
        address=address,responses=[],category='INCONCLUSIVE',retry_allowed=False)
    try:
        for method in ('POST','GET'):
            raw=exchange(address,method)
            if type(raw) is not bytes or not 0<len(raw)<=4095:raise ValueError('Response budget')
            report['responses'].append(dict(method=method,raw_base64=base64.b64encode(raw).decode()))
            document=decode_diagnostic_json(raw,maximum=4095)
            assess_gain(document,**subject)
            if method=='POST':first=raw
            elif raw!=first:raise ValueError('Retained gain changed')
        saved=export_gain(root,document,**subject)
        report.update(category=saved['assessment']['category'],gain_export=Path(saved['export_path']).name)
    except (OSError,ValueError,TypeError,KeyError) as error:
        report['error_type']=type(error).__name__
        report['failed_method']=method
        if hasattr(error,'gain_exchange_diagnostic'):
            report['exchange_diagnostic']=error.gain_exchange_diagnostic
    saved=exporter.export({'mode':'gain-capture-transport'},[],attachments={
        'gain-transport.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Transport export invalid')
    return dict(export_path=saved['path'],report=report)
