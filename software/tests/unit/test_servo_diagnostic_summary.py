import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_summary import summarize_trace
from rocell.application.servo_diagnostic_simulation import simulate_trace


def test_compensation_and_wrong_readback_are_separate():
    trace=simulate_trace('wrong_target')
    trace['command']['desired_count']=2099
    summary=summarize_trace(canonical(trace))
    assert (summary['desired_count'],summary['wire_count'],summary['final_target_count'],
        summary['final_position_count'])==(2099,2100,2110,2100)
    assert summary['position_minus_desired']==1
    assert summary['position_minus_wire']==0
    assert summary['position_minus_readback']==-10
    assert summary['stages']['controller_receipt']=='UNAVAILABLE'


def test_final_failed_read_does_not_reuse_earlier_success():
    trace=simulate_trace('paired_arrival')
    trace['samples'][-1]['feedback'].update(status='FAILED',raw_hex=None,device_error=None)
    summary=summarize_trace(canonical(trace))
    assert summary['final_target_count']==2100
    assert summary['final_position_count'] is None
    assert summary['position_minus_wire'] is None
    assert all(value['decoded_value'] is None for value in summary['raw_health'].values())


@pytest.mark.parametrize('scenario',['reboot','paired_stale_read'])
def test_invalid_trace_has_no_summary(scenario):
    assert summarize_trace(canonical(simulate_trace(scenario))) is None


def test_signed_position_and_raw_health_not_calibrated():
    summary=summarize_trace(canonical(simulate_trace('paired_negative_position')))
    assert summary['final_position_count']==-1
    assert summary['raw_health']['voltage']['units']=='RAW_REFERENCE'
    assert summary['torque_enable']=='UNAVAILABLE'
    assert not summary['progression_authority']
