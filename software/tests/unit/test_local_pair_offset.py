import pytest
from rocell.application.local_pair_offset import LocalPairOffset


def model():return LocalPairOffset('r29',(2419,1695),(2429,1688))


def test_frozen_offset_predicts_separate_r31_observation():
    result=model().evaluate(evidence_id='r31',goals=[2405,1709],actual=[2414,1702])
    assert result['predicted']==[2415,1702]
    assert result['signed_error']==[-1,0]
    assert not result['live_validated']


def test_projected_proposal_preserves_goal_sum():
    result=model().propose(current_positions=[2414,1702],current_goals=[2405,1709],desired=[2400,1716])
    assert result['proposed_goals']==[2391,1723]
    assert result['predicted_positions']==[2401,1716]
    assert result['goal_sum']==4114
    assert result['movement_authorized'] is False


@pytest.mark.parametrize('goals',[[2405,1710],[2300,1814],[True,1695],[1.0,2],[4096,0]])
def test_reject_invalid_or_outside_neighborhood(goals):
    with pytest.raises(ValueError):model().predict(goals)


@pytest.mark.parametrize('desired',[[2420,1700],[2370,1746],[2400,1726],[2400,1703]])
def test_reject_reverse_large_or_incompatible_desired_pair(desired):
    with pytest.raises(ValueError):model().propose(current_positions=[2414,1702],current_goals=[2405,1709],desired=desired)


def test_no_self_evaluation_or_unbounded_offset():
    with pytest.raises(ValueError):model().evaluate(evidence_id='r29',goals=[2405,1709],actual=[2414,1702])
    with pytest.raises(ValueError):LocalPairOffset('bad',[2419,1695],[2450,1660])


def test_changed_residual_rejects_proposal():
    with pytest.raises(ValueError,match='contradicts'):
        model().propose(current_positions=[2420,1702],current_goals=[2405,1709],desired=[2406,1716])
