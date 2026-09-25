"""Build a hash-linked elbow response map from saved exports; no hardware access."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.elbow_response_map import build_response_map
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_ids',nargs='+')
    args=parser.parse_args()
    if not 2<=len(args.export_ids)<=12: parser.error('Select 2–12 exports')
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports'
    sources=[]
    for identifier in args.export_ids:
        report,digest=_read(root,identifier,'attachment-cartesian-trial.json')
        sources.append(dict(source_export=identifier,source_attachment_sha256=digest,report=report))
    report=build_response_map(sources)
    exporter=WizardDiagnosticExporter(root.resolve()); exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-elbow-response-map'),[],attachments={
        'elbow-response-map.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']: raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],comparable_pairs=report['comparable_pairs'],pairs=report['pairs'])))


if __name__=='__main__': main()
