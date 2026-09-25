"""Stage only the two-header fault-evidence correction; never access hardware."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    source=root/'.firmware-tools/configured-diagnostic-candidate-r23/RoArm-M3_example'
    target=root/'.firmware-tools/configured-diagnostic-candidate-r24/RoArm-M3_example'
    report,receipt=_read(exports,'wizard-20260919T182939587224Z-a44b766fe9a943deabd1777fb22ce582',
                         'attachment-compile-review.json')
    sha=lambda b:hashlib.sha256(b).hexdigest()
    prefix='.firmware-tools/configured-diagnostic-candidate-r23/RoArm-M3_example/'
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    if report['status']!='COMPILED' or set(files)!=set(expected) or any(sha(b)!=expected[n] for n,b in files.items()):
        raise ValueError('Pinned r23 inventory mismatch')
    changes={}
    for name in ('shoulder_preload_session.h','shoulder_hold_event_json.h'):
        updated=(root/'firmware/diagnostics'/name).read_bytes()
        if updated==files[name]:raise ValueError('Expected fault retention correction missing')
        changes[name]=dict(before=sha(files[name]),after=sha(updated));files[name]=updated
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback mismatch')
    result=dict(schema='rocell.shoulder_failure_stage.v1',revision=24,
        predecessor_compile_receipt=receipt,changed_files=changes,hardware_access=False,
        movement_limits_changed=False,additional_servo_operations=False,uploaded=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r24-fault-retention-stage'},[],attachments={'shoulder-failure-stage.json':canonical(result)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export invalid')
    print(saved['path'])


if __name__=='__main__':main()
