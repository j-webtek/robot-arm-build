import math
import pytest

from test_observational_wrist_analysis import evaluate


def test_endpoint_check_does_not_depend_on_visual_approval():
    result = evaluate(operator_outcome='UNKNOWN', operator_covered_trial=False)
    endpoint = result['endpoint_verification']
    assert endpoint['status'] == 'REPORTED_SETTLED'
    assert endpoint['movement_detected'] and endpoint['endpoint_verified']
    assert result['status'] == 'HELD'  # Existing operator contract is preserved.
    assert endpoint['automatic_next_command_allowed'] is False


@pytest.mark.parametrize('fault,expected', [
    ('stationary', 'NO_RESPONSE'), ('miss', 'TARGET_MISSED'),
    ('oscillate', 'NOT_SETTLED'), ('leave', 'TARGET_MISSED'),
    ('other', 'OTHER_JOINT_CHANGED'), ('bad', 'FEEDBACK_INVALID'),
    ('transport', 'TRANSPORT_FAULT'), ('overshoot', 'WRIST_EXCURSION'),
])
def test_endpoint_faults_never_advance(fault, expected):
    target = .02-math.radians(1)
    kwargs = {}
    if fault == 'stationary': kwargs['values'] = [.02]*10
    if fault == 'miss': kwargs['values'] = [target]+[target+math.radians(.7)]*9
    if fault == 'oscillate': kwargs['values'] = [target+math.radians(.2)*(-1)**i for i in range(10)]
    if fault == 'leave': kwargs['values'] = [target]*9+[target+math.radians(.7)]
    if fault == 'other': kwargs['other_at'] = 3
    if fault == 'bad': kwargs['corrupt_at'] = 3
    if fault == 'transport': kwargs['transport_clean'] = False
    if fault == 'overshoot': kwargs['values'] = [target-math.radians(1)]+[target]*9
    result = evaluate(**kwargs)
    assert result['endpoint_verification']['status'] == expected
    assert not result['endpoint_verification']['endpoint_verified']
    assert not result['endpoint_verification']['automatic_next_command_allowed']
    assert result['status'] == 'HELD'


def test_target_band_dwell_is_not_enough_when_wrist_oscillates():
    target = .02-math.radians(1)
    result = evaluate(values=[target+math.radians(.2)*(-1)**i for i in range(10)])
    assert result['host_target_dwell_entry_bounds_ns'] is not None
    assert result['endpoint_verification']['quiet_dwell_entry_bounds_ns'] is None
    assert 'REPORTED_ENDPOINT_NOT_SETTLED_OR_INVALID' in result['issues']


@pytest.mark.parametrize('span_ns,expected', [(199_999_999, False), (200_000_000, True)])
def test_quiet_dwell_boundary_uses_host_interval_bounds(span_ns, expected):
    from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
    start = (0.,0.,0.,.02,0.,0.)
    target = .02-math.radians(1)
    pose = (0.,0.,0.,target,0.,0.)
    rows = [(1_000_000_000,1_000_000_010,pose),
            (1_000_000_010+span_ns,1_000_000_020+span_ns,pose)]
    result = verify_reported_wrist(rows, start=start, target=target,
        capture_issues=set(), transport_clean=True)
    assert result['endpoint_verified'] is expected


def test_a_batch_of_identical_samples_is_not_temporal_dwell():
    from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
    start = (0.,0.,0.,.02,0.,0.)
    target = .02-math.radians(1)
    rows = [(1_000_000_000,1_000_000_010,(0.,0.,0.,target,0.,0.))]*20
    result = verify_reported_wrist(rows, start=start, target=target,
        capture_issues=set(), transport_clean=True)
    assert result['status'] == 'NOT_SETTLED'


def test_repeated_cached_goal_can_only_establish_reported_settling():
    """Model T1051 re-publishing cached pose with new host arrival times.

    With no device status/sequence in these rows, fresh stationary and stale
    cached-at-goal readings are observationally identical. Never infer physical
    freshness or permission for another command from the reported endpoint.
    """
    from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
    start, target = (0., 0., 0., .02, 0., 0.), 0.
    cached_pose = (0., 0., 0., target, 0., 0.)
    rows = [(1_000_000_000+i*50_000_000, 1_000_000_001+i*50_000_000,
             cached_pose) for i in range(100)]
    result = verify_reported_wrist(rows, start=start, target=target,
                                   capture_issues=set(), transport_clean=True)
    assert result['status'] == 'REPORTED_SETTLED'
    assert result['endpoint_verified'] is True  # Reported endpoint only.
    assert result['device_sample_freshness_verified'] is False
    assert result['physical_accuracy_verified'] is False
    assert result['motion_authorized'] is False
    assert result['automatic_next_command_allowed'] is False


def test_incremental_settling_is_revoked_by_later_departure():
    from rocell.arm.wrist_endpoint_verification import ReportedWristMonitor, verify_reported_wrist
    start, target = (0.,0.,0.,.02,0.,0.), .02-math.radians(1)
    monitor = ReportedWristMonitor(start=start,target=target)
    rows = [(1_000_000_000+i*50_000_000,1_000_000_001+i*50_000_000,
             (0.,0.,0.,target,0.,0.)) for i in range(10)]
    for row in rows: monitor.push(row)
    assert monitor.snapshot()['endpoint_verified']
    rows.append((1_500_000_000,1_500_000_001,(0.,0.,0.,.02,0.,0.)))
    monitor.push(rows[-1])
    assert monitor.snapshot()['status'] == 'TARGET_MISSED'
    assert monitor.snapshot() == verify_reported_wrist(rows,start=start,target=target,
        capture_issues=set(),transport_clean=True)


@pytest.mark.parametrize('row',[(0,1,(0,)*6),(20,10,(0,)*6),(1,2,(True,)*6),
    (1,2,(float('nan'),)*6),(1,2,(0,)*5)])
def test_incremental_invalid_row_is_sticky(row):
    from rocell.arm.wrist_endpoint_verification import ReportedWristMonitor
    monitor = ReportedWristMonitor(start=(0,)*6,target=.02)
    with pytest.raises(ValueError): monitor.push(row)
    with pytest.raises(ValueError): monitor.push((10,11,(0,)*6))
    assert monitor.snapshot()['status'] == 'FEEDBACK_INVALID'


def test_incremental_work_budget_is_finite():
    from rocell.arm.wrist_endpoint_verification import ReportedWristMonitor
    monitor = ReportedWristMonitor(start=(0,)*6,target=.02)
    for i in range(4096): monitor.push((i+1,i+1,(0,)*6))
    with pytest.raises(ValueError): monitor.push((4097,4097,(0,)*6))
    assert monitor.snapshot()['status'] == 'FEEDBACK_INVALID'
