import copy
import pytest
from rocell.application import local_wrist_response_map as module


@pytest.fixture
def reports(monkeypatch):
    monkeypatch.setattr(module,'review_coordinated_trace',lambda _:dict(
        feedback_failures=[],joints=[{},{},{},dict(unchanged_tail_s=8)]))
    result=[]
    for command,reported in ((-.045917158220085054,-.052155347),(-.053761811220085054,-.056757289)):
        start=[.001533981,.033747577,1.67357304,-.072097097,.018407769,3.138524692]
        final=list(start);final[3]=reported
        result.append(dict(run=dict(error=None,acknowledgment_received=True,transaction=dict(
            command=dict(T=101,joint=4,rad=command,spd=20,acc=1),
            baseline_joints=start,rows=[[1,2,None,final]]))))
    return result


def test_inverse_interpolation_and_order(reports):
    m=module.fit_local_map(reports)
    assert m==module.fit_local_map(list(reversed(reports)))
    command=module.predict_command(m,-.055)
    assert -.053761811220085054<command<-.045917158220085054
    assert command*m['response_slope']+m['response_intercept']==pytest.approx(-.055)
    assert not m['held_out_validated']


@pytest.mark.parametrize('desired',[-.060,-.050,-.052155347,float('nan'),True])
def test_no_extrapolation_or_training_endpoint(reports,desired):
    with pytest.raises(ValueError):module.predict_command(module.fit_local_map(reports),desired)


@pytest.mark.parametrize('fault',['start','speed','direction','other_joint','duplicate','error'])
def test_incompatible_evidence_rejected(reports,fault):
    tx=reports[1]['run']['transaction']
    if fault=='start':tx['baseline_joints'][3]+=.001
    if fault=='speed':tx['command']['spd']=30
    if fault=='direction':tx['rows'][-1][3][3]=-.08
    if fault=='other_joint':tx['rows'][-1][3][2]+=.001
    if fault=='duplicate':reports[1]=copy.deepcopy(reports[0])
    if fault=='error':reports[1]['run']['error']='UNCERTAIN'
    with pytest.raises(ValueError):module.fit_local_map(reports)


def test_changed_map_rejected(reports):
    m=module.fit_local_map(reports);m['response_slope']=1
    with pytest.raises(ValueError):module.predict_command(m,-.055)
