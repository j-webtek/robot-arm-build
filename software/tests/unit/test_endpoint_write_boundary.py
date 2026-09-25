"""Final one-write gate using supervisor permits and an incapable byte sink."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import time

import pytest

from rocell.application.endpoint_trial_contract import create_endpoint_request, REFERENCE_NAMES
from rocell.application.endpoint_write_boundary import EndpointWriteBoundary, EndpointWriteContext
from test_characterization_executor import setup_trial


def boundary(released_snapshot):
    plan, kw = setup_trial(released_snapshot)
    now = time.monotonic_ns()
    references = dict.fromkeys(REFERENCE_NAMES, 'a'*64)
    references['build_snapshot_sha256'] = released_snapshot.snapshot_hash
    request = create_endpoint_request(plan, 'out', attempt_id='operation-'+'b'*32,
        references=references,usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        issued_monotonic_ns=now,deadline_monotonic_ns=now+20_000_000_000)
    gate = EndpointWriteBoundary(request,kw['permit'],connection_id='owned-test-session')
    def context():
        return EndpointWriteContext('owned-test-session','A'*32,tuple(sorted(references.items())),
            (0.,0.,0.,0.,0.,0.),time.monotonic_ns(),now+15_000_000_000)
    writes = []
    def write(payload):
        writes.append(payload)
        return len(payload)
    return gate,context,write,writes,kw['permit']


def test_one_owned_write_does_not_claim_physical_movement(released_snapshot):
    gate,ctx,write,writes,permit = boundary(released_snapshot)
    result = gate.attempt(context_reader=ctx,write_once=write,cancellation=Event())
    assert result['status'] == 'BYTES_WRITTEN_NOT_MOVEMENT_VERIFIED'
    assert len(writes) == 1 and result['confirmed_write_bytes'] == len(writes[0])
    assert permit.revoked and permit.remaining_uses == 0
    assert not result['physical_movement_verified'] and not result['physical_stop_verified']
    with pytest.raises(ValueError,match='no retry'):
        gate.attempt(context_reader=ctx,write_once=write,cancellation=Event())
    assert len(writes) == 1


@pytest.mark.parametrize('change', ['session','usb','references','baseline_time','presence','pose','nan'])
def test_changed_or_stale_context_prevents_write(released_snapshot,change):
    gate,ctx,write,writes,permit = boundary(released_snapshot)
    def bad_context():
        c = ctx()
        values = {'session':{'connection_id':'other'},'usb':{'usb_serial_number':'B'*32},
                  'references':{'references':()},'baseline_time':{'baseline_acquired_ns':1},
                  'presence':{'operator_presence_expires_ns':1},'pose':{'baseline_pose':(2,0,0,0,0,0)},
                  'nan':{'baseline_pose':(float('nan'),0,0,0,0,0)}}
        return replace(c,**values[change])
    result = gate.attempt(context_reader=bad_context,write_once=write,cancellation=Event())
    assert result['status'] == 'NOT_SENT'
    assert not result['write_attempted'] and writes == []
    assert permit.revoked


@pytest.mark.parametrize('kind',['partial','exception','bool'])
def test_uncertain_write_cannot_retry_and_preserves_known_byte_count(released_snapshot,kind):
    gate,ctx,_,writes,permit = boundary(released_snapshot)
    def uncertain(payload):
        writes.append(payload)
        if kind == 'exception':
            raise RuntimeError('sensitive external exception text')
        return 2 if kind == 'partial' else True
    result = gate.attempt(context_reader=ctx,write_once=uncertain,cancellation=Event())
    assert result['status'] == 'WRITE_UNCERTAIN_NO_RETRY'
    assert result['write_completion_uncertain']
    assert result['confirmed_write_bytes'] == (2 if kind == 'partial' else 0)
    assert 'sensitive' not in result['error']
    assert result['write_finished_ns'] >= result['write_started_ns']
    with pytest.raises(ValueError):
        gate.attempt(context_reader=ctx,write_once=uncertain,cancellation=Event())
    assert len(writes) == 1 and permit.revoked


def test_cancellation_during_context_collection_blocks_dispatch(released_snapshot):
    gate,ctx,write,writes,permit = boundary(released_snapshot)
    cancellation = Event()
    def cancelled_context():
        cancellation.set()
        return ctx()
    result = gate.attempt(context_reader=cancelled_context,write_once=write,cancellation=cancellation)
    assert not result['write_attempted'] and writes == []
    assert permit.revoked


def test_concurrent_boundary_attempts_issue_one_callback(released_snapshot):
    gate,ctx,write,writes,_ = boundary(released_snapshot)
    def attempt(_):
        try:
            return gate.attempt(context_reader=ctx,write_once=write,cancellation=Event())['status']
        except ValueError:
            return 'REJECTED'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt,range(2)))
    assert sorted(results) == ['BYTES_WRITTEN_NOT_MOVEMENT_VERIFIED','REJECTED']
    assert len(writes) == 1


def test_late_write_completion_preserves_count_without_claiming_success(released_snapshot,monkeypatch):
    import rocell.application.endpoint_write_boundary as module
    gate,ctx,_,writes,_ = boundary(released_snapshot)
    clock = [time.monotonic_ns()]
    monkeypatch.setattr(module.time,'monotonic_ns',lambda:clock[0])
    def late(payload):
        writes.append(payload)
        clock[0] += 1_100_000_000
        return len(payload)
    result = gate.attempt(context_reader=ctx,write_once=late,cancellation=Event())
    assert result['status'] == 'WRITE_UNCERTAIN_NO_RETRY'
    assert result['error'] == 'WRITE_TIME_BUDGET_EXCEEDED'
    assert result['confirmed_write_bytes'] == len(writes[0])


def test_context_expiring_during_consumption_prevents_writer_call(released_snapshot,monkeypatch):
    import rocell.application.endpoint_write_boundary as module
    gate,ctx,write,writes,permit = boundary(released_snapshot)
    clock = [time.monotonic_ns()]
    original_allows = permit.allows
    monkeypatch.setattr(module.time,'monotonic_ns',lambda:clock[0])
    def delayed_consume(goal):
        allowed = original_allows(goal)
        clock[0] += 150_000_000
        return allowed
    monkeypatch.setattr(permit,'allows',delayed_consume)
    result = gate.attempt(context_reader=ctx,write_once=write,cancellation=Event())
    assert result['status'] == 'NOT_SENT'
    assert result['error'] == 'CONTEXT_EXPIRED_AFTER_CONSUMPTION'
    assert writes == [] and permit.revoked
