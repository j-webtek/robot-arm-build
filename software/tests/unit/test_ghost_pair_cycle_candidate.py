import pytest

from rocell.application.ghost_pair_cycle_candidate import plan_ghost_pair_cycle
from rocell.application.local_interval_command_policy import derive_interval_command_policy


def policy():
    def rule(desired,command,expected):
        return {'desired_positions':desired,'required_current_goals':[2377,1737],
                'required_current_positions':{'minimum':[2385,1730],
                                              'maximum':[2386,1730]},
                'command_goals':command,'expected_positions':expected,
                'maximum_observed_error_counts':1}
    endpoint={'schema':'rocell.local_pair_endpoint_policy.v1',
        'fine_endpoint_lookup_validated':True,'local_interpolation_validated':False,
        'movement_authorized':False,'rules':{
            '2387,1727':rule([2387,1727],[2385,1729],[2387,1728]),
            '2389,1725':rule([2389,1725],[2388,1726],[2389,1725])}}
    model={'schema':'rocell.local_interval_model.v1',
        'local_interval_interpolation_validated':False,'movement_authorized':False,
        'centers':[
            {'command_goals':[2385,1729],'observed_position_center':[2387,1728]},
            {'command_goals':[2389,1725],'observed_position_center':[2391,1724]}],
        'validated_subinterval':{'minimum_command':2385,'maximum_command':2389,
            'training_commands':[2385,2389],'heldout_commands':[2388],
            'training_monotonic':True,'interpolation_validated':True,
            'extrapolation_allowed':False,'heldout_maximum_paired_error_counts':1.,
            'heldout_p95_paired_error_counts':1.}}
    return derive_interval_command_policy(endpoint,model,
                                          model_export='r51-model')


def test_three_phase_candidate_uses_bounded_interpolated_commands():
    result=plan_ghost_pair_cycle(policy(),current_goals=[2377,1737],
        current_positions=[2385,1730],hover_positions=[2388,1727],
        press_positions=[2390,1725])
    assert [step['phase'] for step in result['steps']]==['HOVER','PRESS','RETRACT']
    assert [step['resolution']['command_goals'] for step in result['steps']]==[
        [2386,1728],[2388,1726],[2386,1728]]
    assert result['transition_deltas']==[[2,-2],[-2,2]]
    assert result['direct_transition_validation_required'] is True
    assert result['movement_authorized'] is False


@pytest.mark.parametrize('hover,press',[
    ([2388,1727],[2388,1727]),
    ([2387,1728],[2391,1724]),
    ([2386,1729],[2390,1725]),
])
def test_same_large_or_out_of_domain_candidate_is_rejected(hover,press):
    with pytest.raises(ValueError):
        plan_ghost_pair_cycle(policy(),current_goals=[2377,1737],
            current_positions=[2385,1730],hover_positions=hover,
            press_positions=press)
