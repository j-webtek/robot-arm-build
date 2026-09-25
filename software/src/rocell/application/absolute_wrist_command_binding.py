"""Durable one-use absolute diagnostic selection; not a native serial permit.

Reserve before possible opening, retain the owned baseline before selection,
and burn dispatch before returning bytes. A crash cannot resume this latch.
The native composition must still enforce its own exact IO/process boundary.
"""
import base64
import hashlib
import os
from threading import Lock

from rocell.arm.protocol import encode_line
from rocell.motion.absolute_wrist_diagnostic import (
    AbsoluteWristDiagnosticDraft, preview_absolute_wrist_from_capture,
)
from rocell.providers.windows.absolute_wrist_current_context import AuthenticatedAbsoluteWristReader
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .first_motion_contract import canonical
from .observational_command_binding import MAX_SELECTED_BASELINE_AGE_NS
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)


class AbsoluteWristCommandBinding:
    def __init__(self, request, *, reader, root):
        if (type(request) is not AbsoluteWristIntent
                or type(reader) is not AuthenticatedAbsoluteWristReader or reader.request != request):
            raise ValueError('Exact absolute intent and authenticated reader required')
        evidence = reader.verify_endpoint()
        request.require_start_time(evidence['verified_at_ns'])
        self._request, self._reader, self._root = request, reader, safe_root(root)
        self._body = request.to_dict()
        self._port, self._bundle = evidence['port_name'], evidence['bundle_sha256']
        self._last, self._pid = evidence['verified_at_ns'], os.getpid()
        self._state, self._lock, self._records = 'RESERVED', Lock(), []
        self._save('reservation', dict(request=self._body, bundle_sha256=self._bundle,
                   port_name=self._port, owner_pid=self._pid, motion_authorized=False))

    def _save(self, suffix, body):
        name = self._body['attempt_id'] + '-absolute-wrist-' + suffix + '.json'
        raw = canonical(body)
        publish_reservation_bytes(self._root, name, raw, maximum_bytes=65536)
        self._records.append((name, hashlib.sha256(raw).hexdigest()))

    def _check(self):
        if os.getpid() != self._pid:
            raise ValueError('Absolute diagnostic process ownership changed')
        for name, digest in self._records:
            raw = read_bounded_regular_file(contained_path(self._root, name,
                label='absolute diagnostic original'), maximum_bytes=65536)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('Absolute diagnostic original changed')
        evidence = self._reader.verify_endpoint(self._port)
        now = evidence['verified_at_ns']
        if evidence['bundle_sha256'] != self._bundle or now < self._last:
            raise ValueError('Absolute review changed or clock moved backwards')
        self._last = now
        return now

    def claim_open(self):
        """One ownership claim only; does not open hardware or grant IO authority."""
        with self._lock:
            if self._state != 'RESERVED':
                raise ValueError('Open claim already consumed or held')
            self._state = 'HELD'
            self._request.require_start_time(self._check())
            self._save('open-claim', dict(request_sha256=self._request.request_sha256))
            self._request.require_start_time(self._check())
            self._state = 'OPEN_CLAIMED'

    def validate_open_claim(self):
        with self._lock:
            if self._state != 'OPEN_CLAIMED':
                raise ValueError('No current absolute open claim')
            try:
                self._request.require_start_time(self._check())
            except Exception:
                self._state = 'HELD'
                raise

    def selected_payload(self):
        """Exact token-construction data only; dispatch must still consume once."""
        with self._lock:
            if self._state != 'BOUND':
                raise ValueError('No current absolute selection')
            return self._payload

    def bind_baseline(self, raw, windows, *, started_ns, finished_ns):
        with self._lock:
            if self._state != 'OPEN_CLAIMED':
                raise ValueError('Owned open claim required before baseline')
            self._state = 'HELD'
            now = self._check()
            if (type(raw) is not bytes or len(raw) > 16384
                    or type(windows) is not list or len(windows) > 256
                    or type(started_ns) is not int or type(finished_ns) is not int
                    or started_ns < self._body['issued_ns']
                    or not 0 < finished_ns - started_ns <= 1_000_000_000
                    or not 0 <= now - finished_ns <= 100_000_000
                    or now + 8_000_000_000 > self._body['deadline_ns']):
                raise ValueError('Bounded current owned baseline and remaining budget required')
            draft = AbsoluteWristDiagnosticDraft(canonical(self._body['draft']))
            preview = preview_absolute_wrist_from_capture(draft, raw, windows,
                started_ns=started_ns, finished_ns=finished_ns, now_ns=now)
            self._save('selection', dict(request_sha256=self._request.request_sha256,
                raw_base64=base64.b64encode(raw).decode('ascii'), read_windows=windows,
                started_ns=started_ns, finished_ns=finished_ns, preview=preview))
            self._payload = encode_line(preview['candidate_command'])
            self._acquired = preview['baseline_last_host_received_ns']
            self._state = 'BOUND'
            return preview

    def consume_command(self):
        """Durably burn once, recheck freshness after storage, return selection data."""
        with self._lock:
            if self._state != 'BOUND':
                raise ValueError('No unconsumed absolute selection')
            self._state = 'HELD'
            now = self._check()
            self._save('dispatch-claim', dict(request_sha256=self._request.request_sha256,
                payload_sha256=hashlib.sha256(self._payload).hexdigest(), claimed_ns=now))
            now = self._check()
            if (now - self._acquired > MAX_SELECTED_BASELINE_AGE_NS
                    or now + 8_000_000_000 > self._body['deadline_ns']):
                raise ValueError('Selected baseline or remaining capture budget expired')
            self._state = 'CONSUMED'
            return self._payload

    def revoke(self):
        with self._lock:
            self._state = 'HELD'
