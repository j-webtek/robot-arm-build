"""Fit and score the frozen local interval from three completed r51 sessions."""
import argparse,json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_interval_model import fit_local_interval
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-export',action='append',required=True)
    args=parser.parse_args()
    if len(args.session_export)!=3:raise ValueError('Exactly three session exports required')
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    sessions=[]
    for export in args.session_export:
        result,_=_read(exports,export,'attachment-local-interval-session-result.json')
        sessions.append(result['rows'])
    model=fit_local_interval(sessions,source_exports=args.session_export)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'local-interval-model'},[],attachments={
        'local-interval-model.json':canonical(model)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Model export invalid')
    print(json.dumps({'export_path':saved['path'],
        'local_interval_interpolation_validated':model['local_interval_interpolation_validated'],
        'maximum_error_counts':model['heldout_maximum_paired_error_counts'],
        'validated_subinterval':model['validated_subinterval'],
        'movement_authorized':False}))


if __name__=='__main__':main()
