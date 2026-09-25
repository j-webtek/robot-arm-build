"""Durable one-use correction review consumption; no serial or native permit.

Reserve an attempt before consumption and burn its claim before returning data.
Any failure leaves this object held; reconstructing it cannot overwrite the
reservation. Device ownership and native dispatch are separate integration work.
"""
import hashlib
import json
import os
from threading import Lock

from rocell.arm.protocol import encode_line
from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority
from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)


class WristCorrectionConsumption:
    def __init__(self, *, authority, bundle, context, originals, samples, basis, root, clock_ns):
        if type(authority) is not WristCorrectionReviewAuthority or not callable(clock_ns):
            raise ValueError('Exact trusted correction authority and clock required')
        if type(bundle) is not bytes or type(originals) is not list:
            raise ValueError('Immutable bundle and original evidence list required')
        self._authority, self._bundle, self._clock = authority, bundle, clock_ns
        # Prevent caller mutation after validation. Original requests and wire
        # bytes are immutable; preview validation enforces their exact types.
        self._context = json.loads(canonical(context))
        self._samples = json.loads(canonical(samples))
        self._originals = list(originals)
        self._basis, self._root = basis, safe_root(root)
        self._pid, self._last = os.getpid(), 0
        self._state, self._lock, self._records = 'HELD', Lock(), []
        evidence = self._verify()
        self._intent = evidence['intent_sha256']
        self._save('reservation', dict(schema='rocell.wrist_correction_reservation.v1',
            intent_sha256=self._intent, bundle_sha256=evidence['bundle_sha256'],
            owner_pid=self._pid, motion_authorized=False))
        self._state = 'RESERVED'

    def _save(self, suffix, body):
        name = self._context['attempt_id']+'-wrist-correction-'+suffix+'.json'
        raw = canonical(body)
        publish_reservation_bytes(self._root,name,raw,maximum_bytes=16384)
        self._records.append((name,hashlib.sha256(raw).hexdigest()))

    def _verify(self):
        now = self._clock()
        if os.getpid()!=self._pid or type(now) is not int or now < self._last:
            raise ValueError('Correction process changed or clock regressed')
        for name,digest in self._records:
            raw=read_bounded_regular_file(contained_path(self._root,name,label='correction claim'),maximum_bytes=16384)
            if hashlib.sha256(raw).hexdigest()!=digest:
                raise ValueError('Correction consumption record changed')
        evidence=self._authority.verify(self._bundle, expected_context=self._context,
            originals=self._originals,samples=self._samples,now_ns=now,expected_basis=self._basis)
        self._last=now
        return evidence

    def consume(self):
        """Return exact reviewed data only after durable claim and revalidation.

        This receipt is intentionally not accepted by native serial facades.
        It does not certify that a command was sent or completed.
        """
        with self._lock:
            if self._state!='RESERVED':
                raise ValueError('Correction already consumed or held')
            self._state='HELD'
            evidence=self._verify()
            payload=encode_line(evidence['candidate_command'])
            claim=dict(schema='rocell.wrist_correction_consumption.v1',
                intent_sha256=self._intent,bundle_sha256=evidence['bundle_sha256'],
                claimed_ns=self._last,payload_sha256=hashlib.sha256(payload).hexdigest(),
                nominal_endpoint_rad=evidence['nominal_endpoint_rad'],
                candidate_command=evidence['candidate_command'],
                motion_authorized=False,native_dispatch_implemented=False)
            self._save('consumed',claim)
            self._verify()
            self._state='CONSUMED'
            return claim

    def revoke(self):
        with self._lock:
            self._state='HELD'
