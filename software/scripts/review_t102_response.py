"""Review first T102 experiment and its separate passive capture; no hardware I/O."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.all_joint_response_review import review_all_joint_response
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    trial_id='wizard-20260917T204600889945Z-29fa41ba84364dc7b7d39464ec5ce3a9'
    observation_id='wizard-20260917T204704544754Z-55f811903612428d8ec31d37e89a2421'
    trial,trial_hash=_read(root,trial_id,'attachment-all-joint-trial.json')
    observation,observation_hash=_read(root,observation_id,
        'attachment-result-5d78fd7df8624104b2312fd7e2ca5830.json')
    result=review_all_joint_response(trial,observation['steps'][0]['report'])
    result['sources']=[dict(export=trial_id,sha256=trial_hash),
                       dict(export=observation_id,sha256=observation_hash)]
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-t102-response-review'},[],attachments={
        't102-response-review.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
