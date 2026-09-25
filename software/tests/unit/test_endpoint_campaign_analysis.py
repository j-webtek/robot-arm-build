"""Endpoint campaign metrics must never imply observation of initial travel."""

import base64
from copy import deepcopy
import hashlib

import pytest

from rocell.arm.movement_campaign_analysis import summarize_campaign, summarize_endpoint_campaign
from test_movement_campaign_analysis import repeated_plan
from test_endpoint_movement_analysis import endpoints


def observations(plan):
    rows = []
    for trial in plan.to_dict()['trials']:
        start = 800_000_000 if trial['spd']==.05 else 1_000_000_000
        raw,windows,kw = endpoints([trial['target']['x_mm']]*13,
                                  [start+i*50_000_000 for i in range(13)])
        rows.append({'trial_id':trial['trial_id'],'outcome':'MODEL_COMPLETED',
            'evidence':dict(kw,raw={'base64':base64.b64encode(raw).decode(),
                                   'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
                            read_windows=windows,physical_authority=False,
                            observation_contract='SUPERVISED_ENDPOINT_ONLY')})
    return rows


def test_delayed_endpoints_compare_dwell_only_and_separate_return_routes():
    plan = repeated_plan()
    result = summarize_endpoint_campaign(plan,observations(plan))
    assert result['schema']=='rocell.endpoint_campaign_analysis.v1'
    assert len(result['groups'])==4
    assert all(g['eligible_count']==3 for g in result['groups'])
    assert all(g['reported_endpoint_spread_mm']==0 for g in result['groups'])
    assert all('median_host_settling_entry_bounds_ns' not in g for g in result['groups'])
    assert all(c['relation']=='FIRST_HAS_EARLIER_HOST_ENDPOINT_DWELL_BOUNDS'
               and c['physical_speed_ranking'] is None for c in result['host_timing_comparisons'])
    assert result['recommended_settings'] is result['travel_time_s'] is None
    assert not result['physical_stop_verified'] and not result['continuous_motion_observation']
    assert all(r['analysis']['status']=='OBSERVED_ENDPOINT_DWELL' for r in result['trials'])


def test_contracts_cannot_be_mixed_or_inferred():
    plan = repeated_plan()
    rows = observations(plan)
    with pytest.raises(ValueError,match='continuous'): summarize_campaign(plan,rows)
    rows[0]['evidence'].pop('observation_contract')
    with pytest.raises(ValueError,match='explicit'): summarize_endpoint_campaign(plan,rows)


def test_failed_missing_and_duplicate_captures_do_not_count_as_repeats():
    plan = repeated_plan()
    rows = observations(plan)
    for row in rows:
        row['outcome']='OBSERVATION_COMPLETED'
        row['evidence']['basis']='RETAINED_PHYSICAL_CAPTURE'
    rows[0]['outcome']='WRITE_UNCERTAIN'
    rows.pop()
    result = summarize_endpoint_campaign(plan,rows)
    assert 'TRIAL_OUTCOME_NOT_COMPLETED' in result['trials'][0]['exclusions']
    assert 'REUSED_PHYSICAL_CAPTURE_NOT_INDEPENDENT' in result['trials'][2]['exclusions']
    assert result['trials'][-1]['outcome']=='NOT_OBSERVED'
    assert all(g['status']=='INSUFFICIENT_REPETITIONS' for g in result['groups'])


def test_raw_is_reanalyzed_and_later_gap_is_not_excused():
    plan = repeated_plan()
    rows = observations(plan)
    rows[0]['evidence']['analysis']={'status':'FABRICATED'}
    assert summarize_endpoint_campaign(plan,rows)['trials'][0]['analysis']['status']=='OBSERVED_ENDPOINT_DWELL'
    broken = deepcopy(rows)
    for window in broken[0]['evidence']['read_windows'][5:]:
        window[2]+=200_000_000
        window[3]+=200_000_000
    broken[0]['evidence']['observation_end_ns']+=200_000_000
    result = summarize_endpoint_campaign(plan,broken)
    assert result['trials'][0]['exclusions']==['INSUFFICIENT_ENDPOINT_DWELL']
    rows[0]['evidence']['raw']['sha256']='f'*64
    with pytest.raises(ValueError,match='digest'): summarize_endpoint_campaign(plan,rows)
