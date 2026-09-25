"""Offline joint residual/timing analysis; counterfactual FK is not calibration."""
import math
import hashlib
import base64
import json
from .first_motion_contract import canonical
from rocell.kinematics.firmware_reference import forward,inverse,joint_response_comparison


def review_servo_packets(report):
    """Describe retained numeric servo fields without inventing health limits.

    Load variation rules out byte-identical packets, not cached position reads.
    Missing voltage/torque/read-status fields remain unknown, never healthy.
    """
    originals=report['run'].get('feedback_originals',[])
    packets=[]
    for sample in originals:
        if sample.get('status')!='SUCCEEDED':continue
        if not sample.get('response_base64'):continue
        raw=base64.b64decode(sample['response_base64'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=sample.get('response_sha256'):
            raise ValueError('Original servo packet hash mismatch')
        packet=json.loads(raw)
        if packet.get('T')!=1051:raise ValueError('Servo feedback packet required')
        packets.append(packet)
    fields={}
    for key in ('e','tE','torswitchE','v'):
        values=[p[key] for p in packets if key in p]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValueError('Finite numeric servo field required')
        fields[key]=dict(present_samples=len(values),missing_samples=len(packets)-len(values),
            minimum=min(values) if values else None,maximum=max(values) if values else None,
            unique_values=sorted(set(values)))
    return dict(retained_packet_count=len(packets),fields=fields,
        whole_packet_unique_count=len({canonical(p) for p in packets}),
        per_servo_acquisition_freshness_verified=False,actuator_health_verified=False,
        load_is_calibrated_force=False,root_cause_identified=False)


def audit_command_mapping(report):
    """Audit host command binding and reference math, not actual servo writes."""
    run=report['run'];tx=run['transaction'];command=tx['command']
    if command.get('T')!=104 or not all(k in command for k in ('x','y','z','t','r','g')):
        return None
    target=[command[k] for k in ('x','y','z','t')]
    expected=[*inverse(*target),command['r'],command['g']]
    receipt=report.get('receipt') or {}
    request=run.get('move_request') or {}
    digest=hashlib.sha256(canonical(command)).hexdigest()
    rows=joint_response_comparison(tx['baseline_joints'],expected,tx['rows'][-1][3])
    opposite=[r['joint'] for r in rows if r['predicted_count_change']*r['reported_count_change']<0]
    return dict(schema='rocell.command_mapping_audit.v1',
        command_payload_sha256=digest,
        transport_payload_hash_matches=receipt.get('payload_sha256')==digest,
        reserved_command_matches=request.get('command')==command,
        inverse_expected_max_error_rad=max(abs(a-b) for a,b in zip(expected,tx['expected_joints'])),
        reference_count_comparison=rows,opposite_reported_count_direction=opposite,
        quantization_only_explanation_supported=all(abs(r['count_error'])<=1 for r in rows),
        controller_execution_acknowledged=receipt.get('controller_execution_acknowledged') is True,
        installed_firmware_verified=False,servo_bus_writes_observed=False,
        physical_cause_identified=False,motion_authorized=False)


def review_coordinated_trace(report):
    tx=(report.get('run') or {}).get('transaction') or {}
    command=tx.get('command') or {}
    if report.get('schema')!='rocell.native_cartesian_trial.v1' or not (command.get('T')==104 or (command.get('T')==101 and command.get('joint') in (3,4))):
        raise ValueError('Native Cartesian trace required')
    rows=tx.get('rows'); expected=tx.get('expected_joints'); baseline=tx.get('baseline_joints')
    if not isinstance(rows,list) or not 2<=len(rows)<=128 or len(expected)!=6 or len(baseline)!=6:
        raise ValueError('Bounded complete trace required')
    dispatch=tx['dispatch_started_ns']; previous=dispatch
    for row in rows:
        begin,end,pose,joints=row
        if (type(begin) is not int or type(end) is not int or not previous<=begin<=end
                or len(pose)!=4 or len(joints)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in [*pose,*joints,*expected,*baseline])):
            raise ValueError('Invalid trace values or time order')
        predicted=forward(*joints[:4])
        if math.dist(predicted[:3],pose[:3])>.01 or abs(predicted[3]-pose[3])>1e-5:
            raise ValueError('Trace differs from controller model')
        previous=end
    final=rows[-1][3]; target=forward(*expected[:4]); actual=forward(*final[:4])
    residual=[a-b for a,b in zip(actual[:3],target[:3])]
    last_time=(rows[-1][1]-dispatch)/1e9
    reviews=[]
    for i,key in enumerate(('base','shoulder','elbow','wrist_pitch','wrist_roll','gripper')):
        last_change=None; value=baseline[i]
        for row in rows:
            if abs(row[3][i]-value)>1e-9: last_change=(row[1]-dispatch)/1e9
            value=row[3][i]
        hypothetical=list(final); hypothetical[i]=expected[i]
        corrected=forward(*hypothetical[:4])
        reviews.append(dict(joint=key,requested_delta_deg=math.degrees(expected[i]-baseline[i]),
            reported_delta_deg=math.degrees(final[i]-baseline[i]),residual_deg=math.degrees(final[i]-expected[i]),
            last_reported_change_s=last_change,unchanged_tail_s=None if last_change is None else last_time-last_change,
            error_if_only_this_joint_ideal_mm=math.dist(corrected[:3],target[:3]),
            counterfactual_not_independent_measurement=True))
    failed=[dict(status=s.get('status'),phase=s.get('failure_phase'),category=s.get('error_category'),
                 elapsed_ms=s.get('elapsed_ms'),budget_s=s.get('http_io_deadline_budget_s'),
                 cleanup_confirmed=s.get('cleanup_confirmed'))
            for s in report['run'].get('feedback_originals',[]) if s.get('status')!='SUCCEEDED']
    from .joint_response_diagnosis import diagnose_joint_response
    return dict(schema='rocell.coordinated_trace_review.v1',source_status=report['status'],
        joint_response_diagnosis=diagnose_joint_response(report),
        servo_packet_review=review_servo_packets(report),
        command_mapping_audit=audit_command_mapping(report),
        position_residual_xyz_mm=residual,position_error_mm=math.dist(actual[:3],target[:3]),
        pitch_residual_rad=actual[3]-target[3],joints=reviews,last_retained_observation_s=last_time,
        feedback_failures=failed,physical_accuracy_verified=False,sensor_freshness_verified=False,
        compensation_fitted=False,hardware_access=False,motion_authorized=False)
