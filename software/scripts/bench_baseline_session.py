"""Run one operator-confirmed zero-command baseline via public wizard actions.

No raw serial API, motion command or retry is available here. Serial opening may
cause controller startup movement. Use only with a present operator and current
secured/clear, stationary, adapter-powered USB setup confirmation.
"""
import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-confirmed',action='store_true')
    parser.add_argument('--serial',required=True)
    args=parser.parse_args()
    if not args.operator_confirmed:
        parser.error('A current operator setup confirmation is required')
    workspace=Path(__file__).resolve().parents[2]
    service=ArrivalWizardService(workspace,mode='physical')
    def action(name,**values):
        ticket=service.prepare_action(name,values,service.view()['revision'])
        receipt=service.execute_action(ticket['ticket_id'])
        while True:
            operation=service.operation(receipt['operation_id'])
            if operation['status'] not in {'QUEUED','RUNNING'}:
                print(json.dumps(operation),flush=True)
                if operation['status']!='SUCCEEDED':
                    raise RuntimeError(name+' did not succeed; no retry')
                return operation
            time.sleep(.1)
    try:
        action('inventory_devices',metadata_only=True,power_disconnected=False)
        candidates=service.view()['device_selection']['devices']['SERIAL']['candidates']
        matches=[c for c in candidates if (c['vid'],c['pid'],c['unit_serial'])==
                 ('10c4','ea60',args.serial) and not c['identity_blockers']]
        if len(matches)!=1:
            raise RuntimeError('Exact unique controller identity not found; no port opened')
        action('review_arm_candidate',choice_id=matches[0]['choice_id'],
               reviewer_id='Codex',metadata_only=True)
        action('inspect_native_arm_metadata',metadata_only=True,power_disconnected=False)
        action('record_powered_arm_startup',operator_id='Jack',adapter_on=True,
               usb_connected=True,secured_and_clear=True,stationary=True,startup_motion='unknown')
        action('capture_powered_arm_telemetry',firmware_unchanged=True)
    finally:
        try:
            action('export_logs')
        finally:
            service.shutdown()


if __name__=='__main__':
    main()
