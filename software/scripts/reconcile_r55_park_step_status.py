"""Read only: reconcile r55 route after a known sequence-zero rejection.

The prior signed status export proves sequence 0 was accepted on this boot.
No POST is available from this resumed client; it cannot retry movement.
"""

import argparse
import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


PRIOR_STATUS = 'wizard-20260921T230313784880Z-300b4316c2e74d4289d70ab17e08dcc9'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    binding=review_recovery_startup(root,args.startup_export,revision=55)
    exports=root/'runs/wizard-exports'
    earlier,_=_read(exports,PRIOR_STATUS,'attachment-r55-park-step-status.json')
    if (earlier.get('schema')!='rocell.r55_park_step_readonly_route.v1' or
            earlier.get('boot')!=binding['expected_boot'] or
            earlier.get('route_status')!='NEW|0' or
            earlier.get('movement_sent') is not False):
        raise ValueError('Prior signed sequence-zero status not established')
    client=CharacterizationHTTP(binding['address'],key=load_reviewed_key(root),
        boot=binding['expected_boot'],read_only_initial_sequence=1)
    status=client('GET','/rocell/park-step/status')
    if status not in (b'NEW|0',b'CAPTURING_START|0',b'PREWRITE|0',
                      b'CAPTURING_ENDPOINT|1',b'AWAITING_DURABLE_EXPORT|1',
                      b'PARK_STEP_RECORDED|1') and not status.startswith(
                          (b'START_GATE_FAILED|0',b'PREWRITE_CHANGED|0',
                           b'WRITE_DELIVERY_UNCERTAIN|1',b'ENDPOINT_GATE_FAILED|1')):
        raise ValueError('Unexpected park-step route status')
    report=dict(schema='rocell.r55_park_step_reconciliation.v1',
                boot=binding['expected_boot'],prior_status_export_id=PRIOR_STATUS,
                route_status=status.decode('ascii'),read_only=True,
                movement_command_sent_by_reconciliation=False,
                retry_allowed=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r55-park-step-readonly-reconciliation'},[],
        attachments={'r55-park-step-reconciliation.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Reconciliation export invalid')
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__':main()
