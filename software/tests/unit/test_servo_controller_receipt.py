import pytest
from rocell.application.servo_controller_receipt import assess_controller_receipt


def fixture():
    raw=b'{"T":101,"joint":3,"rad":1.7,"spd":20,"acc":1}'
    receipt=dict(schema='rocell.controller_receipt.v1',boot_id='boot',command_id='command',
        received_us=1000,payload_utf8=raw.decode(),joint=3,received_rad=1.7,
        received_rad_text='1.7000000476837158',speed=20,acceleration=1)
    dispatch=dict(boot_id='boot',command_id='command',servo_id=14,device_us=1002,speed=20,acceleration=1)
    return receipt,raw,dispatch


def test_exact_receipt_reports_parser_delta_without_compensating():
    result=assess_controller_receipt(*fixture())
    assert result['exact_payload_match'] and result['parser_delta_rad']>0
    assert not result['progression_authority']


@pytest.mark.parametrize('field,value',[
    ('payload_utf8','{}'),('command_id','other'),('boot_id','other'),('received_us',1003),
    ('received_us',True),('joint',4),('speed',21),('acceleration',2),
    ('received_rad_text','nan'),('received_rad_text','2.0'),('received_rad',True)])
def test_rejects_contradictions(field,value):
    receipt,raw,dispatch=fixture();receipt[field]=value
    with pytest.raises(ValueError):assess_controller_receipt(receipt,raw,dispatch)
