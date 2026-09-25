"""Hardware-free elbow initialization model; proposals never authorize I/O.

Snapshots are simulated decoded registers, NOT raw-read/provenance validation.
Native ownership, signed admission and durable exports must precede deployment.
The model deliberately has no transport, reset, torque-release or retry method.
"""
from dataclasses import dataclass

from .servo_diagnostic_contract import _integer


@dataclass(frozen=True)
class Joint:
    position: int
    goal: int
    torque: int
    mode: int = 0
    moving: int = 0


@dataclass(frozen=True)
class Snapshot:
    """Ordered IDs 11..17 on one simulated monotonic clock."""
    started_us: int
    finished_us: int
    joints: tuple[Joint, ...]


@dataclass(frozen=True)
class Limits:
    max_age_us: int = 250_000
    max_scan_us: int = 100_000
    min_baseline_gap_us: int = 100_000
    settle_us: int = 100_000
    deadline_us: int = 2_000_000
    drift_counts: int = 2
    speed: int = 20
    acceleration: int = 1


class HoldInitializationModel:
    """One elbow hold, optionally one explicit enable, then stable readback.

Each operation is consumed when proposed, before its ACK. Losing an ACK faults
even if the simulated actuator executed it. Faults retain partial state; they
never cause a compensating write or torque release. Export failure also latches.
"""
    progression_authority = False
    origin = 'SIMULATION'

    def __init__(self, *, allow_enable=False, limits=Limits(), supported_recovery=False,
                 recovery_limit=5):
        if type(recovery_limit) is not int or recovery_limit not in (5,6) or (not supported_recovery and recovery_limit!=5):
            raise ValueError('Explicit reviewed recovery limit required')
        self.recovery_limit=recovery_limit
        if type(allow_enable) is not bool or type(limits) is not Limits:
            raise ValueError('Explicit simulated policy required')
        for name in ('max_age_us', 'max_scan_us', 'min_baseline_gap_us',
                     'settle_us', 'deadline_us'):
            _integer(getattr(limits, name), 1, 10_000_000)
        _integer(limits.drift_counts, 0, 8)
        _integer(limits.speed, 1, 40)
        _integer(limits.acceleration, 1, 1)
        if type(supported_recovery) is not bool or (supported_recovery and
                (allow_enable or limits.drift_counts != 2 or limits.speed != 20)):
            raise ValueError('Recovery requires enabled-only hold with unchanged tolerances')
        self.supported_recovery = supported_recovery
        self.limits = limits
        self.allow_enable = allow_enable
        self.state = 'NEW'
        self.reason = None
        self.actions = []
        self.original = None
        self.last = None
        self.target = None
        self.pending_us = None
        self.stable_since = None

    def _fail(self, reason):
        # Preserve the first causal fault if a caller tries to reuse this model.
        if self.state == 'FAULT':
            raise ValueError(self.reason)
        self.state = 'FAULT'
        self.reason = reason
        raise ValueError(reason)

    def _require(self, *states):
        if self.state not in states:
            self._fail('INVALID_PHASE')

    def _scan(self, scan, now):
        try:
            _integer(now)
            if type(scan) is not Snapshot or type(scan.joints) is not tuple or len(scan.joints) != 7:
                raise ValueError('shape')
            _integer(scan.started_us)
            _integer(scan.finished_us)
            if not scan.started_us <= scan.finished_us <= now:
                raise ValueError('clock')
            if (now - scan.started_us > self.limits.max_age_us or
                    scan.finished_us - scan.started_us > self.limits.max_scan_us):
                raise ValueError('age')
            if self.last and scan.started_us <= self.last.finished_us:
                raise ValueError('replayed scan')
            for joint in scan.joints:
                if type(joint) is not Joint:
                    raise ValueError('joint')
                _integer(joint.position, 0, 4095)
                _integer(joint.goal, 0, 4095)
                _integer(joint.torque, 0, 1)
                _integer(joint.mode, 0, 0)
                _integer(joint.moving, 0, 0)
            if self.supported_recovery:
                elbow = scan.joints[3]
                if elbow.torque != 1 or (self.target is None and abs(elbow.position-elbow.goal) > self.recovery_limit):
                    raise ValueError('Recovery torque or initial residual')
            if self.original:
                if now - self.original.started_us > self.limits.deadline_us:
                    raise ValueError('deadline')
                for index, (original, observed) in enumerate(zip(self.original.joints, scan.joints)):
                    if abs(observed.position - original.position) > self.limits.drift_counts:
                        raise ValueError('drift')
                    if index != 3 and (observed.goal, observed.torque) != (original.goal, original.torque):
                        raise ValueError('neighbor change')
        except (ValueError, TypeError):
            self._fail('INVALID_OR_CHANGED_SNAPSHOT')

    def baseline(self, first, second, *, now_us):
        self._require('NEW')
        self._scan(first, first.finished_us)
        self.original = self.last = first
        self._scan(second, now_us)
        if (second.started_us - first.finished_us < self.limits.min_baseline_gap_us or
                any((a.goal, a.torque) != (b.goal, b.torque)
                    for a, b in zip(first.joints, second.joints)) or
                (first.joints[3].torque == 1 and
                 abs(first.joints[3].position-first.joints[3].goal)>
                 (self.recovery_limit if self.supported_recovery else self.limits.drift_counts))):
            self._fail('BASELINE_MISMATCH')
        self.last = second
        self.state = 'READY_HOLD'

    def propose(self, scan, *, now_us):
        """Return immutable simulation bytes, never an executable transport call."""
        self._require('READY_HOLD', 'READY_ENABLE')
        self._scan(scan, now_us)
        elbow = scan.joints[3]
        if self.state == 'READY_HOLD':
            if (elbow.goal, elbow.torque) != (self.original.joints[3].goal, self.original.joints[3].torque):
                self._fail('ELBOW_CHANGED_BEFORE_HOLD')
            self.target = elbow.position
            # SMS_STS WritePosEx layout: acc, little-endian goal, time=0, speed.
            data = (bytes([self.limits.acceleration]) + self.target.to_bytes(2, 'little') +
                    b'\x00\x00' + self.limits.speed.to_bytes(2, 'little'))
            action = (14, 41, data)
            self.state = 'WAIT_HOLD_ACK'
        else:
            if (not self.allow_enable or elbow.torque != 0 or elbow.goal != self.target or
                    abs(elbow.position - self.target) > self.limits.drift_counts):
                self._fail('ENABLE_NOT_ELIGIBLE')
            action = (14, 40, b'\x01')
            self.state = 'WAIT_ENABLE_ACK'
        self.last = scan
        self.pending_us = now_us
        self.actions.append(action)
        return action

    def acknowledge(self, *, success, finished_us):
        self._require('WAIT_HOLD_ACK', 'WAIT_ENABLE_ACK')
        try:
            _integer(finished_us)
            if (success is not True or not self.pending_us <= finished_us or
                    finished_us - self.original.started_us > self.limits.deadline_us):
                raise ValueError('ack')
        except ValueError:
            self._fail('UNCERTAIN_ACK')
        self.state = 'READ_HOLD' if self.state == 'WAIT_HOLD_ACK' else 'READ_ENABLE'
        self.pending_us = finished_us

    def observe(self, scan, *, now_us):
        self._require('READ_HOLD', 'READ_ENABLE', 'SETTLING')
        self._scan(scan, now_us)
        elbow = scan.joints[3]
        if (scan.started_us <= self.pending_us or elbow.goal != self.target or
                abs(elbow.position - self.target) > self.limits.drift_counts):
            self._fail('HOLD_READBACK_MISMATCH')
        self.last = scan
        if elbow.torque == 0:
            if self.state != 'READ_HOLD' or not self.allow_enable or self.original.joints[3].torque != 0:
                self._fail('TORQUE_NOT_ENABLED')
            self.state = 'READY_ENABLE'
            return self.state
        if self.stable_since is None:
            self.stable_since = scan.finished_us
        self.state = ('AWAIT_EXPORT' if scan.started_us - self.stable_since >= self.limits.settle_us
                      else 'SETTLING')
        return self.state

    def finish_export(self, *, verified):
        self._require('AWAIT_EXPORT')
        if verified is not True:
            self._fail('EXPORT_FAILED')
        self.state = 'SIMULATED_ELBOW_HELD'
        # This is partial initialization, NOT all-arm motion readiness.
        return dict(origin=self.origin, state=self.state, servo_id=14,
                    target_count=self.target, action_count=len(self.actions),
                    whole_arm_ready=False, progression_authority=False)
