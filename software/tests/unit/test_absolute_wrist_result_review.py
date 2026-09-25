"""Exercise the real bounded collector using synthetic timed reads, no hardware."""
import base64
import copy
import json
import math
from threading import Event

import pytest

from rocell.application.absolute_wrist_capture import capture_absolute_wrist_window
from rocell.application.absolute_wrist_result_review import review_absolute_wrist_result
from rocell.application.first_motion_contract import canonical
from rocell.arm.protocol import encode_line
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from test_absolute_wrist_review_authority import intent


def fixture(direction=1, fault=None, load_values=None):
    body = intent()
    start = -direction * math.radians(4)
    body['draft']['direction'] = direction
    body['draft']['expected_start_joints_rad']['t'] = start
    request = AbsoluteWristIntent(canonical(body))
    tick = [2_000_000_000]
    joints = body['draft']['expected_start_joints_rad']
    def capture(phase, completed=None):
        count = [0]
        def read(n, timeout):
            count[0] += 1
            tick[0] += 20_000_000
            value = start if phase == 'baseline' else 0.
            if phase == 'post' and fault == 'miss': value = -direction * math.radians(.87)
            if phase == 'post' and fault == 'no_response': value = start
            if phase == 'post' and fault == 'departure' and count[0] > 50: value = start
            if phase == 'post' and fault == 'corrupt' and count[0] == 20: return b'broken\n'
            fields = dict(T=1051, x=1, y=2, z=3, tit=0, **dict(joints, t=value))
            if load_values is not None:
                fields['tT'] = load_values[(count[0]-1) % len(load_values)]
            if phase == 'post' and fault == 'other_joint': fields['b'] += .1
            raw = json.dumps(fields, separators=(',', ':')).encode() + b'\n'
            assert len(raw) <= n
            return raw
        return capture_absolute_wrist_window(request, phase, read_once=read, cancellation=Event(),
            clock_ns=lambda: tick[0], idle_wait=lambda seconds: tick.__setitem__(0, tick[0]+round(seconds*1e9)),
            command_completed_ns=completed)
    baseline = capture('baseline')
    begin = tick[0]
    tick[0] += 1_000_000
    payload = encode_line(dict(T=101, joint=4, rad=0., spd=20, acc=1))
    write = dict(payload_base64=base64.b64encode(payload).decode('ascii'),
        started_ns=begin, finished_ns=tick[0], attempted=True,
        confirmed_bytes=len(payload), completion_uncertain=False)
    post = capture('post', tick[0])
    cleanup = dict(started_ns=tick[0], finished_ns=tick[0]+1_000_000,
                   all_handles_closed=True, pending_io_count=0)
    trial = dict(schema='rocell.absolute_wrist_trial.v1', request_sha256=request.request_sha256,
        basis='SYNTHETIC_WIRE_REHEARSAL', baseline=baseline, post=post, write=write, cleanup=cleanup)
    return request, trial


def review(request, trial):
    return review_absolute_wrist_result(request, canonical(trial), expected_basis='SYNTHETIC_WIRE_REHEARSAL')


@pytest.mark.parametrize('fault', [None, 'miss', 'no_response', 'corrupt'])
def test_trace_summary_does_not_promote_miss_or_invalid_feedback(fault):
    from rocell.application.absolute_wrist_result_review import summarize_absolute_wrist_trace
    request, trial = fixture(fault=fault)
    report = summarize_absolute_wrist_trace(request, canonical(trial), expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert report['endpoint_status'] == review(request, trial)['endpoint']['status']
    assert not report['motion_authorized'] and not report['campaign_advance_allowed']
    assert not report['sample_freshness_verified']
    if fault == 'corrupt':
        assert report['status'] == 'UNAVAILABLE'
        assert report['final_constant_span_ns'] is None
    else:
        assert report['final_constant_report_count'] == report['sample_count']
        assert 4_000_000_000 < report['final_constant_span_ns'] < 5_000_000_000
        assert report['final_error_deg'] == pytest.approx(-.87 if fault == 'miss' else -4 if fault == 'no_response' else 0)


@pytest.mark.parametrize('direction', [-1, 1])
@pytest.mark.parametrize('fault,status', [(None, 'REPORTED_SETTLED'), ('miss', 'TARGET_MISSED'),
    ('no_response', 'NO_RESPONSE'), ('departure', 'TARGET_MISSED'),
    ('corrupt', 'FEEDBACK_INVALID'), ('other_joint', 'OTHER_JOINT_CHANGED')])
def test_rebuilds_endpoint_from_actual_collector(direction, fault, status):
    request, trial = fixture(direction, fault)
    original = copy.deepcopy(trial)
    result = review(request, trial)
    assert result['endpoint']['status'] == status
    assert result['preview']['candidate_command']['rad'] == 0.
    assert result['post_samples'] > 100
    assert not result['motion_authorized'] and not result['campaign_advance_allowed']
    assert not result['physical_movement_verified'] and not result['owned_process_verified']
    assert trial == original


@pytest.mark.parametrize('fault', ['short', 'uncertain', 'cleanup'])
def test_transport_fault_cannot_pass_even_at_exact_target(fault):
    request, trial = fixture()
    if fault == 'short': trial['write']['confirmed_bytes'] -= 1
    if fault == 'uncertain': trial['write']['completion_uncertain'] = True
    if fault == 'cleanup': trial['cleanup']['all_handles_closed'] = False
    result = review(request, trial)
    assert result['endpoint']['status'] == 'TRANSPORT_FAULT'
    assert not result['endpoint']['endpoint_verified']


@pytest.mark.parametrize('fault', ['request', 'basis', 'raw_hash', 'coverage', 'payload',
    'byte_count', 'bool_count', 'write_order', 'deadline', 'cleanup_time', 'extra', 'incomplete'])
def test_changed_originals_or_accounting_rejected(fault):
    request, trial = fixture()
    if fault == 'request': trial['request_sha256'] = 'a' * 64
    if fault == 'basis': trial['basis'] = 'RETAINED_PHYSICAL_CAPTURE'
    if fault == 'raw_hash': trial['post']['raw']['sha256'] = 'a' * 64
    if fault == 'coverage': trial['post']['coverage']['retained_bytes'] = 0
    if fault == 'payload': trial['write']['payload_base64'] = base64.b64encode(b'{"T":999}\n').decode()
    if fault == 'byte_count': trial['write']['confirmed_bytes'] = 999
    if fault == 'bool_count': trial['write']['confirmed_bytes'] = True
    if fault == 'write_order': trial['write']['started_ns'] = trial['baseline']['started_ns']
    if fault == 'deadline': trial['post']['window_deadline_ns'] += 1
    if fault == 'cleanup_time': trial['cleanup']['finished_ns'] += 3_000_000_000
    if fault == 'extra': trial['endpoint_pass'] = True
    if fault == 'incomplete': trial['post']['status'] = 'CANCELLED'
    with pytest.raises(ValueError): review(request, trial)
