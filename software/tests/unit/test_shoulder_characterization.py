from dataclasses import replace
import pytest
from rocell.application.compensated_shoulder_contract import Pose,REFERENCE,GOALS
from rocell.application.shoulder_characterization import draft_manifest,assess_leg


def inputs(residual=(9,-7)):
    before=Pose(REFERENCE,GOALS,(1,)*7,(False,)*7,1,1000)
    goals=(2397,1717);positions=list(REFERENCE);positions[1:3]=[g+r for g,r in zip(goals,residual)]
    changed=list(GOALS);changed[1:3]=goals
    samples=[Pose(positions,changed,(1,)*7,(False,)*7,200000+i*200000,201000+i*200000) for i in range(3)]
    bounds=[(max(0,p-32),min(4095,p+32)) for p in REFERENCE]
    return before,goals,samples,bounds


@pytest.mark.parametrize('residual,status',[((9,-7),'SETTLED_MISS'),((0,0),'SETTLED_ACCURATE')])
def test_miss_is_not_safety_fault_or_movement_permission(residual,status):
    before,goals,samples,bounds=inputs(residual)
    result=assess_leg(before,goals,samples,bounds=bounds,delivery_confirmed=True,export_verified=True)
    assert result['status']==status and result['continuation_eligible']
    assert result['movement_authorized'] is False


@pytest.mark.parametrize('fault',['delivery','export','wrong_goal','neighbor','reverse','moving','stale','torque','bounds','no_response'])
def test_fault_stops_progression(fault):
    before,goals,samples,bounds=inputs();last=samples[-1]
    if fault=='wrong_goal':samples[-1]=replace(last,goals=GOALS)
    if fault=='neighbor':samples[-1]=replace(last,positions=(2051,)+last.positions[1:])
    if fault=='reverse':samples[-1]=replace(last,positions=(2047,2420,1690)+last.positions[3:])
    if fault=='moving':samples[-1]=replace(last,moving=(False,True,False,False,False,False,False))
    if fault=='stale':samples[-1]=replace(last,started_us=9000000,finished_us=9001000)
    if fault=='torque':samples[-1]=replace(last,torque=(1,0,1,1,1,1,1))
    if fault=='bounds':bounds[1]=(2414,2414)
    if fault=='no_response':samples=[replace(p,positions=REFERENCE) for p in samples]
    result=assess_leg(before,goals,samples,bounds=bounds,delivery_confirmed=fault!='delivery',export_verified=fault!='export')
    assert result['status']=='STOP' and not result['continuation_eligible']


def test_finite_repeatable_uncompensated_draft():
    manifest=draft_manifest((2405,1709))
    assert len(manifest['legs'])==12 and manifest['simulation_only']
    assert all(sum(leg['command_goals'])==4114 for leg in manifest['legs'])
    assert not manifest['compensation_enabled'] and not manifest['movement_authorized']


def test_matched_target_has_three_approaches_each_way():
    manifest = draft_manifest((2405,1709), pattern='matched')
    prior = 2405
    directions = []
    for leg in manifest['legs']:
        goal = leg['command_goals'][0]
        assert 0 < abs(goal-prior) <= 24
        assert sum(leg['command_goals']) == 4114
        if goal == 2397:
            directions.append(1 if goal > prior else -1)
        prior = goal
    assert directions.count(1) == directions.count(-1) == 3
    assert manifest['simulation_only'] and not manifest['movement_authorized']


def test_unknown_pattern_rejected():
    with pytest.raises(ValueError, match='pattern'):
        draft_manifest((2405,1709), pattern='other')
