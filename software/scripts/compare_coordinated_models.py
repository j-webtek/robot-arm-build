"""Compare offline response models against the last chronologically saved trial."""
import argparse
import json
from pathlib import Path
from rocell.application.coordinated_response_models import compare_response_models
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('exports',nargs='+')
    args=parser.parse_args()
    if not 3<=len(args.exports)<=8:parser.error('Provide 3-8 chronological exports')
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports'
    reports=[];sources=[]
    for identity in args.exports:
        report,digest=_read(root,identity,'attachment-cartesian-trial.json')
        reports.append(report);sources.append(dict(export=identity,attachment_sha256=digest))
    result=compare_response_models(reports);result['sources']=sources
    exporter=WizardDiagnosticExporter(root.resolve());exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-response-model-comparison'),[],attachments={
        'response-models.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],comparison=result)))


if __name__=='__main__':main()
