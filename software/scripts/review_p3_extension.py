"""Export the measured-source P3 extension review; no hardware access."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p3_extension_review import review_p3_extension
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

SOURCE='wizard-20260923T201517566882Z-2a37583111464777b465b59ccec7b9f0'

def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    folder=exports/SOURCE
    if not verify_export(folder)['valid']:raise ValueError('P2 source export invalid')
    raw=bytes.fromhex((folder/'attachment-large-pose-relief.hex.txt').read_text())
    report=review_p3_extension(raw,expected_boot='ce3a5f51d59110826b67e3bf48d1f260',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id']=SOURCE
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-p3-extension-review'},[],attachments={
        'p3-extension-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__=='__main__':main()
