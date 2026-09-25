import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.shoulder_rise_review import ShoulderRiseReview


def stable_event(sequence,positions=None,goals=None,started=None):
    positions=positions or [2047,2448,1667,2904,1590,2041,2047]
    goals=goals or [2047,2443,1671,2907,1589,2040,2047]
    rows=[[11+i,p,goals[i],1,(p.to_bytes(2,'little')+bytes(13)).hex()] for i,p in enumerate(positions)]
    start=100+sequence*200000 if started is None else started
    return dict(schema='rocell.shoulder_hold_event.v1',boot_id='11'*16,
        command_id='shoulder-stable-clearance24-v1',sequence=sequence,
        event='BASELINE' if sequence==0 else 'BASELINE_STABILITY',servo_id=0,result=0,
        scan_started_us=start,scan_finished_us=start+100,joints=rows,
        snapshot_role='OBSERVATION',physical_accuracy_verified=False)


@pytest.mark.parametrize('fault',[None,'drift','goal','too_soon','moving','wrong_event','missing_sample'])
def test_three_stable_baselines_are_required(fault):
    review=ShoulderRiseReview('11'*16,'shoulder-stable-clearance24-v1',stable=True)
    review.accept(canonical(stable_event(0)))
    event=stable_event(1)
    if fault=='drift':event=stable_event(1,positions=[2047,2448,1667,2906,1590,2041,2047])
    if fault=='goal':event['joints'][3][2]+=1
    if fault=='too_soon':event=stable_event(1,started=300)
    if fault=='moving':
        raw=bytearray.fromhex(event['joints'][3][4]);raw[10]=1;event['joints'][3][4]=raw.hex()
    if fault=='wrong_event':event['event']='SHOULDER_STEP_INTENT'
    if fault=='missing_sample':event['sequence']=2
    if fault:
        with pytest.raises(ValueError):review.accept(canonical(event))
        assert review.sent is None
    else:
        review.accept(canonical(event));review.accept(canonical(stable_event(2)))
        assert review.count==3 and review.sent is None and review.targets is None


@pytest.mark.parametrize('index',range(7))
def test_all_joints_bound_to_reviewed_start_before_receipt(index):
    positions=[2047,2455,1659,2906,1589,2040,2047]
    positions[index]+=17
    rows=[[i+11,p,p,1,(p.to_bytes(2,'little')+bytes(13)).hex()] for i,p in enumerate(positions)]
    event=dict(schema='rocell.shoulder_hold_event.v1',boot_id='11'*16,command_id='shoulder-rise12-v1',
        sequence=0,event='BASELINE',servo_id=0,result=0,scan_started_us=100,scan_finished_us=200,
        joints=rows,snapshot_role='OBSERVATION',physical_accuracy_verified=False)
    review=ShoulderRiseReview('11'*16,'shoulder-rise12-v1')
    with pytest.raises(ValueError,match='baseline'):review.accept(canonical(event))
    assert review.count==0
