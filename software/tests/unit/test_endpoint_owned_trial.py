"""Integrated bench trial sequencing with incapable byte callbacks only."""

import json
from threading import Event
import time

import pytest

from rocell.application.endpoint_owned_trial import run_owned_endpoint_trial, EndpointCleanupResult
from rocell.safety.bench_endpoint import authorize_bench_endpoint
from test_bench_endpoint import setup


def run(tmp_path, monkeypatch, *, fault=None):
    tick = [1_000_000_000]
    phase = ['baseline']
    command_finish = [None]
    after_write_clocks = [0]
    def clock():
        if phase[0] == 'post':
            after_write_clocks[0] += 1
            if after_write_clocks[0] == 2:
                tick[0] += 1  # Post capture is after the write completion bound.
        return tick[0]
    monkeypatch.setattr(time, 'monotonic_ns', clock)
    req, evidence = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=evidence,
                                     attempt_root=tmp_path, clock=clock)
    events = []
    cancellation = Event()
    if fault == 'cancel_before':
        cancellation.set()
    def read(n, timeout):
        events.append('read_'+phase[0])
        if fault == 'read_error':
            raise OSError('private device details')
        if fault == 'post_read_error' and phase[0] == 'post':
            raise OSError('private device details')
        step = min(50_000_000, timeout*1_000_000)
        if phase[0] == 'post':
            step = min(step, command_finish[0]+2_000_000_000-tick[0])
        tick[0] += step
        x = 0 if phase[0] == 'baseline' else 1
        if fault == 'wrong_baseline':
            x = 4
        if fault == 'unchanged':
            x = 0
        if fault == 'invalid_baseline' and phase[0] == 'baseline':
            return b'broken\n'
        line = json.dumps(dict(T=1051,x=x,y=0,z=0,tit=0,r=0,g=0,b=0,s=0,e=0,t=0),
                          separators=(',',':')).encode()+b'\n'
        if fault == 'boundary_fragments' and phase[0]=='baseline':
            prefix=b'"tR":24}\n' if events.count('read_baseline')==1 else b''
            suffix=b'{"T":1051,"x":' if tick[0]==2_000_000_000 else b''
            return prefix+line+suffix
        if fault == 'buffered_pair' and phase[0] == 'baseline':
            return line*2 if events.count('read_baseline') == 1 else b''
        if fault == 'suffix' and phase[0] == 'baseline' and tick[0] == 2_000_000_000:
            return line+b'partial'
        return line
    def write(payload):
        events.append('write')
        assert json.loads(payload)['T'] == 104
        tick[0] += 1
        command_finish[0] = tick[0]
        phase[0] = 'post'
        if fault == 'cancel_after_write':
            cancellation.set()
        if fault == 'write_error':
            raise OSError('private write details')
        return len(payload)-1 if fault == 'short_write' else len(payload)
    def close(timeout):
        events.append('close')
        assert timeout == 2000
        if fault == 'close_error':
            raise OSError('private close details')
        if fault == 'close_slow':
            tick[0] += 2_000_000_001
        return EndpointCleanupResult(True, 1 if fault == 'pending_io' else 0)
    result = run_owned_endpoint_trial(req, permit, connection_id='owned-test', read_once=read,
        write_once=write, close_once=close, presence_expiry_reader=lambda:req.to_dict()['deadline_monotonic_ns'],
        cancellation=cancellation, basis='SYNTHETIC_WIRE_REHEARSAL')
    assert events[-1] == 'close' and events.count('close') == 1
    assert events.count('write') <= 1
    assert not permit.consume(req, 'owned-test')
    assert not result['physical_stop_verified'] and not result['physical_movement_verified']
    assert 'private' not in json.dumps(result)
    return result, events


def test_integrated_baseline_write_endpoint_cleanup(tmp_path, monkeypatch):
    result, events = run(tmp_path, monkeypatch)
    assert result['status'] == 'OBSERVED_ENDPOINT_DWELL'
    assert result['baseline']['raw']['bytes'] > 0 and result['post']['raw']['bytes'] > 0
    assert result['analysis']['host_endpoint_dwell_entry_bounds_ns'] is not None
    assert result['cleanup']['status'] == 'HANDLES_CLOSED'
    assert events.index('write') > events.index('read_baseline')
    assert events.index('read_post') > events.index('write')


def test_stream_boundary_fragments_keep_originals_and_allow_valid_baseline(tmp_path,monkeypatch):
    result,events=run(tmp_path,monkeypatch,fault='boundary_fragments')
    assert result['status']=='OBSERVED_ENDPOINT_DWELL'
    assert events.count('write')==1
    assert result['baseline']['coverage']['unprocessed_range'] is not None
    assert result['baseline']['baseline_frame_interval']['unobserved_prefix_range'] is not None
    assert result['baseline']['baseline_frame_interval']['unobserved_suffix_range'] is not None


@pytest.mark.parametrize('fault', ['wrong_baseline','invalid_baseline','read_error','cancel_before',
                                  'buffered_pair','suffix'])
def test_prewrite_faults_always_close_without_writing(tmp_path, monkeypatch, fault):
    result, events = run(tmp_path, monkeypatch, fault=fault)
    assert 'write' not in events and 'read_post' not in events
    assert result['status'] in {'HELD_BEFORE_WRITE','CANCELLED_BEFORE_WRITE'}


@pytest.mark.parametrize('fault', ['short_write','write_error'])
def test_uncertain_write_retains_post_capture_but_never_qualifies(tmp_path, monkeypatch, fault):
    result, events = run(tmp_path, monkeypatch, fault=fault)
    assert result['status'] == 'WRITE_UNCERTAIN_NO_RETRY'
    assert result['post']['raw']['bytes'] > 0 and events.count('write') == 1


@pytest.mark.parametrize('fault', ['unchanged','post_read_error','cancel_after_write'])
def test_post_faults_do_not_qualify(tmp_path, monkeypatch, fault):
    result, events = run(tmp_path, monkeypatch, fault=fault)
    assert result['status'] != 'OBSERVED_ENDPOINT_DWELL'
    assert events.count('write') == 1


@pytest.mark.parametrize('fault', ['close_error','close_slow','pending_io'])
def test_cleanup_fault_overrides_success_without_erasing_evidence(tmp_path, monkeypatch, fault):
    result, events = run(tmp_path, monkeypatch, fault=fault)
    assert result['status'] == 'CLEANUP_UNCERTAIN'
    assert result['analysis']['status'] == 'OBSERVED_ENDPOINT_DWELL'
    assert result['baseline'] and result['write'] and result['post']


def test_clock_failure_cannot_skip_cleanup(tmp_path):
    req, evidence = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=evidence,
                                     attempt_root=tmp_path)
    event = Event()
    event.set()
    calls, closed = [0], []
    def clock():
        calls[0] += 1
        if calls[0] == 2:
            raise RuntimeError('private clock failure')
        return time.monotonic_ns()
    def close(timeout):
        closed.append(timeout)
        return EndpointCleanupResult(True, 0)
    result = run_owned_endpoint_trial(req, permit, connection_id='owned-test',
        read_once=lambda *_:pytest.fail('No read'), write_once=lambda *_:pytest.fail('No write'),
        close_once=close, presence_expiry_reader=lambda:0, cancellation=event,
        basis='SYNTHETIC_WIRE_REHEARSAL', clock_ns=clock)
    assert closed == [2000] and result['status'] == 'CLEANUP_UNCERTAIN'
