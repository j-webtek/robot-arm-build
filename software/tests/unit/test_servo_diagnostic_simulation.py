import json
import pytest
from rocell.application.servo_diagnostic_simulation import simulate_trace,SCENARIOS
from rocell.application.servo_diagnostic_decode import decode_trace


@pytest.mark.parametrize('scenario',SCENARIOS)
def test_scenarios_through_actual_decoder(scenario):
    raw=json.dumps(simulate_trace(scenario)).encode()
    if scenario in ('reboot','stale_sequence','paired_stale_read'):
        with pytest.raises(ValueError):decode_trace(raw)
        return
    result=decode_trace(raw)['assessment']
    expected=('DIAGNOSTIC_ENDPOINT_CRITERIA_MET' if scenario in ('arrival','delayed_arrival','paired_arrival') else
        'BUS_DISPATCH_NOT_VERIFIED' if scenario=='bus_failure' else
        'FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET' if scenario in ('stationary','paired_negative_position') else
        'DIAGNOSTIC_EVIDENCE_INCOMPLETE_OR_CONTRADICTORY')
    assert result['category']==expected
    assert result['origin']=='SIMULATION'
    assert not result['progression_authority']


def test_simulations_are_independent_and_deterministic():
    a=simulate_trace('arrival');b=simulate_trace('arrival')
    assert a==b
    a['samples'][0]['position_count']=0
    assert b['samples'][0]['position_count']==2100


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):simulate_trace('native')
