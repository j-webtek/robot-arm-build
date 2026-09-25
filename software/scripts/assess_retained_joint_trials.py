"""Export evidence-level labels for existing trials, without any hardware I/O."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.joint_diagnostic_assessment import assess_joint_run
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    rows=[]
    for name in ('wizard-20260917T212741969917Z-84e87697a9404f2a95a3a321374800bd',
                 'wizard-20260917T213018314567Z-ebaacbf5eb60410ba58e880c6809b165',
                 'wizard-20260917T213514249166Z-619a4a1004cd42a9a78f67f24018de83'):
        report,digest=_read(root,name,'attachment-all-joint-trial.json')
        rows.append(dict(source_export=name,source_sha256=digest,assessment=assess_joint_run(report)))
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-joint-evidence-assessment'},[],attachments={
        'joint-evidence-assessment.json':json.dumps(rows,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],assessments=rows)))


if __name__=='__main__':main()
