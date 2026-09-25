from copy import deepcopy
import pytest
from test_post_tip_elbow import source
from rocell.application.local_wrist_mapping_cycle import LocalWristMappingCycle,WRISTS
from rocell.providers.windows.compensated_wrist_native import validate_cycle_baseline
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


def adapters(fault=None,at=0):
    events=[]
    def leg(*,index,mode,previous_joints,cancelled):
        events.append(('run',index));b=source();b['joints_rad']['t']=WRISTS[index]
        q=list(b['joints_rad'].values())
        b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
        validate_cycle_baseline(b,mode,previous_joints,mapping_cycle=True)
        tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            wrist_probe=mode,wrist_candidate=True,compensated_endpoint=True)
        tx.begin_dispatch(2);tx.acknowledge(3)
        q[3]=(-.064427193,-.072097097,-.052155347)[index]
        for i in range(1,5):
            end=i*250_000_000;tx.observe((end-1,end,forward(*q[:4]),q),end)
        snap=tx.snapshot();candidate=deepcopy(snap['local_candidate'])
        if fault=='candidate' and index==at:snap['local_candidate']['desired_rad']+=.001
        run=dict(status=snap['state'],transaction=snap,error='FAULT' if fault=='feedback' and index==at else None,
            command_send_attempted=True,acknowledgment_received=True,
            move_request=dict(configuration=dict(compensated_candidate=candidate)),
            feedback_originals=[dict(status='SUCCEEDED',cleanup_confirmed=True,
                identity_before_matched=True,identity_after_matched=True) for _ in range(4)])
        return dict(status=run['status'],run=run,receipt=dict(cleanup_confirmed=True))
    def publish(*,index,report):
        events.append(('publish',index))
        return dict(verified=not(fault=='export' and index==at),export='leg-'+str(index))
    return leg,publish,events


def test_three_legs_publish_before_progress_and_no_replay():
    leg,publish,events=adapters();cycle=LocalWristMappingCycle()
    result=cycle.run(run_leg=leg,publish_leg=publish)
    assert result['status']=='LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED'
    assert result['maximum_legs']==3
    assert events==[(kind,i) for i in range(3) for kind in ('run','publish')]
    assert cycle.run(run_leg=leg,publish_leg=publish)['status']=='CYCLE_ALREADY_USED'


@pytest.mark.parametrize('fault',['feedback','candidate','export'])
@pytest.mark.parametrize('index',[0,1,2])
def test_fault_never_progresses(fault,index):
    leg,publish,events=adapters(fault,index)
    result=LocalWristMappingCycle().run(run_leg=leg,publish_leg=publish)
    assert result['status'] in ('LEG_NOT_VERIFIED','EXPORT_NOT_VERIFIED')
    assert ('run',index+1) not in events


def test_cancel_after_first_export():
    leg,publish,events=adapters()
    result=LocalWristMappingCycle().run(run_leg=leg,publish_leg=publish,
        cancelled=lambda:('publish',0) in events)
    assert result['status']=='CANCELLED_BEFORE_NEXT_LEG'
    assert ('run',1) not in events


@pytest.mark.parametrize('missing_at',[None,0,1,2])
def test_hold_required_at_every_leg_before_progression(missing_at):
    original,publish,events=adapters()
    def leg(**kwargs):
        report=original(**kwargs)
        if kwargs['index']==missing_at:return report
        q=report['run']['transaction']['rows'][-1][3]
        samples=[]
        for i in range(6):
            samples.append(dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
                joints_rad=dict(zip(('b','s','e','t','r','g'),q)),
                controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),forward(*q[:4])))),
                timing_clock='HOST_PERF_COUNTER',request_started_monotonic_s=2+i*.3,
                response_finished_monotonic_s=2.1+i*.3))
        report['post_completion_observation']=dict(status='SUCCEEDED',samples=samples)
        return report
    r=LocalWristMappingCycle(require_hold=True).run(run_leg=leg,publish_leg=publish)
    if missing_at is None:
        assert r['status']=='LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED'
        assert all(e['hold_review']['status']=='REPORTED_HOLD_VERIFIED' for e in r['legs'])
    else:
        assert r['status']=='LEG_NOT_VERIFIED'
        assert ('run',missing_at+1) not in events
        assert ('publish',missing_at) in events
