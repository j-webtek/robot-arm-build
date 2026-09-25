import pytest
from rocell.arm.command_strategy_simulation import run,compare


def test_fixed_offset_requires_correction_in_command_space():
    direct=run('toward_desired_setpoint','fixed_offset')
    incremental=run('previous_setpoint_plus_error','fixed_offset')
    assert direct['reason']=='NO_USEFUL_PROGRESS'
    assert direct['attempts'][0]['command_delta_deg']>0
    assert incremental['attempts'][0]['command_delta_deg']<0
    assert incremental['reason']=='IN_BAND'
    assert len(incremental['attempts'])==2


def test_quantization_and_deadband_are_not_guaranteed_convergence():
    assert run('previous_setpoint_plus_error','quantized_offset')['reason']=='IN_BAND'
    assert run('previous_setpoint_plus_error','deadband')['reason']=='NO_USEFUL_PROGRESS'
    assert run('previous_setpoint_plus_error','changing_offset')['reason']=='EXCURSION'


def test_all_scenarios_bounded_and_non_authoritative():
    for record in compare():
        assert len(record['attempts'])<=3
        assert record['cumulative_command_change_deg']<=.30+1e-12
        assert all(abs(a['command_delta_deg'])<=.1 for a in record['attempts'])
        assert not record['motion_authorized'] and not record['model_fitted']


def test_unknown_hypothesis_rejected():
    with pytest.raises(ValueError):run('automatic','hardware')
