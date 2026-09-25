"""Authenticated one-step host coordinator; inert until run_once is called.

The caller supplies a verified transport, fresh boot binding and offline plan.
No retry, return, follow-on step or physical clearance claim is issued.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import time

from .park_step_record import (RECORD_BYTES, assess_park_step_record,
                               decode_park_step_record, replay_park_step_record)
from .first_motion_contract import canonical
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class ParkStepHost:
    def __init__(self, transport, *, export_root, boot, plan):
        if (plan.get('schema') != 'rocell.first_park_step_plan.v1' or
                plan.get('target_goals') != [2377, 1737] or
                plan.get('movement_authorized') is not False or
                plan.get('observation_boot') == boot or
                plan.get('physical_clearance_verified') is not False):
            raise ValueError('Reviewed inert first-step plan required')
        self.transport = transport
        self.export_root = Path(export_root).resolve()
        self.boot = boot
        self.plan = plan
        self.used = False

    def run_once(self, *, deadline_seconds=12, clock=time.monotonic, pause=time.sleep):
        if self.used or type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= 15:
            raise ValueError('One bounded park-step run only')
        self.used = True
        end = clock() + deadline_seconds
        response = self.transport('POST', '/rocell/park-step/start', b'2377,1737')
        if response != b'CAPTURING_START':
            raise ValueError('Park-step start not accepted')
        while True:
            if clock() >= end:
                raise TimeoutError('Park-step outcome uncertain; no retry')
            status = self.transport('GET', '/rocell/park-step/status')
            if status == b'AWAITING_DURABLE_EXPORT|1':
                break
            if status not in (b'CAPTURING_START|0', b'PREWRITE|0',
                              b'CAPTURING_ENDPOINT|1'):
                # Keep the authenticated terminal bytes even when native
                # firmware cannot expose its failed endpoint samples. A
                # timeout record is diagnostic only, never a success receipt.
                attachments = {'park-step-terminal-status.txt': status}
                fault_record_error = None
                if status == b'ENDPOINT_TIMEOUT|1':
                    try:
                        encoded = self.transport('GET', '/rocell/park-step/record')
                        if (type(encoded) is not bytes or len(encoded) != 2*RECORD_BYTES or
                                encoded.lower() != encoded):
                            raise ValueError('Invalid fault record framing')
                        raw = bytes.fromhex(encoded.decode('ascii'))
                        record = decode_park_step_record(raw)
                        if (record['boot'] != self.boot or
                                record['target_goals'] != self.plan['target_goals']):
                            raise ValueError('Fault record identity mismatch')
                        attachments['park-step-fault.hex.txt'] = encoded
                    except (OSError, ValueError, UnicodeError, TimeoutError) as error:
                        fault_record_error = type(error).__name__
                exporter = WizardDiagnosticExporter(self.export_root)
                exporter.prepare(create=True)
                attachments['park-step-terminal-context.json'] = canonical(dict(
                    schema='rocell.park_step_terminal_fault.v1', boot=self.boot,
                    target_goals=self.plan['target_goals'], retry_allowed=False,
                    endpoint_verified=False, movement_may_have_occurred=True,
                    fault_record_retained='park-step-fault.hex.txt' in attachments,
                    fault_record_error=fault_record_error))
                saved = exporter.export({'mode': 'park-step-terminal-fault'}, [], attachments={
                    **attachments})
                if not verify_export(Path(saved['path']))['valid']:
                    raise ValueError('Park-step terminal fault export failed; no retry')
                raise ValueError('Park-step terminal fault exported: ' + str(saved['path']))
            pause(min(0.1, max(0, end-clock())))
        encoded = self.transport('GET', '/rocell/park-step/record')
        if (type(encoded) is not bytes or len(encoded) != 2*RECORD_BYTES or
                encoded.lower() != encoded):
            raise ValueError('Invalid authenticated park-step record framing')
        try:
            raw = bytes.fromhex(encoded.decode('ascii'))
        except (UnicodeError, ValueError) as error:
            raise ValueError('Invalid park-step record hex') from error
        if raw.hex().encode('ascii') != encoded:
            raise ValueError('Noncanonical park-step record')
        assessment = assess_park_step_record(raw, expected_boot=self.boot,
                                             plan=self.plan)
        exporter = WizardDiagnosticExporter(self.export_root)
        exporter.prepare(create=True)
        saved = exporter.export({'mode': 'park-step-live-result'}, [], attachments={
            'park-step.hex.txt': encoded,
            'park-step-assessment.json': canonical(assessment),
        })
        folder = Path(saved['path'])
        if not verify_export(folder)['valid'] or replay_park_step_record(
                self.export_root, folder.name, expected_boot=self.boot,
                plan=self.plan) != assessment:
            raise ValueError('Park-step export could not be replayed')
        receipt = self.transport('POST', '/rocell/park-step/receipt',
                                 hashlib.sha256(raw).hexdigest().encode('ascii'))
        if receipt != b'PARK_STEP_RECORDED':
            raise ValueError('Park-step receipt uncertain; do not continue')
        return dict(export=str(folder), assessment=assessment,
                    physical_rise_proven=False, continuation_authorized=False)
