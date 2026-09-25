"""Compare selected successful and nonresponsive T101 records, without hardware."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.wrist_command_comparison import summarize_wrist_trial
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

SOURCES=[
 ('wizard-20260917T195626116113Z-de37dc78d4a04d82b6753701b8b387c0','cartesian'),
 ('wizard-20260917T195958969852Z-3ac3e0c83e9d496eaf7ec3676d51460f','cartesian'),
 ('wizard-20260917T205330864210Z-209fca03b0be4574a070160548049c1b','all-joint'),
 ('wizard-20260917T205516533663Z-8c9403ebd3714b3db411695db12db21a','all-joint'),
 ('wizard-20260917T205837977415Z-3631210aa331486cb598544e23ccd9e2','all-joint')]


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    rows=[]
    for source,kind in SOURCES:
        report,digest=_read(root,source,'attachment-'+kind+'-trial.json')
        rows.append(dict(export=source,source_sha256=digest,**summarize_wrist_trial(report)))
    result=dict(schema='rocell.wrist_command_history_comparison.v1',trials=rows,
        fitted_model=None,motion_authorized=False,
        limitation='Selected records at different postures/history; not a deadband measurement or matched A/B trial.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-wrist-command-comparison'},[],attachments={
        'wrist-command-comparison.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
