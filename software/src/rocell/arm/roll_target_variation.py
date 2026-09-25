"""Finite offline experiment definitions; deliberately not native motion intents.

Synthetic traces use the production endpoint/persistence evaluator. They test
analysis and case boundaries, not the mechanical response of the real arm.
"""
import hashlib
import math

from rocell.application.first_motion_contract import canonical
from .endpoint_persistence import analyze_endpoint_persistence
from .endpoint_quality import assess_endpoint_quality

SCHEMA = 'rocell.roll_target_variation_simulation.v1'
ANCHOR = (.007669904, 0., 1.593806039, .047553404, .007669904, 3.149262558)
OFFSETS = {'low': .9, 'nominal': 1., 'high': 1.1}
MODELS = ('ideal', 'bias', 'deadband', 'quantized', 'delayed', 'late_departure',
          'stale', 'partial_write', 'timeout', 'other_joint_drift')
WRITE_NS = 1_000_000_000


def experiment_case(case_id):
    """Return a fresh, enumerated six-joint case, including separate return cases.

    A return assumes an exact nominal outward endpoint. It is not automatically
    usable after an outward trial: its full starting pose must match separately.
    """
    if type(case_id) is not str:
        raise ValueError('Enumerated case required')
    returning = case_id.startswith('return-')
    label = case_id[7:] if returning else case_id
    if label not in OFFSETS:
        raise ValueError('Enumerated case required')
    start = list(ANCHOR)
    target = ANCHOR[4] + math.radians(OFFSETS[label])
    if returning:
        start[4], target = target, ANCHOR[4]
    body = dict(schema=SCHEMA, case_id=case_id, selected_joint='r', command_joint=5,
        direction='DECREASING' if returning else 'INCREASING',
        start_joints_rad=start, target_rad=target, spd=20, acc=1,
        observation_s=35, maximum_writes=1, start_tolerance_deg=.01,
        maximum_delta_deg=1.5, maximum_absolute_target_deg=3.,
        origin='SYNTHETIC_EXPERIMENT_DESIGN', motion_authorized=False,
        automatic_next_command_allowed=False, compensation_applied=False)
    return dict(body, configuration_sha256=hashlib.sha256(canonical(body)).hexdigest())


def validate_case(case):
    """Reject edited parameters even if a caller recomputes their hash."""
    if type(case) is not dict or canonical(case) != canonical(experiment_case(case.get('case_id'))):
        raise ValueError('Case must exactly match an enumerated offline definition')
    start, target = case['start_joints_rad'][4], case['target_rad']
    if not (.5 < abs(math.degrees(target-start)) <= 1.5 and abs(math.degrees(target)) <= 3):
        raise ValueError('Case exceeds local experiment envelope')


def starting_pose_matches(case, pose):
    """Pose agreement alone is not proof of freshness or permission to move."""
    validate_case(case)
    if (type(pose) not in (list, tuple) or len(pose) != 6 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in pose)):
        raise ValueError('Finite six-joint pose required')
    return all(abs(a-b) <= math.radians(.01) for a, b in zip(pose, case['start_joints_rad']))


def simulate_case(case, model='ideal', *, observed_start=None):
    """Evaluate one virtual write and stop; never execute or queue a return.

    Time is deterministic virtual time. Known-stale traces are rejected through
    capture issues: repeated values alone cannot prove device freshness.
    """
    validate_case(case)
    if model not in MODELS:
        raise ValueError('Unknown synthetic response model')
    start = list(case['start_joints_rad'] if observed_start is None else observed_start)
    common = dict(schema='rocell.roll_target_variation_result.v1', case=case,
        model=model, origin='SYNTHETIC_NOT_HARDWARE', physical_writes=0,
        motion_authorized=False, physical_accuracy_verified=False,
        compensation_applied=False, automatic_next_command_allowed=False)
    if not starting_pose_matches(case, start):
        return dict(common, status='START_MISMATCH', simulated_write_attempts=0,
            simulated_complete_writes=0, endpoint=None, quality=None, rows=[])
    target = case['target_rad']
    direction = 1 if target > start[4] else -1
    settled = target
    if model == 'bias':
        settled += math.radians(-.03 if direction > 0 else .4)
    if model == 'deadband':
        settled -= direction * math.radians(.2)
    if model == 'quantized':
        # Illustrative quantization, not a measured encoder resolution.
        quantum = math.radians(.087890625)
        settled = round(settled / quantum) * quantum
    rows = []
    duration_ms = 2000 if model == 'timeout' else 35000
    for ms in range(20, duration_ms + 1, 20):
        pose = start.copy()
        settling_ms = 7000 if model == 'delayed' else 400
        pose[4] += (settled-start[4]) * min(ms / settling_ms, 1.)
        if model == 'late_departure' and ms >= 18000:
            pose[4] += math.radians(.15)
        if model in ('stale', 'partial_write'):
            pose[4] = start[4]
        if model == 'other_joint_drift' and ms >= 10000:
            pose[1] += math.radians(1)
        rows.append((WRITE_NS + ms*1_000_000 - 1_000_000,
                     WRITE_NS + ms*1_000_000, pose))
    persistence = analyze_endpoint_persistence(rows, joint='r', start=start, target=target,
        write_finished_ns=WRITE_NS, capture_finished_ns=WRITE_NS + duration_ms*1_000_000,
        capture_issues=['KNOWN_SYNTHETIC_STALE_FEEDBACK'] if model == 'stale' else (),
        transport_clean=model != 'partial_write')
    endpoint = dict(persistence['full_window_endpoint'], persistence=persistence,
        endpoint_verified=persistence['status'] == 'REPORTED_ENDPOINT_PERSISTENT')
    next_id = 'nominal' if case['case_id'].startswith('return-') else 'return-' + case['case_id']
    next_start = experiment_case(next_id)['start_joints_rad']
    quality = assess_endpoint_quality(endpoint, final_joints=rows[-1][2], next_start_joints=next_start)
    return dict(common, status=persistence['status'], simulated_write_attempts=1,
        simulated_complete_writes=0 if model == 'partial_write' else 1,
        endpoint=endpoint, quality=quality, rows=rows,
        final_joints_rad=rows[-1][2], synthetic_trace_sha256=hashlib.sha256(canonical(rows)).hexdigest())


def simulation_matrix():
    """Independent cases; no implied chain of physical starting positions."""
    results = []
    for label in OFFSETS:
        for case_id in (label, 'return-' + label):
            for model in MODELS:
                result = simulate_case(experiment_case(case_id), model)
                # Keep compact report; full traces are deterministically reproducible.
                result['sample_count'] = len(result.pop('rows'))
                results.append(result)
    return dict(schema='rocell.roll_target_variation_matrix.v1',
        independent_synthetic_cases=True, native_profile_implemented=False,
        physical_writes=0, motion_authorized=False, results=results)
