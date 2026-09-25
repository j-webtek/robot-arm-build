"""Original-byte observational wrist planning and functional assessment.

No device access. Operator observation can support a basic functional pass, not
precision calibration. Every complete frame is inspected, including conflicts.
"""
from rocell.application.first_motion_contract import canonical
from rocell.motion.observational_wrist_plan import preview_observational_wrist
from rocell.motion.observational_wrist_plan import ONE_DEGREE_POLICY
from .first_motion_analysis import _window, JOINTS, TOLERANCE_RAD, DWELL_NS
from .wrist_endpoint_verification import verify_reported_wrist


def _times(*values):
    if any(type(v) is not int or not 0 < v < 2**63 for v in values):
        raise ValueError('Positive host monotonic timestamps required')


def preview_from_capture(raw, read_windows, *, started_ns, finished_ns, now_ns,
                         direction=-1, policy=ONE_DEGREE_POLICY):
    """Recompute a preview from retained bytes, preserving acquisition bounds.

    Invalid interior frames are never filtered to make a stable baseline. Only
    documented stream-attachment fragments may be outside the framed interval.
    """
    _times(started_ns, finished_ns, now_ns)
    if not started_ns < finished_ns <= now_ns:
        raise ValueError('Ordered baseline capture window required')
    rows, issues, framing = _window(raw, read_windows, started_ns, finished_ns)
    if issues:
        raise ValueError('Unsuitable baseline capture: ' + ', '.join(sorted(issues)))
    if rows[-1][0] - rows[0][1] < 100_000_000:
        raise ValueError('Insufficient distinct baseline acquisition span')
    samples = [{'host_received_ns': finish, 'joints_rad': dict(zip(JOINTS, joints))}
               for begin, finish, joints in rows]
    preview = preview_observational_wrist(samples=samples, now_ns=now_ns,
                                         direction=direction, policy=policy)
    return dict(preview, raw_capture_framing=framing,
                baseline_started_ns=started_ns, baseline_finished_ns=finished_ns)


def assess_observational_response(baseline_raw, baseline_windows, post_raw, post_windows,
        *, baseline_started_ns, baseline_finished_ns, write_started_ns,
        write_finished_ns, observation_end_ns, direction, actual_command, operator_outcome,
        operator_covered_trial, transport_clean, basis, policy=ONE_DEGREE_POLICY):
    """Assess one exact candidate from original capture and a reported outcome.

    Callers must independently bind the actual dispatched command and owned
    transport result to these inputs before treating this as a retained trial.
    This pure calculation cannot grant another command or authenticate inputs.
    """
    times = (baseline_started_ns, baseline_finished_ns, write_started_ns,
             write_finished_ns, observation_end_ns)
    _times(*times)
    if not times[0] < times[1] <= times[2] <= times[3] < times[4]:
        raise ValueError('Ordered capture/write times required')
    if times[4] - times[3] > 5_000_000_000:
        raise ValueError('Post capture exceeds bounded trial duration')
    if operator_outcome not in ('EXPECTED_MOVEMENT', 'NO_MOVEMENT', 'WRONG_MOVEMENT', 'UNKNOWN'):
        raise ValueError('Explicit operator outcome required')
    if type(operator_covered_trial) is not bool or type(transport_clean) is not bool:
        raise ValueError('Explicit coverage and transport status required')
    if basis not in ('SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE'):
        raise ValueError('Explicit evidence basis required')
    preview = preview_from_capture(baseline_raw, baseline_windows,
        started_ns=times[0], finished_ns=times[1], now_ns=times[2], direction=direction, policy=policy)
    if type(actual_command) is not dict or canonical(actual_command) != canonical(preview['candidate_command']):
        raise ValueError('Dispatched command differs from the baseline-derived candidate')
    before, _, _ = _window(baseline_raw, baseline_windows, times[0], times[1])
    after, issues, framing = _window(post_raw, post_windows, times[3], times[4])
    issues = {'POST_' + issue for issue in issues}
    start = before[-1][2]
    target = preview['candidate_command']['rad']
    dwell_begin = None
    settled = False
    changed = False
    for begin, finish, joints in after:
        changed |= abs(joints[3] - start[3]) > TOLERANCE_RAD
        if any(abs(joints[i] - start[i]) > TOLERANCE_RAD for i in (0, 1, 2, 4, 5)):
            issues.add('OTHER_REPORTED_JOINT_CHANGED')
        if not min(start[3], target) - TOLERANCE_RAD <= joints[3] <= max(start[3], target) + TOLERANCE_RAD:
            issues.add('REPORTED_WRIST_EXCURSION')
        if abs(joints[3] - target) <= TOLERANCE_RAD:
            if dwell_begin is None:
                dwell_begin = (begin, finish)
            settled = begin - dwell_begin[1] >= DWELL_NS
        else:
            dwell_begin, settled = None, False
    endpoint = verify_reported_wrist(after, start=start, target=target,
        capture_issues={issue for issue in issues if issue.startswith('POST_')},
        transport_clean=transport_clean)
    if settled and not endpoint['endpoint_verified']:
        issues.add('REPORTED_ENDPOINT_NOT_SETTLED_OR_INVALID')
    if not changed: issues.add('NO_RESOLVABLE_REPORTED_WRIST_CHANGE')
    if not settled: issues.add('NO_FINAL_REPORTED_TARGET_DWELL')
    if not transport_clean: issues.add('TRANSPORT_OR_CLEANUP_FAULT')
    if operator_outcome != 'EXPECTED_MOVEMENT': issues.add('OPERATOR_RESPONSE_NOT_EXPECTED')
    if not operator_covered_trial: issues.add('OPERATOR_COVERAGE_INCOMPLETE')
    return dict(schema='rocell.observational_wrist_assessment.v1', basis=basis,
        status=('HELD' if issues else 'SYNTHETIC_FUNCTIONAL_PASS'
                if basis == 'SYNTHETIC_WIRE_REHEARSAL' else 'OBSERVED_FUNCTIONAL_PASS'),
        issues=sorted(issues), preview=preview, post_capture_framing=framing,
        operator_outcome=operator_outcome, operator_covered_trial=operator_covered_trial,
        post_sample_count=len(after), endpoint_verification=endpoint,
        reported_final_error_rad=after[-1][2][3] - target if after else None,
        host_target_dwell_entry_bounds_ns=list(dwell_begin) if settled else None,
        physical_accuracy_verified=False, device_sample_freshness_verified=False,
        motion_authorized=False, campaign_advance_allowed=False,
        limitations=['Functional evidence only; no calibrated accuracy claim.',
                     'Caller must bind actual command, unit, raw capture and operator report.',
                     'A subsequent movement requires its own current admission.'])
