"""Freeze a session-one table and retrospectively score session two, offline."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p4_endpoint_prediction import TRAIN,TEST,load_session,fit_table,evaluate
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    table=fit_table(load_session(exports,TRAIN))
    frozen=canonical(asdict(table));digest=hashlib.sha256(frozen).hexdigest()
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    model=exporter.export({'mode':'p4-endpoint-prediction-freeze'},[],attachments={
        'p4-endpoint-table.json':frozen})
    if not verify_export(Path(model['path']))['valid']:raise ValueError('Model export invalid')
    result=evaluate(table,load_session(exports,TEST))
    if canonical(asdict(table))!=frozen:raise ValueError('Table changed during evaluation')
    report=dict(schema='rocell.p4_endpoint_prediction_review.v1',training_summary=TRAIN,
        evaluation_summary=TEST,model_export=model['path'],model_sha256=digest,
        model=asdict(table),evaluation=result,hardware_access=False,
        compensation_applied=False,physical_accuracy_improvement_verified=False,
        retrospective_split=True,prospectively_blinded_test=False,
        limitations=['Both sessions were already observed before this retrospective analysis',
            'No evaluation-session values used for fitting or refitting the fixed cell means',
            'Only four observed goal/direction cells at fixed pose, speed and load',
            'Predicts feedback for unchanged commands; does not validate corrected commands',
            'No interpolation, other-joint mapping or Cartesian/stylus-accuracy claim'])
    saved=exporter.export({'mode':'p4-endpoint-prediction-review'},[],attachments={
        'p4-endpoint-prediction-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Review export invalid')
    print(json.dumps(dict(export=saved['path'],**report)))


if __name__=='__main__':main()
