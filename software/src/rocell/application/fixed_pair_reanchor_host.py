"""One-shot authenticated re-anchor/export coordinator; construction is inert.

The caller must supply a freshly verified r54 transport, reviewed plan and boot
identity. No retry, return, or next campaign is initiated on any failure.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import time

from .first_motion_contract import canonical
from .fixed_pair_reanchor_record import (
    RECORD_BYTES, assess_fixed_pair_reanchor_record,
    replay_fixed_pair_reanchor_fixture,
)
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class FixedPairReanchorHost:
    def __init__(self, transport, *, export_root, boot, plan):
        if plan.get('schema') != 'rocell.fixed_pair_reanchor_plan.v1':
            raise ValueError('Reviewed re-anchor plan required')
        self.transport = transport
        self.export_root = Path(export_root).resolve()
        self.boot = boot
        self.plan = plan
        self.used = False

    def run_once(self, *, deadline_seconds=12, clock=time.monotonic, pause=time.sleep):
        if self.used or type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= 15:
            raise ValueError('One bounded re-anchor run only')
        self.used = True  # Sticky even if delivery or export fails.
        end = clock() + deadline_seconds
        response = self.transport('POST', '/rocell/reanchor/start', b'')
        if response != b'CAPTURING_START':
            raise ValueError('Re-anchor start not accepted')
        while True:
            if clock() >= end:
                raise TimeoutError('Re-anchor outcome uncertain; no retry')
            status = self.transport('GET', '/rocell/reanchor/status')
            if status == b'AWAITING_DURABLE_EXPORT|1':
                break
            if status not in (b'CAPTURING_START|0', b'PREWRITE|0',
                              b'CAPTURING_ENDPOINT|1'):
                raise ValueError('Re-anchor fault or unknown state; no retry')
            pause(min(0.1, max(0, end-clock())))
        encoded = self.transport('GET', '/rocell/reanchor/record')
        if (type(encoded) is not bytes or len(encoded) != 2*RECORD_BYTES or
                encoded.lower() != encoded):
            raise ValueError('Invalid authenticated re-anchor record framing')
        try:
            raw = bytes.fromhex(encoded.decode('ascii'))
        except (UnicodeError, ValueError) as error:
            raise ValueError('Invalid re-anchor record hex') from error
        if raw.hex().encode('ascii') != encoded:
            raise ValueError('Noncanonical re-anchor record')
        assessment = assess_fixed_pair_reanchor_record(raw, expected_boot=self.boot,
                                                        plan=self.plan)
        exporter = WizardDiagnosticExporter(self.export_root)
        exporter.prepare(create=True)
        saved = exporter.export({'mode': 'fixed-pair-reanchor-live-result'}, [], attachments={
            'fixed-pair-reanchor.hex.txt': encoded,
            'fixed-pair-reanchor-assessment.json': canonical(assessment),
        })
        folder = Path(saved['path'])
        if not verify_export(folder)['valid'] or replay_fixed_pair_reanchor_fixture(
                self.export_root, folder.name, expected_boot=self.boot,
                plan=self.plan) != assessment:
            raise ValueError('Durable re-anchor export could not be replayed')
        # Only the exact retained bytes, now independently checked and exported,
        # are acknowledged. A lost response is not retried on this boot.
        receipt = self.transport('POST', '/rocell/reanchor/receipt',
                                 hashlib.sha256(raw).hexdigest().encode('ascii'))
        if receipt != b'REANCHOR_VERIFIED':
            raise ValueError('Re-anchor receipt uncertain; do not continue')
        return dict(export=str(folder), assessment=assessment,
                    physical_motion_proven=False, continuation_authorized=False)
