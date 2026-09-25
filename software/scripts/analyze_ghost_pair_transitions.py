"""Score three complete ghost-pair transition exports; offline only."""
import argparse,json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.ghost_pair_transition_analysis import analyze_ghost_pair_transitions
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-export',action='append',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    sessions=[]
    for export in args.session_export:
        result,_=_read(exports,export,'attachment-ghost-pair-transition-session-result.json')
        sessions.append(result['rows'])
    analysis=analyze_ghost_pair_transitions(sessions,source_exports=args.session_export)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'ghost-pair-transition-analysis'},[],attachments={
        'ghost-pair-transition-analysis.json':canonical(analysis)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Transition analysis export invalid')
    print(json.dumps({'export_path':saved['path'],
        'ghost_pair_cycle_validated':analysis['ghost_pair_cycle_validated'],
        'failures':len(analysis['failures']),'movement_authorized':False}))


if __name__=='__main__':main()
