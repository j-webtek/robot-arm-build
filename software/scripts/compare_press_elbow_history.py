"""Offline same-command-family elbow comparison; no model fitting or motion."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.wrist_command_comparison import summarize_joint_trial
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    sources=[('wizard-20260917T162113108962Z-9d5d681c4a304b0195449e2e0ab3f489','cartesian'),
        ('wizard-20260917T164706353433Z-856f8792847b494fa047273ad9232888','cartesian'),
        ('wizard-20260917T165233201557Z-8e61d053d46f4edea4faf0db9d7a82b5','cartesian'),
        ('wizard-20260917T165444481148Z-8052bae4d7e74550b842ceb506217f37','cartesian'),
        ('wizard-20260917T211417782591Z-7a6acfc727ba4e6395a14ae328c02760','all-joint'),
        ('wizard-20260917T211830530621Z-37561f57a5134b439898e3cc7fcc7bbb','all-joint')]
    rows=[]
    for source,kind in sources:
        report,digest=_read(root,source,'attachment-'+kind+'-trial.json')
        rows.append(dict(export=source,source_sha256=digest,**summarize_joint_trial(report,joint=3)))
    result=dict(trials=rows,fitted_model=None,motion_authorized=False,
        limitation='Different postures/history and step sizes; failed wire verdicts remain failed. Not a matched A/B trial.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-elbow-command-comparison'},[],attachments={
        'elbow-command-comparison.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],trials=[dict(export=r['export'],
        baseline=r['baseline_joints_rad'],response=r['elbow']) for r in rows])))


if __name__=='__main__':main()
