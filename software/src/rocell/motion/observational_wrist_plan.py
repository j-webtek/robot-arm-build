"""Pure preview for observational commissioning; never an execution permit.

T101 accepts an absolute radian target. An incremental *test intention* must
therefore be converted using the selected controller-reported baseline. Recent
host acquisition does not prove fresh servo feedback or physical clearance.
"""
import hashlib
import math

from rocell.application.first_motion_contract import canonical

JOINTS = ('b', 's', 'e', 't', 'r', 'g')
MAX_SAMPLES = 256
MAX_CAPTURE_AGE_NS = 2_000_000_000
MAX_CAPTURE_SPAN_NS = 2_000_000_000
MIN_CAPTURE_SPAN_NS = 100_000_000
STABILITY_RAD = math.radians(.5)
# Deliberately narrow first-test software envelope, not a calibrated limit.
WRIST_ENVELOPE_RAD = math.radians(10)
ONE_DEGREE_POLICY = 'ONE_WRIST_DEGREE_FROM_OWNED_BASELINE_SPD20_ACC1_NO_RETURN'
FIVE_DEGREE_POLICY = 'FIVE_WRIST_DEGREES_FROM_OWNED_BASELINE_SPD20_ACC1_NO_RETURN'


def policy_degrees(policy):
    """Closed policy set: never accept arbitrary angles or reinterpret old approvals."""
    if policy == ONE_DEGREE_POLICY:
        return 1
    if policy == FIVE_DEGREE_POLICY:
        return 5
    raise ValueError('Unsupported observational wrist policy')


def _number(value):
    return type(value) in (int, float) and abs(value) <= 100 and math.isfinite(value)


def validated_wrist_baseline(*, samples, now_ns):
    """Return a checked copy of bounded six-joint reports; never motion authority.

    Shared by relative and absolute previews so neither skips freshness, gaps,
    conflicting batched records or all-joint stability checks.
    """
    if type(now_ns) is not int or not 0 < now_ns < 2**63:
        raise ValueError('Current host monotonic time required')
    if type(samples) is not list or not 2 <= len(samples) <= MAX_SAMPLES:
        raise ValueError('Bounded baseline capture required')
    previous = 0
    normalized = []
    for sample in samples:
        if type(sample) is not dict or set(sample) != {'host_received_ns', 'joints_rad'}:
            raise ValueError('Exact normalized baseline sample required')
        stamp, joints = sample['host_received_ns'], sample['joints_rad']
        # Multiple frames may arrive in one read. Preserve all of them without
        # inventing different receipt times or discarding a conflicting frame.
        if type(stamp) is not int or not 0 < stamp <= now_ns or stamp < previous:
            raise ValueError('Ordered, nonfuture host timestamps required')
        if (type(joints) is not dict or set(joints) != set(JOINTS)
                or not all(_number(joints[j]) for j in JOINTS)):
            raise ValueError('Six finite reported joint angles required')
        previous = stamp
        normalized.append({'host_received_ns': stamp, 'joints_rad': dict(joints)})
    span = normalized[-1]['host_received_ns'] - normalized[0]['host_received_ns']
    if not MIN_CAPTURE_SPAN_NS <= span <= MAX_CAPTURE_SPAN_NS:
        raise ValueError('Baseline capture duration outside preview bounds')
    if now_ns - previous > MAX_CAPTURE_AGE_NS:
        raise ValueError('Baseline host capture is stale')
    if any(b['host_received_ns'] - a['host_received_ns'] > 100_000_000
           for a, b in zip(normalized, normalized[1:])):
        raise ValueError('Baseline host capture has a gap')
    for joint in JOINTS:
        values = [sample['joints_rad'][joint] for sample in normalized]
        if max(values) - min(values) > STABILITY_RAD:
            raise ValueError('Reported baseline is unstable')
    if any(abs(sample['joints_rad']['t']) > WRIST_ENVELOPE_RAD for sample in normalized):
        raise ValueError('Reported wrist outside first-test software envelope')
    return normalized


def preview_observational_wrist(*, samples, now_ns, direction=-1, policy=ONE_DEGREE_POLICY):
    """Plan the exact approved relative increment from a checked capture."""
    if type(direction) is not int or direction not in (-1, 1):
        raise ValueError('Direction must be -1 or +1')
    normalized = validated_wrist_baseline(samples=samples, now_ns=now_ns)
    previous = normalized[-1]['host_received_ns']
    start = normalized[-1]['joints_rad']['t']
    delta = direction * math.radians(policy_degrees(policy))
    target = start + delta
    if any(abs(sample['joints_rad']['t']) > WRIST_ENVELOPE_RAD for sample in normalized) or abs(target) > WRIST_ENVELOPE_RAD:
        raise ValueError('Reported wrist outside first-test software envelope')
    return {
        'schema': 'rocell.observational_wrist_preview.v1',
        'baseline_sha256': hashlib.sha256(canonical(normalized)).hexdigest(),
        'baseline_last_host_received_ns': previous,
        'reported_start_rad': start,
        'requested_delta_rad': delta,
        'candidate_command': {'T': 101, 'joint': 4, 'rad': target, 'spd': 20, 'acc': 1},
        'speed_units': 'SERVO_STEPS_PER_SECOND',
        'sample_count': len(normalized),
        'basis': 'CONTROLLER_REPORTED_BASELINE',
        'precision_measurements_required': False,
        'device_sample_freshness_verified': False,
        'physical_clearance_verified': False,
        'motion_authorized': False,
        'limitations': [
            'Preview only; not accepted by the measured v1 executor.',
            'Live dispatch requires current unit binding, setup and visual pose sanity checks.',
            'Host recency and constant angles do not prove fresh servo samples.',
            'One-use admission must recompute against its own current baseline.',
        ],
    }
