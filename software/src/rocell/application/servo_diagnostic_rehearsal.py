"""Export/replay named synthetic traces. No arbitrary payloads or native I/O."""
import base64
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .servo_diagnostic_simulation import simulate_trace,simulate_write_evidence
from .servo_write_evidence import assess_write_evidence
from .servo_diagnostic_decode import decode_trace,MAX_TRACE_BYTES
from .servo_diagnostic_summary import summarize_trace
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from .product_ghost_export_review import _read


def _outcome(raw):
    try:
        decoded=decode_trace(raw)
    except ValueError:
        return dict(status='TRACE_REJECTED',assessment=None)
    return dict(status='TRACE_ASSESSED',assessment=decoded['assessment'])


def run_rehearsal(export_root,scenario):
    # Named local generator only: rejected arbitrary data may contain secrets and
    # must not be exported through this synthetic-only entry point.
    trace=simulate_trace(scenario)
    raw=canonical(trace)
    write=simulate_write_evidence(scenario)
    write_raw=canonical(write)
    outcome=_outcome(raw)
    record=dict(schema='rocell.servo_diagnostic_rehearsal.v1',scenario=scenario,
        origin='SIMULATION',raw_sha256=hashlib.sha256(raw).hexdigest(),
        outcome=outcome,motion_commands=0,physical_accuracy_verified=False,
        progression_authority=False,evidence_summary=summarize_trace(raw),
        write_evidence_sha256=hashlib.sha256(write_raw).hexdigest(),
        write_assessment=assess_write_evidence(write,trace['dispatch']))
    exporter=WizardDiagnosticExporter(Path(export_root).resolve())
    exporter.prepare(create=True)
    receipt=exporter.export({'mode':'servo-diagnostic-simulation'},[],attachments={
        'servo-trace.json':canonical(dict(base64=base64.b64encode(raw).decode(),sha256=record['raw_sha256'])),
        'servo-write-evidence.json':write_raw,
        'servo-assessment.json':canonical(record)})
    path=Path(receipt['path'])
    if not verify_export(path)['valid']:raise ValueError('Diagnostic export verification failed')
    replay=replay_rehearsal(path.parent,path.name)
    if not replay['matches']:raise ValueError('Diagnostic replay mismatch')
    return dict(record,export=dict(path=str(path),verified=True),replay_verified=True)


def replay_rehearsal(export_root,export_id):
    """Verify exact retained bytes and recompute outcome, including rejection."""
    root=Path(export_root).resolve()
    stored,_=_read(root,export_id,'attachment-servo-trace.json')
    record,_=_read(root,export_id,'attachment-servo-assessment.json')
    if (record.get('schema')!='rocell.servo_diagnostic_rehearsal.v1'
            or record.get('origin')!='SIMULATION' or record.get('motion_commands')!=0
            or record.get('progression_authority') is not False):
        raise ValueError('Synthetic rehearsal metadata required')
    if type(stored.get('base64')) is not str or len(stored['base64'])>4*((MAX_TRACE_BYTES+2)//3):
        raise ValueError('Bounded raw trace required')
    raw=base64.b64decode(stored['base64'],validate=True)
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=stored['sha256'] or digest!=record['raw_sha256']:
        raise ValueError('Raw trace identity mismatch')
    # Verify provenance against the deterministic fixture, not merely its label.
    if raw!=canonical(simulate_trace(record['scenario'])):
        raise ValueError('Named synthetic fixture mismatch')
    actual=_outcome(raw)
    if actual!=record['outcome']:raise ValueError('Recorded assessment mismatch')
    # Historical exports predate the optional presentation contract. New exports
    # must reproduce it from original bytes, not merely trust a stored summary.
    if 'evidence_summary' in record and record['evidence_summary']!=summarize_trace(raw):
        raise ValueError('Recorded evidence summary mismatch')
    # Older bundles have neither field. Partial metadata is not a legacy bundle.
    if 'write_evidence_sha256' in record or 'write_assessment' in record:
        write,_=_read(root,export_id,'attachment-servo-write-evidence.json')
        expected=simulate_write_evidence(record['scenario'])
        if (write!=expected or hashlib.sha256(canonical(write)).hexdigest()!=
                record.get('write_evidence_sha256')):
            raise ValueError('Synthetic write evidence mismatch')
        assessed=assess_write_evidence(write,simulate_trace(record['scenario'])['dispatch'])
        if assessed!=record.get('write_assessment'):
            raise ValueError('Recorded write assessment mismatch')
    return dict(matches=True,outcome=actual,motion_commands=0,progression_authority=False)
