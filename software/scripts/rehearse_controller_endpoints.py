"""Rehearse the owned Cartesian endpoint path from a verified feedback export."""
import argparse
import json
from pathlib import Path
from rocell.application.controller_endpoint_rehearsal import rehearse_vertical_endpoints
from rocell.application.wizard_endpoint_rehearsal import FAULTS
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--fault',choices=FAULTS,default='NONE')
    args = parser.parse_args()
    folder = args.input.resolve(strict=True)
    if not verify_export(folder)['valid']:
        raise ValueError('Invalid source export')
    reports = []
    for file in folder.glob('attachment-result-*.json'):
        result = json.loads(file.read_text())
        if result.get('action_id') == 'read_arm_wifi_feedback':
            reports.append(result['steps'][0]['report'])
    if len(reports)!=1:
        raise ValueError('Select exactly one retained feedback result')
    root = Path(__file__).resolve().parents[2]
    report = rehearse_vertical_endpoints(root,reports[0],first_fault=args.fault)
    report['input_export'] = str(folder)
    exporter = WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt = exporter.export(dict(mode='offline-rehearsal'),[],attachments={
        'controller-endpoints.json':json.dumps(report,allow_nan=False).encode(),
        'campaign-plan.json':json.dumps(report['plan'],allow_nan=False).encode()})
    print(json.dumps(dict(status=report['status'],fault=args.fault,
        trials=[r['trial']['status'] for r in report['trial_results']],
        skipped=report['skipped_trial_ids'],export=receipt['path'])))


if __name__=='__main__':
    main()
