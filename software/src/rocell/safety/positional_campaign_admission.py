"""One-open, finite per-leg admission state machine. No native facade accepts it yet.

Uses current authenticated context and durable, original-bound records. Returned
command bytes are for the future exact native composition, not a serial shortcut.
This module never opens devices, retries writes, homes, or clears a stop.
"""
import base64
import hashlib
import math
import os
from threading import Lock

from .positional_campaign_authority import PositionalCampaignIntent, require_correction_start, verify_campaign_endpoint, campaign_joint_index
from rocell.providers.windows.positional_current_context import AuthenticatedPositionalReader
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import (
    safe_root,contained_path,publish_reservation_bytes,read_bounded_regular_file,
)
from rocell.arm.first_motion_analysis import _window
from rocell.arm.campaign_stream_sync import campaign_window, campaign_post_window, FRAMED_SCHEMAS, CampaignFramingError
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
from rocell.arm.protocol import encode_line

_ISSUER = object()


class BaselineAgeExceeded(ValueError):
    """Structured recency failure; never exports arbitrary exception text."""
    def __init__(self,phase,age_ns):
        super().__init__('Selected baseline expired: '+phase)
        self.diagnostic=dict(reason='SELECTED_BASELINE_EXPIRED',phase=phase,
            selected_sample_age_ns=age_ns,maximum_age_ns=250_000_000)


class PositionalCampaignAdmission:
    """Burn-before-check states; any uncertain boundary permanently holds the run."""
    def __init__(self,issuer,request,reader,root,evidence):
        if issuer is not _ISSUER:
            raise ValueError('Campaign admission factory required')
        self.request,self._reader,self._root = request,reader,safe_root(root)
        self._record_limit = 2_097_152 if request.to_dict()['schema'] in ('rocell.attended_positional_intent.v18','rocell.attended_positional_intent.v19','rocell.attended_positional_intent.v20','rocell.attended_positional_intent.v21','rocell.attended_positional_intent.v22') else 262144
        self._bundle,self._port = evidence['bundle_sha256'],evidence['port_name']
        self._last,self._pid = evidence['verified_at_ns'],os.getpid()
        self._state,self._next,self._lock = 'ADMITTED',0,Lock()
        self._originals,self._total_bytes = {},0
        self._previous = request.sha256
        self._last_endpoint = tuple(request.to_dict()['start_joints_rad'])
        self._publish('owner',dict(intent=request.to_dict(),review_sha256=self._bundle,
            pid=self._pid,replay_allowed=False,motion_authorized=False))

    def _publish(self,stage,body):
        name=self.request.to_dict()['campaign_id']+'-'+stage+'.json'
        raw=canonical(body)
        try:
            # The supervisor pins this directory against rename. These are
            # one-use campaign records, not shared ledger commits. CREATE_NEW,
            # flush and exact readback must finish before state can advance;
            # an incomplete record remains consumed/held, never repaired.
            publish_reservation_bytes(self._root,name,raw,maximum_bytes=self._record_limit)
            path=contained_path(self._root,name,label='campaign admission record')
            if read_bounded_regular_file(path,maximum_bytes=self._record_limit)!=raw:
                raise ValueError('Campaign admission readback failed')
            self._originals[name]=raw
        except BaseException:
            self._state='HELD'
            raise
        return hashlib.sha256(raw).hexdigest()

    def _check(self):
        if os.getpid()!=self._pid:
            raise ValueError('Campaign process ownership changed')
        for name,raw in self._originals.items():
            if read_bounded_regular_file(contained_path(self._root,name,label='campaign original'),maximum_bytes=self._record_limit)!=raw:
                raise ValueError('Campaign original changed')
        evidence=self._reader.verify_endpoint(self._port)
        if evidence['bundle_sha256']!=self._bundle or evidence['verified_at_ns']<self._last:
            raise ValueError('Campaign context changed or clock regressed')
        self._last=evidence['verified_at_ns']
        return self._last

    def claim_open(self):
        with self._lock:
            if self._state!='ADMITTED': raise ValueError('Campaign open consumed or held')
            self._state='HELD'
            self.request.require_start_time(self._check())
            self._publish('open',dict(intent_sha256=self.request.sha256,claimed_ns=self._last,
                open_may_have_occurred=True,replay_allowed=False))
            self._ready_ns=self._last
            self._state='OPEN_CLAIMED'

    def _capture(self,raw,windows,started_ns,finished_ns,duration_ns,*,write_started_ns=None,write_finished_ns=None):
        # Decode the immutable request once per boundary, not once per sample.
        # This is only a local copy; authenticated context is still rechecked.
        body=self.request.to_dict()
        capture_duration = (int(body['limits']['baseline_s']*1_000_000_000)
            if duration_ns==1_000_000_000 else duration_ns)
        if (type(raw) is not bytes or len(raw)>body['limits']['maximum_raw_bytes_per_leg'] or type(started_ns) is not int
                or type(finished_ns) is not int or finished_ns-started_ns<capture_duration
                or finished_ns-started_ns>capture_duration+250_000_000
                or not body['issued_ns']<=started_ns<finished_ns<=self._last):
            raise ValueError('Capture byte, duration or ownership bounds invalid')
        framing=None
        if duration_ns!=1_000_000_000 and body['schema'] in FRAMED_SCHEMAS:
            rows,issues,framing=campaign_post_window(body,raw,windows,started_ns,finished_ns,
                baseline_raw=base64.b64decode(self._baseline['raw_base64'],validate=True),
                baseline_windows=self._baseline['read_windows'],
                write_started_ns=write_started_ns,write_finished_ns=write_finished_ns)
        else:
            rows,issues,_=campaign_window(body,'baseline' if duration_ns==1_000_000_000 else 'post',raw,windows,started_ns,finished_ns,
                maximum_bytes=body['limits']['maximum_raw_bytes_per_leg'])
        if issues or len(rows)<(10 if duration_ns==1_000_000_000 else 20):
            if framing is not None:
                raise CampaignFramingError('POST_FEEDBACK_INVALID')
            raise ValueError('Complete clean campaign feedback required')
        self._total_bytes+=len(raw)
        if self._total_bytes>body['limits']['maximum_total_raw_bytes']:
            raise ValueError('Campaign raw byte budget exceeded')
        capture=dict(raw_base64=base64.b64encode(raw).decode(),read_windows=windows,
            started_ns=started_ns,finished_ns=finished_ns,raw_sha256=hashlib.sha256(raw).hexdigest())
        if framing is not None:
            capture['cross_window_framing']=framing
        return rows,capture

    def bind_baseline(self,raw,windows,*,started_ns,finished_ns):
        with self._lock:
            body=self.request.to_dict()
            if self._state!='OPEN_CLAIMED' or self._next>=len(body['legs']):
                raise ValueError('No next eligible campaign baseline')
            self._state='HELD'
            now=self._check()
            rows,capture=self._capture(raw,windows,started_ns,finished_ns,1_000_000_000)
            leg=body['legs'][self._next]
            start=rows[-1][2]
            axis=campaign_joint_index(body)
            if (started_ns<self._ready_ns or now-finished_ns>100_000_000 or now-rows[-1][1]>250_000_000
                    or now+(len(body['legs'])-self._next)*body['limits']['maximum_leg_s']*1_000_000_000+2_000_000_000>body['deadline_ns']
                    or any(max(row[2][i] for row in rows)-min(row[2][i] for row in rows)>math.radians(.1) for i in range(6))
                    or any(abs(start[i]-self._last_endpoint[i])>math.radians(.5) for i in range(6))
                    or abs(start[axis]-leg['expected_start_rad'])>math.radians(.5)
                    or abs(start[axis])>math.radians(10)
                    or abs(leg['target_rad']-start[axis])>math.radians(5)):
                raise ValueError('Baseline drift, stability, recency or remaining budget failed')
            for row in rows:
                require_correction_start(body, row[2], leg)
            self._baseline,self._start,self._acquired = capture,start,rows[-1][1]
            self._leg_bytes=len(raw)
            self._payload=encode_line(leg['command'])
            self._leg_start_ns=started_ns
            self._publish(leg['leg_id']+'-reserved',dict(intent_sha256=self.request.sha256,
                leg=leg,baseline=capture,predecessor_sha256=self._previous,
                command_sha256=hashlib.sha256(self._payload).hexdigest(),replay_allowed=False))
            self._state='BOUND'
            return dict(leg_id=leg['leg_id'],target_rad=leg['target_rad'],motion_authorized=False)

    def consume_command(self):
        with self._lock:
            if self._state!='BOUND': raise ValueError('No unconsumed campaign command')
            self._state='HELD'
            now=self._check()
            self.request.require_remaining_time(now, phase='dispatch')
            if now-self._acquired>250_000_000:
                raise BaselineAgeExceeded('BEFORE_DISPATCH_CLAIM',now-self._acquired)
            leg=self.request.to_dict()['legs'][self._next]
            self._publish(leg['leg_id']+'-dispatch',dict(intent_sha256=self.request.sha256,
                command_sha256=hashlib.sha256(self._payload).hexdigest(),claimed_ns=now,
                submission_may_have_occurred=True,replay_allowed=False))
            # Reservation IO may consume the recency budget. Recheck after it,
            # leaving an irrevocable claim if the boundary is now too late.
            self._dispatch_ns=self._check()
            self.request.require_remaining_time(self._dispatch_ns, phase='dispatch')
            if self._dispatch_ns-self._acquired>250_000_000:
                raise BaselineAgeExceeded('AFTER_DISPATCH_CLAIM',self._dispatch_ns-self._acquired)
            self._state='DISPATCHED'
            return self._payload

    def check_dispatch_time(self, dispatch_ns):
        """Final incapable-executor check after consumption, with no storage IO.

        This cannot preempt an OS pause or qualify a native dispatch boundary.
        A failed time check burns the existing claim; it never issues another.
        """
        with self._lock:
            self._require_dispatch_time(dispatch_ns)

    def _require_dispatch_time(self, dispatch_ns):
        # Caller holds the admission lock. This helper performs no storage IO.
        if self._state != 'DISPATCHED':
            raise ValueError('No consumed campaign command awaiting dispatch')
        if (type(dispatch_ns) is not int or os.getpid() != self._pid
                or not self._dispatch_ns <= dispatch_ns < 2**63
                or dispatch_ns-self._acquired > 250_000_000
                or dispatch_ns+(self.request.to_dict()['limits']['observation_s']+3)*1_000_000_000 > self.request.to_dict()['deadline_ns']):
            self._state = 'HELD'
            raise ValueError('Campaign command expired before submission')

    def claim_submission(self, payload, dispatch_ns):
        """Consume the exact next submission once, separately from reservation.

        A failure burns this leg. A successful call records only that submission
        may follow, not that bytes reached a controller. The owned caller must
        retain actual write accounting and must never retry an uncertain write.
        """
        with self._lock:
            self._require_dispatch_time(dispatch_ns)
            self._state = 'HELD'
            if type(payload) is not bytes or payload != self._payload:
                raise ValueError('Exact reserved campaign payload required')
            self._state = 'SUBMITTED'

    def validate_connection_open(self, connection_id, port_name):
        """Recheck the claimed first connection immediately before DLL access."""
        with self._lock:
            if (self._state != 'OPEN_CLAIMED' or self._next != 0
                    or connection_id != self.request.to_dict()['campaign_id']
                    or port_name != self._port):
                raise ValueError('Exact first campaign connection required')
            self.request.require_start_time(self._check())

    def selected_payload(self):
        with self._lock:
            if self._state != 'DISPATCHED':
                raise ValueError('No reserved campaign payload awaiting submission')
            return self._payload

    def require_leg_start(self, leg_id, now_ns):
        with self._lock:
            if (self._state != 'OPEN_CLAIMED' or self._next >= len(self.request.to_dict()['legs'])
                    or leg_id != self.request.to_dict()['legs'][self._next]['leg_id']):
                raise ValueError('Verified predecessor and exact next campaign leg required')
            self._check()
            self.request.require_remaining_time(now_ns, phase='leg')

    def commit_endpoint(self,raw,windows,*,started_ns,finished_ns,confirmed_write_bytes,
                        write_finished_ns,write_uncertain,write_started_ns=None):
        with self._lock:
            if self._state!='SUBMITTED': raise ValueError('No submitted campaign leg')
            self._state='HELD'
            self._check()
            # Observation deadline is anchored to actual write completion. A
            # small collector-start delay must not extend it or make it fail
            # merely because the measured collector duration is slightly <5 s.
            observation_ns=self.request.to_dict()['limits']['observation_s']*1_000_000_000
            if (type(write_finished_ns) is not int or type(started_ns) is not int
                    or type(finished_ns) is not int
                    or not 0<=started_ns-write_finished_ns<=100_000_000
                    or not observation_ns<=finished_ns-write_finished_ns<=observation_ns+150_000_000):
                raise ValueError('Post window must remain anchored to write completion')
            rows,capture=self._capture(raw,windows,started_ns,finished_ns,observation_ns-100_000_000,
                write_started_ns=write_started_ns,write_finished_ns=write_finished_ns)
            if self._leg_bytes+len(raw)>self.request.to_dict()['limits']['maximum_raw_bytes_per_leg']:
                raise ValueError('Per-leg combined raw byte budget exceeded')
            leg=self.request.to_dict()['legs'][self._next]
            clean=(type(confirmed_write_bytes) is int and confirmed_write_bytes==len(self._payload)
                and write_uncertain is False and type(write_finished_ns) is int
                and self._dispatch_ns<=write_finished_ns<=started_ns
                and write_finished_ns-self._dispatch_ns<=1_000_000_000
                and finished_ns-self._leg_start_ns<=self.request.to_dict()['limits']['maximum_leg_s']*1_000_000_000)
            endpoint=verify_campaign_endpoint(self.request.to_dict(),leg,rows,start=self._start,
                capture_issues=(),transport_clean=clean,
                write_finished_ns=write_finished_ns,capture_finished_ns=finished_ns)
            result=dict(intent_sha256=self.request.sha256,leg_id=leg['leg_id'],
                predecessor_sha256=self._previous,post=capture,endpoint=endpoint,
                confirmed_write_bytes=confirmed_write_bytes,write_uncertain=write_uncertain,
                write_finished_ns=write_finished_ns,dispatch_claimed_ns=self._dispatch_ns,replay_allowed=False)
            digest=self._publish(leg['leg_id']+'-result',result)
            if endpoint['endpoint_verified']:
                self._previous,self._last_endpoint=digest,rows[-1][2]
                self._ready_ns=finished_ns
                self._next+=1
                self._state='COMPLETE' if self._next==len(self.request.to_dict()['legs']) else 'OPEN_CLAIMED'
            return dict(endpoint=endpoint,state=self._state,committed_sha256=digest,
                dispatch_claimed_ns=self._dispatch_ns,native_execution_released=False)

    def revoke(self):
        with self._lock:
            self._state='HELD'


def admit_positional_campaign(request,*,reader,root):
    if (type(request) is not PositionalCampaignIntent or type(reader) is not AuthenticatedPositionalReader
            or reader.request!=request):
        raise ValueError('Exact campaign and authenticated current reader required')
    evidence=reader.verify_endpoint()
    request.require_start_time(evidence['verified_at_ns'])
    return PositionalCampaignAdmission(_ISSUER,request,reader,root,evidence)
