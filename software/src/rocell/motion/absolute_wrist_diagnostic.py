"""Immutable single absolute-target diagnostic draft; no native authority.

Unlike relative trials, fresh baseline variation never changes the target.
The native single-trial intent deliberately rejects this distinct schema until
review, admission, worker binding and reconstruction support it end to end.
"""
from dataclasses import dataclass
import hashlib
import math

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from .observational_wrist_plan import JOINTS, STABILITY_RAD, validated_wrist_baseline

SCHEMA = 'rocell.absolute_wrist_diagnostic_draft.v1'
TARGETS_DEG = (-4, 0, 4)


@dataclass(frozen=True, slots=True)
class AbsoluteWristDiagnosticDraft:
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    def to_dict(self):
        raw = self.canonical_bytes
        if type(raw) is not bytes:
            raise ValueError('Immutable diagnostic draft required')
        body = decode_diagnostic_json(raw, maximum=8192)
        fields = {'schema', 'target_deg', 'direction', 'expected_start_joints_rad',
                  'limits', 'motion_authorized'}
        if (type(body) is not dict or set(body) != fields or canonical(body) != raw
                or body['schema'] != SCHEMA or body['motion_authorized'] is not False
                or type(body['target_deg']) is not int or body['target_deg'] not in TARGETS_DEG
                or type(body['direction']) is not int or body['direction'] not in (-1, 1)
                or canonical(body['limits']) != canonical(_limits())):
            raise ValueError('Exact bounded absolute diagnostic draft required')
        start = body['expected_start_joints_rad']
        if (type(start) is not dict or set(start) != set(JOINTS)
                or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100
                       for v in start.values()) or abs(start['t']) > math.radians(10)):
            raise ValueError('Exact finite six-joint expected start required')
        _check_displacement(start['t'], math.radians(body['target_deg']), body['direction'])
        return body

    @property
    def sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def _limits():
    return dict(maximum_delta_deg=5, minimum_delta_deg=.5, maximum_start_drift_deg=.5,
                minimum_wrist_deg=-10, maximum_wrist_deg=10, spd=20, acc=1,
                maximum_commands=1, return_motion=False, retry=False)


def _check_displacement(start, target, direction):
    # The lower bound distinguishes an actual diagnostic approach from a no-op.
    # Check the whole baseline, not only its final value, before selecting bytes.
    if not math.radians(.5) < direction * (target - start) <= math.radians(5):
        raise ValueError('Wrong approach direction or displacement outside diagnostic bounds')


def draft_absolute_wrist(*, expected_start_joints_rad, target_deg, direction):
    return AbsoluteWristDiagnosticDraft(canonical(dict(schema=SCHEMA,
        expected_start_joints_rad=expected_start_joints_rad, target_deg=target_deg,
        direction=direction, limits=_limits(), motion_authorized=False)))


def preview_absolute_wrist(draft, *, samples, now_ns):
    """Validate current reports against a frozen start and target, without IO.

    Fresh raw-capture validation and native identity/source association remain
    the caller's responsibility. This normalized preview cannot authorize a write.
    """
    if type(draft) is not AbsoluteWristDiagnosticDraft:
        raise ValueError('Exact absolute diagnostic draft required')
    body = draft.to_dict()
    baseline = validated_wrist_baseline(samples=samples, now_ns=now_ns)
    target = math.radians(body['target_deg'])
    for row in baseline:
        joints = row['joints_rad']
        if any(abs(joints[j] - body['expected_start_joints_rad'][j]) > STABILITY_RAD for j in JOINTS):
            raise ValueError('Current baseline differs from the frozen expected start')
        _check_displacement(joints['t'], target, body['direction'])
    return dict(schema='rocell.absolute_wrist_diagnostic_preview.v1', draft_sha256=draft.sha256,
        baseline_sha256=hashlib.sha256(canonical(baseline)).hexdigest(),
        baseline_last_host_received_ns=baseline[-1]['host_received_ns'],
        reported_start_rad=baseline[-1]['joints_rad']['t'],
        candidate_command=dict(T=101, joint=4, rad=target, spd=20, acc=1),
        motion_authorized=False, physical_accuracy_verified=False,
        device_sample_freshness_verified=False, automatic_next_command_allowed=False)


def preview_absolute_wrist_from_capture(draft, raw, read_windows, *, started_ns,
                                       finished_ns, now_ns):
    """Check every complete original frame before computing an absolute preview.

    Stream-attachment fragments retain the existing documented framing policy.
    Interior errors cannot be filtered out; this still grants no native authority.
    """
    from rocell.arm.first_motion_analysis import _window
    if (any(type(t) is not int for t in (started_ns, finished_ns, now_ns))
            or not 0 < started_ns < finished_ns <= now_ns < 2**63):
        raise ValueError('Ordered original-capture timestamps required')
    rows, issues, framing = _window(raw, read_windows, started_ns, finished_ns)
    if issues or rows[-1][0] - rows[0][1] < 100_000_000:
        raise ValueError('Unsuitable complete-frame absolute diagnostic baseline')
    samples = [dict(host_received_ns=finish, joints_rad=dict(zip(JOINTS, joints)))
               for begin, finish, joints in rows]
    return dict(preview_absolute_wrist(draft, samples=samples, now_ns=now_ns),
                raw_capture_framing=framing, baseline_started_ns=started_ns,
                baseline_finished_ns=finished_ns)
