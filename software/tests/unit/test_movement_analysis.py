"""Known synthetic trajectories encoded through the actual wire parser."""

import json
import math
import pytest

from rocell.arm.movement_analysis import analyze_trial
from rocell.motion.characterization_plan import freeze_campaign
from test_characterization_plan import candidate

EPOCH = 1_000_000_000


def wire(values, times=None):
    raw=b''; windows=[]
    for index,value in enumerate(values):
        pose={'T':1051,'x':value,'y':0,'z':0,'tit':0,'b':0,'s':0,'e':0,'t':0,'r':0,'g':0}
        line=json.dumps(pose,separators=(',',':')).encode()+b'\n'
        begin=EPOCH + (times[index] if times is not None else (index+1)*50_000_000)
        windows.append([len(raw),len(raw)+len(line),begin,begin+1_000_000])
        raw+=line
    return raw,windows


def analyze(values,times=None,**kwargs):
    raw,windows=wire(values,times)
    return analyze_trial(freeze_campaign(candidate()),'out',raw,windows,
        command_completed_ns=EPOCH,observation_end_ns=windows[-1][3],
        basis='SYNTHETIC_WIRE_REHEARSAL',**kwargs)


def test_known_endpoint_overshoot_and_conservative_dwell():
    result=analyze([0,.5,1.2]+[1]*13)
    assert result['status']=='OBSERVED_SETTLING'
    assert result['peak_observed_directional_overshoot_mm']==pytest.approx(.2)
    assert result['latest_reported_endpoint']['position_error_mm']==0
    assert result['host_settling_entry_bounds_ns']==[200_000_000,201_000_000]
    assert not result['sample_freshness_verified']
    assert not result['physical_ready']


@pytest.mark.parametrize('values',[[0]*16,[0,.5,1],[0,.5]+[1]*12+[.5]])
def test_stale_short_dwell_and_late_departure_cannot_settle(values):
    result=analyze(values)
    assert result['host_settling_entry_bounds_ns'] is None
    assert result['status']=='INSUFFICIENT_EVIDENCE'


def test_gap_prevents_settling_even_with_perfect_last_position():
    times=[(i+1)*50_000_000+(200_000_000 if i>=5 else 0) for i in range(16)]
    result=analyze([0,.5]+[1]*14,times)
    assert 'READ_COVERAGE_GAP' in result['issues']
    assert result['latest_reported_endpoint']['position_error_mm']==0
    assert result['host_settling_entry_bounds_ns'] is None


def test_suffix_is_not_silently_ignored():
    raw,w=wire([0,.5]+[1]*14)
    w.append([len(raw),len(raw)+1,w[-1][3]+1,w[-1][3]+2]); raw+=b'{'
    result=analyze_trial(freeze_campaign(candidate()),'out',raw,w,command_completed_ns=EPOCH,
        observation_end_ns=w[-1][3],basis='SYNTHETIC_WIRE_REHEARSAL')
    assert 'UNTERMINATED_CAPTURE_SUFFIX' in result['issues']


def test_empty_capture_and_numeric_range_have_no_fabricated_metrics():
    result=analyze_trial(freeze_campaign(candidate()),'out',b'',[],command_completed_ns=EPOCH,
        observation_end_ns=EPOCH+1_000_000_000,basis='SYNTHETIC_WIRE_REHEARSAL')
    assert result['latest_reported_endpoint'] is None
    assert result['peak_observed_directional_overshoot_mm'] is None
    invalid=analyze([1e200]*16)
    assert 'NUMERIC_ANALYSIS_RANGE' in invalid['issues']
    assert 'NaN' not in json.dumps(invalid,allow_nan=False)


def test_angles_do_not_wrap_to_claim_target_match():
    raw,w=wire([0,.5]+[1]*14)
    raw2=b''; w2=[]
    for original in w:
        p=json.loads(raw[original[0]:original[1]])
        p['r']=2*math.pi
        line=json.dumps(p,separators=(',',':')).encode()+b'\n'
        w2.append([len(raw2),len(raw2)+len(line),original[2],original[3]])
        raw2+=line
    result=analyze_trial(freeze_campaign(candidate()),'out',raw2,w2,command_completed_ns=EPOCH,
        observation_end_ns=w2[-1][3],basis='SYNTHETIC_WIRE_REHEARSAL')
    assert result['host_settling_entry_bounds_ns'] is None
    assert result['latest_reported_endpoint']['max_unwrapped_angle_error_rad']==pytest.approx(2*math.pi)
