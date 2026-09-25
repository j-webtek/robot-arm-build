"""Six-leg composition with frozen-model provenance and per-leg score exports."""
import copy
import json
from pathlib import Path
from .characterization_matched_runner import MatchedRunner
from .characterization_reference import decode_reference
from .shoulder_repeatability_plan import draft_repeatability, predict
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class RepeatabilityRunner(MatchedRunner):
    def __init__(self, *args, frozen_models, **kwargs):
        super().__init__(*args, **kwargs)
        self.frozen_models=copy.deepcopy(frozen_models)

    def _export(self, name, document):
        exporter=WizardDiagnosticExporter(self.root.resolve());exporter.prepare(create=True)
        saved=exporter.export({'mode':'repeatability-frozen-model-evidence'},[],
            attachments={name:json.dumps(document,indent=2).encode()})
        if not verify_export(Path(saved['path']))['valid']:
            raise ValueError('Prediction export verification failed; no progression')
        return saved['path']

    def review(self, raw, challenge):
        reference=decode_reference(raw,expected_sha256=challenge['reference'])
        joints=reference['poses'][-1]['joints']
        anchor=[joint['position'] for joint in joints]
        goals=[joints[i]['goal'] for i in (1,2)]
        expected=[[goals[0]+offset,goals[1]-offset] for offset in (-12,0)*3]
        if challenge['manifest']['goals']!=expected:
            raise ValueError('Exact six-leg repeatability sequence required')
        if any(abs(target[j]-anchor[j+1])>32 for target in expected for j in range(2)):
            raise ValueError('Repeatability target exceeds anchor envelope')
        proposal=draft_repeatability(goals,anchor[1:3],challenge['manifest']['bounds'],self.frozen_models)
        # This durable pre-start export freezes parameters and hypothetical
        # rollouts. Real per-leg scoring later uses measured, not predicted starts.
        prediction_export=self._export('repeatability-predictions.json',dict(
            proposal=proposal,boot=self.boot,campaign=challenge['campaign'],
            reference_sha256=challenge['reference'],compensation_enabled=False))
        return dict(measured_anchor=anchor,maximum_selected_excursion_counts=32,
            maximum_neighbour_excursion_counts=2,movement_authorized=False,
            physical_clearance_verified=False,live_qualified=False,
            experiment='three_twelve_count_outbound_return_pairs',
            prediction_export=prediction_export,frozen_model_sha256=self.frozen_models['sha256'])

    def check_result(self, report, result):
        super().check_result(report,result)
        record=json.loads((Path(result['export_path'])/'attachment-characterization-result.json').read_text())
        before=[record['baseline']['joints'][i]['position'] for i in (1,2)]
        actual=[record['observations'][-1]['joints'][i]['position'] for i in (1,2)]
        target=record['goals'][record['leg']]
        direction=1 if target[0]>record['baseline']['joints'][1]['goal'] else -1
        predictions=predict(self.frozen_models,target=target,before=before,direction=direction)
        score=dict(leg=record['leg'],source_export=result['export_path'],before=before,actual=actual,
            target=target,frozen_model_sha256=self.frozen_models['sha256'],refit_performed=False,
            basis='one_step_from_recorded_measured_start',compensation_enabled=False,
            predictions={name:dict(endpoint=values,signed_error=[a-p for a,p in zip(actual,values)])
                         for name,values in predictions.items()})
        report.setdefault('prediction_scores',[]).append(dict(leg=record['leg'],
            export_path=self._export('repeatability-score.json',score)))
