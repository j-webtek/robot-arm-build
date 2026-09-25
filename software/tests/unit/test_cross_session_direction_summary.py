"""Offline grouping keeps failures and confounders out of accuracy claims."""
import math
import json
import hashlib
import pytest
from pathlib import Path
import sys

SCRIPTS=Path(__file__).resolve().parents[2]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from review_cross_session_roll import direction_summary, completed_journal


def row(name,start,final,*,desired=1.25,valid=True,speed=20):
    return dict(export_id=name,session_id=name,full_validation_success=valid,
        baseline_rad=[0,0,0,0,math.radians(start),0],
        command=dict(T=101,joint=5,rad=math.radians(1.25),spd=speed,acc=1),
        desired_endpoint_deg=desired,final_deg=final)


def test_separates_directions_targets_and_speed_and_excludes_failed_hold():
    groups=direction_summary([row('up',0,1.23),row('down',2.28,1.49),
        row('lookup',2.28,1.49,desired=1.5),row('fast',0,1.23,speed=30),
        row('failed',2.28,9,valid=False)])
    assert len(groups)==4 and sum(g['count'] for g in groups)==4
    assert {g['direction'] for g in groups}=={'ascending','descending'}


def test_retains_variability_and_starting_roll_not_just_mean():
    groups=direction_summary([row('a',2.28,1.23),row('b',2.3,1.41)])
    g=groups[0]
    assert g['count']==2 and len(g['starting_roll_deg'])==2
    assert g['in_illustrative_005_band']==1
    assert g['reported_endpoint_span_deg']>.17
    assert g['exports']==['a','b']


@pytest.mark.parametrize('fault',[None,'changed','wrong_session','wrong_order','unfinished','duplicate','wrong_hash'])
def test_frozen_journal_rejects_changed_or_incomplete_evidence(tmp_path,fault):
    session='a'*32
    header=json.dumps(dict(session_id=session)).encode()
    (tmp_path/f'comparison-{session}-header.json').write_bytes(header)
    previous=hashlib.sha256(header).hexdigest()
    events=[dict(event='LEG_VERIFIED',index=0,export_id='one'),
            dict(event='LEG_VERIFIED',index=1,export_id='two'),
            dict(event='FINISHED',status='COMPLETED',reviewed_legs=2)]
    if fault=='wrong_order':events[1]['index']=0
    if fault=='unfinished':events[-1]['status']='STOPPED'
    if fault=='duplicate':events[1]['export_id']='one'
    for i,event in enumerate(events):
        event['session_id']='b'*32 if fault=='wrong_session' else session
        raw=json.dumps(dict(sequence=i,previous_sha256=previous,event=event)).encode()
        (tmp_path/f'comparison-{session}-{i:04d}.json').write_bytes(raw)
        previous=hashlib.sha256(raw).hexdigest()
    if fault=='changed':(tmp_path/f'comparison-{session}-0000.json').write_bytes(b'{}')
    if fault=='wrong_hash':previous='0'*64
    if fault:
        with pytest.raises((ValueError,KeyError)):
            completed_journal(tmp_path,session,expected_legs=2,expected_final_hash=previous)
    else:
        assert len(completed_journal(tmp_path,session,expected_legs=2,expected_final_hash=previous))==2
