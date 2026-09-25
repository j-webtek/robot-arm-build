"""Baseline-bound model experiment preview, deliberately not native admission.

Rebuild from model and original exports, never from an editable proposal. A
future native owner must repeat this check on its own capture before dispatch.
"""
import hashlib
import math

from .first_motion_contract import canonical
from .wrist_model_correction import propose_model_correction
from rocell.motion.observational_wrist_plan import JOINTS, validated_wrist_baseline


def verify_model_correction_preview(preview_raw, model_raw, **evidence):
    """Reconstruct every field; a hash alone cannot validate edited targets.

    Intended for independent boundary checks once native integration exists.
    This read-only comparison does not grant ownership or dispatch permission.
    """
    if type(preview_raw) is not bytes or len(preview_raw)>16384:
        raise ValueError('Bounded immutable model preview required')
    rebuilt = preview_model_correction(model_raw, **evidence)
    if canonical(rebuilt) != preview_raw:
        raise ValueError('Model preview targets, baseline or context changed')
    return dict(preview_sha256=hashlib.sha256(preview_raw).hexdigest(),
                consistent=True, motion_authorized=False)


def preview_model_correction(model_raw, *, expected_model_sha256, exports,
                             historical_start_joints_rad, samples, now_ns,
                             current_context_references):
    """Bind both targets to every recent baseline row and historical context.

    These supplied samples/context are not authenticated physical evidence.
    Native identity, owned raw capture, one-use admission and retention remain
    separate requirements. Nothing returned here can dispatch a command.
    """
    proposal = propose_model_correction(model_raw,
        expected_model_sha256=expected_model_sha256, exports=exports,
        start_joints_rad=historical_start_joints_rad)
    p = proposal.to_dict()
    if current_context_references != p['context_references']:
        raise ValueError('Current context differs from model evidence')
    baseline = validated_wrist_baseline(samples=samples, now_ns=now_ns)
    if now_ns-baseline[-1]['host_received_ns'] > 100_000_000:
        raise ValueError('Model preview baseline exceeds 100ms age')
    nominal = math.radians(p['nominal_target_deg'])
    motor = p['proposed_command_target_rad']
    direction = 1 if p['direction']=='INCREASING' else -1
    for sample in baseline:
        joints = sample['joints_rad']
        if any(abs(joints[j]-historical_start_joints_rad[i]) > math.radians(.5)
               for i,j in enumerate(JOINTS)):
            raise ValueError('Baseline differs from historical six-joint context')
        for target in (nominal, motor):
            delta = target-joints['t']
            if not math.radians(.5) < abs(delta) <= math.radians(5) or delta*direction <= 0:
                raise ValueError('Nominal or command delta exceeds approach bounds')
    return dict(schema='rocell.model_correction_preview.v1',
        proposal_sha256=proposal.sha256,
        baseline_sha256=hashlib.sha256(canonical(baseline)).hexdigest(),
        context_references=dict(current_context_references),
        nominal_endpoint_rad=nominal,
        candidate_command=dict(T=101,joint=4,rad=motor,spd=20,acc=1),
        reported_start_joints_rad=dict(baseline[-1]['joints_rad']),
        baseline_last_host_received_ns=baseline[-1]['host_received_ns'],
        maximum_commands=1, observation_s=5, endpoint_tolerance_rad=math.radians(.5),
        automatic_retry=False, motion_authorized=False,
        native_admission_implemented=False, device_sample_freshness_verified=False)
