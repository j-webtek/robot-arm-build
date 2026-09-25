"""Replay retained elbow telemetry offline; never send a command or alter source."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.arm.cartesian_transaction import CartesianTransaction


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    source='wizard-20260917T193314387752Z-d975fcaf16c34888a2ab6f69bce92c81'
    report,digest=_read(root,source,'attachment-cartesian-trial.json')
    saved=report['run']['transaction']
    tx=CartesianTransaction(baseline=report['baseline'],baseline_finished_ns=saved['baseline_finished_ns'],
        completion_budget_ns=saved['completion_budget_ns'],elbow_only=True,elbow_degrees=-8)
    if tx.begin_dispatch(saved['dispatch_started_ns'])!=saved['command']:
        raise ValueError('Replay command mismatch')
    tx.acknowledge(saved['acknowledgment_finished_ns'])
    for row in saved['rows']:
        if tx.snapshot()['state']!='OBSERVING':break
        tx.observe(row,row[1])
    result=dict(source_export=source,source_attachment_sha256=digest,
        original_status=report['status'],replayed_transaction=tx.snapshot(),
        hardware_access=False,motion_commands=0,source_modified=False,
        limitation='Offline sampled model guard replay, not a physical emergency stop.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-tip-guard-replay'},[],attachments={
        'tip-guard-replay.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise RuntimeError('Replay export invalid')
    print(json.dumps(dict(export=receipt['path'],state=tx.snapshot()['state'],
        consumed_samples=len(tx.snapshot()['rows']),source_samples=len(saved['rows']))))


if __name__=='__main__':main()
