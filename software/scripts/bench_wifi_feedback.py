"""Explicit read-only wizard Wi-Fi diagnostic and workspace export; no motion."""
import json
import argparse
from pathlib import Path
import time
from rocell.application.arrival_wizard_service import ArrivalWizardService


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--sample',action='store_true',help='Eight sequential read-only observations; stop on fault')
    group.add_argument('--observe',action='store_true',help='35-second feedback-only observation with original responses')
    group.add_argument('--observe-fast',action='store_true',help='35-second feedback observation at up to 10 Hz, no movement')
    group.add_argument('--observe-spaced',action='store_true',help='35-second feedback observation with 500 ms post-completion cooldown')
    group.add_argument('--observe-intermediate',action='store_true',help='35-second feedback observation with 150 ms post-completion cooldown')
    group.add_argument('--observe-bounded',action='store_true',help='150 ms cooldown with native absolute 800 ms HTTP deadline')
    args=parser.parse_args()
    service=ArrivalWizardService(Path(__file__).resolve().parents[2],mode='physical')
    def action(name):
        ticket=service.prepare_action(name,{},service.view()['revision'])
        receipt=service.execute_action(ticket['ticket_id'])
        while True:
            operation=service.operation(receipt['operation_id'])
            if operation['status'] not in ('QUEUED','RUNNING'):
                return operation
            time.sleep(.1)
    try:
        outcome=action('observe_arm_wifi_bounded' if args.observe_bounded else 'observe_arm_wifi_feedback_intermediate' if args.observe_intermediate else 'observe_arm_wifi_feedback_spaced' if args.observe_spaced else 'observe_arm_wifi_feedback_fast' if args.observe_fast else 'observe_arm_wifi_feedback' if args.observe else 'sample_arm_wifi_feedback' if args.sample else 'read_arm_wifi_feedback')
        print(json.dumps(outcome),flush=True)
    finally:
        try:
            exported=action('export_logs')
            print(json.dumps(dict(export_status=exported['status'],
                receipt=exported.get('result',{}).get('receipt'))),flush=True)
        finally:
            service.shutdown()


if __name__=='__main__':
    main()
