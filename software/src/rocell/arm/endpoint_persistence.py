"""Bounded, read-only persistence analysis of one uninterrupted capture.

Rows use host read bounds, not device sample times. Callers must verify original
capture integrity and single-connection provenance separately. This module never
grants movement authority or replaces the historical five-second decision.
"""
import math

from .joint_endpoint_verification import JOINT_KEYS, verify_reported_joint

HORIZONS_S = (5, 10, 20, 35)
MAX_ROWS = 4096
MAX_GAP_NS = 250_000_000
PERSISTENCE_RAD = math.radians(.01)


def analyze_endpoint_persistence(rows, *, joint, start, target, write_finished_ns,
                                 capture_finished_ns, capture_issues=(),
                                 transport_clean=True, cancelled=False):
    """Keep early/final decisions and flag departures even when they return.

    Up to 4096 six-joint records are retained (35 seconds at typical arm rates).
    Horizon samples must have finished by their cutoff; a straddling read is not
    silently assigned to the earlier horizon. Gaps are reported conservatively.
    """
    if (joint not in JOINT_KEYS or type(start) not in (list, tuple) or len(start) != 6
            or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100 for v in start)
            or type(target) not in (int, float) or not math.isfinite(target) or abs(target) > 100
            or type(write_finished_ns) is not int or write_finished_ns <= 0
            or type(capture_finished_ns) is not int
            or not write_finished_ns <= capture_finished_ns <= write_finished_ns + 35_000_000_000
            or type(transport_clean) is not bool or type(cancelled) is not bool):
        raise ValueError('Finite joint configuration and explicit host capture bounds required')
    index = JOINT_KEYS.index(joint)
    records, problems = [], list(capture_issues)
    previous = (write_finished_ns, write_finished_ns)
    largest_gap = 0
    for row in rows:
        try:
            begin, end, pose = row
            if (len(records) >= MAX_ROWS or type(begin) is not int or type(end) is not int
                    or not write_finished_ns <= begin <= end <= capture_finished_ns
                    or begin < previous[0] or end < previous[1]
                    or type(pose) not in (list, tuple) or len(pose) != 6
                    or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100 for v in pose)):
                raise ValueError('Invalid row or row budget exhausted')
        except (ValueError, TypeError):
            problems.append('INVALID_OR_EXCESS_ROWS')
            break
        largest_gap = max(largest_gap, begin - previous[1], end - begin)
        records.append((begin, end, tuple(pose)))
        previous = (begin, end)
    largest_gap = max(largest_gap, capture_finished_ns - previous[1])
    horizons = []
    for seconds in HORIZONS_S:
        cutoff = write_finished_ns + seconds * 1_000_000_000
        prefix = [row for row in records if row[1] <= cutoff]
        covered = (capture_finished_ns >= cutoff - 25_000_000 and bool(prefix)
                   and cutoff - prefix[-1][1] <= MAX_GAP_NS)
        result = verify_reported_joint(prefix, joint=joint, start=start, target=target,
            capture_issues=problems, transport_clean=transport_clean)
        horizons.append(dict(seconds=seconds, covered=covered, sample_count=len(prefix),
            final_rad=prefix[-1][2][index] if prefix else None,
            endpoint=result))
    early = horizons[0]['final_rad']
    after_early = [r for r in records if r[0] >= write_finished_ns + 5_000_000_000]
    departure = (max((abs(r[2][index] - early) for r in after_early), default=0)
                 if early is not None else None)
    # Bound display detail independently of the full record budget. Keep counting
    # transitions after the display fills; never pretend a truncated list is all.
    transitions = []
    transition_count = 0
    prior_value = early
    for begin, end, pose in after_early:
        value = pose[index]
        if prior_value is not None and value != prior_value:
            transition_count += 1
            if len(transitions) < 16:
                transitions.append(dict(host_read_bounds_ns=[begin, end],
                    previous_rad=prior_value, reported_rad=value))
        prior_value = value
    final = records[-1][2][index] if records else None
    complete = all(h['covered'] for h in horizons) and largest_gap <= MAX_GAP_NS
    full = verify_reported_joint(records, joint=joint, start=start, target=target,
        capture_issues=problems, transport_clean=transport_clean)
    if cancelled:
        status = 'CANCELLED'
    elif not transport_clean:
        status = 'TRANSPORT_FAULT'
    elif problems:
        status = 'FEEDBACK_INVALID'
    elif not complete:
        status = 'OBSERVATION_INCOMPLETE'
    elif not full['endpoint_verified'] or not horizons[0]['endpoint']['endpoint_verified']:
        status = 'ENDPOINT_NOT_VERIFIED'
    elif departure > PERSISTENCE_RAD:
        status = 'REPORTED_ENDPOINT_CHANGED'
    else:
        status = 'REPORTED_ENDPOINT_PERSISTENT'
    values = [r[2][index] for r in records]
    return dict(schema='rocell.endpoint_persistence.v1', status=status, joint=joint,
        horizons=horizons, sample_count=len(records), issues=problems,
        capture_coverage_complete=complete, maximum_host_gap_ns=largest_gap,
        early_final_rad=early, final_rad=final,
        final_minus_early_rad=final-early if final is not None and early is not None else None,
        maximum_departure_after_5s_rad=departure, persistence_threshold_rad=PERSISTENCE_RAD,
        after_5s_transition_count=transition_count, first_transitions=transitions,
        transition_display_truncated=transition_count > len(transitions),
        observed_min_rad=min(values) if values else None,
        observed_max_rad=max(values) if values else None,
        full_window_endpoint=full,
        other_joint_maximum_drift_rad={key: max((abs(r[2][i]-start[i]) for r in records), default=0)
            for i, key in enumerate(JOINT_KEYS) if i != index},
        single_connection_provenance_verified=False, physical_accuracy_verified=False,
        device_sample_freshness_verified=False, motion_authorized=False,
        automatic_next_command_allowed=False)
