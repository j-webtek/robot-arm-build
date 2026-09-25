"""Descriptive comparisons rebuilt from bounded trial originals, never permits.

Repeatability means reported endpoint spread, not calibrated physical accuracy.
Timing comparisons use host-acquisition bounds only; unknown USB/device latency
prevents a hardware settings recommendation even if those bounds do not overlap.
"""

import base64
import hashlib
import json
import math
import statistics

from rocell.motion.characterization_plan import AXES, FrozenCampaign
from .movement_analysis import analyze_trial, analyze_endpoint_trial


def summarize_campaign(plan: FrozenCampaign, observations: list, *, minimum_repetitions=3) -> dict:
    """Summarize one frozen plan; missing/failed trials remain visible.

    Observation rows contain trial_id, outcome, and evidence (or None). Evidence
    supplies raw bytes/hash/base64, read windows and command/end timestamps.
    Stored analysis is not trusted: metrics are recomputed through the wire
    decoder. Evidence labels describe provenance, not authenticated live capture.
    """
    return _summarize(plan,observations,minimum_repetitions=minimum_repetitions,endpoint_only=False)


def summarize_endpoint_campaign(plan: FrozenCampaign, observations: list, *, minimum_repetitions=3) -> dict:
    """Compare endpoint captures without asserting continuous travel coverage.

    Uses the same bounded original validation and exact-route grouping as the
    continuous report. Every input must explicitly select the endpoint contract.
    Host dwell-entry comparisons are not measured travel time or speed ranking.
    """
    return _summarize(plan,observations,minimum_repetitions=minimum_repetitions,endpoint_only=True)


def _summarize(plan, observations, *, minimum_repetitions, endpoint_only):
    analyzer = analyze_endpoint_trial if endpoint_only else analyze_trial
    timing_field = 'host_endpoint_dwell_entry_bounds_ns' if endpoint_only else 'host_settling_entry_bounds_ns'
    median_field = 'median_'+timing_field
    if type(plan) is not FrozenCampaign or type(observations) is not list or len(observations) > 128:
        raise ValueError('Expected frozen plan and at most 128 observations')
    if type(minimum_repetitions) is not int or not 2 <= minimum_repetitions <= 128:
        raise ValueError('Repetition threshold must be an integer from 2 to 128')
    trials = plan.to_dict()['trials']
    ids = {trial['trial_id'] for trial in trials}
    by_id = {}
    for row in observations:
        if type(row) is not dict or set(row) != {'trial_id', 'outcome', 'evidence'}:
            raise ValueError('Invalid observation row')
        trial_id = row['trial_id']
        if type(trial_id) is not str or trial_id not in ids or trial_id in by_id:
            raise ValueError('Unknown or duplicate trial observation')
        if type(row['outcome']) is not str or not 0 < len(row['outcome']) <= 80:
            raise ValueError('Bounded outcome label required')
        by_id[trial_id] = row

    results, groups, seen_physical = [], {}, set()
    for trial in trials:
        row = by_id.get(trial['trial_id'])
        result = {'trial_id': trial['trial_id'], 'outcome': row['outcome'] if row else 'NOT_OBSERVED',
                  'basis': None, 'analysis': None, 'eligible_for_descriptive_comparison': False,
                  'exclusions': []}
        evidence = row['evidence'] if row else None
        if evidence is None:
            result['exclusions'].append('NO_RETAINED_EVIDENCE')
        else:
            if type(evidence) is not dict or evidence.get('physical_authority') is not False:
                raise ValueError('Evidence must not carry physical authority')
            if endpoint_only and evidence.get('observation_contract')!='SUPERVISED_ENDPOINT_ONLY':
                raise ValueError('Endpoint campaign requires explicit endpoint-only evidence')
            if not endpoint_only and evidence.get('observation_contract', 'CONTINUOUS') != 'CONTINUOUS':
                raise ValueError('Endpoint-only evidence cannot enter continuous campaign comparisons')
            basis = evidence.get('basis')
            if basis not in {'SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE'}:
                raise ValueError('Explicit supported evidence basis required')
            original = evidence.get('raw')
            if type(original) is not dict or type(original.get('base64')) is not str or len(original['base64']) > 87384:
                raise ValueError('Bounded original bytes required')
            raw = base64.b64decode(original['base64'], validate=True)
            digest = hashlib.sha256(raw).hexdigest()
            if (len(raw) > 65536 or type(original.get('bytes')) is not int or original['bytes'] != len(raw)
                    or original.get('sha256') != digest):
                raise ValueError('Original capture digest/length mismatch')
            analysis = analyzer(plan, trial['trial_id'], raw, evidence.get('read_windows'),
                                     command_completed_ns=evidence.get('command_completed_ns'),
                                     observation_end_ns=evidence.get('observation_end_ns'), basis=basis)
            result.update(basis=basis, analysis=analysis)
            if basis == 'RETAINED_PHYSICAL_CAPTURE':
                if digest in seen_physical:
                    result['exclusions'].append('REUSED_PHYSICAL_CAPTURE_NOT_INDEPENDENT')
                seen_physical.add(digest)
            expected = 'MODEL_COMPLETED' if basis == 'SYNTHETIC_WIRE_REHEARSAL' else 'OBSERVATION_COMPLETED'
            if result['outcome'] != expected:
                result['exclusions'].append('TRIAL_OUTCOME_NOT_COMPLETED')
            if analysis['status'] != ('OBSERVED_ENDPOINT_DWELL' if endpoint_only else 'OBSERVED_SETTLING'):
                result['exclusions'].append('INSUFFICIENT_ENDPOINT_DWELL' if endpoint_only
                                            else 'INSUFFICIENT_MOTION_COVERAGE_OR_SETTLING')
            result['eligible_for_descriptive_comparison'] = not result['exclusions']
        results.append(result)
        # Exact same route, orientation, dwell, timeout, policy and coefficient.
        # Different directions or tolerances must not become repeated trials.
        context = {key: value for key, value in trial.items() if key != 'trial_id'}
        key = json.dumps([context, result['basis']], sort_keys=True, separators=(',', ':'))
        group = groups.setdefault(key, {'context': context, 'basis': result['basis'], 'rows': []})
        group['rows'].append(result)

    summaries = []
    for group in groups.values():
        good = [row for row in group['rows'] if row['eligible_for_descriptive_comparison']]
        endpoints = [row['analysis']['latest_reported_endpoint']['pose'] for row in good]
        pairs = [(a, b) for index, a in enumerate(endpoints) for b in endpoints[index + 1:]]
        enough = len(good) >= minimum_repetitions
        bounds = [row['analysis'][timing_field] for row in good]
        summaries.append({
            'context': group['context'], 'basis': group['basis'],
            'trial_ids': [row['trial_id'] for row in group['rows']],
            'eligible_count': len(good), 'minimum_repetitions': minimum_repetitions,
            'status': 'DESCRIPTIVE_REPEATS_AVAILABLE' if enough else 'INSUFFICIENT_REPETITIONS',
            'reported_endpoint_spread_mm': max((math.dist([a[k] for k in AXES[:3]], [b[k] for k in AXES[:3]]) for a, b in pairs), default=None),
            'reported_unwrapped_angle_spread_rad': max((max(abs(a[k] - b[k]) for k in AXES[3:]) for a, b in pairs), default=None),
            median_field: [statistics.median([v[i] for v in bounds]) for i in (0, 1)] if enough else None,
        })

    comparisons = []
    for i, first in enumerate(summaries):
        for j, second in enumerate(summaries[i + 1:], i + 1):
            route_a = {k: v for k, v in first['context'].items() if k != 'spd'}
            route_b = {k: v for k, v in second['context'].items() if k != 'spd'}
            if route_a != route_b or first['basis'] != second['basis'] or first['context']['spd'] == second['context']['spd']:
                continue
            a, b = first[median_field], second[median_field]
            relation = 'INSUFFICIENT_REPETITIONS'
            if a is not None and b is not None:
                relation = 'HOST_BOUNDS_OVERLAP_OR_TOUCH'
                if a[1] < b[0]:
                    relation = 'FIRST_HAS_EARLIER_HOST_ENDPOINT_DWELL_BOUNDS' if endpoint_only else 'FIRST_HAS_EARLIER_HOST_SETTLING_BOUNDS'
                elif b[1] < a[0]:
                    relation = 'SECOND_HAS_EARLIER_HOST_ENDPOINT_DWELL_BOUNDS' if endpoint_only else 'SECOND_HAS_EARLIER_HOST_SETTLING_BOUNDS'
            comparisons.append({'group_indices': [i, j], 'relation': relation,
                                'physical_speed_ranking': None})
    report = {'schema': 'rocell.movement_campaign_analysis.v1', 'plan_sha256': plan.sha256,
            'trials': results, 'groups': summaries, 'host_timing_comparisons': comparisons,
            'recommended_settings': None, 'recommendation_status': 'NOT_QUALIFIED',
            'motion_authorized': False, 'physical_ready': False,
            'limitations': ['Synthetic repetition is deterministic rehearsal, not hardware repeatability.',
                            'Unknown buffering and device latency are not bounded by host acquisition intervals.',
                            'Reported endpoint spread is not independent physical accuracy or contact-force evidence.',
                            'Hashes verify supplied byte consistency, not provenance, freshness or physical approval.']}
    if endpoint_only:
        report.update(schema='rocell.endpoint_campaign_analysis.v1',
            observation_contract='SUPERVISED_ENDPOINT_ONLY',
            continuous_motion_observation=False,travel_time_s=None,
            physical_stop_verified=False)
        report['limitations'].append('Endpoint-only capture leaves initial travel unobserved; dwell-entry bounds cannot rank servo speed or establish path clearance.')
    return report
