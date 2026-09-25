"""Read-only preflight by default. --execute sends at most two local elbow moves."""
import argparse
import json
from pathlib import Path
from rocell.providers.windows.compensated_elbow_native import run_native_cycle, validate_cycle_baseline
from rocell.providers.windows.arm_wifi_deadline import bounded_probe
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]/'software/runs'
    exporter=WizardDiagnosticExporter((root/'wizard-exports').resolve()); exporter.prepare(create=True)
    def publish(*,index,report):
        receipt=exporter.export(dict(mode='compensated-local-elbow-cycle',leg_index=index),[],
            attachments={'cartesian-trial.json':json.dumps(report,allow_nan=False).encode()})
        valid=verify_export(Path(receipt['path']).resolve())['valid']
        return dict(export=receipt['path'],verified=valid)
    if args.execute:
        reservations=(root/'cartesian-reservations').resolve(); reservations.mkdir(parents=True,exist_ok=True)
        report=run_native_cycle(root=reservations,publish_leg=publish)
    else:
        with arm_transport_lock(): baseline=bounded_probe(retain_response=True)
        report=dict(status='PREFLIGHT_REJECTED',baseline=baseline,motion_commands=0)
        try:
            report['preview']=validate_cycle_baseline(baseline,3)
            report['status']='FIRST_LEG_PREFLIGHT_PASS_SECOND_REQUIRES_FRESH_FEEDBACK'
        except (ValueError,KeyError,TypeError): pass
    receipt=exporter.export(dict(mode='compensated-cycle-index',execute_requested=args.execute),[],
        attachments={'compensated-cycle.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']: raise ValueError('Cycle export verification failed')
    print(json.dumps(dict(status=report['status'],export=receipt['path'],legs=report.get('legs',[]))))


if __name__=='__main__': main()
