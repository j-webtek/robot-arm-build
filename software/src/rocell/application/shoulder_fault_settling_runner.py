"""Bounded fault-only workflow used by the session runner's candidate path.

call() is the parent's audited, deadline-bound transport. No restart, actuator
target, torque operation or motion-fault reset is available here.
"""
from pathlib import Path
from .shoulder_fault_settling_export import FaultSettlingExport
from .shoulder_export_receipt import export_and_sign
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def collect_fault_settling(root, original, *, boot, command, sequence, key, call, pause):
    review = FaultSettlingExport(original, boot=boot, parent_command=command)
    evidence = export_and_sign(root, original, key=key, boot=boot, command=command, sequence=sequence)
    result = dict(state='IN_PROGRESS', parent_motion_state='FAULT', original_export=evidence['export_path'],
                  records=[], raw_exports=[], physical_accuracy_verified=False)
    # Raw records are retained even when independent validation rejects them.
    exporter = WizardDiagnosticExporter(Path(root).resolve()); exporter.prepare(create=True)
    try:
        _, ack = call('POST', 'start', evidence['receipt'].hex().encode('ascii'))
        if ack != {'accepted': True, 'movement_performed_by_handler': False}:
            raise ValueError('Settling start unconfirmed')
        for _ in range(64):
            _, status = call('GET', 'status')
            if (status.get('schema') != 'rocell.shoulder_settling_status.v1'
                    or status.get('boot_id') != boot or status.get('command_id') != review.command
                    or status.get('parent_fault_latched') is not True
                    or status.get('movement_authorized') is not False
                    or type(status.get('count')) is not int):
                raise ValueError('Settling status binding mismatch')
            state = status.get('state')
            pending = status.get('record_available') is True
            if pending:
                if status['count'] != review.count+1:
                    raise ValueError('Settling pending sequence mismatch')
                raw, _ = call('GET', 'record')
                saved = exporter.export({'mode': 'fault-settling-raw'}, [],
                                         attachments={'settling-record.txt': raw})
                path = Path(saved['path'])
                if (not verify_export(path)['valid']
                        or (path/'attachment-settling-record.txt').read_bytes() != raw):
                    raise ValueError('Raw settling export failed')
                result['raw_exports'].append(str(path))
                if state != 'WAITING_EXPORT':
                    result['state'] = 'FAILED';result['controller_reason'] = status.get('reason')
                    return result
                exported = review.export(root, raw, key=key)
                result['records'].append(exported['export_path'])
                _, ack = call('POST', 'receipt', exported['receipt'].hex().encode('ascii'))
                if ack != {'accepted': True, 'movement_performed_by_handler': False}:
                    raise ValueError('Settling export receipt unconfirmed')
                continue
            if status['count'] != review.count:
                raise ValueError('Settling count mismatch')
            if state in ('SETTLED', 'EXHAUSTED', 'FAILED'):
                if state == 'SETTLED' and review.stable_count < 3:
                    raise ValueError('Insufficient settled evidence')
                result['state'] = state;result['controller_reason'] = status.get('reason')
                return result
            if state != 'READING':
                raise ValueError('Unexpected settling state')
            pause(0.1)
        raise TimeoutError('Settling poll budget')
    except (OSError, ValueError, TypeError, KeyError) as error:
        result['state'] = 'STOPPED';result['error_type'] = type(error).__name__
        return result
