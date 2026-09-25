"""Review one verified native Cartesian trial offline and export diagnostics."""
import argparse
import json
from pathlib import Path
from rocell.application.coordinated_trace_review import review_coordinated_trace
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('export_id'); args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports'
    source,digest=_read(root,args.export_id,'attachment-cartesian-trial.json')
    report=review_coordinated_trace(source)
    report.update(source_export=args.export_id,source_attachment_sha256=digest)
    exporter=WizardDiagnosticExporter(root.resolve()); exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-coordinated-trace'),[],attachments={
        'coordinated-trace.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']: raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=report)))


if __name__=='__main__': main()
