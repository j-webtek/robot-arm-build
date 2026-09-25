"""Pure comparison-block checks, never live wizard actions."""
import importlib.util
import math
from pathlib import Path
import sys

import pytest

scripts=Path(__file__).resolve().parents[2]/'scripts'
spec=importlib.util.spec_from_file_location('block_review',scripts/'review_roll_comparison_block.py')
block=importlib.util.module_from_spec(spec)
sys.path.insert(0,str(scripts))
try:spec.loader.exec_module(block)
finally:sys.path.pop(0)


def legs():
    result=[]
    for i,(role,c,d) in enumerate(block.EXPECTED):
        result.append(dict(summary=dict(export_id=str(i),manifest_file_sha256=str(i),
            full_validation_success=True,command_attempts=1,
            command=dict(T=101,joint=5,spd=20,acc=1,rad=math.radians(c)),
            desired_endpoint_deg=d,candidate=dict(candidate_sha256=block.LOOKUP_HASH) if role=='lookup' else None,
            hold_assessment=dict(hold_final_error_deg=.24 if role=='control' else .15)),
            dispatch_s=100+i*60,baseline=[0]*6,last_hold=dict(
                response_finished_monotonic_s=140+i*60,joints_rad=dict.fromkeys(block.JOINTS,0))))
    return result


def test_compatible_intervals_do_not_prove_shared_clock():
    r=block.assess_block(legs())
    assert r['individual_legs_and_protocol_pass'] and r['observed_intervals_within_window']
    assert r['comparison']['absolute_error_reduction_deg']==pytest.approx(.09)
    assert not r['controlled_block_qualified'] and not r['motion_authorized']


@pytest.mark.parametrize('kind',['failure','command','candidate','baseline'])
def test_invalid_leg_never_produces_success_comparison(kind):
    v=legs()
    if kind=='failure':v[1]['summary']['full_validation_success']=False
    elif kind=='command':v[1]['summary']['command']['spd']=21
    elif kind=='candidate':v[3]['summary']['candidate']['candidate_sha256']='wrong'
    else:v[2]['baseline'][0]=1
    r=block.assess_block(v)
    assert r['failures'] and r['comparison'] is None


def test_timing_miss_preserved_without_rewriting_evidence():
    v=legs();v[2]['dispatch_s']+=3
    r=block.assess_block(v)
    assert not r['observed_intervals_within_window']
    assert r['links'][1]['interval_s']==23


def test_missing_hold_does_not_bridge():
    v=legs();v[0]['last_hold']=None
    assert not block.assess_block(v)['individual_legs_and_protocol_pass']


def test_duplicate_wrong_count_and_reversed_clock_rejected():
    v=legs()
    with pytest.raises(ValueError):block.assess_block(v[:3])
    with pytest.raises(ValueError):block.assess_block([v[0]]*4)
    v[1]['dispatch_s']=0
    with pytest.raises(ValueError):block.assess_block(v)
