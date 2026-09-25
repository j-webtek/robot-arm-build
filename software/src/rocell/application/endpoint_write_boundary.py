"""One-attempt endpoint write boundary for a future owned native connection.

This component does not open devices or authenticate operator/metadata originals.
The admitting service must supply fresh, authenticated context and the writer
for its already-owned connection. Tests use an incapable writer. A request or
context dictionary alone cannot replace a supervisor-issued cell permit or the
separately issued, request-bound bench endpoint permit.
"""

from dataclasses import dataclass
import math
from threading import Event, Lock
import time
from typing import Callable

from rocell.arm.protocol import encode_line
from rocell.rc03.build_snapshot import Capability
from rocell.safety.permit import MotionPermit
from rocell.safety.bench_endpoint import BenchEndpointPermit
from rocell.motion.characterization_plan import AXES, freeze_campaign
from .endpoint_trial_contract import EndpointTrialRequest


class _BoundaryRefusal(RuntimeError):
    """Fixed internal reason codes; external writer exception text is not logged."""


@dataclass(frozen=True, slots=True)
class EndpointWriteContext:
    """Service-validated current evidence, not an independently authentic permit.

    Baseline timestamps are host observations. The referenced qualification must
    independently resolve buffering/freshness; a recent timestamp is insufficient.
    """

    connection_id: str
    usb_serial_number: str
    references: tuple[tuple[str, str], ...]
    baseline_pose: tuple[float, ...]
    baseline_acquired_ns: int
    operator_presence_expires_ns: int


class EndpointWriteBoundary:
    """Consume one exact-goal permit immediately before one owned write attempt.

    Callbacks are trusted native composition dependencies, not browser inputs.
    No retry, partial-write completion, torque operation or automatic stop is
    attempted. Failure permanently closes this boundary to further dispatch.
    """

    def __init__(self, request: EndpointTrialRequest, permit: MotionPermit | BenchEndpointPermit, *, connection_id: str,
                 clock_ns=None):
        if type(request) is not EndpointTrialRequest or type(permit) not in (MotionPermit, BenchEndpointPermit):
            raise ValueError('Exact endpoint request and supervisor permit required')
        if type(connection_id) is not str or not 1 <= len(connection_id) <= 80:
            raise ValueError('Bounded owned connection ID required')
        self._request = request
        self._permit = permit
        self._connection_id = connection_id
        clock_ns = (lambda: time.monotonic_ns()) if clock_ns is None else clock_ns
        if not callable(clock_ns):
            raise ValueError('Trusted monotonic clock required')
        self._clock_ns = clock_ns
        self._last_ns = 0
        self._lock = Lock()
        self._attempted = False

    def _now(self):
        value = self._clock_ns()
        if type(value) is not int or not 0 < value < 2**63 or value < self._last_ns:
            raise ValueError('Invalid or backwards write clock')
        self._last_ns = value
        return value

    def attempt(self, *, context_reader: Callable[[], EndpointWriteContext],
                write_once: Callable[[bytes], int], cancellation: Event) -> dict:
        if type(cancellation) is not Event or not callable(context_reader) or not callable(write_once):
            raise ValueError('Owned context/writer and exact cancellation event required')
        with self._lock:
            if self._attempted:
                raise ValueError('Endpoint boundary already attempted; no retry')
            self._attempted = True
            result = {'schema':'rocell.endpoint_write_attempt.v1',
                      'request_sha256':self._request.request_sha256,
                      'status':'NOT_SENT', 'write_attempted':False, 'confirmed_write_bytes':0,
                      'write_completion_uncertain':False, 'error':None,
                      'physical_movement_verified':False, 'physical_stop_verified':False}
            try:
                body = self._request.to_dict()
                goal = self._request.goal()
                payload = encode_line(goal.to_message())
                plan_hash = freeze_campaign(body['campaign']).sha256
                if cancellation.is_set():
                    raise _BoundaryRefusal('CANCELLED_BEFORE_WRITE')
                context = context_reader()
                now = self._now()
                if type(context) is not EndpointWriteContext:
                    raise _BoundaryRefusal('CURRENT_CONTEXT_UNAVAILABLE')
                if (context.connection_id != self._connection_id
                        or context.usb_serial_number != body['usb_identity']['serial_number']
                        or context.references != tuple(sorted(body['references'].items()))):
                    raise _BoundaryRefusal('CURRENT_CONTEXT_CHANGED')
                if (type(context.baseline_acquired_ns) is not int
                        or not body['issued_monotonic_ns'] <= context.baseline_acquired_ns <= now
                        or now-context.baseline_acquired_ns > 100_000_000):
                    raise _BoundaryRefusal('BASELINE_NOT_RECENT_IN_OWNED_SESSION')
                if (type(context.operator_presence_expires_ns) is not int
                        or context.operator_presence_expires_ns <= now
                        or context.operator_presence_expires_ns > body['deadline_monotonic_ns']):
                    raise _BoundaryRefusal('OPERATOR_PRESENCE_EXPIRED_OR_UNBOUNDED')
                # Reserve the full post-observation and cleanup windows; a host
                # deadline never implies the controller will stop by that time.
                if now+8_000_000_000 > body['deadline_monotonic_ns']:
                    raise _BoundaryRefusal('INSUFFICIENT_POST_CAPTURE_CLEANUP_BUDGET')
                trial = next(t for t in body['campaign']['trials'] if t['trial_id'] == body['trial_id'])
                pose = context.baseline_pose
                if (type(pose) is not tuple or len(pose) != 6
                        or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6 for v in pose)):
                    raise _BoundaryRefusal('INVALID_BASELINE_POSE')
                target_start = [trial['start'][a] for a in AXES]
                if (math.dist(pose[:3],target_start[:3]) > trial['stop']['position_tolerance_mm']
                        or max(abs(pose[i]-target_start[i]) for i in range(3,6)) > trial['stop']['angle_tolerance_rad']):
                    raise _BoundaryRefusal('BASELINE_START_MISMATCH')
                permit = self._permit
                if type(permit) is MotionPermit and (permit.capability is not Capability.EMPTY_CELL_MOTION
                        or permit.plan_hash != plan_hash
                        or permit.snapshot_hash != body['references']['build_snapshot_sha256']
                        or permit.remaining_uses != 1):
                    raise _BoundaryRefusal('PERMIT_CONTEXT_MISMATCH')
                if cancellation.is_set():
                    raise _BoundaryRefusal('CANCELLED_OR_PERMIT_REFUSED')
                # Bench scope is separate: it binds the whole request and owned
                # session, and re-authenticates bench reviews at consumption.
                allowed = (permit.consume(self._request, self._connection_id,
                                          baseline_acquired_ns=context.baseline_acquired_ns)
                           if type(permit) is BenchEndpointPermit else permit.allows(goal))
                if not allowed:
                    raise _BoundaryRefusal('CANCELLED_OR_PERMIT_REFUSED')
                if cancellation.is_set():
                    raise _BoundaryRefusal('CANCELLED_AFTER_CONSUMPTION')
                final_now = self._now()
                if (final_now-context.baseline_acquired_ns > 100_000_000
                        or final_now >= context.operator_presence_expires_ns
                        or final_now+8_000_000_000 > body['deadline_monotonic_ns']):
                    raise _BoundaryRefusal('CONTEXT_EXPIRED_AFTER_CONSUMPTION')
                result['write_attempted'] = True
                result['write_started_ns'] = self._now()
                count = write_once(payload)
                result['write_finished_ns'] = self._now()
                if type(count) is int and 0 <= count <= len(payload):
                    result['confirmed_write_bytes'] = count
                if type(count) is not int or count != len(payload):
                    raise _BoundaryRefusal('SHORT_OR_UNKNOWN_WRITE_NO_RETRY')
                if (result['write_finished_ns']-result['write_started_ns'] > 1_000_000_000
                        or result['write_finished_ns']+7_000_000_000 > body['deadline_monotonic_ns']):
                    raise _BoundaryRefusal('WRITE_TIME_BUDGET_EXCEEDED')
                result.update(status='BYTES_WRITTEN_NOT_MOVEMENT_VERIFIED', confirmed_write_bytes=count)
            except Exception as error:
                result['error'] = str(error) if type(error) is _BoundaryRefusal else type(error).__name__
                result['write_completion_uncertain'] = result['write_attempted']
                if result['write_attempted']:
                    if 'write_finished_ns' not in result:
                        try:
                            result['write_finished_ns'] = self._now()
                        except Exception:
                            result['write_finished_ns'] = None
                    result['status'] = 'WRITE_UNCERTAIN_NO_RETRY'
            finally:
                self._permit.revoke()
            return result
