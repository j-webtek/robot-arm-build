"""One finite acquisition request and retained-record retrieval; never motion.

The caller must verify installed capability and fresh idle boot before entry.
No fallback, retry, reset, provisioning or policy editing is provided here.
"""
import base64
from pathlib import Path
import socket
import time
import re

from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .pose_observation_export import export_pose_observation
from .product_ghost_export_review import _read
from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length
from .servo_diagnostic_contract import _identifier
from .servo_start_authorization import _hex
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter


class PoseHTTPStatus(ValueError):
    """Bounded status-only failure; never retain arbitrary controller body."""
    def __init__(self, status: int):
        self.status = status
        super().__init__("Pose endpoint returned a non-success HTTP status")


def pose_exchange(address, method, path, body=b'', *, port=80):
    checked=DiagnosticHTTPReader(address,port)
    post=method=='POST' and path=='/rocell/pose/capture'
    get=method=='GET' and path in {f'/rocell/pose/record?index={i}' for i in range(4)}
    if not (post or get) or type(body) is not bytes or len(body)>384 or (get and body):
        raise ValueError('Unsupported pose request')
    deadline=time.monotonic()+3
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:raise TimeoutError('Pose exchange deadline')
        return value
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
        connection.settimeout(remaining());connection.connect((checked.address,checked.port))
        request=(f'{method} {path} HTTP/1.1\r\nHost: {checked.address}:{checked.port}\r\n'
            f'Content-Length: {len(body)}\r\nContent-Type: application/json\r\n'
            'Accept-Encoding: identity\r\nConnection: close\r\n\r\n').encode()+body
        connection.settimeout(remaining());connection.sendall(request)
        def receive(count):
            connection.settimeout(remaining());chunk=connection.recv(count);remaining()
            if not chunk:raise ValueError('Truncated pose response')
            return chunk
        header=bytearray()
        while not header.endswith(b'\r\n\r\n'):
            if len(header)>=2048:raise ValueError('Pose header budget')
            header.extend(receive(1))
        status=re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})(?: [\x20-\x7e]*)?',
                            bytes(header).split(b'\r\n',1)[0])
        if status and int(status[1])!=(202 if post else 200):
            raise PoseHTTPStatus(int(status[1]))
        length=_content_length(bytes(header),512 if post else 4095,expected_status=202 if post else 200)
        raw=bytearray()
        while len(raw)<length:raw.extend(receive(length-len(raw)))
        return bytes(raw)


def capture_pose(root, *, address, expected_boot, scan_id, authorized=False,
                 exchange=pose_exchange, pause=time.sleep):
    if authorized is not True:raise ValueError('Explicit acquisition approval required')
    _hex(expected_boot,16);_identifier(scan_id);DiagnosticHTTPReader(address)
    root=Path(root);exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    subject=dict(expected_boot=expected_boot,expected_id=scan_id)
    publish_reservation_bytes(root,'pose-observation-'+expected_boot+'.json',
        canonical(dict(subject,retry_allowed=False)),maximum_bytes=2048)
    report=dict(schema='rocell.pose_capture.v1',subject=subject,address=address,
        responses=[],category='INCONCLUSIVE',retry_allowed=False,progression_authority=False)
    def save():
        saved=exporter.export({'mode':'pose-capture'},[],attachments={'pose-capture.json':canonical(report)})
        retained,_=_read(root,Path(saved['path']).name,'attachment-pose-capture.json')
        if canonical(retained)!=canonical(report):raise ValueError('Capture export changed')
        return saved['path']
    save() # A durable reservation and intent must precede network activity.
    records=[]
    try:
        body=canonical(dict(boot_id=expected_boot,scan_id=scan_id))
        raw=exchange(address,'POST','/rocell/pose/capture',body)
        report['responses'].append(dict(method='POST',raw_base64=base64.b64encode(raw).decode()))
        save()
        if decode_diagnostic_json(raw,maximum=512)!=dict(status='POSE_QUEUED',retry_allowed=False):
            raise ValueError('Capture not accepted')
        pause(1.25) # Beyond the finite one-second acquisition budget, no polling retry.
        for i in range(4):
            raw=exchange(address,'GET',f'/rocell/pose/record?index={i}')
            report['responses'].append(dict(method='GET',index=i,raw_base64=base64.b64encode(raw).decode()))
            records.append(raw);save()
            doc=decode_diagnostic_json(raw,maximum=4095)
            if type(doc) is not dict:raise ValueError('Pose record object required')
            if doc.get('schema')=='rocell.pose_observation_terminal.v1':break
        assessed=export_pose_observation(root,records,**subject,origin='DEVICE_CAPTURE')
        report['assessment_export_id']=Path(assessed['export_path']).name
        report['category']=assessed['assessment']['category']
    except (OSError,ValueError,TypeError,KeyError) as error:
        report['error_type']=type(error).__name__
        if isinstance(error,PoseHTTPStatus):
            report['http_status']=error.status
    return dict(export_path=save(),report=report)
