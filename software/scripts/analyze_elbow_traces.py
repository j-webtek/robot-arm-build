"""Verify and analyze saved elbow trials; export a compact comparison offline."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.elbow_trace_analysis import analyze_elbow_trace
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_ids',nargs='+')
    args=parser.parse_args()
    if not 1<=len(args.export_ids)<=4: parser.error('Select one through four trial exports')
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports'
    results=[]
    for identifier in args.export_ids:
        source,digest=_read(root,identifier,'attachment-cartesian-trial.json')
        results.append(dict(source_export=identifier,source_attachment_sha256=digest,
                            analysis=analyze_elbow_trace(source)))
    exporter=WizardDiagnosticExporter(root.resolve()); exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-elbow-trace-analysis'),[],attachments={
        'elbow-traces.json':json.dumps(dict(trials=results,model_fitted=False)).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']: raise ValueError('Export verification failed')
    print(json.dumps(dict(export=receipt['path'],trials=[{k:v for k,v in r['analysis'].items() if k!='samples'} for r in results])))


if __name__=='__main__': main()
