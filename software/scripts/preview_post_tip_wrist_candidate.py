"""Freeze a local wrist candidate from one pinned verified export; offline only."""
import json
import argparse
from pathlib import Path
from rocell.application.post_tip_wrist_candidate import SOURCE, SOURCE_SHA256, REVERSE_SOURCE, REVERSE_SOURCE_SHA256, build_candidate
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reverse',action='store_true')
    parser.add_argument('--post-overshoot',action='store_true')
    args=parser.parse_args()
    if args.reverse and args.post_overshoot:parser.error('Choose one candidate scope')
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    report,digest=_read(root,REVERSE_SOURCE if args.reverse else SOURCE,'attachment-cartesian-trial.json')
    if digest!=(REVERSE_SOURCE_SHA256 if args.reverse else SOURCE_SHA256):
        raise ValueError('Pinned training bytes changed')
    candidate=build_candidate(report,reverse=args.reverse)
    if args.post_overshoot:
        from rocell.application.post_tip_wrist_candidate import transfer_post_overshoot_candidate
        candidate=transfer_post_overshoot_candidate(candidate)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-candidate-preview'},[],attachments={
        'post-tip-wrist-candidate.json':json.dumps(candidate,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:
        raise RuntimeError('Candidate export failed verification')
    print(json.dumps(dict(export=receipt['path'],candidate=candidate)))


if __name__=='__main__':main()
