"""Export an offline explanation of the captured r10 baseline failure."""
import hashlib
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.hold_transport_export import replay_hold_transport_bundle
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    identity='wizard-20260919T022349264443Z-a35770140cab466ba6640bc3c2af2010'
    bundle,source_sha=_read(exports,identity,'attachment-hold-transport.json')
    summary=replay_hold_transport_bundle(bundle)['summary']
    if summary['category']!='TRANSPORT_CAPTURED' or not summary['stable_status_observed']:
        raise ValueError('Stable exported failure required')
    auth,scan,terminal=summary['records']
    if (summary['status']['state']!='FAULT' or terminal['action_count']!=0 or
            terminal['reason']!='CONTROL_READ_INVALID' or scan['complete'] is not False or
            auth['authentication_verified'] is not True):
        raise ValueError('Unexpected baseline failure')
    previous,failed=scan['reads'][-2:]
    sequence,start,finish,count,error,success,raw=failed[3]
    if (failed[:3]!=[15,33,1] or count!=1 or error!=0 or success is not False or raw is not None
            or start!=previous[3][2] or finish<start or sequence!=8):
        raise ValueError('Captured timing boundary differs')
    installed=root/'.firmware-tools/configured-diagnostic-candidate-r10/RoArm-M3_example/servo_control_state_read.h'
    code=installed.read_bytes()
    if b'r.started_us>previous' not in code:
        raise ValueError('Installed candidate timing predicate differs')
    report=dict(schema='rocell.r10_hold_timing_fault_review.v1',source_export_id=identity,
        source_sha256=source_sha,boot_id=scan['boot_id'],command_id=scan['command_id'],
        controller_reported_action_count=terminal['action_count'],servo_id=15,register_address=33,
        returned_bytes=count,device_error=error,previous_read_finished_us=previous[3][2],
        failed_read_started_us=start,failed_read_finished_us=finish,
        installed_source_sha256=hashlib.sha256(code).hexdigest(),
        cause='STRICT_ADJACENT_TIMESTAMP_COMPARISON',
        interpretation='Successful-length, zero-device-error read rejected at equal microsecond boundary.',
        raw_byte_discarded_by_firmware=True,endpoint_verified=False,
        hardware_access=False,firmware_deployed=False,retry_allowed=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r10-hold-timing-fault-review'},[],
        attachments={'r10-hold-timing-fault-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export verification failed')
    print(json.dumps(dict(export_path=saved['path'],report=report)))


if __name__=='__main__':main()
