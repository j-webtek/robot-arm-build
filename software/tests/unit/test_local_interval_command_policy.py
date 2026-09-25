import pytest

from rocell.application.local_interval_command_policy import (
    derive_interval_command_policy,resolve_interval_endpoint)


def endpoint_policy():
    def rule(desired,command,expected):
        return {'desired_positions':desired,'required_current_goals':[2377,1737],
                'required_current_positions':{'minimum':[2385,1730],
                                              'maximum':[2386,1730]},
                'command_goals':command,'expected_positions':expected,
                'maximum_observed_error_counts':1}
    return {'schema':'rocell.local_pair_endpoint_policy.v1',
        'fine_endpoint_lookup_validated':True,'local_interpolation_validated':False,
        'movement_authorized':False,'rules':{
            '2387,1727':rule([2387,1727],[2385,1729],[2387,1728]),
            '2389,1725':rule([2389,1725],[2388,1726],[2389,1725])}}


def interval_model():
    return {'schema':'rocell.local_interval_model.v1',
        'local_interval_interpolation_validated':False,'movement_authorized':False,
        'centers':[
            {'command_goals':[2385,1729],'observed_position_center':[2387,1728]},
            {'command_goals':[2389,1725],'observed_position_center':[2391,1724]}],
        'validated_subinterval':{'minimum_command':2385,'maximum_command':2389,
            'training_commands':[2385,2389],'heldout_commands':[2388],
            'training_monotonic':True,'interpolation_validated':True,
            'extrapolation_allowed':False,'heldout_maximum_paired_error_counts':1.,
            'heldout_p95_paired_error_counts':1.}}


def policy():
    return derive_interval_command_policy(endpoint_policy(),interval_model(),
                                          model_export='r51-model')


def test_interpolated_upper_endpoints_resolve_from_conditioned_plateau():
    result=resolve_interval_endpoint(policy(),current_goals=[2377,1737],
        current_positions=[2385,1730],desired_positions=[2390,1725])
    assert result['resolution_mode']=='UPPER_INTERVAL_INTERPOLATION'
    assert result['command_goals']==[2388,1726]
    assert result['expected_positions']==[2390,1725]
    assert result['maximum_observed_error_counts']==1
    assert result['movement_authorized'] is False


def test_existing_discrete_endpoint_is_preserved():
    result=resolve_interval_endpoint(policy(),current_goals=[2377,1737],
        current_positions=[2386,1730],desired_positions=[2389,1725])
    assert result['resolution_mode']=='DISCRETE_VALIDATED_ENDPOINT'
    assert result['command_goals']==[2388,1726]


@pytest.mark.parametrize('goals,positions,desired',[
    ([2389,1725],[2385,1730],[2390,1725]),
    ([2377,1737],[2387,1728],[2390,1725]),
    ([2377,1737],[2385,1730],[2386,1729]),
    ([2377,1737],[2385,1730],[2392,1723]),
    ([2377,1737],[2385,1730],[2390,1724]),
])
def test_interpolation_rejects_wrong_start_extrapolation_or_off_manifold(
        goals,positions,desired):
    with pytest.raises(ValueError):
        resolve_interval_endpoint(policy(),current_goals=goals,
            current_positions=positions,desired_positions=desired)


def test_policy_rejects_unvalidated_or_relaxed_model():
    model=interval_model();model['validated_subinterval']['interpolation_validated']=False
    with pytest.raises(ValueError):
        derive_interval_command_policy(endpoint_policy(),model,model_export='bad')
