from copy import deepcopy
import pytest
from rocell.application.transferred_wrist_cycle import TransferredWristCycle,WRISTS
from rocell.providers.windows.compensated_wrist_native import validate_cycle_baseline
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.kinematics.firmware_reference import forward


@pytest.mark.parametrize('fault_at',[None,0,1,2])
def test_finite_transfer_cycle_holds_and_exports_before_next(fault_at):
    events=[]
    def leg(*,index,mode,previous_joints,cancelled):
        events.append(('run',index))
        q=[.001533981,.033747577,1.691980809,WRISTS[index],.018407769,3.138524692]
        def feedback(q):
            return dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
                joints_rad=dict(zip(('b','s','e','t','r','g'),q)),
                controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),forward(*q[:4])))))
        b=feedback(q);validate_cycle_baseline(b,mode,previous_joints,transfer_cycle=True)
        tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            wrist_probe=mode,wrist_candidate=True,compensated_endpoint=True)
        tx.begin_dispatch(2);tx.acknowledge(3)
        q[3]=(-.064427193,-.075165059,-.052155347)[index]
        for i in range(1,5):
            end=i*250_000_000;tx.observe((end-1,end,forward(*q[:4]),q),end)
        snap=tx.snapshot();candidate=deepcopy(snap['local_candidate'])
        run=dict(status=snap['state'],transaction=snap,error=None,command_send_attempted=True,
            acknowledgment_received=True,move_request=dict(configuration=dict(compensated_candidate=candidate)),
            feedback_originals=[dict(status='SUCCEEDED',cleanup_confirmed=True,identity_before_matched=True,
                identity_after_matched=True) for _ in range(4)])
        samples=[]
        for i in range(6):
            s=feedback(q);s.update(timing_clock='HOST_PERF_COUNTER',
                request_started_monotonic_s=2+i*.3,response_finished_monotonic_s=2.1+i*.3)
            samples.append(s)
        return dict(status=run['status'],run=run,receipt=dict(cleanup_confirmed=True),
            post_completion_observation=dict(status='FAILED' if index==fault_at else 'SUCCEEDED',samples=samples))
    def publish(*,index,report):
        events.append(('publish',index));return dict(verified=True,export=str(index))
    cycle=TransferredWristCycle();r=cycle.run(run_leg=leg,publish_leg=publish)
    assert r['status']==('LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED' if fault_at is None else 'LEG_NOT_VERIFIED')
    count=3 if fault_at is None else fault_at+1
    assert events==[(kind,i) for i in range(count) for kind in ('run','publish')]
    assert cycle.run(run_leg=leg,publish_leg=publish)['status']=='CYCLE_ALREADY_USED'
