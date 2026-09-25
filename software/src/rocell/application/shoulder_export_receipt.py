"""Export exact event bytes before signing a command-bound persistence receipt.

No transport or motion authority. Receipt proves a host assertion of export,
not physical arrival or correctness of the recorded servo observations.
"""
import hashlib
import hmac
from pathlib import Path
from .servo_start_authorization import _hex
from .servo_diagnostic_contract import _identifier
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def export_and_sign(root, raw, *, key, boot, command, sequence):
    if type(key) is not bytes or len(key)!=32:
        raise ValueError('32-byte session key required')
    _hex(boot,16);_identifier(command)
    if type(sequence) is not int or not 0<=sequence<64:
        raise ValueError('Bounded event sequence required')
    if type(raw) is not bytes or not 0<len(raw)<4096:
        raise ValueError('Bounded exact record bytes required')
    doc=decode_diagnostic_json(raw,maximum=4095)
    if (type(doc) is not dict or doc.get('schema')!='rocell.shoulder_hold_event.v1'
            or doc.get('boot_id')!=boot or doc.get('command_id')!=command
            or type(doc.get('sequence')) is not int or doc['sequence']!=sequence):
        raise ValueError('Event identity mismatch')
    exporter=WizardDiagnosticExporter(Path(root).resolve());exporter.prepare(create=True)
    saved=exporter.export({'mode':'shoulder-record-export'},[],attachments={'shoulder-event.txt':raw})
    path=Path(saved['path'])
    if not verify_export(path)['valid']:
        raise ValueError('Export verification failed; no receipt')
    # Text avoids JSON reformatting. If redaction changes bytes, do not sign.
    if (path/'attachment-shoulder-event.txt').read_bytes()!=raw:
        raise ValueError('Export bytes differ; no receipt')
    unsigned=(b'RCSHEX01'+bytes.fromhex(boot)+hashlib.sha256(command.encode('utf-8')).digest()
              +sequence.to_bytes(4,'little')+hashlib.sha256(raw).digest())
    return dict(export_path=str(path),receipt=unsigned+hmac.digest(key,unsigned,'sha256'))
