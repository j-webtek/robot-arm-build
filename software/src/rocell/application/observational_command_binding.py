"""Bind one baseline-derived command to one owned observational connection.

This is a command-selection latch, NOT an open/write permit. A native executor
must additionally enforce its authenticated unit/session admission. Durable
reservation prevents replay of the same attempt after a worker restart.
"""
import hashlib
import re
from threading import Lock

from rocell.arm.observational_wrist_analysis import preview_from_capture
from rocell.arm.protocol import encode_line
from rocell.motion.observational_wrist_plan import ONE_DEGREE_POLICY, policy_degrees
from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)


# Host receipt-to-dispatch allowance for the stationary, bounded wrist profile.
# Includes capture closing time and authenticated dispatch checks. This is not
# a servo freshness guarantee and does not relax measured-motion policies.
MAX_SELECTED_BASELINE_AGE_NS = 250_000_000


class ObservationalCommandBinding:
    """Reserve -> derive from owned baseline -> consume once, or permanently hold.

    No copied preview or arbitrary command can be supplied. Returned bytes are
    selection data only; existing native facades deliberately do not accept this
    class as a permit. It performs no USB access or metadata discovery.
    """

    def __init__(self, *, root, session_id, attempt_id, connection_id,
                 usb_identity, issued_ns, deadline_ns, direction=-1, policy=ONE_DEGREE_POLICY):
        if (type(session_id) is not str or not re.fullmatch(r'wizard-[a-f0-9]{32}', session_id)
                or type(attempt_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', attempt_id)
                or connection_id != attempt_id):
            raise ValueError('Exact session, attempt and owned connection IDs required')
        if (type(usb_identity) is not dict or set(usb_identity) != {'vid', 'pid', 'serial_number'}
                or type(usb_identity['vid']) is not int or usb_identity['vid'] != 0x10c4
                or type(usb_identity['pid']) is not int or usb_identity['pid'] != 0xea60
                or type(usb_identity['serial_number']) is not str
                or not re.fullmatch(r'[A-F0-9]{32}', usb_identity['serial_number'])):
            raise ValueError('Expected USB unit identity required')
        if (type(issued_ns) is not int or type(deadline_ns) is not int
                or not 0 < issued_ns < deadline_ns < 2**63
                or not 11_000_000_000 <= deadline_ns-issued_ns <= 30_000_000_000
                or type(direction) is not int or direction not in (-1, 1)):
            raise ValueError('Bounded observational selection required')
        self._root = safe_root(root)
        self._session, self._attempt, self._connection = session_id, attempt_id, connection_id
        self._identity = canonical(usb_identity)
        self._issued, self._deadline, self._last = issued_ns, deadline_ns, issued_ns
        policy_degrees(policy)
        self._direction, self._policy = direction, policy
        self._lock = Lock()
        self._state = 'RESERVED'
        self._payload = self._selection_sha = self._acquired_ns = None
        name = attempt_id + '-observational-command-reservation.json'
        self._reservation_path = contained_path(self._root, name, label='observational reservation')
        original = canonical(dict(schema='rocell.observational_command_reservation.v1',
            session_id=session_id, attempt_id=attempt_id, connection_id=connection_id,
            usb_identity=usb_identity, issued_ns=issued_ns, deadline_ns=deadline_ns,
            direction=direction, policy=policy, physical_authority=False))
        self._reservation_sha = hashlib.sha256(original).hexdigest()
        publish_reservation_bytes(self._root, name, original, maximum_bytes=8192)

    def _context(self, session_id, connection_id, usb_identity, now_ns):
        if (session_id != self._session or connection_id != self._connection
                or canonical(usb_identity) != self._identity
                or type(now_ns) is not int or not self._last <= now_ns < self._deadline):
            raise ValueError('Observational connection context changed or expired')
        self._last = now_ns
        raw = read_bounded_regular_file(self._reservation_path, maximum_bytes=8192)
        if hashlib.sha256(raw).hexdigest() != self._reservation_sha:
            raise ValueError('Observational reservation changed')

    def bind_baseline(self, raw, read_windows, *, started_ns, finished_ns,
                      session_id, connection_id, usb_identity, now_ns):
        with self._lock:
            if self._state != 'RESERVED':
                raise ValueError('Baseline selection already attempted')
            self._state = 'HELD'  # Any interrupted/failed derivation burns this attempt.
            self._context(session_id, connection_id, usb_identity, now_ns)
            if type(started_ns) is not int or started_ns < self._issued:
                raise ValueError('Baseline predates this owned attempt')
            preview = preview_from_capture(raw, read_windows, started_ns=started_ns,
                finished_ns=finished_ns, now_ns=now_ns, direction=self._direction, policy=self._policy)
            if now_ns-finished_ns > 100_000_000 or now_ns+8_000_000_000 > self._deadline:
                raise ValueError('Baseline recency or remaining trial budget exceeded')
            selection = canonical(dict(schema='rocell.observational_command_selection.v1',
                session_id=self._session, attempt_id=self._attempt,
                connection_id=self._connection, usb_identity=usb_identity,
                preview=preview, selected_ns=now_ns, physical_authority=False))
            name = self._attempt + '-observational-command-selection.json'
            publish_reservation_bytes(self._root, name, selection, maximum_bytes=16384)
            self._selection_path = contained_path(self._root, name, label='observational selection')
            self._selection_sha = hashlib.sha256(selection).hexdigest()
            self._payload = encode_line(preview['candidate_command'])
            self._acquired_ns = preview['baseline_last_host_received_ns']
            self._state = 'BOUND'
            return dict(preview=preview, selection_sha256=self._selection_sha,
                        motion_authorized=False)

    def consume_command(self, *, session_id, connection_id, usb_identity, now_ns):
        with self._lock:
            if self._state != 'BOUND':
                raise ValueError('No unconsumed observational command')
            self._state = 'CONSUMED'
            self._context(session_id, connection_id, usb_identity, now_ns)
            if now_ns-self._acquired_ns > MAX_SELECTED_BASELINE_AGE_NS or now_ns+8_000_000_000 > self._deadline:
                raise ValueError('Selected baseline or remaining trial budget expired')
            raw = read_bounded_regular_file(self._selection_path, maximum_bytes=16384)
            if hashlib.sha256(raw).hexdigest() != self._selection_sha:
                raise ValueError('Retained observational selection changed')
            return self._payload

    def revoke(self):
        with self._lock:
            self._state = 'HELD'
