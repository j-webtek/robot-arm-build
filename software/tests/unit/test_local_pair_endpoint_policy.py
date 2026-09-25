import pytest

from rocell.application.local_pair_endpoint_policy import derive_endpoint_policy,resolve_endpoint


@pytest.fixture
def anchor():
    return {'schema':'rocell.local_pair_plateau_policy.v1',
        'encoder_anchor_navigation_validated':True,'heldout':{'passed':True},
        'training_export':'r49','heldout_export':'r48','rules':{
            'lower':{'command_goals':[2377,1737],
                     'expected_positions':{'minimum':[2385,1730],'maximum':[2386,1730]}}}}


@pytest.fixture
def analysis():
    def entry(desired,command,actual,error):
        return {'desired_positions':desired,'command_goals':command,
                'observed_positions':[actual,actual],
                'candidate_errors_counts':[error,error],'validated':True}
    return {'schema':'rocell.fine_pair_lookup_analysis.v1',
        'fine_endpoint_lookup_validated':True,'movement_authorized':False,
        'entries':[entry([2387,1727],[2385,1729],[2387,1728],1),
                   entry([2389,1725],[2388,1726],[2389,1725],0)]}


def test_two_discrete_lookups_resolve_only_from_lower_plateau(anchor,analysis):
    policy=derive_endpoint_policy(anchor,analysis,lookup_analysis_export='r50')
    first=resolve_endpoint(policy,current_goals=[2377,1737],
        current_positions=[2385,1730],desired_positions=[2387,1727])
    second=resolve_endpoint(policy,current_goals=[2377,1737],
        current_positions=[2386,1730],desired_positions=[2389,1725])
    assert first['command_goals']==[2385,1729]
    assert first['expected_positions']==[2387,1728]
    assert second['command_goals']==[2388,1726]
    assert second['maximum_observed_error_counts']==0
    assert first['movement_authorized'] is second['movement_authorized'] is False


@pytest.mark.parametrize('goals,positions,desired',[
    ([2389,1725],[2385,1730],[2387,1727]),
    ([2377,1737],[2387,1728],[2387,1727]),
    ([2377,1737],[2385,1730],[2388,1726]),
])
def test_unvalidated_start_or_interpolation_is_rejected(anchor,analysis,goals,positions,desired):
    policy=derive_endpoint_policy(anchor,analysis,lookup_analysis_export='r50')
    with pytest.raises(ValueError):
        resolve_endpoint(policy,current_goals=goals,current_positions=positions,
                         desired_positions=desired)
