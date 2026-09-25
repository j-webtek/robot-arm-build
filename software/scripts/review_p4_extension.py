"""Export the measured-source P4 extension review; no hardware access."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p4_extension_review import review_p4_extension
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

SOURCE='wizard-20260924T100122313690Z-ba8afa38d92b436c8f137dae16978a84'

def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    folder=exports/SOURCE
    if not verify_export(folder)['valid']:raise ValueError('T4 source export invalid')
    raw=bytes.fromhex((folder/'attachment-large-pose-relief.hex.txt').read_text())
    report=review_p4_extension(raw,expected_boot='4ea6cf4781ec4a1ff14ebbe6a45bf2bc',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id']=SOURCE
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-p4-extension-review'},[],attachments={
        'p4-extension-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__=='__main__':main()
