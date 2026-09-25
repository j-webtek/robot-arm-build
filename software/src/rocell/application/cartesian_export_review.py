"""Read-only projection of a verified workspace movement export, never replay."""
import hashlib
import math
import re
from pathlib import Path
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.kinematics.firmware_reference import inverse, joint_response_comparison


def validate_export_id(value):
    if type(value) is not str or not re.fullmatch(r'wizard-[0-9]{8}T[0-9]{12}Z-[a-f0-9]{32}',value):
        raise ValueError('Exact workspace diagnostic export ID required')
    return value


def _vector(value,count):
    if type(value) not in (list,tuple) or len(value)!=count or any(
            type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Complete finite retained telemetry required')
    return value


def review_cartesian_export(workspace,export_id):
    # Do not resolve the selected child: verification must see/reject symlinks.
    folder=Path(workspace).resolve()/'software/runs/wizard-exports'/validate_export_id(export_id)
    verified=verify_export(folder)
    if not verified['valid']:
        raise ValueError('Source export verification failed')
    filename='attachment-cartesian-trial.json'
    matches=[f for f in verified['files'] if f['name']==filename]
    if len(matches)!=1:
        raise ValueError('Export does not contain one Cartesian trial attachment')
    raw=read_bounded_regular_file(folder/filename,maximum_bytes=1024*1024)
    if hashlib.sha256(raw).hexdigest()!=matches[0]['sha256']:
        raise ValueError('Source changed after verification')
    source=decode_diagnostic_json(raw,maximum=1024*1024)
    if source.get('schema')!='rocell.native_cartesian_trial.v1':
        raise ValueError('A retained native trial is required, not a preview')
    run=source.get('run') or {}
    tx=run.get('transaction') or {}
    report=dict(schema='rocell.cartesian_export_review.v1',status='REVIEW_COMPLETE',
        source_export_id=export_id,source_attachment_sha256=matches[0]['sha256'],
        source_manifest_sha256=verified['manifest_sha256'],
        source_status=source.get('status'),command=tx.get('command'),
        reported_sample_count=len(tx.get('rows',[])),joint_comparison=[],
        position_error_mm=None,pitch_error_rad=None,next_step='REVIEW_INCOMPLETE_OBSERVATION',
        basis='RETAINED_CONTROLLER_TELEMETRY_NOT_INDEPENDENT_MEASUREMENT',
        hardware_access=False,motion_authorized=False,physical_accuracy_verified=False,
        replay_allowed=False,actuator_health_verified=False)
    if not tx.get('rows'):
        return report
    joints=_vector(tx['baseline_joints'],6)
    last=tx['rows'][-1]
    if type(last) is not list or len(last)!=4:
        raise ValueError('Retained observation layout invalid')
    pose=_vector(last[2],4)
    actual=_vector(last[3],6)
    command=tx['command']
    target=_vector(tx['target'],4)
    if command.get('T')==104:
        command_pose=_vector([command.get(k) for k in ('x','y','z','t')],4)
        if list(target)!=command_pose:
            raise ValueError('Recorded target differs from command')
        expected=(*inverse(*target),command.get('r'),command.get('g'))
        commanded=('b','s','e','t','r','g')
    elif command.get('T')==101 and command.get('joint')==3:
        expected=list(joints)
        expected[2]=command.get('rad')
        commanded=('e',)
    else:
        raise ValueError('Unsupported diagnostic command')
    _vector(expected,6)
    rows=joint_response_comparison(joints,expected,actual,commanded_joints=commanded)
    for row in rows:
        delta=row['predicted_count_change']
        observed=row['reported_count_change']
        row['response']='UNCOMMANDED_OBSERVATION' if not row['commanded'] else 'COMPARE_ENDPOINT_ERROR'
        if row['commanded'] and abs(delta)>=3:
            if observed==0:row['response']='NO_REPORTED_RESPONSE'
            elif delta*observed<0:row['response']='OPPOSITE_REPORTED_CHANGE'
            else:row['response']='EXPECTED_DIRECTION_REPORTED'
    report.update(joint_comparison=rows,target_pose=list(target),last_reported_pose=list(pose),
        position_error_mm=math.dist(target[:3],pose[:3]),pitch_error_rad=abs(target[3]-pose[3]),
        next_step='INVESTIGATE_JOINT_RESPONSE_BEFORE_MORE_MOTION' if any(r['response'] in
            ('NO_REPORTED_RESPONSE','OPPOSITE_REPORTED_CHANGE') for r in rows) else 'REVIEW_ENDPOINT_ERROR_AND_CLEARANCE')
    return report
