"""Export the exact next wrist contract without accessing the controller."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p4_wrist_review import review_p4_wrist
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260924T101235379282Z-701e8f9afca3454682c92dafbb258f43'

def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    source = exports/SOURCE
    if not verify_export(source)['valid']:
        raise ValueError('P4E source export invalid')
    raw = bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    report = review_p4_wrist(raw, expected_boot='30838e5a53f316c62ac21f976ce95424',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id'] = SOURCE
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'offline-p4-wrist-review'}, [], attachments={
        'p4-wrist-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Wrist review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__ == '__main__':
    main()
