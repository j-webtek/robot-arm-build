"""One authenticated, read-only r57 return-route probe; no servo command."""

import argparse
import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    exports = root / 'runs/wizard-exports'
    binding = review_recovery_startup(root, args.startup_export, revision=57)
    boot = binding['expected_boot']
    key = load_reviewed_key(root)
    publish_reservation_bytes(exports, f'r57-auth-gate-used-{boot}.json',
                              canonical({'boot': boot, 'scope': 'one-read-only-route-probe',
                                         'retry_allowed': False,
                                         'servo_command_sent': False}),
                              maximum_bytes=2048)
    client = CharacterizationHTTP(binding['address'], key=key, boot=boot)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    try:
        response = client('GET', '/rocell/park-return/status')
    except Exception as error:
        saved = exporter.export({'mode': 'r57-park-return-read-only-probe-fault'}, [],
                                attachments={'r57-park-return-probe.json': canonical({
                                    'schema': 'rocell.r57_return_route_probe.v1',
                                    'boot': boot, 'startup_export_id': args.startup_export,
                                    'status': 'INCONCLUSIVE',
                                    'error_type': type(error).__name__,
                                    'retry_allowed': False,
                                    'servo_command_sent': False,
                                })})
        if not verify_export(Path(saved['path']))['valid']:
            raise ValueError('Read-only probe fault export failed') from error
        raise ValueError('Read-only probe fault exported: ' + saved['path']) from error
    if response != b'NEW|0':
        raise ValueError('Return route not idle on reviewed boot')
    saved = exporter.export({'mode': 'r57-park-return-read-only-probe'}, [],
                            attachments={'r57-park-return-status.txt': response,
                                         'r57-park-return-probe.json': canonical({
                                             'schema': 'rocell.r57_return_route_probe.v1',
                                             'boot': boot,
                                             'startup_export_id': args.startup_export,
                                             'response': response.decode('ascii'),
                                             'servo_command_sent': False,
                                             'movement_authorized': False,
                                             'retry_allowed': False,
                                         })})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Read-only route export failed')
    print(json.dumps({'status': 'R57_RETURN_ROUTE_IDLE', 'boot': boot,
                      'export': saved['path'], 'servo_command_sent': False}))


if __name__ == '__main__':
    main()
