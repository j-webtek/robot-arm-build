"""Single-trial execution lifecycle, currently admitted only to exact replay I/O.

This is the incapable qualification path for the future native executor, not a
physical provider. It reuses the existing final-boundary MotionPermit consumer.
No serial factory, arbitrary command callback, query, return or retry is exposed.
Native admission, independently qualified baseline freshness, stop behavior and
sustained capture ownership must be implemented separately before hardware use.
"""

from copy import deepcopy
import math
import time
from threading import Event, Lock

from rocell.arm.protocol import CartesianGoal
from rocell.arm.serial_transport import ReplayTransport
from rocell.rc03.build_snapshot import Capability
from rocell.safety.permit import MotionPermit
from .characterization_plan import AXES, FrozenCampaign
from .characterization_wire_sim import analyze_synthetic_trial


def execute_request_rehearsal(request, *, permit, session, cancellation):
    """Exercise the native-shaped request only through the incapable entry.

    This is not a native admission shortcut: referenced reviews remain synthetic
    fixture data here. Request construction cannot replace supervisor issuance.
    """
    from rocell.application.endpoint_trial_contract import EndpointTrialRequest
    from .characterization_plan import freeze_campaign
    if type(request) is not EndpointTrialRequest:
        raise ValueError('Exact endpoint request required')
    request.require_start_time(time.monotonic_ns())
    body = request.to_dict()
    report = execute_rehearsal_trial(freeze_campaign(body['campaign']), body['trial_id'],
        permit=permit, expected_snapshot_hash=body['references']['build_snapshot_sha256'],
        session=session, cancellation=cancellation)
    report['request_sha256'] = request.request_sha256
    report['attempt_id'] = body['attempt_id']
    return report


class IncapableTrialSession:
    """Explicit synthetic fixture inputs; constructor never opens any device."""

    def __init__(self, *, baseline_samples: list, post_samples: list, context: dict, fault='NONE'):
        if fault not in {'NONE', 'WRITE_UNCERTAIN', 'CLOSE_UNCERTAIN', 'CONTEXT_CHANGED', 'CANCEL_BEFORE_WRITE'}:
            raise ValueError('Unsupported execution fault')
        self.baseline_samples = deepcopy(baseline_samples)
        self.post_samples = deepcopy(post_samples)
        self.context = deepcopy(context)
        self.fault = fault
        self.transport = ReplayTransport(initially_open=False)
        self._claim_lock = Lock()
        self._claimed = False

    def claim(self):
        with self._claim_lock:
            if self._claimed:
                raise ValueError('Trial session is already claimed; no retry')
            self._claimed = True


def execute_rehearsal_trial(plan, trial_id, *, permit, expected_snapshot_hash, session, cancellation):
    """Execute one exact selected trial in memory, retaining all exit evidence.

    A real supervisor-issued EMPTY_CELL_MOTION permit is required even here;
    the executor does not mint one or convert a simulation result into authority.
    Claiming the session is irreversible. The outbound replay consumes the goal;
    finally revokes any remainder and closes the owned replay on every path.
    """
    if (type(plan) is not FrozenCampaign or type(session) is not IncapableTrialSession
            or type(session.transport) is not ReplayTransport or type(cancellation) is not Event
            or type(permit) is not MotionPermit):
        raise ValueError('Exact frozen plan, incapable session, event and motion permit required')
    data = plan.to_dict()
    trials = [trial for trial in data['trials'] if trial['trial_id'] == trial_id]
    if len(trials) != 1 or data['frame'] != 'R_ctrl':
        raise ValueError('One explicit controller-frame trial required')
    trial = trials[0]
    goal = CartesianGoal(*(trial['target'][axis] for axis in AXES), trial['spd'])
    if (permit.capability is not Capability.EMPTY_CELL_MOTION or permit.plan_hash != plan.sha256
            or permit.snapshot_hash != expected_snapshot_hash or permit.remaining_uses != 1):
        raise ValueError('Permit context must bind one empty-cell goal and this plan/snapshot')
    if session.transport.is_open or session.transport.sent_lines:
        raise ValueError('Executor requires an unused closed replay connection')
    session.claim()
    report = {'schema': 'rocell.single_trial_execution_rehearsal.v1',
              'basis': 'INCAPABLE_REPLAY_ONLY', 'plan_sha256': plan.sha256, 'trial_id': trial_id,
              'observation_contract': 'SUPERVISED_ENDPOINT_ONLY',
              'goal': goal.to_message(), 'events': ['CLAIMED'], 'status': 'FAILED', 'errors': [],
              'baseline_evidence': None, 'post_evidence': None, 'write_attempted': False,
              'replay_write_confirmed': False, 'cleanup_confirmed': False,
              'device_opens': 0, 'physical_command_writes': 0, 'physical_ready': False,
              'motion_authorized': False, 'physical_stop_verified': False}

    def check_context():
        if cancellation.is_set():
            raise RuntimeError('CANCELLED')
        if session.context != data['evidence']:
            raise RuntimeError('IDENTITY_OR_SOURCE_CONTEXT_CHANGED')

    try:
        check_context()
        session.transport.connect()
        report['events'].append('REPLAY_OPENED')
        # Retain encoded baseline even on mismatch; it is not declared physical
        # freshness simply because its final coordinate matches the plan.
        baseline = analyze_synthetic_trial(plan, trial_id, session.baseline_samples)
        report['baseline_evidence'] = baseline
        endpoint = baseline['analysis']['latest_reported_endpoint']
        if endpoint is None or len(session.baseline_samples) < 2:
            raise RuntimeError('BASELINE_UNAVAILABLE')
        if baseline['analysis']['longest_host_coverage_gap_ns'] > trial['stop']['max_read_gap_s'] * 1e9:
            raise RuntimeError('BASELINE_COVERAGE_GAP')
        poses = [sample['pose'] for sample in session.baseline_samples]
        for pose in poses:
            if (math.dist([pose[a] for a in AXES[:3]], [trial['start'][a] for a in AXES[:3]]) > trial['stop']['position_tolerance_mm']
                    or max(abs(pose[a] - trial['start'][a]) for a in AXES[3:]) > trial['stop']['angle_tolerance_rad']):
                raise RuntimeError('BASELINE_START_MISMATCH')
        report['events'].append('SYNTHETIC_BASELINE_MATCHED')
        if session.fault == 'CONTEXT_CHANGED':
            session.context = {}
        if session.fault == 'CANCEL_BEFORE_WRITE':
            cancellation.set()
        check_context()
        report['write_attempted'] = True
        report['events'].append('OUTBOUND_BOUNDARY_ENTERED')
        # No retry: any exception after entering this boundary is treated as
        # possibly sent. The transport consumes the exact goal before appending.
        session.transport.send_motion(goal, permit)
        if session.fault == 'WRITE_UNCERTAIN':
            raise RuntimeError('WRITE_COMPLETION_UNCERTAIN')
        report['replay_write_confirmed'] = True
        report['events'].append('ONE_REPLAY_COMMAND_RECORDED')
        check_context()
        report['post_evidence'] = analyze_synthetic_trial(plan, trial_id, session.post_samples,
            observation_contract='SUPERVISED_ENDPOINT_ONLY')
        report['status'] = ('REHEARSAL_OBSERVED_ENDPOINT_DWELL' if report['post_evidence']['analysis']['status'] == 'OBSERVED_ENDPOINT_DWELL'
                            else 'REHEARSAL_INSUFFICIENT_EVIDENCE')
    except Exception as error:
        report['errors'].append(str(error) if type(error) is RuntimeError else type(error).__name__)
    finally:
        permit.revoke()
        try:
            session.transport.close()
            if session.fault == 'CLOSE_UNCERTAIN':
                raise RuntimeError('CLEANUP_UNKNOWN')
            report['cleanup_confirmed'] = not session.transport.is_open
        except Exception as error:
            report['errors'].append(str(error) if type(error) is RuntimeError else type(error).__name__)
        report['events'].append('REPLAY_CLOSE_ATTEMPTED')
        report['retained_replay_lines'] = [line.decode('ascii') for line in session.transport.sent_lines]
        if report['errors'] or not report['cleanup_confirmed']:
            report['status'] = 'FAILED'
    return report
