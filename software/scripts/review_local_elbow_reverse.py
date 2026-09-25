"""Offline reverse-elbow evidence bundle; no device access or command dispatch."""
import json
from pathlib import Path
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.elbow_reverse_review import review_reverse_identification
from rocell.application.wrist_command_comparison import summarize_joint_trial
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    software=Path(__file__).resolve().parents[1]
    root=(software/'runs/wizard-exports').resolve()
    source='wizard-20260917T213018314567Z-ebaacbf5eb60410ba58e880c6809b165'
    report,digest=_read(root,source,'attachment-all-joint-trial.json')
    followup='wizard-20260917T213104814701Z-86eef1254d414e90bcb09785af62cc32'
    passive,pdigest=_read(root,followup,'attachment-result-f22e6df632804f2c90c96587126fef60.json')
    model=UrdfModel.from_file(software/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    result=review_reverse_identification(report,passive['steps'][0]['report'],model)
    speed_export='wizard-20260917T213514249166Z-619a4a1004cd42a9a78f67f24018de83'
    speed_report,speed_digest=_read(root,speed_export,'attachment-all-joint-trial.json')
    speed_summary=summarize_joint_trial(speed_report,joint=3)
    original=result['trial']
    if (speed_summary['baseline_joints_rad']!=original['baseline_joints_rad']
            or speed_summary['command']!=dict(original['command'],spd=40)):
        raise ValueError('Same-start same-target speed comparison required')
    result['speed_comparison']=dict(export=speed_export,sha256=speed_digest,
        summary=speed_summary,matched_reported_start_and_target=True,
        limitation='Sequential trials have different command history; not randomized causal evidence.')
    history=[]
    for export in ('wizard-20260917T163506671259Z-de320d9a030045a3a03e24bfa4bff6a7',
                   'wizard-20260917T164028812312Z-ede1be83a00144d48545ebaea698d838'):
        old,sha=_read(root,export,'attachment-cartesian-trial.json')
        history.append(dict(export=export,sha256=sha,summary=summarize_joint_trial(old,joint=3)))
    result.update(sources=[dict(export=source,sha256=digest),dict(export=followup,sha256=pdigest)],
                  historical_trials=history,historical_posture_matches=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-elbow-reverse-review'},[],attachments={
        'elbow-reverse-review.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Export invalid')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
