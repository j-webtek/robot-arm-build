"""Export the exact next wrist contract without accessing the controller."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p3_wrist_review import review_p3_wrist
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260923T220934352526Z-00cc861d428f4b168b5c1ead42c5de8e'

def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    source = exports/SOURCE
    if not verify_export(source)['valid']:
        raise ValueError('P3E source export invalid')
    raw = bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    report = review_p3_wrist(raw, expected_boot='e61c5767d2d5b0616ac34cd847b2f59d',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id'] = SOURCE
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'offline-p3-wrist-review'}, [], attachments={
        'p3-wrist-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Wrist review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__ == '__main__':
    main()
