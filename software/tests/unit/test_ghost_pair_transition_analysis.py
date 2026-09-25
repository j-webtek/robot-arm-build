import pytest

from rocell.application.ghost_pair_transition_analysis import analyze_ghost_pair_transitions
from rocell.application.ghost_pair_transition_campaign import PRIMARY_ROUTE


def session(*,bad_direction=False,bad_endpoint=False):
    endpoint={2377:[2385,1730],2386:[2388,1727],
              2388:[2390,1725],2389:[2391,1724]}
    rows=[]
    for leg,command in enumerate(PRIMARY_ROUTE):
        actual=list(endpoint[command])
        if bad_direction and leg==2:actual=[2388,1727]
        if bad_endpoint and leg==3:actual=[2391,1724]
        rows.append({'leg':leg,'target':[command,4114-command],
                     'actual':actual,'assessment':{'continuation_eligible':True}})
    return rows


def test_three_complete_sessions_validate_only_encoder_cycle():
    result=analyze_ghost_pair_transitions([session() for _ in range(3)],
                                          source_exports=['a','b','c'])
    assert result['ghost_pair_cycle_validated'] is True
    assert len(result['direct_transitions'])==21
    assert result['movement_authorized'] is False
    assert result['cartesian_accuracy_validated'] is False


@pytest.mark.parametrize('fault',['session','route','direction','endpoint','spread','duplicate'])
def test_transition_faults_do_not_release_cycle(fault):
    sessions=[session() for _ in range(3)];sources=['a','b','c']
    if fault=='session':sessions.pop()
    elif fault=='route':sessions[0][2]['target']=[0,0]
    elif fault=='direction':sessions[0]=session(bad_direction=True)
    elif fault=='endpoint':sessions[0]=session(bad_endpoint=True)
    elif fault=='spread':sessions[0][1]['actual']=[2390,1725]
    else:sources[2]='a'
    if fault in ('session','route','duplicate'):
        with pytest.raises(ValueError):
            analyze_ghost_pair_transitions(sessions,source_exports=sources)
    else:
        result=analyze_ghost_pair_transitions(sessions,source_exports=sources)
        assert result['ghost_pair_cycle_validated'] is False
