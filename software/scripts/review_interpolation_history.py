"""Compare measured-start and prior-command-start reference paths; no hardware."""
import json
import math
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.application.wrist_tip_review import modeled_tip
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward,inverse
from rocell.simulation.controller import ControllerPose,simulate_t104_trace


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    ids=('wizard-20260917T201423927986Z-2d8334fcc06a430eb158652560d12a63',
         'wizard-20260917T202005073864Z-4a7bed0ff01649c3b16e0e62452abdc7')
    records=[_read(root,i,'attachment-cartesian-trial.json') for i in ids]
    prior=records[0][0]['run']['transaction'];current=records[1][0]['run']['transaction']
    q=current['baseline_joints'];actual=forward(*q[:4]);old=prior['command'];cmd=current['command']
    if old['T']!=104 or cmd['T']!=104:raise ValueError('Consecutive retained T104 commands required')
    previous_goal=[old[k] for k in ('x','y','z','t')];target=[cmd[k] for k in ('x','y','z','t')]
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin=modeled_tip(model,q);scenarios=[]
    for label,start in (('REPORTED_START_ASSUMPTION',actual),('PREVIOUS_GOAL_WITHOUT_INTERVENING_FEEDBACK',previous_goal),
                        ('REFERENCE_T105_REFRESHED_XYZ_PITCH',actual)):
        trace=simulate_t104_trace(ControllerPose(*start,*q[4:]),ControllerPose(*target,*q[4:]),
            spd_coefficient=cmd['spd'],maximum_samples=1024)
        samples=[]
        for sample in trace.samples:
            p=sample.pose;joints=[*inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad),*q[4:]]
            samples.append(dict(fraction=sample.cosine_eased_fraction,joints_rad=joints,
                hypothetical_tip_displacement_mm=math.dist(origin,modeled_tip(model,joints))))
        scenarios.append(dict(scenario=label,sample_count=len(samples),
            starting_joint_offset_deg=[math.degrees(a-b) for a,b in zip(samples[0]['joints_rad'],q)],
            maximum_tip_displacement_mm=max(s['hypothetical_tip_displacement_mm'] for s in samples),samples=samples))
    result=dict(schema='rocell.interpolation_history_review.v1',sources=[dict(export=i,sha256=r[1]) for i,r in zip(ids,records)],
        prior_goal_to_reported_start_mm=math.dist(previous_goal[:3],actual[:3]),scenarios=scenarios,
        installed_firmware_verified=False,physical_cause_identified=False,motion_authorized=False,
        limitations=['Stored controller interpolation state is not exposed by the retained feedback.',
            'Reference T105 refreshes stored XYZ/pitch. Prior-goal-only scenario omits intervening feedback and cannot be presumed applicable.',
            'Reference archive is not verified installed firmware; prior goal is a counterfactual, not recovered state.',
            'Ideal reference paths do not simulate servo lag, backlash or closed-loop dynamics.'])
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-interpolation-history-review'},[],attachments={
        'interpolation-history.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],gap_mm=result['prior_goal_to_reported_start_mm'],
        scenarios=[{k:v for k,v in s.items() if k!='samples'} for s in scenarios])))


if __name__=='__main__':main()
