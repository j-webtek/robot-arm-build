from dataclasses import replace
import pytest
from rocell.application.compensated_shoulder_contract import Pose
from rocell.application.shoulder_movement_matrix import draft_matrix, classify_observation


def test_matrix_three_sizes_two_repeats_both_directions():
    draft=draft_matrix((2389,1725),(2398,1718),previous_targets=[(2389,1725),(2397,1717)])
    legs=draft['legs']
    assert len(legs)==12
    assert [leg['register_delta'][0] for leg in legs]==[-4,4,-8,8,-12,12]*2
    assert legs[1]['previously_visited_target']
    assert not legs[0]['previously_visited_target']
    assert not draft['movement_authorized']


def test_envelope_rejected():
    with pytest.raises(ValueError):draft_matrix((2389,1725),(2450,1718))


def scenario(deltas):
    before=Pose((2047,2398,1716,2904,1591,2041,2047),
                (2047,2397,1717,2907,1589,2040,2047),(1,)*7,(False,)*7,1,1000)
    goals=(2389,1725)
    samples=[]
    for index,(a,b) in enumerate(deltas):
        p=list(before.positions);p[1]+=a;p[2]+=b
        g=list(before.goals);g[1:3]=goals
        t=201000+index*200000
        samples.append(Pose(p,g,(1,)*7,(False,)*7,t,t+1000))
    return before,goals,samples


def classify(data,**kwargs):
    return classify_observation(*data,bounds=[(0,4095)]*7,
                                delivery_confirmed=True,export_verified=True,**kwargs)


def test_observed_small_response_not_no_movement():
    data=scenario([(0,0),(0,1),(0,2),(0,2),(0,2)])
    r=classify(data)
    assert r['classification']=='SMALL_SETTLED_RESPONSE'
    assert r['final_net_counts']==[0,2] and r['sampled_motion_observed']
    assert r['candidate_progression_eligible'] and not r['movement_authorized']
    assert not classify(data,consecutive_small=1)['candidate_progression_eligible']


def test_transient_retained_separately():
    r=classify(scenario([(-4,4),(0,2),(0,2),(0,2)]))
    assert r['classification']=='TRANSIENT_THEN_SMALL_NET_RESPONSE'
    assert r['sampled_peak_absolute_counts']==[4,4]


@pytest.mark.parametrize('fault',['delivery','export','neighbor','torque','direction','unsettled'])
def test_small_policy_never_relaxes_unsafe_evidence(fault):
    before,goals,samples=scenario([(0,2)]*3)
    if fault=='neighbor':
        samples=[replace(p,positions=(2050,)+p.positions[1:]) for p in samples]
    if fault=='torque':samples=[replace(p,torque=(0,)+(1,)*6) for p in samples]
    if fault=='direction':
        samples=[replace(p,positions=(p.positions[0],2401)+p.positions[2:]) for p in samples]
    if fault=='unsettled':samples=[replace(p,moving=(True,)+(False,)*6) for p in samples]
    r=classify_observation(before,goals,samples,bounds=[(0,4095)]*7,
        delivery_confirmed=fault!='delivery',export_verified=fault!='export')
    assert not r['candidate_progression_eligible']
