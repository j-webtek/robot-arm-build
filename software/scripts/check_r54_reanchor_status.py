"""Authenticated read-only r54 route check on a pose-observation-claimed boot.

Do not reuse this boot for motion: this read consumes the auth sequence, and
the separate pose observation already owns its one-use physical state.
"""
import argparse
import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binding = review_recovery_startup(root, args.startup_export, revision=54)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    if not (exports/f'pose-observation-{boot}.json').exists():
        raise ValueError('Use only after this boot has been claimed by read-only pose observation')
    client = CharacterizationHTTP(binding['address'], key=load_reviewed_key(root), boot=boot)
    status = client('GET', '/rocell/reanchor/status')
    if status != b'NEW|0':
        raise ValueError('Unexpected r54 re-anchor route state')
    report = dict(schema='rocell.r54_reanchor_readonly_route.v1', boot=boot,
                  response=status.decode('ascii'), movement_sent=False,
                  boot_reusable_for_motion=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r54-readonly-route-check'}, [], attachments={
        'r54-reanchor-route.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Read-only route export invalid')
    print(json.dumps(dict(export_path=saved['path'], **report)))


if __name__ == '__main__':
    main()
