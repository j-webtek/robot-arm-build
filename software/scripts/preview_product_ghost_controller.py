"""Verify a saved product ghost export and project its joint route offline."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_controller_bridge import bridge_product_ghost
from rocell.application.product_ghost_interpolation import screen_product_ghost
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args()
    source=args.input.resolve(strict=True)
    if not verify_export(source)['valid']:
        raise ValueError('Source export failed verification')
    source_report=json.loads((source/'attachment-static-task.json').read_bytes())
    report=bridge_product_ghost(source_report)
    interpolation=screen_product_ghost(source_report)
    root=Path(__file__).resolve().parents[2]
    exporter=WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-product-ghost-reference',source_export=source.name),[],attachments={
        'product-ghost-controller.json':json.dumps(report,allow_nan=False).encode(),
        'product-ghost-interpolation.json':json.dumps(interpolation,allow_nan=False).encode()})
    valid=verify_export(Path(receipt['path']).resolve())['valid']
    print(json.dumps(dict(status=report['status'],samples=len(report['samples']),legs=len(report['legs']),
        maximum_roundtrip_rad=report['maximum_inverse_roundtrip_rad'],export=receipt['path'],valid=valid,
        interpolation_status=interpolation['status'],interpolation_samples=interpolation['total_samples'])))
    return 0 if valid and interpolation['status']=='REFERENCE_INTERPOLATION_PASS' else 1


if __name__=='__main__': raise SystemExit(main())
