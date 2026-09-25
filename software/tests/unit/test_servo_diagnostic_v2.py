import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_decode import decode_trace
from rocell.application.servo_diagnostic_simulation import simulate_trace


@pytest.mark.parametrize('scenario,category,error',[
    ('paired_arrival','DIAGNOSTIC_ENDPOINT_CRITERIA_MET',0),
    ('paired_negative_position','FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET',-2101),
    ('paired_failed_read','DIAGNOSTIC_EVIDENCE_INCOMPLETE_OR_CONTRADICTORY',None),
])
def test_separate_reads_end_to_end(scenario,category,error):
    trace=simulate_trace(scenario)
    decoded=decode_trace(canonical(trace))
    assert decoded['trace']==trace
    assessment=decoded['assessment']
    assert assessment['category']==category
    assert assessment['final_desired_error_counts']==error
    assert not assessment['acquisitions_simultaneous']
    assert not assessment['progression_authority']
    assert assessment['fresh_position_samples']==(0 if scenario=='paired_failed_read' else 6)


@pytest.mark.parametrize('field,value',[
    ('command_id','other-command'),('servo_id',4),('sequence',0),
    ('read_started_us',100),('raw_hex','00'),('device_error',1)])
def test_invalid_pair_rejected(field,value):
    trace=simulate_trace('paired_arrival')
    trace['samples'][3]['feedback'][field]=value
    with pytest.raises(ValueError):decode_trace(canonical(trace))


def test_unsigned_v1_contract_remains_unchanged():
    trace=simulate_trace('arrival')
    trace['samples'][0]['position_count']=-1
    with pytest.raises(ValueError):decode_trace(canonical(trace))
