from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest
from rocell.application.p4_endpoint_prediction import TRAIN,TEST,GOALS,load_session,fit_table,evaluate

EXPORTS=Path(__file__).resolve().parents[2]/'runs/wizard-exports'

@pytest.fixture(scope='module')
def sessions():return load_session(EXPORTS,TRAIN),load_session(EXPORTS,TEST)

def test_retained_split_predictions(sessions):
    train,test=sessions;table=fit_table(train);result=evaluate(table,test)
    assert table.cells==((1915,-1,3,4,0),(1947,-1,3,2,0),(1947,1,0,2,0),(1980,1,-2,4,2))
    assert result['table_mae_counts']==pytest.approx(1/3)
    assert result['table_max_error_counts']==1
    assert result['goal_only_mae_counts']==2.5
    with pytest.raises(FrozenInstanceError):table.training_boot='changed'

@pytest.mark.parametrize('goal,direction',[(1916,-1),(1915,1),(1980,-1),(4096,1),(1947,0)])
def test_unseen_scope_rejected(sessions,goal,direction):
    with pytest.raises(ValueError):fit_table(sessions[0]).predict(goal,direction)

def test_scope_and_leakage_rejected(sessions):
    train,test=sessions;table=fit_table(train)
    with pytest.raises(ValueError):evaluate(table,train)
    with pytest.raises(ValueError):evaluate(table,test[:-1])
    with pytest.raises(ValueError):evaluate(table,list(reversed(test)))
    with pytest.raises(ValueError):fit_table(train[:-1])
    with pytest.raises(ValueError):table.predict(1947,1,speed=30)
    changed=list(GOALS);changed[3]+=1
    with pytest.raises(ValueError):table.predict(1947,1,passive_goals=changed)

def test_evaluation_cannot_refit_table(sessions):
    train,test=sessions;table=fit_table(train);original=table.cells
    altered=[dict(r,final_positions=[*r['final_positions'][:4],r['final_positions'][4]+1,*r['final_positions'][5:]]) for r in test]
    evaluate(table,altered)
    assert table.cells==original
