"""Analyze one complete r50 result and export its bounded lookup conclusion."""
import argparse
import json
from pathlib import Path

from rocell.application.fine_pair_lookup_analysis import analyze_fine_pair_lookup
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-export',required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    exports=(root/'runs/wizard-exports').resolve()
    result,_=_read(exports,args.result_export,'attachment-fine-pair-lookup-result.json')
    analysis=analyze_fine_pair_lookup(result,source_export=args.result_export)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'fine-pair-lookup-analysis'},[],attachments={
        'fine-pair-lookup-analysis.json':json.dumps(
            analysis,sort_keys=True,separators=(',',':')).encode()})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Fine lookup analysis export invalid')
    print(json.dumps({'export_path':saved['path'],
        'fine_endpoint_lookup_validated':analysis['fine_endpoint_lookup_validated'],
        'movement_authorized':False}))


if __name__=='__main__':main()
