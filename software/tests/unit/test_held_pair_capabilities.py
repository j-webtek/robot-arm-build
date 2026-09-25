import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_capabilities import read_pair_capabilities,validate_pair_capabilities,PATH
from test_servo_diagnostic_http import server,response


def fixture():
    return dict(schema='rocell.held_pair_capabilities.v1',boot_id='11'*16,
        protocol='hold-first-pair-v1',servo_id=14,max_offset_counts=16,
        free_internal_heap_bytes=120000,minimum_free_internal_heap_bytes=110000,
        largest_internal_block_bytes=100000,stack_measured=False,physical_accuracy_verified=False)


def test_read_only_capabilities():
    with server([response(canonical(fixture()))]) as (port,requests):
        result=read_pair_capabilities(address='127.0.0.1',port=port,expected_boot='11'*16)
    assert len(requests)==1 and requests[0].startswith(f'GET {PATH} HTTP/1.0'.encode())
    assert result['capabilities']['free_internal_heap_bytes']==120000
    assert not result['resource_sufficiency_verified'] and not result['firmware_identity_verified']


@pytest.mark.parametrize('change',[{'boot_id':'22'*16},{'protocol':'legacy'},{'servo_id':True},
    {'largest_internal_block_bytes':-1},{'stack_measured':True},{'unknown':0}])
def test_bad_capabilities(change):
    value=fixture();value.update(change)
    with pytest.raises(ValueError):validate_pair_capabilities(canonical(value),expected_boot='11'*16)
