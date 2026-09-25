"""Bounded +2/+5 mm Z native adapter, not a general Cartesian or contact API.

Not registered as a wizard action until integration tests and a live trial are
reviewed. Calling run_native_vertical_trial explicitly can move the arm.
"""
import time
import uuid
from rocell.application.wifi_discrete_runner import run_cartesian_transaction
from rocell.safety.wifi_cartesian_reservation import WifiCartesianReservation
from .wifi_discrete_native import NativeDiscreteTransport, _CommandConnection
from .arm_wifi_deadline import bounded_probe
from .arm_transport_lock import arm_transport_lock


class _CartesianCommandConnection(_CommandConnection):
    _reservation_type = WifiCartesianReservation


class NativeCartesianTransport(NativeDiscreteTransport):
    def _connection_type(self, *args, **kwargs):
        return _CartesianCommandConnection(*args, **kwargs)

    def __init__(self,reservation):
        if type(reservation) is not WifiCartesianReservation:
            raise ValueError('Exact Cartesian reservation required')
        self.reservation=reservation
        self.receipt=None


def run_native_vertical_trial(*, root, cancelled=lambda:False, step_mm=2, elbow_only=False, elbow_degrees=2, ghost_first_step=False,wrist_probe=False,wrist_candidate=False,wrist_prepare=False,compensated_endpoint=False):
    """Own connection -> fresh baseline -> reserve -> one move -> observe.

    No return, reset, torque command or retry. The caller owns external clearance
    review and durable final-result publication. Command intent is persisted
    before sending; a broken receipt is retained as uncertain execution.
    """
    if type(step_mm) is not int or step_mm not in (2,5):
        raise ValueError('Unsupported diagnostic step')
    if type(elbow_degrees) is not int or elbow_degrees not in (2,5,-3,1,-1,3,-4,-5,-6,-7,-8,-9,-10) or (not elbow_only and elbow_degrees!=2):
        raise ValueError('Named elbow lift required')
    if type(elbow_only) is not bool or (elbow_only and step_mm!=2):
        raise ValueError('Unsupported elbow diagnostic')
    if not elbow_only and not wrist_probe:
        # T105 reference acquisition refreshes stored XYZ/pitch, but installed
        # acquisition behavior and coordinated response remain unqualified after
        # the observed tip-bound fault. Do not attribute that fault solely to
        # stale command state; retain the hold pending a discriminating trial.
        # Keep T101 commissioning independent. Do not "synchronize" via a move.
        return dict(schema='rocell.native_cartesian_trial.v1',status='HELD_BEFORE_DISPATCH',
            reason='T104_INTERPOLATION_START_STATE_UNQUALIFIED',baseline=None,run=None,receipt=None,
            physical_accuracy_verified=False,automatic_retry_allowed=False,
            automatic_return_allowed=False,motion_commands=0)
    with arm_transport_lock():
        baseline=bounded_probe(cancelled=cancelled,retain_response=True)
        result=dict(schema='rocell.native_cartesian_trial.v1',status='HELD_BEFORE_DISPATCH',
            baseline=baseline,run=None,receipt=None,physical_accuracy_verified=False,
            automatic_retry_allowed=False,automatic_return_allowed=False)
        if cancelled():
            result['status']='CANCELLED_BEFORE_DISPATCH'
            return result
        try:
            reservation=WifiCartesianReservation(root=root,attempt_id=uuid.uuid4().hex,
                baseline=baseline,now_ns=time.perf_counter_ns(),completion_budget_ns=10_000_000_000,
                step_mm=step_mm,elbow_only=elbow_only,elbow_degrees=elbow_degrees,ghost_first_step=ghost_first_step,wrist_probe=wrist_probe,wrist_candidate=wrist_candidate,wrist_prepare=wrist_prepare,compensated_endpoint=compensated_endpoint)
        except (ValueError,KeyError,TypeError):
            result['reason']='BASELINE_OR_ROUTE_NOT_ADMITTED'
            return result
        transport=NativeCartesianTransport(reservation)
        result['run']=run_cartesian_transaction(reservation,transport=transport,
            clock_ns=time.perf_counter_ns,wait=time.sleep,cancelled=cancelled)
        result['status']=result['run']['status']
        result['receipt']=transport.receipt
        return result
