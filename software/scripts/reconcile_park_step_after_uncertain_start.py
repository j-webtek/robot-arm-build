"""Read-only signed-status reconciliation after the r55 one-use claim.

Rejected sequence guesses do not advance the controller gate. The first
accepted GET reports the park-step state; this script never sends a POST.
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
    parser.add_argument('--max-sequence', type=int, default=64)
    args = parser.parse_args()
    if not 1 <= args.max_sequence <= 256:
        parser.error('Invalid read-only sequence bound')
    root = Path(__file__).resolve().parents[1]
    binding = review_recovery_startup(root, args.startup_export, revision=55)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    if not (exports / f'r55-park-step-{boot}.json').is_file():
        raise ValueError('One-use park-step claim required')
    key = load_reviewed_key(root)
    accepted = None
    for sequence in range(1, args.max_sequence + 1):
        client = CharacterizationHTTP(binding['address'], key=key, boot=boot,
                                      read_only_initial_sequence=sequence)
        try:
            status = client('GET', '/rocell/park-step/status')
        except ValueError as error:
            if str(error) == 'Response sequence mismatch':
                continue
            raise
        accepted = (sequence, status.decode('ascii'))
        break
    report = dict(schema='rocell.r55_uncertain_start_reconciliation.v1', boot=boot,
                  accepted_sequence=accepted[0] if accepted else None,
                  route_status=accepted[1] if accepted else None,
                  next_sequence=accepted[0] + 1 if accepted else None,
                  searched_through=args.max_sequence,
                  read_only=True, movement_sent=False, retry_allowed=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r55-uncertain-start-reconciliation'}, [],
                            attachments={'r55-uncertain-start-reconciliation.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Reconciliation export invalid')
    print(json.dumps(dict(export_path=saved['path'], **report)))


if __name__ == '__main__':
    main()
