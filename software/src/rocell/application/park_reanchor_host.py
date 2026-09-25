"""One-use authenticated host coordinator for a fixed shoulder return.

Construction is inert. A caller must separately verify startup identity,
prior-boot pose evidence, physical clearance and one-use claim before run_once.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import time

from .first_motion_contract import canonical
from .park_reanchor_record import (
    RECORD_BYTES, assess_park_reanchor_record, export_park_reanchor_record,
)
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class ParkReanchorHost:
    def __init__(self, transport, *, export_root, boot, plan):
        valid_plan = ((plan.get('schema') == 'rocell.park_reanchor_plan.v1' and
                       plan.get('target_goals') == [2389, 1725]) or
                      (plan.get('schema') == 'rocell.visible_shoulder_step_plan.v1' and
                       plan.get('target_goals') == [2413, 1701]))
        if (not valid_plan or
                plan.get('movement_authorized') is not False or
                plan.get('observation_boot') == boot or
                plan.get('physical_clearance_verified') is not False):
            raise ValueError('Reviewed inert return plan required')
        self.transport = transport
        self.export_root = Path(export_root).resolve()
        self.boot = boot
        self.plan = plan
        self.used = False

    def _read_record(self):
        encoded = self.transport('GET', '/rocell/park-return/record')
        if (type(encoded) is not bytes or len(encoded) != 2 * RECORD_BYTES or
                encoded.lower() != encoded):
            raise ValueError('Invalid authenticated return record framing')
        try:
            raw = bytes.fromhex(encoded.decode('ascii'))
        except (UnicodeError, ValueError) as error:
            raise ValueError('Invalid return record hex') from error
        if raw.hex().encode('ascii') != encoded:
            raise ValueError('Noncanonical return record')
        return raw

    def run_once(self, *, deadline_seconds=12, clock=time.monotonic,
                 pause=time.sleep):
        if (self.used or type(deadline_seconds) not in (int, float) or
                not 0 < deadline_seconds <= 15):
            raise ValueError('One bounded return run only')
        self.used = True
        end = clock() + deadline_seconds
        # Verify the authenticated route is idle on this exact boot before
        # sending the only request that can activate a servo. Reuse the same
        # transport so its signed sequence remains continuous.
        if self.transport('GET', '/rocell/park-return/status') != b'NEW|0':
            raise ValueError('Return route not idle; no movement or retry')
        if self.transport('POST', '/rocell/park-return/start') != b'CAPTURING_START':
            raise ValueError('Return start not accepted; no retry')
        while True:
            if clock() >= end:
                raise TimeoutError('Return outcome uncertain; no retry')
            status = self.transport('GET', '/rocell/park-return/status')
            if status == b'AWAITING_DURABLE_EXPORT|1':
                break
            if status not in (b'CAPTURING_START|0', b'PREWRITE|0',
                              b'CAPTURING_ENDPOINT|1'):
                # Export status even if the raw fault record is unavailable.
                # A fault record can never get a success receipt.
                saved_record = None
                record_error = None
                if status.endswith(b'|1'):
                    try:
                        raw = self._read_record()
                        assessed = assess_park_reanchor_record(
                            raw, expected_boot=self.boot, plan=self.plan)
                        if assessed['status'] != 'FAULT_RECORDED':
                            raise ValueError('Fault status has success record')
                        saved_record = export_park_reanchor_record(
                            self.export_root, raw, expected_boot=self.boot,
                            plan=self.plan, mode='park-return-live-fault')
                    except (OSError, ValueError, UnicodeError, TimeoutError) as error:
                        record_error = type(error).__name__
                exporter = WizardDiagnosticExporter(self.export_root)
                exporter.prepare(create=True)
                saved = exporter.export({'mode': 'park-return-terminal-fault'}, [],
                                        attachments={
                    'park-return-terminal-status.txt': status,
                    'park-return-terminal-context.json': canonical({
                        'schema': 'rocell.park_reanchor_terminal_fault.v1',
                        'boot': self.boot, 'retry_allowed': False,
                        'endpoint_verified': False,
                        'movement_may_have_occurred': status.endswith(b'|1'),
                        'fault_record_export': saved_record,
                        'fault_record_error': record_error,
                    }),
                })
                if not verify_export(Path(saved['path']))['valid']:
                    raise ValueError('Return terminal export failed; no retry')
                raise ValueError('Return terminal fault exported: ' + str(saved['path']))
            pause(min(0.1, max(0, end-clock())))
        raw = self._read_record()
        assessed = assess_park_reanchor_record(raw, expected_boot=self.boot,
                                                plan=self.plan)
        expected = ('MEASURED_VISIBLE_STEP'
                    if self.plan['schema'] == 'rocell.visible_shoulder_step_plan.v1'
                    else 'MEASURED_RETURN')
        if assessed['status'] != expected:
            raise ValueError('Success status has fault record; no receipt')
        saved = export_park_reanchor_record(self.export_root, raw,
                                            expected_boot=self.boot,
                                            plan=self.plan,
                                            mode='park-return-live-result')
        receipt = self.transport('POST', '/rocell/park-return/receipt',
                                 hashlib.sha256(raw).hexdigest().encode('ascii'))
        if receipt != b'RETURN_RECORDED':
            raise ValueError('Return receipt uncertain; do not continue')
        return {'export': saved, 'assessment': assessed,
                'physical_clearance_proven': False,
                'continuation_authorized': False}
