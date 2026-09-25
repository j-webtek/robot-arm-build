"""Replay frozen affine candidate under independent joint-progress hypotheses."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.asynchronous_response_review import review_response_envelope
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.geometry import UrdfModel


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    source='wizard-20260917T201815261974Z-ed05b78c956046cca2f21cdad0c14675'
    report,digest=_read(root,source,'attachment-affine-trial.json');c=report['candidate']
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    reviews=[review_response_envelope(model,c['baseline_joints_rad'],c['desired_joints_rad'],extra_steps=n) for n in (0,1)]
    result=dict(source_export=source,source_sha256=digest,candidate_sha256=c['candidate_sha256'],
        reviews=reviews,motion_authorized=False,
        limitation='Independent monotone progress and nominal count variation are stress hypotheses, not verified actuator dynamics.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-asynchronous-response-review'},[],attachments={
        'asynchronous-response.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
