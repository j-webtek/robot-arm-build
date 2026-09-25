import pytest
from rocell.application.servo_register_reference import PROFILE_ID
from rocell.application.servo_acquisition_pair import assess_acquisition_pair


@pytest.fixture
def pair():
    def record(address,width,start,sequence):
        return dict(boot_id='boot',command_id='cmd',servo_id=3,sequence=sequence,
            read_started_us=start,read_finished_us=start+10,address=address,width=width,
            status='SUCCEEDED',device_error=0,raw_hex=(bytes(width)).hex())
    result=dict(schema='rocell.servo_acquisition_pair.v1',profile_id=PROFILE_ID,byte_order='little',
        target=record(42,2,120,4),feedback=record(56,15,140,5))
    result['feedback']['raw_hex']=(b'\x01\x80'+bytes(13)).hex()
    return result


def assess(pair,**overrides):
    args=dict(boot_id='boot',command_id='cmd',servo_id=3,dispatch_us=100,
        previous_sequence=3,previous_finished_us=110,maximum_pair_us=50)
    args.update(overrides)
    return assess_acquisition_pair(pair,**args)


def test_separate_intervals_preserve_signed_position(pair):
    result=assess(pair)
    assert result['pair_span_us']==30 and result['last_sequence']==5
    assert result['decoded']['feedback']['position']['decoded_value']==-1
    assert result['decoded']['target']['raw_unsigned']==0
    assert not result['simultaneous'] and not result['progression_authority']


@pytest.mark.parametrize('field,value',[
    ('boot_id','reboot'),('command_id','other'),('servo_id',4),('sequence',3),
    ('read_started_us',100),('read_finished_us',130),('address',33),('width',14),
    ('device_error',1),('raw_hex','00'),('status','cached')])
def test_invalid_feedback_rejected(pair,field,value):
    pair['feedback'][field]=value
    with pytest.raises(ValueError):assess(pair)


def test_profile_mismatch_rejected(pair):
    pair['profile_id']='other'
    with pytest.raises(ValueError):assess(pair)


def test_stale_pair_rejected(pair):
    with pytest.raises(ValueError):assess(pair,maximum_pair_us=20)


def test_overlap_rejected(pair):
    pair['feedback']['read_started_us']=125
    with pytest.raises(ValueError):assess(pair)


def test_equal_adjacent_boundaries_preserve_command_freshness(pair):
    pair['feedback']['read_started_us']=pair['target']['read_finished_us']
    assert assess(pair,previous_finished_us=120)['status']=='REFERENCE_READ_PAIR_COMPLETE'
    with pytest.raises(ValueError):assess(pair,dispatch_us=120)
    with pytest.raises(ValueError):assess(pair,previous_finished_us=121)


def test_failed_read_remains_unknown(pair):
    pair['feedback'].update(status='FAILED',device_error=None,raw_hex=None)
    result=assess(pair)
    assert result['status']=='READ_PAIR_INCOMPLETE'
    assert result['decoded']['feedback']['position']['decoded_value'] is None


def test_failed_read_with_old_bytes_rejected(pair):
    pair['feedback']['status']='FAILED'
    with pytest.raises(ValueError):assess(pair)


def test_opposite_read_order_supported_if_sequential(pair):
    pair['target'].update(read_started_us=160,read_finished_us=170,sequence=6)
    assert assess(pair)['read_order']==['feedback','target']
