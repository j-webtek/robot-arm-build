"""Owned sequencing using synthetic bytes/reviews; no serial device access."""
import json
from threading import Event

import pytest

from rocell.application.first_motion_owned_trial import run_owned_first_motion_trial, FirstMotionCleanupResult
from test_first_motion_admission import setup, admit


def run(tmp_path, fault=None):
    request,reader,clock,_ = setup(tmp_path)
    permit = admit(tmp_path,request,reader,clock)
    connection = request.to_dict()['attempt_id']
    permit.claim_native_open(request,connection,'COM7')
    events = []
    cancellation = Event()
    phase = ['baseline']
    if fault == 'cancel_before': cancellation.set()
    def read(n,timeout):
        events.append('read_'+phase[0])
        clock[0] += min(50,timeout)*1_000_000
        if fault == 'baseline_error' and phase[0]=='baseline': raise OSError('private text')
        if fault == 'invalid_baseline' and phase[0]=='baseline': return b'bad\n'
        if fault == 'post_error' and phase[0]=='post': raise OSError('private text')
        value = 0 if phase[0]=='baseline' or fault=='unchanged' else request.to_dict()['command']['rad']
        return json.dumps(dict(T=1051,x=1,y=2,z=3,tit=0,b=0,s=0,e=0,t=value,r=0,g=0),
                          separators=(',',':')).encode()+b'\n'
    def write(payload):
        permit.claim_native_dispatch(request,connection,'COM7')
        events.append('write')
        assert json.loads(payload)==request.to_dict()['command']
        phase[0]='post'
        clock[0]+=1
        if fault=='cancel_after': cancellation.set()
        if fault=='write_error': raise OSError('private write text')
        return len(payload)-1 if fault=='short_write' else len(payload)
    def close(timeout):
        events.append('close')
        assert timeout==2000
        if fault=='cleanup_error': raise OSError('private cleanup text')
        return FirstMotionCleanupResult(fault!='pending_cleanup',1 if fault=='pending_cleanup' else 0)
    result = run_owned_first_motion_trial(request,permit,connection_id=connection,
        read_once=read,write_once=write,close_once=close,cancellation=cancellation,
        clock_ns=lambda:clock[0],basis='SYNTHETIC_WIRE_REHEARSAL')
    assert events[-1]=='close' and events.count('close')==1 and events.count('write')<=1
    assert not result['physical_movement_verified'] and not result['campaign_advance_allowed']
    assert 'private' not in json.dumps(result)
    with pytest.raises(ValueError): permit.claim_native_dispatch(request,connection,'COM7')
    return result,events


def test_nominal_sequence_retains_both_windows(tmp_path):
    result,events = run(tmp_path)
    assert result['status']=='REPORTED_WRIST_RESPONSE_REVIEW_REQUIRED'
    assert result['baseline']['raw']['bytes']>0 and result['post']['raw']['bytes']>0
    assert events.index('write')>0 and events.index('write')<events.index('read_post')
    assert result['cleanup']['status']=='HANDLES_CLOSED'


@pytest.mark.parametrize('fault',['cancel_before','baseline_error','invalid_baseline'])
def test_baseline_failure_never_writes(tmp_path,fault):
    result,events = run(tmp_path,fault)
    assert 'write' not in events and result['write'] is None


@pytest.mark.parametrize('fault',['short_write','write_error'])
def test_uncertain_submission_still_retains_post_data(tmp_path,fault):
    result,events = run(tmp_path,fault)
    assert result['status']=='WRITE_UNCERTAIN_NO_RETRY'
    assert result['write']['write_completion_uncertain']
    assert result['post']['raw']['bytes']>0 and events.count('write')==1


@pytest.mark.parametrize('fault',['pending_cleanup','cleanup_error'])
def test_cleanup_uncertainty_overrides_telemetry_agreement(tmp_path,fault):
    result,_ = run(tmp_path,fault)
    assert result['status']=='CLEANUP_UNCERTAIN'


@pytest.mark.parametrize('fault',['cancel_after','post_error'])
def test_incomplete_post_cannot_be_success(tmp_path,fault):
    result,_ = run(tmp_path,fault)
    assert result['status']=='POST_CAPTURE_INCOMPLETE'


def test_unchanged_feedback_does_not_qualify(tmp_path):
    result,_ = run(tmp_path,'unchanged')
    assert result['status']=='INSUFFICIENT_OR_UNEXPECTED_TELEMETRY'
