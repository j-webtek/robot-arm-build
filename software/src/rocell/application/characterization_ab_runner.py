"""Bounded matched-history pilot runner; installation-gated CLI, no deployed pilot yet."""
from pathlib import Path
from .characterization_repeatability_runner import RepeatabilityRunner
from .characterization_matched_runner import MatchedRunner
from .characterization_reference import decode_reference
from .characterization_host_session import _pose
from .shoulder_repeatability_plan import predict
from .shoulder_characterization import assess_leg
from .product_ghost_export_review import _read


class ABRunner(RepeatabilityRunner):
    def __init__(self,*args,variant,**kwargs):
        if variant not in ('control','compensated'):raise ValueError('Exact pilot variant required')
        super().__init__(*args,**kwargs)
        if self.frozen_models['sha256']!='963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5':
            raise ValueError('Pilot model identity differs')
        self.variant=variant
        self.targets=[[2377,1737],[2389,1725],[2387,1727] if variant=='control' else [2378,1736]]

    @staticmethod
    def _matched(position):
        return all(abs(p-r)<=1 for p,r in zip(position,(2391,1724)))

    def review(self,raw,challenge):
        reference=decode_reference(raw,expected_sha256=challenge['reference'])
        rows=reference['poses'][-1]['joints'];anchor=[r['position'] for r in rows]
        if challenge['manifest']['goals']!=self.targets:
            raise ValueError('Exact pilot manifest required')
        if ([rows[1]['goal'],rows[2]['goal']] not in ([2389,1725],[2387,1727])
                or not self._matched(anchor[1:3])):
            raise ValueError('Pilot starting state differs')
        if any(abs(g-p)>32 for target in self.targets for g,p in zip(target,anchor[1:3])):
            raise ValueError('Pilot campaign excursion exceeded')
        predict(self.frozen_models,target=self.targets[-1],before=anchor[1:3],direction=-1)
        export=self._export('ab-predictions.json',dict(variant=self.variant,targets=self.targets,
            frozen_models=self.frozen_models,desired=[2388,1729],boot=self.boot,
            campaign=challenge['campaign'],reference_sha256=challenge['reference']))
        return dict(measured_anchor=anchor,maximum_selected_excursion_counts=32,
            maximum_neighbour_excursion_counts=2,prediction_export=export,
            variant=self.variant,movement_authorized=False,physical_clearance_verified=False)

    def _record(self,path):
        p=Path(path)
        return _read(p.parent,p.name,'attachment-characterization-result.json')[0]

    def check_result(self,report,result):
        MatchedRunner.check_result(self,report,result)
        record=self._record(result['export_path'])
        if record['leg']==1:
            final=record['observations'][-1]['joints']
            if not self._matched([final[i]['position'] for i in (1,2)]):
                raise ValueError('Conditioning return unmatched; no trial receipt')
        if record['leg']==2 and not self._matched([record['baseline']['joints'][i]['position'] for i in (1,2)]):
            raise ValueError('Trial starting position unmatched')

    def run(self,**kwargs):
        result=super().run(**kwargs);report=result['report']
        terminal=report.get('failed_leg_export')
        if terminal is None and report.get('legs') and report['legs'][-1]['leg']==2:
            terminal=report['legs'][-1]
        if terminal is not None and terminal.get('leg')==2:
            record=self._record(terminal['export_path'])
            before=_pose(record['baseline']);samples=[_pose(p) for p in record['observations']]
            assessment=assess_leg(before,self.targets[2],samples,bounds=record['bounds'],
                delivery_confirmed=True,export_verified=True)
            residual=[samples[-1].positions[i]-self.targets[2][i-1] for i in (1,2)]
            valid=(record['goals']==self.targets and self._matched(before.positions[1:3]) and
                assessment['reason'] in ('MEASUREMENT_RETAINED','NO_CLEAR_RESPONSE') and
                max(map(abs,residual))<=12)
            if assessment['reason']=='NO_CLEAR_RESPONSE':
                valid=valid and samples[-1].finished_us-samples[0].started_us>=1800000
            actual=list(samples[-1].positions[1:3]);desired=[2388,1729]
            audit=dict(variant=self.variant,source_run=result['export_path'],
                source_result=terminal['export_path'],assessment=assessment,
                terminal_measurement_usable=valid,before=list(before.positions[1:3]),
                actual=actual,desired=desired,signed_error=[a-d for a,d in zip(actual,desired)],
                predictions=predict(self.frozen_models,target=self.targets[2],before=before.positions[1:3],direction=-1),
                continuation_authorized=False,compensation_validated=False)
            result['trial_audit_export']=self._export('ab-terminal-review.json',audit)
        return result
