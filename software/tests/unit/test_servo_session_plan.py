import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_session_plan import freeze_session_plan


def inputs():
    trace=simulate_trace('paired_arrival');trace['command']['servo_id']=14
    schedule=dict(sample_count=3,sample_interval_us=1000000,maximum_lateness_us=1000000,maximum_pair_us=1000)
    return trace['command'],trace['policy'],canonical(trace['command']['payload']),schedule


def test_plan_is_a_deep_immutable_snapshot():
    command,policy,sent,schedule=inputs()
    plan=freeze_session_plan(command,policy,sent,schedule,origin='SIMULATION');digest=plan.sha256
    command['desired_count']=999;policy['tolerance_counts']=90;schedule['sample_count']=1
    copy=plan.to_dict();copy['command']['wire_count']=999
    assert plan.sha256==digest and plan.to_dict()['command']['desired_count']==2100
    assert plan.to_dict()['schedule']['sample_count']==3


@pytest.mark.parametrize('field,value',[('sample_count',12),('sample_count',True),
    ('sample_interval_us',0),('maximum_lateness_us',2),('maximum_pair_us',2000)])
def test_bad_schedule_rejected(field,value):
    command,policy,sent,schedule=inputs();schedule[field]=value
    with pytest.raises(ValueError):freeze_session_plan(command,policy,sent,schedule,origin='SIMULATION')


def test_whole_arm_plan_requires_baseline_and_capacity():
    command,policy,sent,schedule=inputs()
    whole=dict(joints=[[1900,2200] for _ in range(7)],tracking_tolerance=2,
        maximum_pair_us=1000,maximum_scan_us=10000,maximum_age_us=10000)
    elbow=dict(maximum_delta_counts=16,settled_tolerance_counts=2,maximum_pair_us=1000,maximum_age_us=1000)
    with pytest.raises(ValueError):freeze_session_plan(command,policy,sent,schedule,
        origin='SIMULATION',whole_arm_policy=whole)
    for count in (9,10):
        with pytest.raises(ValueError):freeze_session_plan(command,policy,sent,dict(schedule,sample_count=count),
            origin='SIMULATION',baseline_policy=elbow,whole_arm_policy=whole)
    plan=freeze_session_plan(command,policy,sent,dict(schedule,sample_count=8),
        origin='SIMULATION',baseline_policy=elbow,whole_arm_policy=whole)
    assert plan.to_dict()['schema']=='rocell.session_plan.v3'
    whole['joints'][0][0]=0
    assert plan.to_dict()['whole_arm_policy']['joints'][0][0]==1900
