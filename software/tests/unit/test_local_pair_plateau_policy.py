import pytest

from rocell.application.local_pair_plateau_policy import (
    R48_PRIMARY,R49_PRIMARY,derive_plateau_policy,resolve_plateau)


def rows(route,actuals):
    result=[];previous_goal=2381;previous_position=2387
    for leg,(command,actual) in enumerate(zip(route,actuals)):
        result.append({'leg':leg,'target':[command,4114-command],
            'actual':[actual,4114-actual],'approach_direction':1 if command>previous_goal else -1,
            'baseline_positions':[previous_position,4114-previous_position]})
        previous_goal=command;previous_position=actual
    return result


@pytest.fixture
def policy():
    r49=rows(R49_PRIMARY,[2391,2386,2387,2391,2391,2385,2389,2386,2386,2391,2386,2389])
    # Match the retained second-register evidence used by the policy.
    for row,second in zip(r49,[1724,1730,1727,1724,1724,1730,1725,1730,1730,1724,1730,1726]):
        row['actual'][1]=second
    r48=rows(R48_PRIMARY,[2385,2391,2387,2387,2387])
    for row,second in zip(r48,[1731,1724,1728,1727,1728]):row['actual'][1]=second
    return derive_plateau_policy(r49,r48,r49_export='r49',r48_export='r48')


def test_cross_session_anchor_policy_is_scoped_and_heldout(policy):
    assert policy['heldout']['passed'] is True
    assert policy['heldout']['maximum_error_counts']==1
    assert policy['fine_endpoint_lookup_validated'] is False
    assert policy['experimental_fine_endpoint_candidates'][0]['heldout_validated'] is False
    assert policy['movement_authorized'] is False


def test_only_validated_anchor_transitions_resolve(policy):
    lower=resolve_plateau(policy,current_goals=[2389,1725],current_positions=[2391,1724],
                          desired_plateau='lower')
    assert lower['command_goals']==[2377,1737]
    upper=resolve_plateau(policy,current_goals=[2377,1737],current_positions=[2385,1731],
                          desired_plateau='upper')
    assert upper['command_goals']==[2389,1725]
    assert upper['movement_authorized'] is False


@pytest.mark.parametrize('kwargs',[
    {'current_goals':[2388,1726],'current_positions':[2391,1724],'desired_plateau':'lower'},
    {'current_goals':[2389,1725],'current_positions':[2387,1728],'desired_plateau':'lower'},
    {'current_goals':[2389,1725],'current_positions':[2391,1724],'desired_plateau':'middle'}])
def test_unvalidated_or_stale_resolution_is_rejected(policy,kwargs):
    with pytest.raises(ValueError):resolve_plateau(policy,**kwargs)
