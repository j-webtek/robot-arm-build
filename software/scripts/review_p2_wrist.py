"""Export the exact next wrist contract without accessing the controller."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p2_wrist_review import review_p2_wrist
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260923T194529289849Z-76fd6c1bf73a4a6eacf42e7510b2072d'

def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    source = exports/SOURCE
    if not verify_export(source)['valid']:
        raise ValueError('P2L source export invalid')
    raw = bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    report = review_p2_wrist(raw, expected_boot='6d2f06e84d08620829bd579b7f337c8b',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id'] = SOURCE
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'offline-p2-wrist-review'}, [], attachments={
        'p2-wrist-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Wrist review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__ == '__main__':
    main()
