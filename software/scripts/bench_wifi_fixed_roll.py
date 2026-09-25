"""ONE LIVE fixed roll target, followed only by read-only observation and export.

No sequence, retry or return. Each invocation is a distinct wizard action.
"""
import argparse
import json
import math
from pathlib import Path
import time
from rocell.application.arrival_wizard_service import ArrivalWizardService


def summarize_operation(op):
    """Display failures without treating absent endpoint evidence as success."""
    result=op.get('result') or {}
    steps=result.get('steps') or [{}]
    report=steps[0].get('report') or {}
    outcome=report.get('outcome') or {}
    tx=outcome.get('transaction') or {}
    endpoint=(tx.get('result') or {}).get('endpoint') or {}
    samples=report.get('samples') or [{}]
    return dict(operation=op['operation_id'],action=op['action_id'],status=op['status'],
        transaction_state=tx.get('state'),failure_reason=report.get('reason') or outcome.get('error'),
        command_send_attempted=outcome.get('command_send_attempted'),
        target_deg=report.get('fixed_target_deg'),correction=report.get('correction_candidate'),
        characterization=report.get('characterization'),
        final_deg=math.degrees(tx['rows'][-1][2][4]) if tx.get('rows') else None,
        error_deg=math.degrees(endpoint['final_error_rad']) if endpoint.get('final_error_rad') is not None else None,
        observation=report.get('reconstruction'),last_pose=samples[-1].get('joints_rad'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',choices=('low','high','zero','center_up','center_down','corrected_up','corrected_down','probe_low','probe_high','lookup','adjacent','adjacent_low','adjacent_high','adjacent_lookup'),help='LIVE fixed roll leg; adjacent variants use desired 1.50 degrees')
    parser.add_argument('--position-only',action='store_true',help='Omit the separate 35-second observation after endpoint verification; still one live command and export')
    args=parser.parse_args()
    service=ArrivalWizardService(Path(__file__).resolve().parents[2],mode='physical')
    def action(name):
        ticket=service.prepare_action(name,{},service.view()['revision'])
        receipt=service.execute_action(ticket['ticket_id'])
        while True:
            operation=service.operation(receipt['operation_id'])
            if operation['status'] not in ('QUEUED','RUNNING'):return operation
            time.sleep(.05)
    def show(op):
        print(json.dumps(summarize_operation(op)),flush=True)
    try:
        outcome=action('run_wifi_roll_'+args.target+'_trial');show(outcome)
        if outcome['status']=='SUCCEEDED' and not args.position_only:show(action('observe_arm_wifi_bounded'))
    finally:
        try:
            exported=action('export_logs')
            print(json.dumps(dict(export_status=exported['status'],
                path=exported.get('result',{}).get('receipt',{}).get('path'))),flush=True)
        finally:service.shutdown()


if __name__=='__main__':main()
