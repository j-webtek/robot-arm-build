"""Compare verified pre-command, transient and settled records, offline only."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.shoulder_rise_review import ShoulderRiseReview
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    run_id='wizard-20260919T212201457428Z-7365a00c813a4fdfb9727a9a4cec7146'
    pose_id='wizard-20260919T212404883110Z-d3b2fe63cc114e438ead8d5f8f9d81d2'
    run,run_hash=_read(root,run_id,'attachment-shoulder-run.json')
    pose,pose_hash=_read(root,pose_id,'attachment-pose-assessment.json')
    review=ShoulderRiseReview(run['boot_id'],run['command_id'],stable=True)
    records=[]
    for item in run['records']:
        path=Path(item).resolve()
        if path.parent!=root or not verify_export(path)['valid']:raise ValueError('Invalid event export')
        records.append(review.accept((path/'attachment-shoulder-event.txt').read_bytes()))
    faults=[op['response'] for op in run['operations'] if op.get('response',{}).get('event')=='STATE_MISMATCH']
    if len(records)!=5 or len(faults)!=1 or pose['category']!='STABLE_SAMPLED_POSE':
        raise ValueError('Unexpected result sequence')
    baseline=records[0]['joints'];transient=faults[0]['joints'];joints=[]
    for index,joint in enumerate(pose['joints']):
        if joint['servo_id']!=11+index or joint['position_span']!=0 or not joint['controls_unchanged']:
            raise ValueError('Settled capture changed')
        start=baseline[index][1];final=joint['last_position']
        joints.append(dict(servo_id=11+index,initial_position=start,
            transient_position=transient[index][1],settled_sampled_position=final,
            commanded_goal=joint['last_goal'],observed_delta=final-start,
            residual=final-joint['last_goal']))
    report=dict(schema='rocell.r29_settled_recovery_analysis.v1',run_export=run_id,
        run_receipt=run_hash,settled_assessment_export=pose_id,settled_receipt=pose_hash,
        joints=joints,verified_prewrite_and_action_records=len(records),
        outcome='DIRECTIONAL_PROGRESS_WITH_ENDPOINT_SHORTFALL',
        diagnostic_restart_between_command_and_settled_capture=True,
        no_additional_target_writes=True,hardware_access=False,
        physical_clearance_verified=False,physical_accuracy_verified=False,
        limitation='The settled observations are sampled encoder positions, not a current or physical-tip guarantee.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-r29-settled-analysis'},[],
                         attachments={'settled-recovery-analysis.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid analysis export')
    print(canonical(dict(export_path=saved['path'],**report)).decode())


if __name__=='__main__':main()
