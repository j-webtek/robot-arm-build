"""Single-trial lifecycle against incapable I/O and genuine replay permits."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import pytest

from rocell.arm.protocol import CartesianGoal
from rocell.motion.characterization_executor import IncapableTrialSession, execute_rehearsal_trial
from rocell.motion.characterization_plan import AXES, freeze_campaign
from rocell.rc03.build_snapshot import Capability
from rocell.safety.supervisor import SafetySupervisor
from test_characterization_plan import candidate
from test_safety_core import _valid_calibrations, _healthy_interlocks, _healthy_runtime, _advance_to_armed


def setup_trial(released_snapshot, fault='NONE', mismatch=False):
    data = candidate()
    data['frame'] = 'R_ctrl'
    data['evidence']['usb_identity'] = 'A'*32
    plan = freeze_campaign(data)
    trial = plan.to_dict()['trials'][0]
    goal = CartesianGoal(*(trial['target'][a] for a in AXES), trial['spd'])
    now = time.monotonic()
    supervisor = SafetySupervisor(released_snapshot)
    report = supervisor.evaluate(Capability.EMPTY_CELL_MOTION, plan_hash=plan.sha256,
        calibrations=_valid_calibrations(), interlocks=_healthy_interlocks(now),
        runtime=_healthy_runtime(), now_monotonic=now)
    _advance_to_armed(supervisor)
    permit = supervisor.authorize(report, goals=[goal], ttl_s=5, now_monotonic=now)
    baseline = [{'model_elapsed_s': i*.05, 'pose': dict(trial['start'], x_mm=3 if mismatch else 0)} for i in range(2)]
    post = [{'model_elapsed_s': i*.05, 'pose': dict(trial['start'], x_mm=min(i/10, 1))} for i in range(21)]
    session = IncapableTrialSession(baseline_samples=baseline, post_samples=post,
                                    context=plan.to_dict()['evidence'], fault=fault)
    kwargs = dict(permit=permit, expected_snapshot_hash=released_snapshot.snapshot_hash,
                  session=session, cancellation=Event())
    return plan, kwargs


def test_one_trial_does_not_automatically_execute_return(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert result['status'] == 'REHEARSAL_OBSERVED_ENDPOINT_DWELL'
    assert result['cleanup_confirmed']
    assert result['baseline_evidence'] and result['post_evidence']
    assert len(result['retained_replay_lines']) == 1
    assert kw['permit'].revoked
    assert result['physical_command_writes'] == result['device_opens'] == 0
    with pytest.raises(ValueError):
        execute_rehearsal_trial(plan, 'out', **kw)
    assert len(kw['session'].transport.sent_lines) == 1


@pytest.mark.parametrize('fault,expected,writes', [
    ('WRITE_UNCERTAIN', 'WRITE_COMPLETION_UNCERTAIN', 1),
    ('CONTEXT_CHANGED', 'IDENTITY_OR_SOURCE_CONTEXT_CHANGED', 0),
    ('CANCEL_BEFORE_WRITE', 'CANCELLED', 0),
    ('CLOSE_UNCERTAIN', 'CLEANUP_UNKNOWN', 1),
])
def test_failure_boundaries_never_retry_or_advance(released_snapshot, fault, expected, writes):
    plan, kw = setup_trial(released_snapshot, fault)
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert result['status'] == 'FAILED'
    assert expected in result['errors']
    assert len(result['retained_replay_lines']) == writes
    assert kw['permit'].remaining_uses == 0
    assert not result['physical_stop_verified']


def test_wrong_baseline_retained_without_movement(released_snapshot):
    plan, kw = setup_trial(released_snapshot, mismatch=True)
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert 'BASELINE_START_MISMATCH' in result['errors']
    assert result['baseline_evidence'] is not None
    assert not result['write_attempted']
    assert result['retained_replay_lines'] == []


def test_wrong_source_before_open_and_cancel_prevent_dispatch(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    kw['session'].context['source_sha256'] = 'f' * 64
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert 'REPLAY_OPENED' not in result['events']
    assert not result['write_attempted']
    plan, kw = setup_trial(released_snapshot)
    kw['cancellation'].set()
    assert execute_rehearsal_trial(plan, 'out', **kw)['errors'] == ['CANCELLED']


def test_concurrent_attempts_share_irreversible_claim(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    def attempt():
        try:
            return execute_rehearsal_trial(plan, 'out', **kw)['status']
        except ValueError:
            return 'REJECTED'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ['REHEARSAL_OBSERVED_ENDPOINT_DWELL', 'REJECTED']


def test_endpoint_first_execution_retains_initial_blind_interval(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    start = plan.to_dict()['trials'][0]['start']
    kw['session'].post_samples = [
        {'model_elapsed_s': .8+i*.05, 'pose': dict(start, x_mm=1)} for i in range(13)]
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert result['status'] == 'REHEARSAL_OBSERVED_ENDPOINT_DWELL'
    assert result['observation_contract'] == 'SUPERVISED_ENDPOINT_ONLY'
    analysis = result['post_evidence']['analysis']
    assert analysis['initial_unobserved_interval_ns'] is not None
    assert analysis['peak_observed_directional_overshoot_mm'] is None
    assert len(kw['session'].transport.sent_lines) == 1


def test_mutated_plan_and_wrong_snapshot_cannot_use_permit(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    data = plan.to_dict()
    data['trials'][0]['spd'] = .06
    with pytest.raises(ValueError, match='Permit context'):
        execute_rehearsal_trial(freeze_campaign(data), 'out', **kw)
    kw['expected_snapshot_hash'] = 'f'*64
    with pytest.raises(ValueError, match='Permit context'):
        execute_rehearsal_trial(plan, 'out', **kw)
    assert kw['session'].transport.sent_lines == ()


def test_baseline_gap_and_expired_permit_cannot_record_a_move(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    kw['session'].baseline_samples[1]['model_elapsed_s'] = .5
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert 'BASELINE_COVERAGE_GAP' in result['errors']
    assert not result['retained_replay_lines']
    plan, kw = setup_trial(released_snapshot)
    kw['permit'].expires_at_monotonic = time.monotonic() - 1
    result = execute_rehearsal_trial(plan, 'out', **kw)
    assert result['status'] == 'FAILED'
    assert not result['retained_replay_lines']
    assert kw['permit'].revoked


def test_native_transport_is_rejected_without_open(released_snapshot):
    from rocell.arm.serial_transport import SerialTransport
    plan, kw = setup_trial(released_snapshot)
    kw['session'].transport = SerialTransport('COM_NEVER_OPEN')
    with pytest.raises(ValueError, match='incapable'):
        execute_rehearsal_trial(plan, 'out', **kw)
    assert not kw['session'].transport.is_open


def test_request_binding_reaches_one_use_execution_boundary(released_snapshot):
    from rocell.application.endpoint_trial_contract import create_endpoint_request, REFERENCE_NAMES
    from rocell.motion.characterization_executor import execute_request_rehearsal
    plan, kw = setup_trial(released_snapshot)
    now = time.monotonic_ns()
    references = dict.fromkeys(REFERENCE_NAMES, 'a'*64)
    references['build_snapshot_sha256'] = released_snapshot.snapshot_hash
    request = create_endpoint_request(plan, 'out', attempt_id='operation-'+'b'*32,
        references=references, usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        issued_monotonic_ns=now, deadline_monotonic_ns=now+20_000_000_000)
    del kw['expected_snapshot_hash']
    report = execute_request_rehearsal(request, **kw)
    assert report['request_sha256'] == request.request_sha256
    assert report['status'] == 'REHEARSAL_OBSERVED_ENDPOINT_DWELL'
    assert len(report['retained_replay_lines']) == 1
    with pytest.raises(ValueError):
        execute_request_rehearsal(request, **kw)
    assert len(kw['session'].transport.sent_lines) == 1
