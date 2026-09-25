"""Recomputed correction experiment preview; no native admission or device IO."""
import hashlib
import math

from rocell.motion.observational_wrist_plan import validated_wrist_baseline, JOINTS
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
from .first_motion_contract import canonical
from .wrist_correction_proposal import propose_wrist_correction


def preview_wrist_correction(originals, *, expected_basis, samples, now_ns, usb_identity):
    """Bind original evidence to a recent stable start, never caller-edited offsets.

    Host recency is checked, not device sample freshness. Future native admission
    must repeat these checks on its own capture and authenticate the USB context.
    """
    proposal = propose_wrist_correction(originals, expected_basis=expected_basis)
    if proposal['status'] != 'OFFLINE_EXPERIMENT_CANDIDATE':
        raise ValueError('Correction proposal held: '+', '.join(proposal['reasons']))
    if usb_identity != proposal['supplied_usb_identities'][0]:
        raise ValueError('Current USB identity differs from experiment evidence')
    baseline = validated_wrist_baseline(samples=samples, now_ns=now_ns)
    nominal = math.radians(proposal['nominal_target_deg'])
    motor = math.radians(proposal['experimental_motor_target_deg'])
    for sample in baseline:
        joints = sample['joints_rad']
        # Check every selected row, not just whichever sample is most favorable.
        for context, evidence in zip(proposal['expected_start_contexts_rad'], proposal['evidence']):
            expected = dict(context, t=math.radians(evidence['start_reported_deg']))
            if any(abs(joints[j]-expected[j]) > math.radians(.5) for j in JOINTS):
                raise ValueError('Starting pose differs from repeated experiment')
        delta = motor-joints['t']
        if not math.radians(.5) < abs(delta) <= math.radians(5):
            raise ValueError('Corrected motor delta outside bounded experiment')
        if delta*proposal['approach_direction'] <= 0 or (nominal-joints['t'])*proposal['approach_direction'] <= 0:
            raise ValueError('Correction approach direction differs')
    return dict(schema='rocell.wrist_correction_preview.v1',
        proposal_sha256=hashlib.sha256(canonical(proposal)).hexdigest(),
        baseline_sha256=hashlib.sha256(canonical(baseline)).hexdigest(),
        nominal_endpoint_rad=nominal, reported_start_joints_rad=baseline[-1]['joints_rad'],
        candidate_command=dict(T=101, joint=4, rad=motor, spd=20, acc=1),
        endpoint_tolerance_rad=math.radians(.5), maximum_commands=1,
        motion_authorized=False, automatic_next_command_allowed=False,
        device_sample_freshness_verified=False, physical_accuracy_verified=False,
        native_admission_implemented=False)


def simulate_wrist_correction(originals, *, samples, now_ns, usb_identity, residual_bias_deg,
                             transient_overshoot_deg=None):
    """Fixed five-second synthetic response using the real nominal-endpoint checker.

    This deliberately simple bias model tests verification semantics, not robot
    dynamics. A transient overshoot is sticky even if the final value recovers.
    No caller-supplied preview or physical-basis promotion is accepted.
    """
    values = [residual_bias_deg] + ([] if transient_overshoot_deg is None else [transient_overshoot_deg])
    if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10 for v in values):
        raise ValueError('Finite bounded synthetic bias required')
    preview = preview_wrist_correction(originals, expected_basis='SYNTHETIC_WIRE_REHEARSAL',
        samples=samples, now_ns=now_ns, usb_identity=usb_identity)
    start = tuple(preview['reported_start_joints_rad'][j] for j in JOINTS)
    final = preview['candidate_command']['rad']+math.radians(residual_bias_deg)
    rows = []
    for i in range(1,251):
        joints = list(start)
        joints[3] = start[3]+(final-start[3])*min(i/50,1)
        if i == 75 and transient_overshoot_deg is not None:
            joints[3] = preview['nominal_endpoint_rad']+math.radians(transient_overshoot_deg)
        stamp = now_ns+i*20_000_000
        rows.append((stamp, stamp, joints))
    endpoint = verify_reported_wrist(rows, start=start, target=preview['nominal_endpoint_rad'],
                                    capture_issues=(), transport_clean=True)
    return dict(schema='rocell.wrist_correction_simulation.v1',
        basis='SYNTHETIC_WIRE_REHEARSAL', preview=preview, endpoint=endpoint,
        simulated_final_rad=final, device_open_count=0, serial_write_count=0,
        motion_authorized=False, automatic_next_command_allowed=False)
