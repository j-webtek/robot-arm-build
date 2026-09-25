import pytest
from rocell.application.elbow_response_map import build_response_map


def source(identifier,command=1.48,final=1.532,start=1.552):
    joints=[0.,0.,start,.05,.02,3.14]
    end=[*joints]; end[2]=final
    tx=dict(command=dict(T=101,joint=3,rad=command,spd=20,acc=1),
            baseline_joints=joints,dispatch_started_ns=1,command_attempts=1,
            rows=[[i*1_000_000_000,i*1_000_000_000+1,[0,0,0,0],end] for i in range(1,7)])
    return dict(source_export=identifier,source_attachment_sha256='a'*64,
                report=dict(schema='rocell.native_cartesian_trial.v1',status='COMPLETION_DEADLINE_EXCEEDED',run=dict(transaction=tx)))


def test_plateau_without_accuracy_claim():
    result=build_response_map([source('a'),source('b',command=1.479)])
    assert result['pairs'][0]['classification']=='REPORTED_PLATEAU'
    assert result['pairs'][0]['secant_gain']==0
    assert not result['inverse_model_qualified'] and not result['motion_authorized']


@pytest.mark.parametrize('change',['start','speed','other_joint','direction'])
def test_unlike_trials_not_combined(change):
    a=source('a'); b=source('b',command=1.479)
    tx=b['report']['run']['transaction']
    if change=='start': tx['baseline_joints'][2]+=.01
    if change=='speed': tx['command']['spd']=30
    if change=='other_joint': tx['rows'][-1][3][4]+=.01
    if change=='direction': tx['command']['rad']=1.56
    assert build_response_map([a,b])['comparable_pairs']==0


def test_monotonic_and_reversed_response():
    assert build_response_map([source('a'),source('b',command=1.49,final=1.54)])['pairs'][0]['classification']=='MONOTONIC_PAIR'
    assert build_response_map([source('a'),source('b',command=1.49,final=1.52)])['pairs'][0]['classification']=='NONMONOTONIC_PAIR'


def test_duplicate_and_nonfinite_rejected():
    with pytest.raises(ValueError): build_response_map([source('a'),source('a')])
    b=source('b'); b['report']['run']['transaction']['baseline_joints'][0]=float('nan')
    with pytest.raises(ValueError): build_response_map([source('a'),b])
