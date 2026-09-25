"""Authenticated read-only status check for the installed r55 park-step route."""

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
    binding = review_recovery_startup(root, args.startup_export, revision=55)
    exports = root/'runs/wizard-exports'
    # This signed GET consumes the gate's first request sequence even though
    # it is read-only. Record that fact before network I/O so a later launcher
    # cannot create a new sequence-zero client on this boot.
    publish_reservation_bytes(exports,
        f'r55-auth-gate-used-{binding["expected_boot"]}.json',
        canonical(dict(boot=binding['expected_boot'], sequence=0,
                       route='/rocell/park-step/status',
                       attempt_may_have_reached_controller=True,
                       movement_sent=False)), maximum_bytes=2048)
    client = CharacterizationHTTP(binding['address'], key=load_reviewed_key(root),
                                  boot=binding['expected_boot'])
    status = client('GET', '/rocell/park-step/status')
    if status != b'NEW|0':
        raise ValueError('Park-step route is not idle')
    report = dict(schema='rocell.r55_park_step_readonly_route.v1',
                  boot=binding['expected_boot'], startup_export_id=args.startup_export,
                  route_status=status.decode('ascii'), movement_sent=False,
                  hardware_access=True, progression_authority=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r55-park-step-readonly-status'}, [], attachments={
        'r55-park-step-status.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Status export failed')
    print(json.dumps(dict(export_path=saved['path'], **report)))


if __name__ == '__main__':
    main()
