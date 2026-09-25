"""Fit pinned increasing-direction trials offline and export held-out proposal."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.local_wrist_response_map import fit_local_map,predict_command
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    sources=[('wizard-20260917T191656675614Z-0b1fef1e816a4c11abc7ff289f2a78b1',
              'ecd19db5709c72bb04e2e5090bd82f5b5cb30d4d1e84cfa5d71bb769499bacb9'),
             ('wizard-20260917T192154079024Z-5a6776c530fc4b3e9833aa453c8c3777',
              '7e35da2f41d46a9bba5b42bc903c3c91911825a901776f36545f509910c0a9d1')]
    reports=[]
    for source,expected in sources:
        report,digest=_read(root,source,'attachment-cartesian-trial.json')
        if digest!=expected:raise ValueError('Pinned trial changed')
        reports.append(report)
    model=fit_local_map(reports)
    proposal=dict(model=model,sources=sources,desired_rad=-.055,
        command_rad=predict_command(model,-.055),
        baseline_preparation_required=True,arc_preview_required=True,motion_authorized=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-response-map'},[],attachments={
        'wrist-response-map.json':json.dumps(proposal,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise RuntimeError('Export verification failed')
    print(json.dumps(dict(export=receipt['path'],proposal=proposal)))


if __name__=='__main__':main()
