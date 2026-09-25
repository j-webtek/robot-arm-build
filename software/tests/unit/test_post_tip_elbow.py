import pytest
from test_compensated_elbow_native import baseline
from rocell.application.controller_route_preview import preview_elbow_isolation
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def source():
    b=baseline()
    q=[.001533981,.033747577,1.67357304,-.052155347,.018407769,3.138524692]
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),q))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
    return b


def test_isolated_comparison_exact_command_and_arrival():
    b=source();p=preview_elbow_isolation(b,elbow_degrees=-7)
    assert p['status']=='PREVIEW_ONLY_NOT_EXECUTABLE' and p['hypothetical_tip_sweep_mm']<=6
    for s in p['samples']:
        assert all(s['joints_rad'][i]==v for i,v in enumerate(b['joints_rad'].values()) if i!=2)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
                            elbow_only=True,elbow_degrees=-7)
    assert tx.begin_dispatch(2)==dict(T=101,joint=3,rad=1.6579063063032675,spd=20,acc=1)
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['policy']['scope']=='POST_TIP_REVERSE_ELBOW_ISOLATION_V1'


@pytest.mark.parametrize('key',('b','s','e','t','r','g'))
def test_changed_pose_is_held(key):
    b=source();b['joints_rad'][key]+=.001
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
                              elbow_only=True,elbow_degrees=-7)


def test_increasing_diagnostic_is_smaller_separate_and_screened():
    b=source();p=preview_elbow_isolation(b,elbow_degrees=-8)
    assert p['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    assert p['hypothetical_tip_sweep_mm']<=6
    assert p['target_joints_rad'][2]==pytest.approx(1.68557304)
    assert p['target_joints_rad'][2]-b['joints_rad']['e']==pytest.approx(.012)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        elbow_only=True,elbow_degrees=-8)
    assert tx.begin_dispatch(2)==dict(T=101,joint=3,rad=1.68557304,spd=20,acc=1)
    assert tx.snapshot()['policy']['scope']=='POST_TIP_ELBOW_PLUS_0P012_RAD_V1'
    b['joints_rad']['e']+=.001
    assert preview_elbow_isolation(b,elbow_degrees=-8)['status']!='PREVIEW_ONLY_NOT_EXECUTABLE'


def test_retained_overshoot_stops_progression_without_return():
    b=source()
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        elbow_only=True,elbow_degrees=-8)
    tx.begin_dispatch(2);tx.acknowledge(3)
    q=list(b['joints_rad'].values());q[2]=1.691980809
    tx.observe((100,200,forward(*q[:4]),q),200)
    result=tx.snapshot()
    assert result['state']=='OBSERVED_HYPOTHETICAL_TIP_BOUND_EXCEEDED'
    assert result['observed_hypothetical_tip_displacement_mm']==pytest.approx(6.1962844107071575)
    assert len(result['rows'])==1
    assert not result['result']['endpoint_verified']
    assert tx.next_deadline_ns() is None
    with pytest.raises(ValueError):tx.begin_dispatch(201)


def test_post_overshoot_diagnostic_has_sweep_headroom():
    b=source();b['joints_rad']['e']=1.691980809
    q=list(b['joints_rad'].values())
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
    p=preview_elbow_isolation(b,elbow_degrees=-9)
    assert p['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    assert p['hypothetical_tip_sweep_mm']<3
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        elbow_only=True,elbow_degrees=-9)
    assert tx.begin_dispatch(2)==dict(T=101,joint=3,rad=1.683980809,spd=20,acc=1)
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert preview_elbow_isolation(source(),elbow_degrees=-9)['status']!='PREVIEW_ONLY_NOT_EXECUTABLE'


def test_speed_variant_preserves_target_and_records_actual_settings(monkeypatch,tmp_path):
    from rocell.safety import wifi_cartesian_reservation as reservations
    from rocell.providers.windows.arm_wifi_feedback import ADDRESS,MAC
    b=source();b['joints_rad']['e']=1.691980809
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*list(b['joints_rad'].values())[:4])))
    b.update(address=ADDRESS,expected_mac=MAC,cleanup_confirmed=True,response_finished_monotonic_s=1.)
    # This unit test isolates reservation metadata; raw feedback verification
    # remains covered by the existing reservation/transport tests.
    monkeypatch.setattr(reservations,'review_observation',lambda _:None)
    captured={}
    monkeypatch.setattr(reservations.WifiCartesianReservation,'_publish',lambda self,**kw:captured.update(kw))
    r=reservations.WifiCartesianReservation(root=tmp_path,attempt_id='a'*32,baseline=b,
        now_ns=1_000_000_000,completion_budget_ns=3_000_000_000,elbow_only=True,elbow_degrees=-10)
    command=r.transaction.begin_dispatch(1_000_000_001)
    assert command==dict(T=101,joint=3,rad=1.683980809,spd=40,acc=1)
    assert captured['request']['configuration']['speed']==dict(spd=40,acc=1,units='FIRMWARE_SERVO_NATIVE')
    slow=preview_elbow_isolation(b,elbow_degrees=-9)
    fast=preview_elbow_isolation(b,elbow_degrees=-10)
    assert slow['samples']==fast['samples']
    assert fast['hypothetical_tip_sweep_mm']<3
