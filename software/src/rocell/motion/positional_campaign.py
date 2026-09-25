"""Immutable finite wrist campaign specification. Data, never motion authority.

The first profile is deliberately simulation-only. Adding native execution
requires a separate authenticated campaign/leg permit; this cannot be passed to
the existing single-command executor or used as an unattended release record.
"""
from dataclasses import dataclass
import hashlib
import json
import math

from rocell.application.first_motion_contract import canonical

SCHEMA = 'rocell.positional_campaign.v1'
PROFILE = 'SIMULATED_WRIST_ABSOLUTE_V1'


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_campaign(body):
    fields = {'schema','mode','profile','start_rad','legs','limits','basis'}
    if type(body) is not dict or set(body) != fields or body['schema'] != SCHEMA:
        raise ValueError('Exact positional campaign schema required')
    if (body['mode'] != 'SIMULATION_ONLY' or body['profile'] != PROFILE
            or body['basis'] != 'SYNTHETIC_NOT_CONNECTED_HARDWARE'):
        raise ValueError('Native/unattended positional campaigns are not released')
    limits = dict(maximum_legs=8, maximum_duration_s=64, maximum_delta_deg=5,
        minimum_wrist_deg=-10, maximum_wrist_deg=10, spd=20, acc=1,
        baseline_s=1, observation_s=5, maximum_leg_s=8,
        arrival_tolerance_deg=.5, settling_span_deg=.1, dwell_ms=200,
        maximum_raw_bytes_per_leg=65536, maximum_total_raw_bytes=524288)
    if canonical(body['limits']) != canonical(limits):
        raise ValueError('Fixed positional profile limits required')
    previous = body['start_rad']
    if not _number(previous) or abs(previous) > math.radians(10):
        raise ValueError('Bounded initial wrist pose required')
    legs = body['legs']
    if type(legs) is not list or not 1 <= len(legs) <= 8:
        raise ValueError('One to eight explicitly enumerated legs required')
    ids = set()
    for index, leg in enumerate(legs):
        if type(leg) is not dict or set(leg) != {'leg_id','expected_start_rad','target_rad','command'}:
            raise ValueError('Exact leg fields required')
        if leg['leg_id'] != f'leg-{index+1:02d}' or leg['leg_id'] in ids:
            raise ValueError('Unique ordered leg IDs required')
        ids.add(leg['leg_id'])
        target = leg['target_rad']
        if (not _number(target) or abs(target) > math.radians(10)
                or not _number(leg['expected_start_rad']) or leg['expected_start_rad'] != previous
                or not math.radians(.5) < abs(target-previous) <= math.radians(5)):
            raise ValueError('Invalid absolute target, predecessor or bounded displacement')
        if canonical(leg['command']) != canonical(dict(T=101,joint=4,rad=target,spd=20,acc=1)):
            raise ValueError('Only the fixed wrist command is modeled')
        previous = target
    return body


@dataclass(frozen=True, slots=True)
class PositionalCampaign:
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    def to_dict(self):
        if type(self.canonical_bytes) is not bytes or len(self.canonical_bytes) > 16384:
            raise ValueError('Bounded immutable campaign bytes required')
        body = json.loads(self.canonical_bytes)
        if canonical(body) != self.canonical_bytes:
            raise ValueError('Canonical campaign bytes required')
        return validate_campaign(body)

    @property
    def sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def compile_wrist_campaign(pattern='OUT_AND_BACK', leg_count=2):
    """Synthetic absolute targets only; never infer a connected arm's pose.

    Opposite-approach includes every repositioning as an explicit leg: from
    zero to -4, back to zero, then +4 and back to the SAME zero target.
    """
    if pattern not in ('OUT_AND_BACK','OPPOSITE_APPROACH') or type(leg_count) is not int or leg_count not in (2,4,8):
        raise ValueError('Closed pattern and leg count required')
    if pattern == 'OPPOSITE_APPROACH' and leg_count < 4:
        raise ValueError('Opposite approaches require four or eight explicit legs')
    targets = (4,0) if pattern == 'OUT_AND_BACK' else (-4,0,4,0)
    legs, previous = [], 0.
    for index in range(leg_count):
        target = math.radians(targets[index % len(targets)])
        legs.append(dict(leg_id=f'leg-{index+1:02d}',expected_start_rad=previous,
            target_rad=target,command=dict(T=101,joint=4,rad=target,spd=20,acc=1)))
        previous = target
    body = dict(schema=SCHEMA, mode='SIMULATION_ONLY',profile=PROFILE,start_rad=0.,
        legs=legs,basis='SYNTHETIC_NOT_CONNECTED_HARDWARE',limits=dict(
            maximum_legs=8,maximum_duration_s=64,maximum_delta_deg=5,
            minimum_wrist_deg=-10,maximum_wrist_deg=10,spd=20,acc=1,
            baseline_s=1,observation_s=5,maximum_leg_s=8,
            arrival_tolerance_deg=.5,settling_span_deg=.1,dwell_ms=200,
            maximum_raw_bytes_per_leg=65536,maximum_total_raw_bytes=524288))
    return PositionalCampaign(canonical(body))
