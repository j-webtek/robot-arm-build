"""One wizard-owned zero-write USB capture bracketed by read-only HTTP probes.

Requires explicit standing-setup acknowledgement. Does not retry an attempt,
send motion/configuration commands, or substitute a raw serial implementation.
"""
import argparse
import json
import time
from pathlib import Path
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
from rocell.providers.windows.arm_wifi_deadline import bounded_probe


class ActionTracker:
    """Keep only references in the wrapper; raw evidence belongs to wizard exports.

    A polling timeout is not completion. Retain the exact operation handle so
    callers cannot start another action while the owner may still be running.
    """
    def __init__(self, service, record, *, clock=time.monotonic, sleep=time.sleep):
        self.service, self.record = service, record
        self.clock, self.sleep = clock, sleep
        self.pending_id = None

    def __call__(self, name, values):
        if self.pending_id is not None:
            raise RuntimeError('Unresolved operation; do not start another action')
        ticket = self.service.prepare_action(name, values, self.service.view()['revision'])
        # If dispatch raises, delivery is uncertain; keep a sentinel, not a false
        # idle state. Shutdown remains the owner's responsibility.
        self.pending_id = 'DISPATCH_UNCERTAIN'
        receipt = self.service.execute_action(ticket['ticket_id'])
        self.pending_id = receipt['operation_id']
        entry = dict(name=name, operation_id=self.pending_id, status='PENDING')
        self.record.setdefault('actions', []).append(entry)
        deadline = self.clock() + 60
        while self.clock() < deadline:
            operation = self.service.operation(self.pending_id)
            entry['status'] = operation['status']
            if operation['status'] not in ('QUEUED', 'RUNNING'):
                self.pending_id = None
                if operation['status'] != 'SUCCEEDED':
                    raise RuntimeError(name + ': ' + operation['status'])
                return operation
            self.sleep(.05)
        raise RuntimeError('Pending operation; do not retry')


def timed_probe():
    """Bracket HTTP in the USB collector's monotonic clock domain.

    Python 3.10 on Windows can use different clocks for perf_counter and
    monotonic. Keep the original transport timing, but never compare it directly
    to serial monotonic timestamps without an explicit common-clock bracket.
    """
    started = time.monotonic_ns()
    result = bounded_probe(retain_response=True)
    finished = time.monotonic_ns()
    result['host_monotonic_started_ns'] = started
    result['host_monotonic_finished_ns'] = finished
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standing-powered-clear-setup',action='store_true',required=True)
    args=parser.parse_args()
    workspace=Path(__file__).resolve().parents[2]
    service=ArrivalWizardService(workspace,mode='physical')
    record=dict(schema='rocell.usb_http_capture.v1',setup_basis='USER_STANDING_POWERED_SECURED_CLEAR_ASSUMPTION',
                motion_commands=0,serial_command_writes_requested=0)
    action = ActionTracker(service, record)
    try:
        with arm_transport_lock():
            record['http_before']=timed_probe()
            if record['http_before']['status']!='SUCCEEDED':raise RuntimeError('HTTP baseline unavailable')
            action('inventory_devices',dict(metadata_only=True))
            candidates=service.view()['device_selection']['devices']['SERIAL']['candidates']
            matches=[c for c in candidates if (c.get('vid'),c.get('pid'),c.get('unit_serial'))==
                ('10c4','ea60','52E4E1E8337FEF119E92181CEDD322A4')]
            if len(matches)!=1 or matches[0].get('identity_blockers'):raise RuntimeError('Exact USB unit unavailable')
            action('review_arm_candidate',dict(choice_id=matches[0]['choice_id'],reviewer_id='bench-identity-review',metadata_only=True))
            action('inspect_native_arm_metadata',dict(metadata_only=True))
            action('record_powered_arm_startup',dict(operator_id='user-standing-setup',adapter_on=True,
                usb_connected=True,secured_and_clear=True,stationary=True,startup_motion='unknown'))
            record['capture_started_ns']=time.perf_counter_ns()
            action('capture_powered_arm_telemetry',dict(firmware_unchanged=True))
            record['capture_finished_ns']=time.perf_counter_ns()
            record['http_after']=timed_probe()
    except Exception as exc:
        record['error']=str(exc)
    finally:
        # Shutdown the owner before any further operation if capture is pending.
        pending = action.pending_id is not None
        record['unresolved_operation_id'] = action.pending_id
        if not pending:
            try:
                exported=action('export_logs',{})
                record['wizard_export']=exported['result']['receipt']['path']
            except Exception as exc:record['export_error']=str(exc)
        service.shutdown()
        exporter=WizardDiagnosticExporter((workspace/'software/runs/wizard-exports').resolve())
        exporter.prepare(create=True)
        receipt=exporter.export(dict(mode='usb-http-diagnostic'),[],attachments={
            'usb-http-capture.json':json.dumps(record,allow_nan=False).encode()})
        assert verify_export(Path(receipt['path']).resolve())['valid']
        print(json.dumps(dict(export=receipt['path'],error=record.get('error'),wizard_export=record.get('wizard_export'),
            http_after_status=(record.get('http_after') or {}).get('status'))))


if __name__=='__main__':main()
