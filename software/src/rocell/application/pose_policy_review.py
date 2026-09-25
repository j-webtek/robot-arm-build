"""Offline pose versus installed-policy comparison, never movement admission.

Register windows are firmware admission constraints, not collision geometry.
Keep base placement unknown until independent registration evidence establishes it.
"""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .observed_pose_candidate import replay_candidate
from .observed_pose_installation import review_observed_installation
from .pose_observation_export import replay_pose_observation
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def compare_pose_policy(assessment, hold, pair):
    if assessment.get('origin')!='DEVICE_CAPTURE' or assessment.get('category')!='STABLE_SAMPLED_POSE':
        raise ValueError('Replayed stable device pose required')
    rows=assessment['joints']; windows=hold['hold_policy']['joints']
    if [r['servo_id'] for r in rows]!=list(range(11,18)) or len(windows)!=7:
        raise ValueError('Seven ordered joints required')
    compared=[]
    for row,window in zip(rows,windows):
        position=row['last_position']; low,high=window
        if any(type(v) is not int for v in (position,low,high)) or not 0<=low<=high<=4095:
            raise ValueError('Invalid position window')
        if not 0<=position<=4095 or row['torque'] not in (0,1):
            raise ValueError('Invalid joint state')
        compared.append(dict(servo_id=row['servo_id'],position=position,
            goal_readback=row['last_goal'],torque=row['torque'],installed_window=[low,high],
            position_within_window=low<=position<=high,
            distance_outside_window_counts=max(low-position,position-high,0)))
    offset=pair['offset_counts']
    if type(offset) is not int:raise ValueError('Integer offset required')
    elbow=compared[3]; target=elbow['position']+offset
    return dict(schema='rocell.pose_policy_comparison.v1',joints=compared,
        incompatible_servo_ids=[r['servo_id'] for r in compared if not r['position_within_window']],
        existing_pair_offset_counts=offset,existing_pair_target_if_reused=target,
        existing_pair_target_within_window=elbow['installed_window'][0]<=target<=elbow['installed_window'][1],
        base_to_board_registration='UNKNOWN_AFTER_REPOSITION',physical_clearance_verified=False,
        current_pose_verified=False,progression_authority=False,motion_authorized=False,
        message='Historical sampled pose only. Derived target is a compatibility check, not a motion proposal.')


def build_review(root, *, pose_export, stage_export, installation_export):
    root=Path(root).resolve(); exports=root/'runs/wizard-exports'
    installed=review_observed_installation(root,stage_export=stage_export,installation_export=installation_export)
    candidate=replay_candidate(root,installed['public_candidate_export'])['report']
    pose=replay_pose_observation(exports,pose_export)
    report=compare_pose_policy(pose['assessment'],candidate['hold_settings'],candidate['pair_settings'])
    return dict(report,pose_export=pose_export,pose_raw_sha256=pose['raw_bundle_sha256'],
        stage_export=stage_export,installation_export=installation_export,
        settings_candidate_sha256=installed['candidate_sha256'],
        hold_sha256=hashlib.sha256(canonical(candidate['hold_settings'])).hexdigest(),
        hardware_access=False,settings_changed=False)


def replay_review(root, export_id):
    root=Path(root).resolve()
    report,_=_read(root/'runs/wizard-exports',export_id,'attachment-pose-policy-review.json')
    rebuilt=build_review(root,**{k:report[k] for k in ('pose_export','stage_export','installation_export')})
    if canonical(report)!=canonical(rebuilt):raise ValueError('Pose policy review does not reproduce')
    return rebuilt


def export_review(root, **receipts):
    root=Path(root).resolve(); report=build_review(root,**receipts)
    exporter=WizardDiagnosticExporter(root/'runs/wizard-exports');exporter.prepare(create=True)
    saved=exporter.export({'mode':'pose-policy-review'},[],attachments={'pose-policy-review.json':canonical(report)})
    replay_review(root,Path(saved['path']).name)
    return dict(export_path=saved['path'],report=report)
