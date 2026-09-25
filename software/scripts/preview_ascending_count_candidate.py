"""Offline source-derived normalization; no controller access or runtime refit."""
import json
from pathlib import Path
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.wrist_command_comparison import summarize_wrist_trial
from rocell.application.ascending_wrist_candidate import evaluate_count_normalization,preview_candidate
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    sources=[('wizard-20260917T195958969852Z-3ac3e0c83e9d496eaf7ec3676d51460f','cartesian'),
        ('wizard-20260917T205837977415Z-3631210aa331486cb598544e23ccd9e2','all-joint')]
    rows=[];provenance=[]
    for source,kind in sources:
        data,digest=_read(root,source,'attachment-'+kind+'-trial.json')
        rows.append(summarize_wrist_trial(data));provenance.append(dict(export=source,sha256=digest))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    result=dict(evaluation=evaluate_count_normalization(model,rows),sources=provenance,
        candidate=preview_candidate(model,rows[-1]['final_joints_rad']),
        limitation='Counterfactual correction is not a replay of actuator dynamics; fresh baseline and separate desired/wire verdicts required before live use.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-ascending-count-candidate'},[],attachments={
        'ascending-count-candidate.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
