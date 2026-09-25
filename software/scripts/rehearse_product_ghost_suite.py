"""Export product-size endpoint trials individually and a compact suite index."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_endpoints import rehearse_product_endpoints
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rehearse_ghost_suite import CASES, evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args()
    source=args.input.resolve(strict=True)
    if not verify_export(source)['valid']: raise ValueError('Invalid source archive')
    data=json.loads((source/'attachment-static-task.json').read_bytes())
    root=Path(__file__).resolve().parents[2]
    exporter=WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    def save(metadata, attachments):
        receipt=exporter.export(metadata,[],attachments={k:json.dumps(v,allow_nan=False).encode() for k,v in attachments.items()})
        path=Path(receipt['path']).resolve()
        if not verify_export(path)['valid']: raise ValueError('Export failed verification')
        return path.name
    cases=[]
    for fault in CASES:
        report=rehearse_product_endpoints(root,data,fault=fault)
        verdict=evaluate(report)
        # Full owned-trial traces stay in individual archives, preserving
        # bounded exporter limits rather than truncating or nesting 55 trials.
        refs=[]
        for mapping,row in zip(report['trial_mapping'],report['trial_results']):
            refs.append(dict(**mapping,export=save(dict(mode='offline-product-leg',case=fault),
                {'product-leg.json':dict(parent_plan_sha256=report['plan_sha256'],mapping=mapping,result=row)})))
        compact={k:v for k,v in report.items() if k!='trial_results'}
        compact['trial_exports']=refs
        case_export=save(dict(mode='offline-product-case',case=fault),{'product-case.json':compact})
        cases.append(dict(case=fault,attempted=len(refs),skipped=len(report['skipped_trial_ids']),
            case_export=case_export,**verdict))
    passed=all(c['passed'] for c in cases)
    summary=dict(status='SIMULATION_SUITE_PASS' if passed else 'SIMULATION_SUITE_FAIL',cases=cases,
        source_export=source.name,hardware_access=False,physical_qualification=False)
    archive=save(dict(mode='offline-product-suite'),{'product-suite.json':summary})
    print(json.dumps(dict(status=summary['status'],export=archive,cases=cases)))
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
