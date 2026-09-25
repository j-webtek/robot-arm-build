import math
from copy import deepcopy
import pytest
from rocell.application.base_endpoint_dataset import build_base_dataset,fit_local_base_lines,predict_unseen_base_target
from test_model_corrected_native_campaign import install
from test_campaign_stream_sync import sync_body
from test_positional_campaign_native_export import bundle


def test_dataset_extracts_portable_six_joint_originals(tmp_path,monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',sync_body)
    path,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\r\n',missed_leg=1)
    from rocell.application.positional_campaign_native_export import verify_native_retained_export
    v=verify_native_retained_export(path,name)
    selection=dict(directory=path,report_name=name,report_sha256=v['report_sha256'])
    d=build_base_dataset([selection]);r=d['rows'][0]
    assert len(r['start_joints_rad'])==len(r['final_joints_rad'])==6
    assert r['status']=='NO_RESPONSE' and not r['endpoint_verified']
    assert not d['motion_authorized']
    with pytest.raises(ValueError):build_base_dataset([selection,selection])
    with pytest.raises(ValueError):build_base_dataset([dict(selection,report_sha256='f'*64)])


def data():
    rows=[]
    for direction in ('INCREASING','DECREASING'):
        for target in (1.,2.):
            for repeat in range(2):
                start=0. if direction=='INCREASING' else 3.
                rows.append(dict(campaign_id=f'{direction}-{target}-{repeat}',
                    context={'fixture':'only'},command_rad=math.radians(target),
                    final_joints_rad=[math.radians(.5*target+.25),0,0,0,0,0],
                    start_joints_rad=[math.radians(start),0,0,0,0,0],
                    direction=direction,spd=20,acc=1,capture_profile='fixture'))
    return dict(rows=rows)


def test_repeat_groups_are_anchors_not_held_out_validation():
    model=fit_local_base_lines(data())
    assert model['held_out_target_count']==0 and not model['validated']
    assert all(len(m['anchors'])==2 for m in model['models'])
    p=predict_unseen_base_target(model,target_rad=math.radians(1.5),start_joints_rad=[0.]*6)
    assert math.degrees(p['predicted_final_rad'])==pytest.approx(1)
    assert math.degrees(p['nearest_anchor_final_rad'])==pytest.approx(.75)
    assert math.degrees(p['nearest_anchor_command_rad'])==pytest.approx(1)
    assert not p['motion_authorized'] and not p['validation_completed']


@pytest.mark.parametrize('target',[.9,1,2,2.1])
def test_seen_targets_and_extrapolation_rejected(target):
    with pytest.raises(ValueError):predict_unseen_base_target(fit_local_base_lines(data()),target_rad=math.radians(target),start_joints_rad=[0.]*6)


@pytest.mark.parametrize('fault',['context','pose','repeat','duplicate','speed'])
def test_mixed_or_insufficient_training_context_rejected(fault):
    d=data()
    if fault=='context':d['rows'][0]['context']={'different':True}
    if fault=='pose':d['rows'][0]['start_joints_rad'][2]=math.radians(1)
    if fault=='repeat':d['rows'].pop(0)
    if fault=='duplicate':d['rows'][0]['campaign_id']=d['rows'][1]['campaign_id']
    if fault=='speed':d['rows'][0]['spd']=30
    with pytest.raises(ValueError):fit_local_base_lines(d)


def test_prediction_rejects_unseen_start_and_opposite_response():
    model=fit_local_base_lines(data())
    with pytest.raises(ValueError):predict_unseen_base_target(model,target_rad=math.radians(1.5),start_joints_rad=[math.radians(.1),0,0,0,0,0])
    bad=deepcopy(model);bad['models'][0]['intercept_rad']=-10
    with pytest.raises(ValueError):predict_unseen_base_target(bad,target_rad=math.radians(1.5),start_joints_rad=[0.]*6)
