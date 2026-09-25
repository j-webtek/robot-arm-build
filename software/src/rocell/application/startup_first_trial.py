"""Offline first-elbow trial construction; no network, key, reset or dispatch.

The target is a proposed absolute count, NOT an inference of current position.
Native startup admission must freshly observe the arm and reject a delta > 8.
"""
import hashlib
import math

from .first_motion_contract import canonical
from .servo_session_plan import freeze_session_plan
from .startup_command_contract import freeze_startup_plan

CONFIG_SHA256 = '75047d49f29468cf69374198321be3f19d56b35a8f98340781458cae56b0a216'


def build_first_trial(configuration, *, boot_id, command_id, target_count=2727,
                      origin='SIMULATION'):
    """Freeze the reviewed trial; DEVICE_CAPTURE is a label, not permission.

    No compensation is applied. The pinned elbow conversion is
    round(rad / (2*pi) * 4096) + 1024, clamped to [1024,3071].
    This inverse selects the count centre, away from rounding boundaries.
    """
    if hashlib.sha256(canonical(configuration)).hexdigest() != CONFIG_SHA256:
        raise ValueError('First trial requires exact provisioned configuration')
    if type(target_count) is not int:
        raise ValueError('Integer elbow target required')
    controller = configuration['controller_policy']
    policy = configuration['startup_policy']
    low, high = policy['joints'][3]
    rad = (target_count - 1024) * (2 * math.pi) / 4096
    limits = controller['elbow_bounds']
    if (not 1024 <= target_count <= 3071 or not low <= target_count <= high or
            not limits['minimum_rad'] <= rad <= limits['maximum_rad']):
        raise ValueError('Proposed elbow target outside reviewed bounds')
    payload = dict(T=101, joint=3, rad=rad, spd=20, acc=1)
    encoded = canonical(payload)
    command = dict(boot_id=boot_id, command_id=command_id, joint=3, servo_id=14,
        conversion_version=controller['conversion_version'], angle_units='rad',
        position_units='count', desired_rad=rad, wire_rad=rad,
        desired_count=target_count, wire_count=target_count, payload=payload,
        payload_sha256=hashlib.sha256(encoded).hexdigest())
    assessment = dict(tolerance_counts=2, settle_us=1000000,
        maximum_gap_us=600000, maximum_pair_us=policy['maximum_pair_us'])
    schedule = dict(sample_count=6, sample_interval_us=500000,
        maximum_lateness_us=500000, maximum_pair_us=policy['maximum_pair_us'])
    baseline = dict(maximum_delta_counts=8, settled_tolerance_counts=2,
        maximum_pair_us=policy['maximum_pair_us'], maximum_age_us=policy['maximum_age_us'])
    normal = freeze_session_plan(command, assessment, encoded, schedule, origin=origin,
        baseline_policy=baseline, whole_arm_policy=controller['whole_arm_policy'])
    return freeze_startup_plan(normal, policy)
