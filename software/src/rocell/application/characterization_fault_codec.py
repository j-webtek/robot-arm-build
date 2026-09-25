"""Decode retained fault evidence; never treat the last valid pose as current."""


def decode_fault(raw: bytes) -> dict:
    magic = b'RCCFAULT01\0'
    if type(raw) is not bytes or not raw.startswith(magic) or len(raw) > 256:
        raise ValueError('Invalid fault framing')
    offset = len(magic)

    def take(size):
        nonlocal offset
        if offset + size > len(raw):
            raise ValueError('Truncated fault')
        value = raw[offset:offset+size]
        offset += size
        return value

    def number(size):
        return int.from_bytes(take(size), 'big')

    size = number(1)
    if not 1 <= size <= 63:
        raise ValueError('Invalid reason length')
    reason_bytes = take(size)
    if any(byte not in b'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for byte in reason_bytes):
        raise ValueError('Invalid reason')
    phase, leg, writes, timestamp, present = number(1), number(1), number(1), number(8), number(1)
    phases = ['New', 'Baseline', 'Prewrite', 'Observe', 'AwaitExport', 'Complete', 'Fault']
    if phase >= len(phases) or leg > 12 or writes > 12 or present not in (0, 1):
        raise ValueError('Invalid fault metadata')
    pose = None
    if present:
        started, finished = number(8), number(8)
        if not 0 < started <= finished or finished-started > 300000:
            raise ValueError('Invalid pose timing')
        joints = []
        for index in range(7):
            position, goal, torque = number(2), number(2), number(1)
            feedback = take(15)
            if position > 4095 or goal > 4095 or torque != 1 or int.from_bytes(feedback[:2], 'little') != position:
                raise ValueError('Invalid pose evidence')
            joints.append(dict(id=index+11, position=position, goal=goal, torque=torque,
                               feedback_hex=feedback.hex()))
        pose = dict(started_us=started, finished_us=finished, joints=joints)
    if offset != len(raw):
        raise ValueError('Trailing fault bytes')
    return dict(schema='rocell.characterization_fault.v1', reason=reason_bytes.decode('ascii'),
                phase=phases[phase], leg=leg, writes_attempted=writes,
                last_owner_time_us=timestamp, last_valid_pose=pose,
                pose_is_current=False, movement_authorized=False)


def export_fault(root, raw: bytes) -> dict:
    import json
    from pathlib import Path
    from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

    decoded = decode_fault(raw)
    exporter = WizardDiagnosticExporter(Path(root).resolve())
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'characterization-fault-review'}, [], attachments={
        'characterization-fault.json': json.dumps(decoded, indent=2).encode(),
        'characterization-fault.hex.txt': raw.hex().encode('ascii'),
    })
    path = Path(saved['path'])
    if not verify_export(path)['valid']:
        raise ValueError('Fault export verification failed')
    if (path/'attachment-characterization-fault.hex.txt').read_text().strip() != raw.hex():
        raise ValueError('Fault export bytes differ')
    return dict(export_path=str(path), reason=decoded['reason'], movement_authorized=False)
