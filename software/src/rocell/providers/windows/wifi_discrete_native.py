"""Exact one-degree roll commissioning, no generic command interface or retry."""
import base64
import hashlib
import json
import math
import time
import uuid
from threading import Event
from pathlib import Path
from urllib.parse import quote_from_bytes

from rocell.application.wifi_discrete_runner import run_reserved_transaction
from rocell.safety.wifi_dispatch_reservation import WifiDispatchReservation
from rocell.arm.feedback import parse_feedback_1051, KNOWN_1051_FIELDS
from .arm_wifi_deadline import DeadlineFeedbackConnection, bounded_probe, IO_BUDGET_S
from .arm_wifi_feedback import ADDRESS, MAC, neighbor_mac, unique_object
from .arm_transport_lock import arm_transport_lock


class _CommandConnection(DeadlineFeedbackConnection):
    # A successful HTTP exchange may have no application body. This never counts
    # as arrival: the runner must obtain independent post-command T105 feedback.
    _minimum_body_length = 0
    _reservation_type = WifiDispatchReservation
    def request(self,*args,**kwargs):
        raise ValueError('Use exact reserved dispatch only')

    def dispatch(self,reservation,payload):
        if type(reservation) is not self._reservation_type:
            raise ValueError('Exact reservation required')
        self._check()
        mac=neighbor_mac()
        reservation.claim_native_send(payload,now_ns=time.perf_counter_ns(),observed_mac=mac)
        self._check()
        self._send_path('/js?json='+quote_from_bytes(payload,safe=''))


class NativeDiscreteTransport:
    # Do not begin an observation with only a fragment of its normal I/O budget.
    # The transaction deadline still wins; this never extends a motion window.
    feedback_budget_ns = round(IO_BUDGET_S*1e9)
    def _connection_type(self, *args, **kwargs):
        return _CommandConnection(*args, **kwargs)
    def __init__(self,reservation):
        if type(reservation) is not WifiDispatchReservation:raise ValueError('Reservation required')
        self.reservation=reservation;self.receipt=None

    def identity(self):return neighbor_mac()

    def send_once(self,payload,*,deadline_ns,cancelled):
        connection=self._connection_type(ADDRESS,cancelled=cancelled,deadline=deadline_ns/1e9)
        self.receipt=dict(status='UNCERTAIN',http_status=None,cleanup_confirmed=False,
            payload_sha256=hashlib.sha256(payload).hexdigest())
        try:
            connection.dispatch(self.reservation,payload)
            response=connection.getresponse()
            self.receipt['http_status']=response.status
            raw=response.read1(2049)
            data=json.loads(raw,object_pairs_hook=unique_object) if raw else None
            # No-body HTTP 200 is transport receipt only, not a controller ack.
            accepted=(not raw or type(data) is dict and
                (not data or set(data)=={'ok'} and type(data['ok']) is int and data['ok']==1))
            numeric_feedback=False
            if type(data) is dict and data.get('T')==1051:
                parse_feedback_1051(data)
                numeric_feedback=(set(data)<=KNOWN_1051_FIELDS and
                    all(type(v) in (int,float) and math.isfinite(v) for v in data.values()) and
                    all(k in data for k in ('b','s','e','t','r','g')))
                accepted=numeric_feedback
            if not accepted:
                raise ValueError('Unrecognized command receipt')
            if neighbor_mac()!=MAC:raise ValueError('Identity changed')
            self.receipt.update(status='HTTP_RECEIPT_ONLY',http_status=response.status,
                receipt_kind='NUMERIC_FEEDBACK_HTTP_200' if numeric_feedback else 'EMPTY_HTTP_200' if not raw else 'JSON_HTTP_200',
                controller_execution_acknowledged=False,
                receipt_used_as_endpoint=False,
                response_base64=base64.b64encode(raw).decode(),
                response_sha256=hashlib.sha256(raw).hexdigest())
            return True
        except Exception as error:
            self.receipt['failure_category']=('TIMEOUT' if isinstance(error,TimeoutError) else
                'CONNECTION_RESET' if isinstance(error,ConnectionResetError) else
                'RESPONSE_OR_BINDING_REJECTED' if isinstance(error,ValueError) else 'IO_FAILURE')
            raise
        finally:
            self.receipt['framing']=getattr(connection,'response_metadata',{}).copy()
            connection.close()
            self.receipt['cleanup_confirmed']=True

    def feedback(self,*,deadline_ns,cancelled):
        return bounded_probe(cancelled=cancelled,retain_response=True,deadline=deadline_ns/1e9)


def run_native_roll_trial(*, root, cancelled=lambda:False):
    """One +1 degree roll move, absolute target within +/-3 degrees, 20/1 speed/acc.

Caller explicitly executes the wizard action. Construction/preview is inert.
Never sends initialization, return, torque, or a retry. A failed receipt may mean
the command executed: retain uncertainty, not a replacement command.
"""
    return _run_roll_trial(root=root,cancelled=cancelled,direction=1)


def run_native_roll_negative_trial(*, root, cancelled=lambda:False):
    """Distinct -1 degree trial from its own baseline; never an automatic return."""
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1)


def run_native_roll_low_trial(*,root,cancelled=lambda:False):
    """Distinct descending trial to absolute roll 1 degree."""
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,fixed_target=1.)


def run_native_roll_high_trial(*,root,cancelled=lambda:False):
    """Distinct ascending trial to absolute roll 2.5 degrees."""
    return _run_roll_trial(root=root,cancelled=cancelled,direction=1,fixed_target=2.5)


def run_native_roll_zero_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,fixed_target=0.)


def run_native_roll_center_up_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=1,fixed_target=1.25)


def run_native_roll_center_down_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,fixed_target=1.25)


def run_native_roll_corrected_up_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=1,correction='ascending')


def run_native_roll_corrected_down_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,correction='descending')


def run_native_roll_probe_low_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,probe_target=.95)


def run_native_roll_probe_high_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,probe_target=1.15)


def run_native_roll_lookup_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,lookup=True)


def run_native_roll_adjacent_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,fixed_target=1.5)


def run_native_roll_adjacent_low_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,adjacent_probe=1.25)


def run_native_roll_adjacent_high_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,adjacent_probe=1.35)


def run_native_roll_adjacent_lookup_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,adjacent_lookup=True)


def run_native_roll_sweep_low_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,sweep_target=.85)


def run_native_roll_sweep_center_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,sweep_target=.95)


def run_native_roll_sweep_high_trial(*,root,cancelled=lambda:False):
    return _run_roll_trial(root=root,cancelled=cancelled,direction=-1,sweep_target=1.05)


def _run_roll_trial(*, root, cancelled, direction, fixed_target=None, correction=None, probe_target=None, lookup=False, adjacent_probe=None, adjacent_lookup=False,sweep_target=None):
    if type(direction) is not int or direction not in (-1,1):
        raise ValueError('Fixed single-degree direction required')
    candidate=None
    characterization=None
    if sweep_target is not None:
        if (type(sweep_target) not in (int,float) or sweep_target not in (.85,.95,1.05)
                or direction!=-1 or lookup or adjacent_lookup or
                any(v is not None for v in (fixed_target,correction,probe_target,adjacent_probe))):
            raise ValueError('Exclusive enumerated command-spacing probe required')
        fixed_target=sweep_target
        characterization=dict(protocol='LOCAL_COMMAND_SPACING_V1',
            desired_endpoint_deg=1.25,command_deg=sweep_target,
            held_out=False,model_updated=False,globally_enabled=False)
    if type(adjacent_lookup) is not bool:
        raise ValueError('Explicit adjacent lookup mode required')
    if adjacent_lookup:
        if lookup or direction!=-1 or any(v is not None for v in (fixed_target,correction,probe_target,adjacent_probe)):
            raise ValueError('Exclusive adjacent lookup validation required')
        lookup=True
    if adjacent_probe is not None:
        if (type(adjacent_probe) not in (int,float) or adjacent_probe not in (1.25,1.35)
                or direction!=-1 or lookup or any(v is not None for v in (fixed_target,correction,probe_target))):
            raise ValueError('Exclusive enumerated adjacent probe required')
        fixed_target=adjacent_probe
        characterization=dict(protocol='ADJACENT_ROLL_1_50_PROBES',
            desired_endpoint_deg=1.5,command_deg=adjacent_probe,
            held_out=False,model_updated=False,globally_enabled=False)
    if fixed_target==1.5:
        if direction!=-1 or correction is not None or probe_target is not None or lookup:
            raise ValueError('Exclusive descending adjacent characterization required')
        characterization=dict(protocol='ADJACENT_ROLL_1_50_UNCORRECTED',
            desired_endpoint_deg=1.5,command_deg=1.5,
            held_out=False,model_updated=False,globally_enabled=False)
    if type(lookup) is not bool:
        raise ValueError('Explicit lookup mode required')
    if lookup:
        if direction!=-1 or any(v is not None for v in (fixed_target,correction,probe_target)):
            raise ValueError('Exclusive descending lookup validation required')
        filename='WIFI_ROLL_150_LOOKUP_CANDIDATE.json' if adjacent_lookup else 'WIFI_ROLL_125_LOOKUP_CANDIDATE.json'
        expected=('3bdb830355bdef5c493ed9ee8b6341bd7bf7dc8dbf9ab7ed1c04d98ac6b18e53'
            if adjacent_lookup else '822965da1d902c86993a50c8647b06e672e37323b56a211a42a1c4bc6e48a910')
        raw=(Path(__file__).resolve().parents[4]/'docs'/filename).read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        if digest!=expected:
            raise ValueError('Frozen lookup candidate changed')
        data=json.loads(raw)
        fixed_target=data['command_deg']
        candidate=dict(candidate_sha256=digest,candidate_schema=data['schema'],
            model=data['model'],approach=data['approach'],
            desired_endpoint_deg=data['desired_endpoint_deg'],command_deg=fixed_target,
            held_out=True,refitted=False,globally_enabled=False)
    if probe_target is not None:
        if (type(probe_target) not in (int,float) or probe_target not in (.95,1.15)
                or direction!=-1 or correction is not None or fixed_target is not None):
            raise ValueError('Enumerated descending probe required')
        fixed_target=probe_target
        characterization=dict(protocol='LOCAL_ROLL_RESPONSE_PROBE_20260916',
            desired_endpoint_deg=1.25,command_deg=probe_target,
            held_out=False,model_updated=False,globally_enabled=False)
    if correction is not None:
        # Frozen training artifact: explicit experiment only, never global enablement.
        raw=(Path(__file__).resolve().parents[4]/'docs'/'WIFI_ROLL_125_CANDIDATE.json').read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        if digest!='cda559d3b575d0a4c755317621454cfafd73fbc1cb0b7efaed113cc8409567f0':
            raise ValueError('Frozen candidate changed')
        if correction not in ('ascending','descending') or direction!=(1 if correction=='ascending' else -1):
            raise ValueError('Fixed correction direction required')
        data=json.loads(raw)
        fixed_target=data[correction]['candidate_command_deg']
        candidate=dict(candidate_sha256=digest,approach=correction,
            desired_endpoint_deg=data['desired_endpoint_deg'],command_deg=fixed_target,
            held_out=True,refitted=False,globally_enabled=False)
    with arm_transport_lock():
        baseline=bounded_probe(cancelled=cancelled,retain_response=True)
        target=baseline.get('joints_rad',{}).get('r',0)+math.radians(direction) if fixed_target is None else math.radians(fixed_target)
        report=dict(schema='rocell.native_wifi_roll_trial.v3' if fixed_target is not None else 'rocell.native_wifi_roll_trial.v1' if direction==1 else 'rocell.native_wifi_roll_trial.v2',
            status='FAILED',baseline=baseline,requested_delta_deg=direction,
            physical_accuracy_verified=False,automatic_retry_allowed=False)
        if candidate is not None:
            report.update(schema='rocell.native_wifi_roll_trial.v4',correction_candidate=candidate)
        if characterization is not None:
            report.update(schema='rocell.native_wifi_roll_trial.v5',characterization=characterization)
        if baseline['status']!='SUCCEEDED':return report
        if fixed_target is not None:
            if candidate is None and characterization is None and fixed_target not in (0.,1.,1.25,2.5):raise ValueError('Enumerated fixed target required')
            report.update(fixed_target_deg=fixed_target,
                requested_delta_deg=math.degrees(target-baseline['joints_rad']['r']))
            if direction*(target-baseline['joints_rad']['r'])<=0:
                report['reason']='BASELINE_NOT_ON_REQUIRED_APPROACH_SIDE';return report
        try:
            reservation=WifiDispatchReservation(root=root,attempt_id=uuid.uuid4().hex,
                baseline=baseline,target=target,
                desired_endpoint=math.radians(characterization['desired_endpoint_deg']) if characterization is not None else None if candidate is None else math.radians(candidate['desired_endpoint_deg']),
                now_ns=time.perf_counter_ns(),completion_budget_ns=10_000_000_000)
        except ValueError:
            report['reason']='BASELINE_OR_TARGET_OUTSIDE_FIXED_ENVELOPE';return report
        transport=NativeDiscreteTransport(reservation)
        outcome=run_reserved_transaction(reservation,transport=transport,clock_ns=time.perf_counter_ns,
            wait=Event().wait,cancelled=cancelled)
        report.update(status='SUCCEEDED' if outcome['status']=='REPORTED_ENDPOINT_VERIFIED' else 'FAILED',
            outcome=outcome,command_receipt=transport.receipt)
        return report
