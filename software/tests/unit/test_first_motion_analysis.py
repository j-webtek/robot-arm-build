"""Synthetic joint wire windows cannot certify physical movement."""
import json
import math

import pytest

from rocell.arm.first_motion_analysis import analyze_first_motion
from test_first_motion_measurement_binding import setup


def wire(values, start, *, corrupt_at=None, other_at=None):
    raw = b''
    windows = []
    for i, value in enumerate(values):
        fields = dict(T=1051,x=1,y=2,z=3,tit=0,b=0,s=0,e=0,t=value,r=0,g=0)
        if i == other_at: fields['e'] = .1
        line = json.dumps(fields,separators=(',',':')).encode()+b'\n'
        if i == corrupt_at: line = b'broken\n'
        windows.append([len(raw),len(raw)+len(line),start+i*50_000_000,start+i*50_000_000+1])
        raw += line
    return raw, windows


def analyze(tmp_path, *, values=None, corrupt_at=None, other_at=None, shared=False):
    _, request = setup(tmp_path)
    before, bw = wire([0]*10, 2_000_000_000)
    after, aw = wire([math.radians(1)]*10 if values is None else values,
                     2_500_000_002, corrupt_at=corrupt_at, other_at=other_at)
    if shared:
        for row in aw: row[2:] = [2_500_000_002,2_500_000_002]
    return analyze_first_motion(request,before,bw,after,aw,
        baseline_started_ns=2_000_000_000,baseline_finished_ns=2_500_000_000,
        write_started_ns=2_500_000_000,write_finished_ns=2_500_000_001,
        observation_end_ns=3_000_000_000,basis='SYNTHETIC_WIRE_REHEARSAL')


def test_reported_response_is_never_physical_qualification(tmp_path):
    result = analyze(tmp_path)
    assert result['status'] == 'REPORTED_WRIST_RESPONSE_REVIEW_REQUIRED'
    assert result['baseline_count'] == result['post_count'] == 10
    assert result['host_target_dwell_entry_bounds_ns'] is not None
    for key in ('physical_movement_verified','device_sample_freshness_verified',
                'endpoint_baseline_qualified','motion_authorized','campaign_advance_allowed'):
        assert result[key] is False


@pytest.mark.parametrize('kwargs,issue',[
    ({'values':[0]*10},'NO_RESOLVABLE_REPORTED_WRIST_CHANGE'),
    ({'values':[-.1]*10},'NO_FINAL_REPORTED_TARGET_DWELL'),
    ({'values':[math.radians(1)]*9+[0]},'NO_FINAL_REPORTED_TARGET_DWELL'),
    ({'corrupt_at':5},'POST_INVALID_JOINT_RECORD'),
    ({'other_at':5},'OTHER_REPORTED_JOINT_CHANGED'),
    ({'values':[.2]+[math.radians(1)]*9},'REPORTED_WRIST_EXCURSION'),
    ({'shared':True},'NO_FINAL_REPORTED_TARGET_DWELL'),
])
def test_bad_or_insufficient_full_window_cannot_pass(tmp_path,kwargs,issue):
    result = analyze(tmp_path,**kwargs)
    assert result['status'] == 'INSUFFICIENT_OR_UNEXPECTED_TELEMETRY'
    assert issue in result['issues']
    assert result['host_target_dwell_entry_bounds_ns'] is None


def test_byte_budget_rejected(tmp_path):
    _, request = setup(tmp_path)
    with pytest.raises(ValueError):
        analyze_first_motion(request,b'x'*65537,[],b'',[],baseline_started_ns=2_000_000_000,
            baseline_finished_ns=2_500_000_000,write_started_ns=2_500_000_000,
            write_finished_ns=2_500_000_001,observation_end_ns=3_000_000_000,
            basis='SYNTHETIC_WIRE_REHEARSAL')
