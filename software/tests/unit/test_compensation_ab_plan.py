import pytest
from test_shoulder_repeatability_plan import frozen
from test_stateful_pair_compensation import inputs
from rocell.application.stateful_pair_compensation import propose
from rocell.application.compensation_ab_plan import draft_comparison, compare_endpoints


def test_identical_conditioning_separate_terminal_trials():
    plan=draft_comparison(propose(frozen(),**inputs()),[[0,4095]]*7)
    a,b=plan['campaigns']
    assert a['manifest']['goals']==[[2377,1737],[2389,1725],[2387,1727]]
    assert b['manifest']['goals']==[[2377,1737],[2389,1725],[2378,1736]]
    assert plan['maximum_total_writes']==6 and not plan['movement_authorized']
    assert not a['automatic_return'] and not b['automatic_return']


def test_out_of_range_conditioning_rejected():
    p=propose(frozen(),**inputs());p['tested_primary_range']=[2378,2389]
    with pytest.raises(ValueError,match='empirical'):draft_comparison(p,[[0,4095]]*7)


@pytest.mark.parametrize('start,matched',[((2391,1724),True),((2392,1724),True),((2393,1724),False)])
def test_score_does_not_hide_mismatched_start_or_claim_validation(start,matched):
    score=compare_endpoints(control_before=(2391,1724),compensated_before=start,
        control_end=(2391,1724),compensated_end=(2388,1729),desired=(2388,1729))
    assert score['starts_match_within_one_count'] is matched
    assert score['maximum_absolute_errors']=={'control':5,'compensated':0}
    assert not score['compensation_validated']
