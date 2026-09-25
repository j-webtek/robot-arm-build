"""Normalize old/new wrist trials without changing their original verdicts."""
import base64
import hashlib
import json
import math
from .first_motion_contract import canonical
from rocell.kinematics.firmware_reference import joint_response_comparison


def summarize_wrist_trial(report):
    return summarize_joint_trial(report,joint=4)


def summarize_joint_trial(report, *, joint):
    """Compare isolated elbow or wrist T101 trials, preserving legacy summaries."""
    if type(joint) is not int or joint not in (3,4):
        raise ValueError('Explicit elbow or wrist joint required')
    index=joint-1;label='wrist' if joint==4 else 'elbow'
    run=report.get('run') or report
    tx=run['transaction'];command=tx['command'];receipt=report['receipt']
    if (set(command)!={'T','joint','rad','spd','acc'} or command['T']!=101
            or command['joint']!=joint):
        raise ValueError('Exact matching T101 joint command required')
    if receipt['payload_sha256']!=hashlib.sha256(canonical(command)).hexdigest():
        raise ValueError('Receipt payload binding mismatch')
    raw=base64.b64decode(receipt['response_base64'],validate=True)
    if receipt['response_sha256']!=hashlib.sha256(raw).hexdigest():
        raise ValueError('Receipt response integrity mismatch')
    body=json.loads(raw)
    if not tx.get('rows'):raise ValueError('Observed response required')
    if tx['schema']=='rocell.all_joint_transaction.v1':
        start=[tx['baseline']['joints_rad'][k] for k in ('b','s','e','t','r','g')]
        samples=[r['reported_joints_rad'] for r in tx['rows']]
    else:
        start=tx['baseline_joints'];samples=[r[3] for r in tx['rows']]
    target=list(start);target[index]=command['rad']
    for q in [start,target,*samples]:
        if len(q)!=6 or any(type(x) not in (int,float) or not math.isfinite(x) for x in q):
            raise ValueError('Finite six-joint evidence required')
    comparison=joint_response_comparison(start,target,samples[-1],commanded_joints=(('t' if joint==4 else 'e'),))[index]
    return dict(command=command,original_state=tx['state'],baseline_joints_rad=start,
        final_joints_rad=samples[-1],sample_count=len(samples),**{label:comparison,
        label+'_span_rad':max(q[index] for q in samples)-min(q[index] for q in samples)},
        maximum_other_joint_change_rad=max(abs(q[i]-start[i]) for q in samples for i in range(6) if i!=index),
        receipt_kind=receipt['receipt_kind'],payload_hash_verified=True,
        **{'receipt_'+label+'_load_raw':body.get('tT' if joint==4 else 'tE')},
        load_is_calibrated_force=False,physical_accuracy_verified=False,
        comparison_is_matched_start=False,motion_authorized=False)
