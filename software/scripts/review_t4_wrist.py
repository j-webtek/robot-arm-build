"""Export the exact next wrist contract without accessing the controller."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.t4_wrist_review import review_t4_wrist
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260924T094712566120Z-c199a22385e441c0b96efde228b164e1'

def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    source = exports/SOURCE
    if not verify_export(source)['valid']:
        raise ValueError('T4L source export invalid')
    raw = bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    report = review_t4_wrist(raw, expected_boot='3393ba5a435af3044f3b554f5622f2fa',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id'] = SOURCE
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'offline-t4-wrist-review'}, [], attachments={
        't4-wrist-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Wrist review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__ == '__main__':
    main()
