"""Read-only first-leg preflight by default; --execute sends at most two wrist moves."""
import argparse
import json
from pathlib import Path
from rocell.providers.windows.compensated_wrist_native import run_native_cycle,validate_cycle_baseline
from rocell.providers.windows.arm_wifi_deadline import bounded_probe
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--mapping-cycle',action='store_true',help='Three-leg post-tip local mapping cycle instead of historical pair')
    p.add_argument('--require-hold',action='store_true',help='Require post-completion reported stability before every progression')
    p.add_argument('--transfer-cycle',action='store_true',help='Three-leg new-posture cycle with mandatory hold checks')
    args=p.parse_args()
    if args.transfer_cycle and args.mapping_cycle:p.error('Choose one cycle scope')
    root=Path(__file__).resolve().parents[2]/'software/runs'
    exporter=WizardDiagnosticExporter((root/'wizard-exports').resolve());exporter.prepare(create=True)
    def publish(*,index,report):
        receipt=exporter.export(dict(mode='compensated-local-wrist-cycle',leg_index=index),[],attachments={
            'cartesian-trial.json':json.dumps(report,allow_nan=False).encode()})
        return dict(export=receipt['path'],verified=verify_export(Path(receipt['path']).resolve())['valid'])
    if args.execute:
        reservations=(root/'cartesian-reservations').resolve();reservations.mkdir(parents=True,exist_ok=True)
        report=run_native_cycle(root=reservations,publish_leg=publish,mapping_cycle=args.mapping_cycle,require_hold=args.require_hold,transfer_cycle=args.transfer_cycle)
    else:
        with arm_transport_lock():baseline=bounded_probe(retain_response=True)
        report=dict(status='PREFLIGHT_REJECTED',baseline=baseline,motion_commands=0)
        try:
            report['preview']=validate_cycle_baseline(baseline,'map-transfer-entry' if args.transfer_cycle else 'map-cycle-entry' if args.mapping_cycle else 'down',mapping_cycle=args.mapping_cycle,transfer_cycle=args.transfer_cycle)
            report['status']='FIRST_LEG_PREFLIGHT_PASS_SECOND_REQUIRES_FRESH_FEEDBACK'
        except (ValueError,KeyError,TypeError):pass
    receipt=exporter.export(dict(mode='compensated-wrist-cycle-index',execute_requested=args.execute),[],attachments={
        'compensated-cycle.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid cycle export')
    print(json.dumps(dict(status=report['status'],export=receipt['path'],legs=report.get('legs',[]))))


if __name__=='__main__':main()
