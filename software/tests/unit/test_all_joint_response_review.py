from copy import deepcopy
import pytest
from rocell.application.all_joint_response_review import review_all_joint_response
from rocell.providers.windows.arm_wifi_feedback import probe,MAC
from rocell.kinematics.firmware_reference import forward
from rocell.arm.all_joint_command import all_joint_command
from test_arm_wifi_feedback import Connection


@pytest.fixture
def evidence():
    start=[.001533981,.033747577,1.744136156,-.065961174,.018407769,3.138524692]
    target=list(start);target[2]+=.003;target[3]-=.003
    final=list(start);final[2]=1.753340041
    def sample(q,time):
        fields=dict(zip(('b','s','e','t','r','g'),q))
        fields.update(zip(('x','y','z','tit'),forward(*q[:4])))
        return probe(identity=lambda:MAC,clock=lambda:time,retain_response=True,
            connection_factory=lambda *a,**k:Connection(dict(T=1051,**fields)))
    trial=dict(command_send_attempted=True,transaction=dict(baseline=sample(start,10),
        command=all_joint_command(target,speed=20,acceleration=1),dispatch_s=10.1))
    observation=dict(status='SUCCEEDED',samples=[sample(final,t) for t in (12,13,14)])
    return trial,observation


def test_reference_counts_distinguish_rounding_and_response(evidence):
    result=review_all_joint_response(*evidence)
    rows={r['joint']:r for r in result['joint_comparisons']}
    assert rows['e']['predicted_count_change']==2
    assert rows['e']['reported_count_change']==6
    assert rows['e']['count_error']==4
    assert rows['t']['predicted_count_change']==-3
    assert rows['t']['reported_count_change']==0
    assert rows['b']['predicted_count_change']==-1
    assert not result['rounding_alone_matches_reference_counts']
    assert not result['trajectory_verified'] and not result['compensation_generated']


@pytest.mark.parametrize('fault',['hash','order','identity','not_sent','wrong_command'])
def test_inadequate_evidence_rejected(evidence,fault):
    trial,observation=deepcopy(evidence)
    if fault=='hash':observation['samples'][0]['response_sha256']='bad'
    elif fault=='order':trial['transaction']['dispatch_s']=20
    elif fault=='identity':observation['samples'][0]['identity_after_matched']=False
    elif fault=='not_sent':trial['command_send_attempted']=False
    else:trial['transaction']['command']['T']=104
    with pytest.raises(ValueError):review_all_joint_response(trial,observation)
