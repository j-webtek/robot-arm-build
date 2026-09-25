from rocell.application.local_pair_mapping_analysis import analyze_mapping_rows


def row(leg,command,actual,direction):
    return {'leg':leg,'target':[command,4114-command],'actual':[actual,4114-actual],
            'approach_direction':direction}


def test_analysis_retains_repeatability_and_direction_without_promoting_model():
    result=analyze_mapping_rows([
        {'label':'a','rows':[row(0,2389,2391,1),row(1,2377,2386,-1)]},
        {'label':'b','rows':[row(0,2389,2391,1),row(1,2377,2385,-1)]}])
    assert result['command_response']['2389']['span']==0
    assert result['command_response']['2377']['span']==1
    assert result['endpoint_plateaus']['2391'][0]['command']==2389
    assert result['direction_summary']['1']['residual_mean']==2
    assert result['model_fitted'] is result['compensation_promoted'] is False
    assert result['movement_authorized'] is False


def test_analysis_requires_evidence():
    import pytest
    with pytest.raises(ValueError):analyze_mapping_rows([])
