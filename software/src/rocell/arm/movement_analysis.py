"""Host-observed Cartesian trial metrics from retained wire evidence.

This is not a command-response authenticator or servo-internal timing model.
Acquisition bounds cannot remove USB buffering uncertainty. Even an observed
settling interval grants no motion permission or claim of physical accuracy.
"""

import math

from rocell.motion.characterization_plan import AXES, FrozenCampaign
from .telemetry_coverage import analyze_window_coverage, iter_window_records, complete_frame_interval

WIRE_AXES = ("x", "y", "z", "tit", "r", "g")


def analyze_trial(plan: FrozenCampaign, trial_id: str, raw: bytes, read_windows: list,
                  *, command_completed_ns: int, observation_end_ns: int,
                  basis: str) -> dict:
    """Continuous-coverage contract; initial and later feedback gaps fail closed."""
    return _analyze_trial(plan, trial_id, raw, read_windows,
                          command_completed_ns=command_completed_ns,
                          observation_end_ns=observation_end_ns, basis=basis,
                          endpoint_only=False)


def analyze_endpoint_trial(plan: FrozenCampaign, trial_id: str, raw: bytes, read_windows: list,
                           *, command_completed_ns: int, observation_end_ns: int,
                           basis: str) -> dict:
    """Endpoint-only contract selected for initial supervised trials.

    The initial interval without pose feedback is recorded, not treated as
    observed motion. Subsequent gaps, invalid frames, missing dwell and unchanged
    poses still prevent endpoint qualification. No travel time, complete-path
    overshoot or physical stopping metric can be inferred from this contract.
    """
    return _analyze_trial(plan, trial_id, raw, read_windows,
                          command_completed_ns=command_completed_ns,
                          observation_end_ns=observation_end_ns, basis=basis,
                          endpoint_only=True)


def _analyze_trial(plan: FrozenCampaign, trial_id: str, raw: bytes, read_windows: list,
                   *, command_completed_ns: int, observation_end_ns: int,
                   basis: str, endpoint_only: bool) -> dict:
    """Analyze one explicit target using conservative host read bounds.

    Angles are compared as unwrapped values, matching the candidate planner; no
    shortest-rotation assumption is made for bounded joints. Out-of-window frames
    do not contribute. Gaps, bad lines, missing suffix bytes, and unchanged pose
    make settling unavailable even when the final reported endpoint is on target.
    """
    if type(plan) is not FrozenCampaign:
        raise ValueError("Expected a frozen campaign")
    trials = [t for t in plan.to_dict()['trials'] if t['trial_id'] == trial_id]
    if len(trials) != 1:
        raise ValueError("Unknown trial")
    if basis not in {'SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE'}:
        raise ValueError("Explicit evidence basis required")
    if type(read_windows) is not list:
        raise ValueError("Timed analysis requires explicit read windows")
    if (type(command_completed_ns) is not int or type(observation_end_ns) is not int
            or not 0 < command_completed_ns < observation_end_ns < 2**63):
        raise ValueError("Invalid command/observation interval")
    trial = trials[0]
    if read_windows and read_windows[-1][3] > observation_end_ns:
        raise ValueError("Read window extends beyond observation end")
    framing = None
    if endpoint_only:
        raw, read_windows, framing = complete_frame_interval(raw,read_windows)
    coverage = analyze_window_coverage(raw, read_windows, display_limit=0)
    if read_windows and read_windows[-1][3] > observation_end_ns:
        raise ValueError("Read window extends beyond observation end")
    start, target = ([trial[key][a] for a in AXES] for key in ('start', 'target'))
    policy = trial['stop']
    interval_end = min(observation_end_ns, command_completed_ns + round(trial['timeout_s']*1e9))
    max_gap_ns = round(policy['max_read_gap_s']*1e9)
    dwell_ns = max(1, math.ceil(trial['dwell_s']*1e9))
    direction = [target[i]-start[i] for i in range(3)]
    travel = math.hypot(*direction)
    unit = [d/travel for d in direction] if travel else None
    issues, count, changed, latest = set(), 0, False, None
    previous_finish = command_completed_ns
    initial_unobserved_interval = None
    longest_gap, overshoot, run_first, settled_bounds = 0, 0.0 if unit else None, None, None
    for record in iter_window_records(raw, read_windows):
        begin, finish = record['host_acquisition_bounds_ns']
        if finish <= command_completed_ns or begin > interval_end:
            continue
        if begin <= command_completed_ns or finish > interval_end:
            issues.add('FRAME_STRADDLES_TRIAL_BOUNDARY')
            continue
        if record['kind'] != 'POSE_TELEMETRY':
            issues.add('INVALID_OR_INCOMPLETE_POSE')
            run_first = settled_bounds = None
            continue
        pose = [float(record['fields'][a]) for a in WIRE_AXES]
        # Avoid overflow in derived metrics and flag implausibly large reports;
        # the ceiling is a numeric-analysis bound, not a calibrated robot limit.
        if any(not math.isfinite(v) or abs(v) > 1e6 for v in pose):
            issues.add('NUMERIC_ANALYSIS_RANGE')
            run_first = settled_bounds = None
            continue
        if count == 0:
            initial_unobserved_interval = [command_completed_ns, begin]
        # Only the endpoint contract tolerates the *initial* unobserved interval.
        # Coverage after first observation must still meet the same gap limits.
        gap = finish - begin if endpoint_only and count == 0 else finish - previous_finish
        longest_gap = max(longest_gap, gap)
        if gap > max_gap_ns or finish-begin > max_gap_ns:
            issues.add('READ_COVERAGE_GAP')
        previous_finish = finish
        count += 1
        error = math.dist(pose[:3], target[:3])
        angle_error = max(abs(pose[i]-target[i]) for i in range(3,6))
        changed |= (math.dist(pose[:3], start[:3]) > policy['position_tolerance_mm']
                    or max(abs(pose[i]-start[i]) for i in range(3,6)) > policy['angle_tolerance_rad'])
        if unit is not None:
            overshoot = max(overshoot, sum((pose[i]-target[i])*unit[i] for i in range(3)))
        latest = {'position_error_mm':error, 'max_unwrapped_angle_error_rad':angle_error,
                  'pose':dict(zip(AXES,pose)), 'host_acquisition_bounds_ns':[begin,finish]}
        inside = error <= policy['position_tolerance_mm'] and angle_error <= policy['angle_tolerance_rad']
        if not inside:
            run_first = settled_bounds = None
        else:
            if run_first is None:
                run_first = [begin,finish]
            # Guaranteed host-acquisition separation, not interpolated sample
            # cadence: shared reads alone can never establish a positive dwell.
            if begin-run_first[1] >= dwell_ns:
                settled_bounds = [run_first[0]-command_completed_ns,
                                  run_first[1]-command_completed_ns]
    trailing_gap = interval_end-previous_finish
    longest_gap = max(longest_gap, trailing_gap)
    if trailing_gap > max_gap_ns:
        issues.add('READ_COVERAGE_GAP')
    if coverage['unprocessed_range'] is not None:
        issues.add('UNTERMINATED_CAPTURE_SUFFIX')
    if not count:
        issues.add('NO_POST_COMMAND_POSES')
    if not changed:
        issues.add('NO_OBSERVED_CHANGE')
    if latest and latest['position_error_mm'] > policy['max_endpoint_error_mm']:
        issues.add('ENDPOINT_ERROR_LIMIT')
    if issues:
        settled_bounds = None
    if settled_bounds is None:
        issues.add('SETTLING_NOT_ESTABLISHED')
    report = {
        'schema':'rocell.movement_analysis.v1', 'basis':basis,
        'plan_sha256':plan.sha256, 'trial_id':trial_id, 'raw_sha256':coverage['raw_sha256'],
        'post_command_pose_count':count, 'latest_reported_endpoint':latest,
        'peak_observed_directional_overshoot_mm':overshoot if count else None,
        'longest_host_coverage_gap_ns':longest_gap,
        'observed_change':changed, 'host_settling_entry_bounds_ns':settled_bounds,
        'issues':sorted(issues), 'status':'OBSERVED_SETTLING' if settled_bounds else 'INSUFFICIENT_EVIDENCE',
        'sample_freshness_verified':False, 'physical_accuracy_verified':False,
        'motion_authorized':False, 'physical_ready':False,
        'limitations':['Host read timing is not device timing; buffering remains unknown.',
                      'Angles are unwrapped; joint winding/limits need separate qualification.',
                      'Peak observed overshoot excludes unobserved motion between samples.'],
    }
    if endpoint_only:
        report.update(
            schema='rocell.endpoint_movement_analysis.v1',
            observation_contract='SUPERVISED_ENDPOINT_ONLY',
            status='OBSERVED_ENDPOINT_DWELL' if settled_bounds else 'INSUFFICIENT_ENDPOINT_EVIDENCE',
            host_endpoint_dwell_entry_bounds_ns=settled_bounds,
            initial_unobserved_interval_ns=initial_unobserved_interval,
            host_settling_entry_bounds_ns=None,
            peak_observed_directional_overshoot_mm=None,
            travel_time_s=None, continuous_motion_observation=False,
            physical_stop_verified=False)
        report['limitations'].append(
            'Initial motion is unobserved. Endpoint dwell does not establish path clearance, peak overshoot, travel duration or physical rest.')
        if framing['analysis_range'] != [0,framing['original_bytes']]:
            report['raw_sha256'] = framing['original_sha256']
            report['frame_interval'] = framing
            report['limitations'].append('Boundary fragments are retained but unobserved; all complete interior lines and original host timing bounds remain in analysis.')
    return report
