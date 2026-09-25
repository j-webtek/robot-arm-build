"""Replay evidence and export an offline correction comparison specification."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p4_endpoint_prediction import TRAIN, TEST, load_session
from rocell.application.p4_correction_comparison import review_comparison
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    sessions = [load_session(exports, source) for source in (TRAIN, TEST)]
    review = review_comparison(root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    if tuple(sessions[-1][-1]['final_positions']) != tuple(review['source_positions']):
        raise ValueError('Retained final position differs from comparison source')
    if tuple(sessions[-1][-1]['final_goals']) != tuple(review['source_goals']):
        raise ValueError('Retained final goals differ from comparison source')
    midpoint = [r for rows in sessions for r in rows if r['target']==1947 and r['direction']==-1]
    if len(midpoint)!=4 or any(r['endpoint_error_counts']!=3 for r in midpoint):
        raise ValueError('Repeated midpoint evidence differs')
    review['evidence_exports'] = [TRAIN, TEST]
    review['observed_decreasing_midpoint_errors_counts'] = [r['endpoint_error_counts'] for r in midpoint]
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'p4-correction-comparison-offline-review'}, [],
        attachments={'p4-correction-comparison.json':canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Review export invalid')
    print(saved['path'])
    print(canonical(review).decode())


if __name__ == '__main__':
    main()
