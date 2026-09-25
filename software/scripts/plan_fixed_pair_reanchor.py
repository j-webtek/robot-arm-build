"""Export a non-authorizing one-write re-anchor proposal from device evidence.

Offline only. This does not contact the arm or install firmware.
"""
import argparse
import json
from pathlib import Path

from rocell.application.fixed_pair_reanchor import plan_fixed_pair_reanchor
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-export', required=True)
    args = parser.parse_args(argv)
    exports = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    plan = plan_fixed_pair_reanchor(exports, args.capture_export)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'fixed-pair-reanchor-offline-plan'}, [], attachments={
        'fixed-pair-reanchor-plan.json': json.dumps(plan, sort_keys=True, indent=2).encode(),
    })
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Reanchor plan export invalid')
    print(json.dumps({'status': 'OFFLINE_PLAN_EXPORTED', 'export_path': saved['path'],
                      'movement_authorized': False, 'hardware_access': False}))


if __name__ == '__main__':
    main()
