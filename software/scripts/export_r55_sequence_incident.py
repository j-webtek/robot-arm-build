"""Export the failed first-rise authentication attempt without device access."""

import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


BOOT = '69c6050d2234a9ba244014797621f6dd'
STATUS = 'wizard-20260921T230313784880Z-300b4316c2e74d4289d70ab17e08dcc9'
RECONCILIATION = 'wizard-20260921T230827444781Z-8ad4df27c01c4966adf216f3ad8f266d'


def main():
    root = Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    claim_path = root/f'r55-park-step-{BOOT}.json'
    claim = json.loads(read_bounded_regular_file(claim_path, maximum_bytes=2048))
    prior, _ = _read(root, STATUS, 'attachment-r55-park-step-status.json')
    after, _ = _read(root, RECONCILIATION,
                     'attachment-r55-park-step-reconciliation.json')
    if (claim.get('boot') != BOOT or claim.get('scope') != 'one-first-park-step' or
            prior.get('boot') != BOOT or prior.get('route_status') != 'NEW|0' or
            after.get('boot') != BOOT or after.get('route_status') != 'NEW|0' or
            after.get('retry_allowed') is not False):
        raise ValueError('Incident sources differ')
    report = dict(schema='rocell.r55_first_step_sequence_incident.v1', boot=BOOT,
                  claimed_request=claim, prior_status_export_id=STATUS,
                  reconciliation_export_id=RECONCILIATION,
                  host_exception_type='ValueError',
                  host_exception='Response sequence mismatch',
                  likely_cause='Earlier authenticated status GET consumed sequence zero',
                  reconciled_owner_status='NEW|0',
                  park_owner_writes_attempted=0, motion_proven=False,
                  claim_consumed=True, retry_allowed=False,
                  new_startup_required=True, hardware_access=False)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r55-first-step-sequence-incident'}, [],
                            attachments={'r55-sequence-incident.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Incident export invalid')
    print(json.dumps(dict(export_path=saved['path'], **report)))


if __name__ == '__main__':
    main()
