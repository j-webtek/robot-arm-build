import pytest
from rocell.application.servo_register_reference import decode_register,decode_feedback_block


@pytest.mark.parametrize('field,raw,expected',[
    ('position',0,0),('position',4095,4095),('position',0x8001,-1),
    ('speed',0x8002,-2),('current',0xffff,-32767),('load',0x0401,-1),
    ('load',0x03ff,1023),('position',0x8000,0),('goal_position',0x8001,0x8001)])
def test_reference_signedness(field,raw,expected):
    result=decode_register(field,raw,read_status='SUCCEEDED')
    assert result['decoded_value']==expected and result['raw_unsigned']==raw
    assert not result['installed_compatibility_verified']


def test_negative_one_value_is_not_read_failure():
    assert decode_register('position',0x8001,read_status='SUCCEEDED')['decoded_value']==-1
    assert decode_register('position',None,read_status='FAILED')['decoded_value'] is None


@pytest.mark.parametrize('raw',[-1,65536,True,1.5,None])
def test_invalid_word_rejected(raw):
    with pytest.raises(ValueError):decode_register('position',raw,read_status='SUCCEEDED')


def test_failed_read_cannot_reuse_cached_word():
    with pytest.raises(ValueError):decode_register('position',2000,read_status='FAILED')


@pytest.mark.parametrize('order',['little','big'])
def test_feedback_block_fields_and_out_of_range_exclusion(order):
    raw=bytearray(15);raw[0:2]=(0x8001).to_bytes(2,order)
    raw[4:6]=(0x0402).to_bytes(2,order);raw[13:15]=(0x8003).to_bytes(2,order)
    result=decode_feedback_block(bytes(raw),read_status='SUCCEEDED',byte_order=order)
    assert result['position']['decoded_value']==-1
    assert result['load']['decoded_value']==-2
    assert result['current']['decoded_value']==-3
    assert 'mode' not in result and 'goal_position' not in result


@pytest.mark.parametrize('size',[0,14,16])
def test_short_or_long_block_is_not_success(size):
    with pytest.raises(ValueError):decode_feedback_block(bytes(size),read_status='SUCCEEDED',byte_order='little')


def test_failed_block_yields_unknowns_not_zeroes():
    result=decode_feedback_block(None,read_status='FAILED',byte_order='little')
    assert all(x['decoded_value'] is None for x in result.values())
