from copy import deepcopy
import pytest
from test_shoulder_repeatability_plan import frozen
from rocell.application.stateful_pair_compensation import propose


def inputs():
    return dict(current_goals=(2389,1725),current_positions=(2391,1724),desired=(2388,1729),
        bounds=[[0,4095],[0,4095]],tested_primary_range=(2377,2389),campaign_anchor=(2391,1724))


def test_coupled_interpolated_command_improves_model_prediction_only():
    result=propose(frozen(),**inputs())
    assert result['proposed_goals']==[2378,1736]
    assert sum(result['proposed_goals'])==4114
    assert result['predicted_error']==pytest.approx([-1/3,0])
    assert max(map(abs,result['predicted_error']))<max(map(abs,result['uncompensated_predicted_error']))
    assert not result['movement_authorized'] and result['candidate_count']<=48


def test_reverse_proposal_from_a_measured_example():
    args=inputs();args.update(current_goals=(2377,1737),current_positions=(2386,1730),desired=(2391,1724))
    result=propose(frozen(),**args)
    assert result['proposed_goals']==[2389,1725]
    assert result['predicted_error']==[0,0]


@pytest.mark.parametrize('case',['coupling','unreachable','direction','bounds','envelope','inconsistent','model'])
def test_rejects_unsupported_proposals(case):
    args=inputs();model=frozen()
    if case=='coupling':args['current_goals']=(2389,1726)
    if case=='unreachable':args['desired']=(2370,1745)
    if case=='direction':args['desired']=(2395,1730)
    if case=='bounds':args['bounds']=[[2390,2400],[1700,1740]]
    if case=='envelope':args['campaign_anchor']=(2300,1724)
    if case=='inconsistent':args['current_positions']=(2405,1718)
    if case=='model':model['parameters']['bands'][0][1]=12
    with pytest.raises(ValueError):propose(model,**args)


def test_deterministic_no_parameter_mutation():
    model=frozen();original=deepcopy(model)
    assert propose(model,**inputs())==propose(model,**inputs())
    assert model==original
