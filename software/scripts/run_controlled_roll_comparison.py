"""Explicit LIVE roll comparison or command-spacing sweep. Default/help is inert.

Run only for the secured, powered, clear arm under the existing commissioning
conditions. Software cancellation is not a physical emergency stop.
"""
import argparse
import json
from pathlib import Path
import time

from rocell.arm.comparison_session import ComparisonSession, CommandSpacingSession, PairedSpacingSession, BalancedDirectionSession
from rocell.application.comparison_wizard_adapter import SessionJournal, WizardComparisonAdapter
from review_roll_comparison_block import load_leg


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--live-two-blocks',action='store_true',help='Execute up to eight single-leg wizard movements')
    group.add_argument('--live-six-probes',action='store_true',help='Execute six characterization probes plus six high-positioning moves')
    group.add_argument('--live-paired-spacing',action='store_true',help='Execute four 0.95/1.05 ABBA probes plus four high-positioning moves')
    group.add_argument('--live-balanced-directions',action='store_true',help='Eight bounded legs: ascending control / descending lookup / descending lookup / ascending control, each with positioning')
    args=parser.parse_args()
    if not args.live_two_blocks and not args.live_six_probes and not args.live_paired_spacing and not args.live_balanced_directions:
        parser.print_help();return
    from rocell.application.arrival_wizard_service import ArrivalWizardService
    root=Path(__file__).resolve().parents[2]
    session=(BalancedDirectionSession() if args.live_balanced_directions else
             PairedSpacingSession() if args.live_paired_spacing else
             CommandSpacingSession() if args.live_six_probes else ComparisonSession())
    journal=SessionJournal(root/'software'/'runs'/'wizard-exports',session.session_id)
    def publish(event):
        journal(event)
        print(json.dumps(event),flush=True)
    def exported(path):
        publish(dict(session_id=session.session_id,event='ADAPTER_EXPORT_AVAILABLE',
            host_monotonic_s=time.perf_counter(),export_path=str(path)))
    adapter=WizardComparisonAdapter(root,service_factory=ArrivalWizardService,export_observer=exported)
    result=session.run(execute_leg=adapter,review_leg=load_leg,publish=publish,
        clock=time.perf_counter,wait=time.sleep)
    print(json.dumps(result,indent=2),flush=True)
    if result['status']!='COMPLETED':raise SystemExit(1)


if __name__=='__main__':main()
