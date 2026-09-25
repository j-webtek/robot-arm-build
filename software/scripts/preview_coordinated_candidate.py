"""Fit and screen a local hypothesis from a verified export; no hardware access."""
import argparse
import json
from pathlib import Path
from rocell.application.coordinated_candidate import preview_coordinated_candidate
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_id')
    parser.add_argument('--local-tip',action='store_true',help='Fit the named hypothetical tip press, not the ghost approach')
    parser.add_argument('--post-transfer',action='store_true',help='Separate current-posture tip candidate with 6 mm hypothetical tip bound')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]/'software/runs/wizard-exports'
    source,digest=_read(root,args.export_id,'attachment-cartesian-trial.json')
    model=None
    if args.local_tip or args.post_transfer:
        from rocell.geometry import UrdfModel
        model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report=preview_coordinated_candidate(source,tip_model=model,post_transfer=args.post_transfer)
    report.update(source_export=args.export_id,source_attachment_sha256=digest)
    exporter=WizardDiagnosticExporter(root.resolve());exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='offline-coordinated-candidate'),[],attachments={
        'coordinated-candidate.json':json.dumps(report,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:
        raise ValueError('Candidate export verification failed')
    print(json.dumps(dict(export=receipt['path'],preview=report)))


if __name__=='__main__':main()
