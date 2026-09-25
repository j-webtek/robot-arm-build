"""Offline range screening of the proposed hybrid from verified historical traces."""
import argparse
import json
from pathlib import Path
from rocell.application.coordinated_response_models import screen_hybrid_approach
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('exports',nargs=3);args=p.parse_args()
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports';reports=[];sources=[]
    for identity in args.exports:
        report,digest=_read(root,identity,'attachment-cartesian-trial.json')
        reports.append(report);sources.append(dict(export=identity,attachment_sha256=digest))
    result=screen_hybrid_approach(reports);result['sources']=sources
    exporter=WizardDiagnosticExporter(root.resolve());exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-hybrid-range-screen'),[],attachments={
        'hybrid-screen.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],status=result['status'],sampled_count=result['sampled_count'],
        feasible_count=len(result['feasible']),rejections=result['rejection_counts'])))


if __name__=='__main__':main()
