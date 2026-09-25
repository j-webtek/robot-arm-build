from dataclasses import replace
import pytest
from rocell.application.hold_initialization_model import Joint,Snapshot
from rocell.application.mixed_shoulder_trial import MixedShoulderTrial


def baseline():
    return Snapshot(100,200,tuple(Joint(p,g,t) for p,g,t in
        [(2047,0,0),(2455,2455,1),(1659,0,0),(2906,2907,1),
         (1589,0,0),(2040,0,0),(2047,0,0)]))


def change(scan,index,**values):
    joints=list(scan.joints);joints[index]=replace(joints[index],**values)
    return replace(scan,joints=tuple(joints))


def prepared():
    trial=MixedShoulderTrial(baseline())
    fresh=replace(baseline(),started_us=300,finished_us=400)
    command=trial.propose(fresh,now_us=450)
    assert command['servo_id']==13 and command['target']==1659
    return trial,fresh


@pytest.mark.parametrize('torque',[0,1])
def test_target_write_outcomes_do_not_grant_follow_on(torque):
    trial,fresh=prepared()
    scans=[change(replace(fresh,started_us=500+i*100000,finished_us=600+i*100000),
                  2,goal=1659,torque=torque) for i in range(3)]
    result=trial.assess(scans,delivery_confirmed=True)
    assert result['category']==('TARGET_OBSERVED_ENABLED' if torque else 'TARGET_OBSERVED_PASSIVE')
    assert result['max_abs_error_counts']==0 and not result['progression_authority']
    with pytest.raises(ValueError):trial.propose(fresh,now_us=450)


@pytest.mark.parametrize('fault',['stale','changed_goal','changed_torque','drift','moving'])
def test_prewrite_state_changes_stop(fault):
    trial=MixedShoulderTrial(baseline());fresh=replace(baseline(),started_us=300,finished_us=400)
    if fault=='changed_goal':fresh=change(fresh,1,goal=2456)
    if fault=='changed_torque':fresh=change(fresh,2,torque=1)
    if fault=='drift':fresh=change(fresh,2,position=1662)
    if fault=='moving':fresh=change(fresh,2,moving=1)
    with pytest.raises(ValueError):trial.propose(fresh,now_us=600000 if fault=='stale' else 450)
    assert trial.state=='STOPPED'


@pytest.mark.parametrize('fault',['goal','neighbor','drift','old_scan','torque_oscillation'])
def test_ack_does_not_prove_endpoint(fault):
    trial,fresh=prepared()
    scans=[change(replace(fresh,started_us=500+i*100000,finished_us=600+i*100000),
                  2,goal=1659) for i in range(3)]
    if fault=='goal':scans[1]=change(scans[1],2,goal=0)
    if fault=='neighbor':scans[1]=change(scans[1],1,torque=0)
    if fault=='drift':scans[1]=change(scans[1],2,position=1662)
    if fault=='old_scan':scans[1]=scans[0]
    if fault=='torque_oscillation':scans[1]=change(scans[1],2,torque=1)
    with pytest.raises(ValueError):trial.assess(scans,delivery_confirmed=True)
    assert trial.state=='STOPPED'


def test_uncertain_delivery_has_no_retry():
    trial,fresh=prepared()
    assert trial.assess([],delivery_confirmed=False)['category']=='DELIVERY_UNCERTAIN'
    with pytest.raises(ValueError):trial.propose(fresh,now_us=450)
