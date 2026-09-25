import copy
import pytest
from test_shoulder_repeatability_plan import frozen
from rocell.application.next_compensation_validation import draft


BOUNDS=[[0,4095] for _ in range(7)]


def test_fixed_repeat_and_reverse_design():
    plan=draft(frozen=frozen(),bounds=BOUNDS,installed_goals=(2378,1736),
               installed_positions=(2387,1730))
    assert plan['forward_repeat']['manifest']['goals']==[
        [2389,1725],[2377,1737],[2389,1725],[2378,1736]]
    assert plan['reverse_candidate']['manifest']['goals'][-1]==[2385,1729]
    assert plan['reverse_control']['manifest']['goals'][-1]==[2386,1728]
    assert plan['execution_order']==['forward_repeat','reverse_candidate','reverse_control']
    assert plan['maximum_total_writes']==10 and not plan['movement_authorized']


@pytest.mark.parametrize('goals,positions',[((2377,1737),(2387,1730)),
    ((2378,1736),(2389,1724)),((2378,1736),(2385,1731))])
def test_requires_retained_r40_terminal(goals,positions):
    with pytest.raises(ValueError,match='r40 terminal'):
        draft(frozen=frozen(),bounds=BOUNDS,installed_goals=goals,
              installed_positions=positions)


def test_model_tamper_rejected():
    models=frozen();models['parameters']['bands'][0][0]+=1
    with pytest.raises(ValueError):
        draft(frozen=models,bounds=BOUNDS,installed_goals=(2378,1736),
              installed_positions=(2387,1730))
