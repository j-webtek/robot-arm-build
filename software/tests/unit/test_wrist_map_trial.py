import pytest
from test_post_tip_elbow import source
from test_local_wrist_response_map import reports
from rocell.application import wrist_map_trial as module
from rocell.application.local_wrist_response_map import fit_local_map
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


@pytest.mark.parametrize('preparation',[True,False])
def test_mapping_leg_is_scoped_and_separates_endpoints(reports,monkeypatch,preparation):
    model=fit_local_map(reports)
    monkeypatch.setattr(module,'_read',lambda *args:({'model':model},'hash'))
    b=source();b['joints_rad']['t']=-.056757289 if preparation else -.072097097
    joints=list(b['joints_rad'].values())
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*joints[:4])))
    p=module.preview_map_trial(b,preparation=preparation)
    assert p['hypothetical_tip_sweep_mm']<6
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='map-prepare' if preparation else 'map-held-out',wrist_candidate=True,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['rad']==p['local_candidate']['command_rad']
    tx.acknowledge(3)
    desired=list(joints);desired[3]=p['local_candidate']['desired_rad']
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,forward(*desired[:4]),desired),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    with pytest.raises(ValueError):module.preview_map_trial(source(),preparation=preparation)


def test_no_wire_only_admission():
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=source(),baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            wrist_probe='map-prepare')


def test_transfer_is_explicit_unchanged_model_and_exact_start(reports,monkeypatch):
    model=fit_local_map(reports)
    monkeypatch.setattr(module,'_read',lambda *args:({'model':model},'hash'))
    b=source();b['joints_rad'].update(e=1.691980809,t=-.075165059)
    joints=list(b['joints_rad'].values())
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*joints[:4])))
    p=module.preview_map_trial(b,posture_transfer=True)
    c=p['local_candidate']
    assert c['model_id']==model['model_sha256']
    assert c['command_rad']==pytest.approx(-.050766266637881065)
    assert c['desired_rad']==-.055 and not c['held_out_validated']
    assert p['hypothetical_tip_sweep_mm']<6
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='map-transfer',wrist_candidate=True,compensated_endpoint=True)
    assert tx.begin_dispatch(2)==dict(T=101,joint=4,rad=c['command_rad'],spd=20,acc=1)
    tx.acknowledge(3)
    desired=list(joints);desired[3]=c['desired_rad']
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,forward(*desired[:4]),desired),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['observed_hypothetical_tip_displacement_mm']<6
    with pytest.raises(ValueError):module.preview_map_trial(b)
    with pytest.raises(ValueError):module.preview_map_trial(source(),posture_transfer=True)
    with pytest.raises(ValueError):module.preview_map_trial(b,preparation=True,posture_transfer=True)
    b['joints_rad']['t']=-.073631078
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    with pytest.raises(ValueError):module.preview_map_trial(b,posture_transfer=True)
