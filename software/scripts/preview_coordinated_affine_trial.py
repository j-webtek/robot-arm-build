"""Freeze an interior-domain coordinated model trial; offline only."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.coordinated_affine_trial import build_trial
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    analysis_id='wizard-20260917T201603834704Z-6d84f5b22d7d46829d1471bf7867c04c'
    start_id='wizard-20260917T201423927986Z-2d8334fcc06a430eb158652560d12a63'
    analysis,analysis_hash=_read(root,analysis_id,'attachment-response-comparison.json')
    source,source_hash=_read(root,start_id,'attachment-cartesian-trial.json')
    candidate=build_trial(analysis,source['run']['transaction']['rows'][-1][3])
    report=dict(candidate=candidate,analysis_export=analysis_id,analysis_sha256=analysis_hash,
        baseline_export=start_id,baseline_sha256=source_hash,motion_authorized=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-affine-trial-preview'},[],attachments={
        'affine-trial.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],preview=report)))


if __name__=='__main__':main()
