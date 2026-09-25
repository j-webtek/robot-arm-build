"""At most two fixed wrist commands, with fresh feedback and per-leg export."""
import time
import uuid
from rocell.application.compensated_wrist_cycle import CompensatedWristCycle
from rocell.application.wrist_shared_pair import preview_pair_leg
from rocell.application.controller_route_preview import _baseline
from rocell.application.wifi_discrete_runner import run_cartesian_transaction
from rocell.safety.wifi_cartesian_reservation import WifiCartesianReservation
from .wifi_cartesian_native import NativeCartesianTransport
from .arm_wifi_deadline import bounded_probe
from .arm_transport_lock import arm_transport_lock


def validate_cycle_baseline(baseline,mode,previous_joints=None, *, mapping_cycle=False,transfer_cycle=False):
    _,joints,_=_baseline(baseline)
    if previous_joints is not None and (len(previous_joints)!=6 or
            any(abs(a-b)>1e-8 for a,b in zip(joints,previous_joints))):
        raise ValueError('Reported pose changed between legs')
    if transfer_cycle:
        from rocell.application.transferred_wrist_cycle import preview_leg
        return preview_leg(baseline,mode)
    if mapping_cycle:
        from rocell.application.local_wrist_mapping_cycle import preview_leg
        return preview_leg(baseline,mode)
    return preview_pair_leg(baseline,mode)


def run_native_cycle(*,root,publish_leg,cancelled=lambda:False,mapping_cycle=False,require_hold=False,transfer_cycle=False):
    if type(mapping_cycle) is not bool:raise ValueError('Explicit cycle type required')
    if type(require_hold) is not bool:raise ValueError('Explicit hold policy required')
    if type(transfer_cycle) is not bool or (transfer_cycle and mapping_cycle):raise ValueError('Exclusive cycle type required')
    if transfer_cycle:require_hold=True
    with arm_transport_lock():
        def leg(*,index,mode,previous_joints,cancelled):
            baseline=bounded_probe(cancelled=cancelled,retain_response=True)
            report=dict(schema='rocell.native_cartesian_trial.v1',status='HELD_BEFORE_DISPATCH',
                baseline=baseline,run=None,receipt=None,physical_accuracy_verified=False,
                automatic_retry_allowed=False,automatic_return_allowed=False)
            try:
                if cancelled():
                    report['status']='CANCELLED_BEFORE_DISPATCH';return report
                validate_cycle_baseline(baseline,mode,previous_joints,mapping_cycle=mapping_cycle,transfer_cycle=transfer_cycle)
                reservation=WifiCartesianReservation(root=root,attempt_id=uuid.uuid4().hex,
                    baseline=baseline,now_ns=time.perf_counter_ns(),completion_budget_ns=10_000_000_000,
                    wrist_probe=mode if mapping_cycle or transfer_cycle else 'post-coordinated-ascending' if mode=='up' else 'post-coordinated',
                    wrist_candidate=True if mapping_cycle or transfer_cycle else 'pair-'+mode,compensated_endpoint=True)
            except (ValueError,KeyError,TypeError):
                report['reason']='FRESH_POSE_OR_PATH_NOT_ADMITTED';return report
            transport=NativeCartesianTransport(reservation)
            report['run']=run_cartesian_transaction(reservation,transport=transport,
                clock_ns=time.perf_counter_ns,wait=time.sleep,cancelled=cancelled)
            report['status']=report['run']['status'];report['receipt']=transport.receipt
            if require_hold and report['status']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED':
                # Observation only: never resend or change the target to settle it.
                samples=[];deadline=time.perf_counter()+3.;status='SUCCEEDED'
                while time.perf_counter()<deadline:
                    if cancelled():status='CANCELLED';break
                    sample=bounded_probe(cancelled=cancelled,retain_response=True)
                    samples.append(sample)
                    if sample.get('status')!='SUCCEEDED':status='FAILED';break
                    time.sleep(.15)
                report['post_completion_observation']=dict(status=status,samples=samples)
            return report
        if transfer_cycle:
            from rocell.application.transferred_wrist_cycle import TransferredWristCycle
            cycle=TransferredWristCycle()
        elif mapping_cycle:
            from rocell.application.local_wrist_mapping_cycle import LocalWristMappingCycle
            cycle=LocalWristMappingCycle(require_hold=require_hold)
        else:cycle=CompensatedWristCycle(require_hold=require_hold)
        return cycle.run(run_leg=leg,publish_leg=publish_leg,cancelled=cancelled)
