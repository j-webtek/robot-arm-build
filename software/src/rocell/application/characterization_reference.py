"""Decode/export the exact three-pose reference bound by an authenticated challenge.

Stored samples are historical evidence, not a new acquisition or motion authority.
"""
import hashlib
import json
from pathlib import Path
from .servo_start_authorization import _hex
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def decode_reference(raw, *, expected_sha256):
    _hex(expected_sha256,32)
    if type(raw) is not bytes or len(raw)!=468 or hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Reference length or digest mismatch')
    offset=0
    def number(size):
        nonlocal offset
        value=int.from_bytes(raw[offset:offset+size],'big');offset+=size;return value
    poses=[]
    for index in range(3):
        started,finished=number(8),number(8)
        if not 0<started<=finished or finished-started>300000:
            raise ValueError('Invalid reference timing')
        if index and started-poses[-1]['finished_us']<100000:
            raise ValueError('Reference ordering/spacing invalid')
        joints=[]
        for joint in range(7):
            position,goal,torque=number(2),number(2),number(1)
            feedback=raw[offset:offset+15];offset+=15
            if (position>4095 or goal>4095 or torque!=1
                    or int.from_bytes(feedback[:2],'little')!=position
                    or feedback[2] or feedback[3] or feedback[10]):
                raise ValueError('Invalid or moving reference joint')
            if index:
                first=poses[0]['joints'][joint]
                if first['goal']!=goal or abs(first['position']-position)>1:
                    raise ValueError('Unstable reference joint')
            joints.append(dict(id=joint+11,position=position,goal=goal,torque=torque,
                               feedback_hex=feedback.hex()))
        poses.append(dict(started_us=started,finished_us=finished,joints=joints))
    return dict(schema='rocell.characterization_reference.v1',sha256=expected_sha256,
                poses=poses,movement_authorized=False,physical_accuracy_verified=False)


def export_reference(root, raw, *, expected_sha256):
    decoded=decode_reference(raw,expected_sha256=expected_sha256)
    exporter=WizardDiagnosticExporter(Path(root).resolve());exporter.prepare(create=True)
    saved=exporter.export({'mode':'campaign-reference-review'},[],attachments={
        'reference.json':json.dumps(decoded,indent=2).encode(),
        'reference.hex.txt':raw.hex().encode('ascii')})
    path=Path(saved['path'])
    if not verify_export(path)['valid'] or (path/'attachment-reference.hex.txt').read_text()!=raw.hex():
        raise ValueError('Reference export verification failed')
    return dict(export_path=str(path),reference=decoded,movement_authorized=False)
