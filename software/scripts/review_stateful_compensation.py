"""Prepare an offline interpolation proposal from verified frozen-model evidence."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.stateful_pair_compensation import propose
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    model_id='wizard-20260920T170731881182Z-5aa06999afa04b93a1c450b826e54391'
    run_id='wizard-20260920T172529936570Z-29afb96eae204b2483923ed76723933b'
    plan,model_sha=_read(root,model_id,'attachment-repeatability-plan.json')
    run,run_sha=_read(root,run_id,'attachment-smoke-run.json')
    endpoint_id=Path(run['legs'][-1]['export_path']).name
    record,record_sha=_read(root,endpoint_id,'attachment-characterization-result.json')
    final=record['observations'][-1]['joints']
    positions=[final[i]['position'] for i in (1,2)]
    result=propose(plan['frozen_models'],current_goals=[final[i]['goal'] for i in (1,2)],
        current_positions=positions,desired=(2388,1729),bounds=record['bounds'][1:3],
        tested_primary_range=(2377,2389),campaign_anchor=positions)
    training,_=_read(root,plan['model_source']['export_id'],'attachment-matrix-model-review.json')
    known_targets={tuple(row['target']) for row in training['rows']}
    known_targets.update(tuple(target) for target in record['goals'])
    result.update(anchor_is_historical=True,desired_is_offline_experiment_choice=True,
        source_model=dict(export_id=model_id,sha256=model_sha),
        source_run=dict(export_id=run_id,sha256=run_sha),
        source_pose=dict(export_id=endpoint_id,sha256=record_sha),
        proposed_command_seen_in_prior_evidence=tuple(result['proposed_goals']) in known_targets,
        r38_supports_this_command_sequence=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-stateful-compensation-review'},[],attachments={
        'stateful-compensation.json':json.dumps(result,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Proposal export failed')
    print(json.dumps(dict(export_path=saved['path'],desired=result['desired'],
        proposed_goals=result['proposed_goals'],predicted_error=result['predicted_error'],
        uncompensated_goals=result['uncompensated_coupled_goals'],
        uncompensated_predicted_error=result['uncompensated_predicted_error'],hardware_access=False)))


if __name__=='__main__':main()
