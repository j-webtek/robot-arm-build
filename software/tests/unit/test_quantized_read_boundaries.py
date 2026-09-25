"""Equal adjacent read timestamps are not stale cached feedback or arrival."""
import pytest
from rocell.application.hold_record_replay import _snapshot
from rocell.application.servo_control_state_assessment import assess_control_state
from rocell.application.servo_register_reference import PROFILE_ID


def snapshot():
    rows=[]
    for index in range(28):
        local=index%14
        address=((42,56) if index<14 else (33,40))[local%2]
        width={42:2,56:15,33:1,40:1}[address]
        raw=bytearray(width)
        if address in (42,56):raw[:2]=(2723).to_bytes(2,'little')
        if address==40:raw[0]=1
        rows.append([11+local//2,address,width,[local,100+index,101+index,width,0,True,raw.hex()]])
    return dict(schema='rocell.hold_snapshot.v1',boot_id='boot',command_id='command',
        snapshot_index=0,profile_id=PROFILE_ID,byte_order='little',complete=True,
        reason='HOLD_STATE_CAPTURED',reads=rows)


def control():
    return dict(schema='rocell.control_state_reads.v1',boot_id='boot',command_id='command',
        profile_id=PROFILE_ID,reason='CONTROL_READ_CAPTURED',
        reads=[[11+i//2,40 if i%2 else 33,[i,100+i,101+i,1,0,True,'01' if i%2 else '00']]
               for i in range(14)])


def assess(value,after_us=99):
    return assess_control_state(value,boot_id='boot',command_id='command',reviewed_mode=0,
        after_us=after_us,boundary_us=120,maximum_age_us=100)


def test_adjacent_snapshot_boundaries_are_accepted_without_arrival_claim():
    result=_snapshot(snapshot())
    assert result.started_us==100 and result.finished_us==128
    assert all(joint.position==2723 for joint in result.joints)


@pytest.mark.parametrize('index',[1,2,14,22,27])
def test_snapshot_reversal_rejected_at_every_type_of_boundary(index):
    value=snapshot();value['reads'][index][3][1]-=1
    with pytest.raises(ValueError):_snapshot(value)


@pytest.mark.parametrize('field,value',[(0,0),(3,0),(4,1),(5,False),(6,None)])
def test_equal_clock_boundary_does_not_override_invalid_read(field,value):
    record=snapshot();record['reads'][22][3][field]=value
    with pytest.raises(ValueError):_snapshot(record)


def test_control_equal_adjacent_boundary_but_strict_initial_boundary():
    result=assess(control())
    assert result['status']=='CONTROL_STATE_MATCHES'
    assert result['progression_authority'] is False
    with pytest.raises(ValueError):assess(control(),after_us=100)


def test_control_backward_boundary_still_rejected():
    value=control();value['reads'][8][2][1]-=1
    with pytest.raises(ValueError):assess(value)
