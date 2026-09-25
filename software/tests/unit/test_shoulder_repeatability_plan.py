from copy import deepcopy
import pytest
from rocell.application.shoulder_repeatability_plan import freeze_models, draft_repeatability, predict


def frozen():
    return freeze_models(dict(schema='rocell.matrix_model_review.v1',constant_residual=[6.5,-13/3],
        directional_residual={-1:[29/3,-7],1:[10/3,-5/3]},bands=[[2,29/3],[-7,-1]]))


def test_six_legs_and_predicted_clear_return():
    plan=draft_repeatability((2389,1725),(2391,1724),[[0,4095]]*7,frozen())
    assert plan['manifest']['goals']==[[2377,1737],[2389,1725]]*3
    for index,leg in enumerate(plan['legs']):
        prediction=leg['simulated_rollouts']['stateful_band']
        assert prediction['predicted_endpoint']==pytest.approx([2386+2/3,1730] if index%2==0 else [2391,1724])
        assert all(abs(d)>=2 for d in prediction['predicted_delta'])
    assert not plan['movement_authorized'] and not plan['compensation_enabled']


def test_frozen_parameters_are_copied_and_tampering_rejected():
    model=frozen();plan=draft_repeatability((2389,1725),(2391,1724),[[0,4095]]*7,model)
    model['parameters']['constant'][0]=8
    assert plan['frozen_models']['parameters']['constant'][0]==6.5
    with pytest.raises(ValueError,match='changed'):
        predict(model,target=(2377,1737),before=(2391,1724),direction=-1)


@pytest.mark.parametrize('failure',['anchor','target','coupling','bounds'])
def test_rejects_invalid_proposal(failure):
    goals=(2389,1725);positions=(2391,1724);bounds=[[0,4095] for _ in range(7)]
    if failure=='anchor':positions=(2450,1724)
    if failure=='target':bounds[1]=[2380,2400]
    if failure=='coupling':goals=(2389,1726)
    if failure=='bounds':bounds[2]=[1725,1740]
    with pytest.raises(ValueError):draft_repeatability(goals,positions,bounds,frozen())


def test_measured_start_changes_stateful_prediction_without_refitting():
    model=frozen();saved=deepcopy(model)
    a=predict(model,target=(2389,1725),before=(2395,1722),direction=1)
    b=predict(model,target=(2389,1725),before=(2386,1730),direction=1)
    assert a['stateful_band']!=b['stateful_band']
    assert a['constant']==b['constant'] and model==saved
