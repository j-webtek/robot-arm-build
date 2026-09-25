"""Explicit finite local cycle; never a general task or contact controller."""
import time
import uuid
from rocell.application.compensated_elbow_cycle import CompensatedElbowCycle
from rocell.application.controller_route_preview import _baseline, preview_elbow_isolation
from rocell.application.wifi_discrete_runner import run_cartesian_transaction
from rocell.safety.wifi_cartesian_reservation import WifiCartesianReservation
from .wifi_cartesian_native import NativeCartesianTransport
from .arm_wifi_deadline import bounded_probe
from .arm_transport_lock import arm_transport_lock


def validate_cycle_baseline(baseline,mode,previous_joints=None):
    """Restrict experiment to the observed posture; never extrapolate to a board."""
    _,joints,consistent=_baseline(baseline)
    fixed=(.001533981,0,None,.053689328,.01994175,3.138524692)
    if mode not in (3,-6) or not consistent:
        raise ValueError('Local pair and consistent feedback required')
    if any(abs(v-fixed[i])>1e-8 for i,v in enumerate(joints) if i!=2):
        raise ValueError('Untested non-elbow posture')
    if previous_joints is not None and (len(previous_joints)!=6 or any(abs(a-b)>1e-8 for a,b in zip(joints,previous_joints))):
        raise ValueError('Reported pose changed between legs')
    preview=preview_elbow_isolation(baseline,elbow_degrees=mode)
    if preview['status']!='PREVIEW_ONLY_NOT_EXECUTABLE':
        raise ValueError('Local path not admitted')
    return preview


def run_native_cycle(*,root,publish_leg,cancelled=lambda:False):
    """Own transport through both fresh admissions and verified publications."""
    with arm_transport_lock():
        def leg(*,index,mode,previous_joints,cancelled):
            baseline=bounded_probe(cancelled=cancelled,retain_response=True)
            report=dict(schema='rocell.native_cartesian_trial.v1',status='HELD_BEFORE_DISPATCH',
                        baseline=baseline,run=None,receipt=None,physical_accuracy_verified=False,
                        automatic_retry_allowed=False,automatic_return_allowed=False)
            try:
                if cancelled():
                    report['status']='CANCELLED_BEFORE_DISPATCH'; return report
                validate_cycle_baseline(baseline,mode,previous_joints)
                reservation=WifiCartesianReservation(root=root,attempt_id=uuid.uuid4().hex,
                    baseline=baseline,now_ns=time.perf_counter_ns(),completion_budget_ns=10_000_000_000,
                    elbow_only=True,elbow_degrees=mode,compensated_endpoint=True)
            except (ValueError,KeyError,TypeError):
                report['reason']='FRESH_POSE_OR_PATH_NOT_ADMITTED'; return report
            transport=NativeCartesianTransport(reservation)
            report['run']=run_cartesian_transaction(reservation,transport=transport,
                clock_ns=time.perf_counter_ns,wait=time.sleep,cancelled=cancelled)
            report['status']=report['run']['status']; report['receipt']=transport.receipt
            return report
        return CompensatedElbowCycle().run(run_leg=leg,publish_leg=publish_leg,cancelled=cancelled)
