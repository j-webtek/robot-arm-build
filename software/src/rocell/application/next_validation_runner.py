"""Host runner for fixed repeat/reverse campaigns; no generic target surface."""
from pathlib import Path
from .characterization_repeatability_runner import RepeatabilityRunner
from .characterization_matched_runner import MatchedRunner
from .characterization_reference import decode_reference
from .characterization_host_session import _pose
from .shoulder_repeatability_plan import predict
from .shoulder_characterization import assess_leg
from .product_ghost_export_review import _read


CONFIG={
 'forward_repeat':dict(targets=[[2389,1725],[2377,1737],[2389,1725],[2378,1736]],
   initial_goals=[2378,1736],initial_positions=[2387,1730],initial_tolerance=1,
   trial_leg=3,trial_goals=[2389,1725],trial_positions=[2391,1724],direction=-1),
 'reverse_candidate':dict(targets=[[2389,1725],[2377,1737],[2385,1729]],
   initial_goals=[2378,1736],initial_positions=[2387,1730],initial_tolerance=1,
   trial_leg=2,trial_goals=[2377,1737],trial_positions=[2385,1731],direction=1),
 'reverse_control':dict(targets=[[2389,1725],[2377,1737],[2386,1728]],
   initial_goals=[2385,1729],initial_positions=[2387,1728],initial_tolerance=2,
   trial_leg=2,trial_goals=[2377,1737],trial_positions=[2385,1731],direction=1,
   desired=[2388,1729]),
 'heldout_candidate':dict(targets=[[2377,1737],[2388,1726]],
   initial_goals=[2386,1728],initial_positions=[2388,1727],initial_tolerance=1,
   trial_leg=1,trial_goals=[2377,1737],trial_positions=[2385,1731],direction=1,
   desired=[2390,1725]),
 'heldout_control':dict(targets=[[2377,1737],[2389,1725]],
   initial_goals=[2388,1726],initial_positions=[2390,1725],initial_tolerance=2,
   trial_leg=1,trial_goals=[2377,1737],trial_positions=[2385,1731],direction=1,
   desired=[2390,1725]),
 'second_heldout_candidate':dict(targets=[[2377,1737],[2389,1725],[2378,1736]],
   initial_goals=[2389,1725],initial_positions=[2390,1724],initial_tolerance=2,
   trial_leg=2,trial_goals=[2389,1725],trial_positions=[2391,1724],direction=-1,
   desired=[2387,1729]),
 'second_heldout_control':dict(targets=[[2389,1725],[2377,1737],[2389,1725],[2386,1728]],
   initial_goals=[2378,1736],initial_positions=[2388,1729],initial_tolerance=2,
   trial_leg=3,trial_goals=[2389,1725],trial_positions=[2391,1724],direction=-1,
   desired=[2387,1729]),
}

for _name in ('forward_repeat','reverse_candidate'):
    CONFIG[_name]['desired']=[2388,1729]


class NextValidationRunner(RepeatabilityRunner):
    def __init__(self,*args,variant,**kwargs):
        if variant not in CONFIG:raise ValueError('Fixed validation variant required')
        super().__init__(*args,**kwargs)
        if self.frozen_models['sha256']!='963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5':
            raise ValueError('Validation model identity differs')
        self.variant=variant;self.config=CONFIG[variant];self.targets=self.config['targets']

    @staticmethod
    def _near(actual,expected,tolerance):
        return all(abs(a-e)<=tolerance for a,e in zip(actual,expected))

    def review(self,raw,challenge):
        reference=decode_reference(raw,expected_sha256=challenge['reference'])
        rows=reference['poses'][-1]['joints'];anchor=[r['position'] for r in rows]
        if challenge['manifest']['goals']!=self.targets:raise ValueError('Exact validation manifest required')
        if ([rows[1]['goal'],rows[2]['goal']]!=self.config['initial_goals'] or
            not self._near(anchor[1:3],self.config['initial_positions'],self.config['initial_tolerance'])):
            raise ValueError('Validation starting state differs')
        if any(abs(g-p)>32 for target in self.targets for g,p in zip(target,anchor[1:3])):
            raise ValueError('Validation campaign excursion exceeded')
        prediction=predict(self.frozen_models,target=self.targets[-1],
            before=self.config['trial_positions'],direction=self.config['direction'])
        export=self._export('next-validation-predictions.json',dict(variant=self.variant,
            targets=self.targets,frozen_models=self.frozen_models,desired=self.config['desired'],
            predictions=prediction,boot=self.boot,campaign=challenge['campaign'],
            reference_sha256=challenge['reference']))
        return dict(measured_anchor=anchor,maximum_selected_excursion_counts=32,
            maximum_neighbour_excursion_counts=2,prediction_export=export,
            variant=self.variant,movement_authorized=False,physical_clearance_verified=False)

    def _record(self,path):
        p=Path(path);return _read(p.parent,p.name,'attachment-characterization-result.json')[0]

    def check_result(self,report,result):
        MatchedRunner.check_result(self,report,result)
        record=self._record(result['export_path']);trial=self.config['trial_leg']
        if record['leg']==trial-1:
            final=record['observations'][-1]['joints']
            if ([final[i]['goal'] for i in (1,2)]!=self.config['trial_goals'] or
                not self._near([final[i]['position'] for i in (1,2)],self.config['trial_positions'],1)):
                raise ValueError('Conditioning endpoint unmatched; no trial receipt')
        if record['leg']==trial:
            base=record['baseline']['joints']
            if ([base[i]['goal'] for i in (1,2)]!=self.config['trial_goals'] or
                not self._near([base[i]['position'] for i in (1,2)],self.config['trial_positions'],1)):
                raise ValueError('Trial starting state unmatched')

    def run(self,**kwargs):
        result=super().run(**kwargs);report=result['report'];trial=self.config['trial_leg']
        terminal=report.get('failed_leg_export')
        if terminal is None and report.get('legs') and report['legs'][-1]['leg']==trial:
            terminal=report['legs'][-1]
        if terminal is not None and terminal.get('leg')==trial:
            record=self._record(terminal['export_path']);before=_pose(record['baseline'])
            samples=[_pose(p) for p in record['observations']]
            assessment=assess_leg(before,self.targets[-1],samples,bounds=record['bounds'],
                delivery_confirmed=True,export_verified=True)
            residual=[samples[-1].positions[i]-self.targets[-1][i-1] for i in (1,2)]
            valid=(record['goals']==self.targets and
                self._near(before.positions[1:3],self.config['trial_positions'],1) and
                assessment['reason'] in ('MEASUREMENT_RETAINED','NO_CLEAR_RESPONSE') and
                max(map(abs,residual))<=12)
            if assessment['reason']=='NO_CLEAR_RESPONSE':
                valid=valid and samples[-1].finished_us-samples[0].started_us>=1800000
            actual=list(samples[-1].positions[1:3]);desired=self.config['desired']
            audit=dict(variant=self.variant,source_run=result['export_path'],
                source_result=terminal['export_path'],assessment=assessment,
                terminal_measurement_usable=valid,before=list(before.positions[1:3]),
                actual=actual,desired=desired,signed_error=[a-d for a,d in zip(actual,desired)],
                predictions=predict(self.frozen_models,target=self.targets[-1],
                    before=before.positions[1:3],direction=self.config['direction']),
                continuation_authorized=False,general_compensation_validated=False)
            result['trial_audit_export']=self._export('next-validation-terminal-review.json',audit)
        return result
