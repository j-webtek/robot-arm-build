"""Export a frozen offline repeatability proposal from verified r37 evidence."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.shoulder_repeatability_plan import freeze_models, draft_repeatability
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    model_id='wizard-20260920T170440265418Z-23aea01dab354f209f8c8ca5b3369e06'
    pose_id='wizard-20260920T170057744815Z-7c48419ee435484b97211c2fe9315cb2'
    model,model_sha=_read(root,model_id,'attachment-matrix-model-review.json')
    record,pose_sha=_read(root,pose_id,'attachment-characterization-result.json')
    final=record['observations'][-1]['joints']
    plan=draft_repeatability([final[i]['goal'] for i in (1,2)],
        [final[i]['position'] for i in (1,2)],record['bounds'],freeze_models(model))
    plan.update(model_source=dict(export_id=model_id,sha256=model_sha),
                pose_source=dict(export_id=pose_id,sha256=pose_sha),anchor_is_historical=True,
                evaluation=dict(refit_allowed=False,include_failed_legs=True,
                    metrics=['per-direction endpoint MAE and maximum error',
                             'same-target endpoint range', 'clear-response counts by direction'],
                    no_motion_counts_as_accuracy_validation=False))
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-repeatability-plan'},[],attachments={
        'repeatability-plan.json':json.dumps(plan,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Plan export failed')
    print(json.dumps(dict(export_path=saved['path'],frozen_model_sha256=plan['frozen_models']['sha256'],
        targets=plan['manifest']['goals'],stateful_rollout=[r['simulated_rollouts']['stateful_band'] for r in plan['legs']],
        hardware_access=False)))


if __name__=='__main__':main()
