"""Export the measured-source T4 lift review; no hardware access."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.t4_lift_review import review_t4_lift
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

SOURCE='wizard-20260924T000623600641Z-c2103044389a40f4a53461447c9b9ea8'

def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    folder=exports/SOURCE
    if not verify_export(folder)['valid']:raise ValueError('P3 source export invalid')
    raw=bytes.fromhex((folder/'attachment-large-pose-relief.hex.txt').read_text())
    report=review_t4_lift(raw,expected_boot='f7af4364ee3b87335970ee6052674b12',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    report['source_export_id']=SOURCE
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-t4-lift-review'},[],attachments={
        't4-lift-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Review export invalid')
    print(saved['path'])
    print(canonical(report).decode())

if __name__=='__main__':main()
