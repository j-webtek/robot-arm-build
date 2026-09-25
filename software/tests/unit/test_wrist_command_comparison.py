import base64
import hashlib
from copy import deepcopy
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_command_comparison import summarize_wrist_trial
from rocell.application.wrist_command_comparison import summarize_joint_trial


@pytest.fixture
def report():
    q=[0.,0.,1.76,-.065961174,0.,3.14]
    command=dict(T=101,joint=4,rad=-.080,spd=20,acc=1)
    raw=b'{"T":1051,"tT":25}'
    return dict(transaction=dict(schema='rocell.all_joint_transaction.v1',state='FAULT',
        command=command,baseline=dict(joints_rad=dict(zip(('b','s','e','t','r','g'),q))),
        rows=[dict(reported_joints_rad=q)]),receipt=dict(
        payload_sha256=hashlib.sha256(canonical(command)).hexdigest(),
        response_base64=base64.b64encode(raw).decode(),
        response_sha256=hashlib.sha256(raw).hexdigest(),receipt_kind='NUMERIC_FEEDBACK_HTTP_200'))


def test_unchanged_response_is_not_converted_to_success(report):
    result=summarize_wrist_trial(report)
    assert result['original_state']=='FAULT'
    assert result['wrist']['predicted_count_change']==-10
    assert result['wrist']['reported_count_change']==0
    assert not result['comparison_is_matched_start']


def test_legacy_rows_normalized_equivalently(report):
    expected=summarize_wrist_trial(report)
    old=deepcopy(report);tx=old.pop('transaction')
    tx['baseline_joints']=list(tx.pop('baseline')['joints_rad'].values())
    tx['rows']=[[1,2,[0,0,0,0],tx['rows'][0]['reported_joints_rad']]]
    tx['schema']='rocell.cartesian_transaction.v1';old['run']=dict(transaction=tx)
    assert summarize_wrist_trial(old)==expected


@pytest.mark.parametrize('fault',['payload','response','joint','missing_rows'])
def test_invalid_comparison_evidence_rejected(report,fault):
    if fault=='payload':report['receipt']['payload_sha256']='bad'
    elif fault=='response':report['receipt']['response_sha256']='bad'
    elif fault=='joint':report['transaction']['command']['joint']=3
    else:report['transaction']['rows']=[]
    with pytest.raises(ValueError):summarize_wrist_trial(report)


def test_elbow_comparison_uses_elbow_not_wrist(report):
    tx=report['transaction'];tx['command'].update(joint=3,rad=1.7742992981223962)
    tx['baseline']['joints_rad']['e']=1.762543925
    tx['rows'][0]['reported_joints_rad'][2]=1.779417714
    report['receipt']['payload_sha256']=hashlib.sha256(canonical(tx['command'])).hexdigest()
    result=summarize_joint_trial(report,joint=3)
    assert result['elbow']['count_error']==3
    assert result['elbow']['predicted_count_change']==8
    assert result['maximum_other_joint_change_rad']==0
    assert 'wrist' not in result


@pytest.mark.parametrize('joint',[True,2,5,3.0])
def test_joint_scope_is_explicit(report,joint):
    with pytest.raises(ValueError):summarize_joint_trial(report,joint=joint)
