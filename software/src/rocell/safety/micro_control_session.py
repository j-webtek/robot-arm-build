"""Continuous cooperative ownership for staged micro-command commissioning.

This binds participating-process history, not exclusive physical control:
external web/SDK clients do not honor the mutex. No socket sender lives here.
"""
from contextlib import contextmanager
import hashlib
import os
import threading
import time

from rocell.application.first_motion_contract import canonical
from .micro_command_admission import MicroCommandAdmission


class MicroControlSession:
    """One process/thread, one lease, one predecessor, one staged boundary claim.

    Native composition must use this scope for the WHOLE predecessor command,
    observation, export, fresh baseline and possible micro attempt, never acquire
    a new scope around an old export. This object alone cannot detect external I/O.
    """
    def __init__(self, *, lease_factory, clock_ns=time.perf_counter_ns):
        self._lease_factory=lease_factory;self._clock=clock_ns
        self._state='NEW';self._pid=os.getpid();self._thread=threading.get_ident()
        self._last=None;self._admission=None

    def _now(self):
        if os.getpid()!=self._pid or threading.get_ident()!=self._thread:
            self._state='FAULT';raise ValueError('Session owner changed')
        now=self._clock()
        if type(now) is not int or now<=0 or self._last is not None and now<self._last:
            self._state='FAULT';raise ValueError('Session clock invalid')
        self._last=now
        return now

    @contextmanager
    def scope(self):
        if self._state!='NEW':raise ValueError('Session is not reusable')
        self._state='ACQUIRING'
        try:
            with self._lease_factory():
                self._start=self._now();self._state='OPEN'
                yield self
        finally:
            self._state='CLOSED'

    def predecessor_intent(self):
        """Must be recorded before entering the existing 0.95-degree sender."""
        if self._state!='OPEN':raise ValueError('One predecessor intent required')
        self._intent=self._now();self._state='PREDECESSOR_PENDING'

    def bind(self, admission):
        """Bind a replayed staged admission created while this lease remained held."""
        if self._state!='PREDECESSOR_PENDING':raise ValueError('Predecessor intent missing')
        self._state='FAULT'
        now=self._now()
        if type(admission) is not MicroCommandAdmission:raise ValueError('Exact staged admission required')
        context=admission.snapshot();prior=context['predecessor']
        if (not self._intent<=prior['dispatch_ns']<=prior['finished_ns']<=context['created_ns']<=now
                or now>context['expires_ns'] or context['owner_pid']!=self._pid):
            raise ValueError('Predecessor/session timing mismatch')
        self._context=context;self._admission=admission;self._state='BOUND'

    def claim_staged_boundary(self, payload, *, cancelled=False):
        """Burn before checking; returns audit metadata, not native authorization.

        The eventual sender must still enforce socket deadlines and identity.
        A separate claim is necessary because consume/replay can exhaust freshness.
        """
        if self._state!='BOUND':raise ValueError('Staged boundary unavailable')
        self._state='CLAIMED'
        self._now()
        receipt=self._admission.consumed_receipt()
        now=self._now()  # Disk verification may consume the remaining freshness.
        if (type(cancelled) is not bool or cancelled or type(payload) is not bytes
                or payload!=canonical(self._context['command'])
                or not self._context['created_ns']<=receipt['consumed_ns']<=now<=self._context['expires_ns']
                or receipt['attempt_id']!=self._context['attempt_id']):
            raise ValueError('Staged boundary mismatch or expiry')
        return dict(schema='rocell.micro_cooperative_boundary.v1',claimed_ns=now,
                    payload_sha256=hashlib.sha256(payload).hexdigest(),
                    attempt_id=receipt['attempt_id'],cooperative_scope_checked=True,
                    exclusive_external_control_proven=False,native_enabled=False,
                    motion_authorized=False)
