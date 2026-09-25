"""Exclusively freeze r30 plus the local-step board composition. No hardware I/O."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r30/RoArm-M3_example/'
    report,receipt=_read(exports,'wizard-20260919T221302697829Z-343bb03334ac4b208bac6495cef8dc99','attachment-compile-review.json')
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    if report['status']!='COMPILED' or set(expected)!=set(files) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned r30 source differs')
    changes={}
    for name in ('shoulder_preload_candidate.h','shoulder_board_session.h','local_shoulder_step_contract.h',
                 'local_shoulder_step_authorization.h','local_shoulder_step_session.h',
                 'local_shoulder_step_routes.h','local_shoulder_step_board.h'):
        raw=(root/'firmware/diagnostics'/name).read_bytes()
        if name=='shoulder_board_session.h':raw=b'#define ROCELL_LOCAL_SHOULDER_STEP 1\n'+raw
        changes[name]=dict(before=sha(files[name]) if name in files else None,after=sha(raw));files[name]=raw
    target=root/'.firmware-tools/configured-diagnostic-candidate-r31/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback failed')
    evidence=dict(schema='rocell.local_step_stage.v1',revision=31,predecessor_compile_receipt=receipt,
        changed_files=changes,capture_records=3,step_range_counts=[12,24],maximum_actual_travel_counts=32,
        maximum_target_packets=1,explicit_torque_commands=0,heap_reserve_bytes=32768,
        command_id='local-step-1',live_release_binding=False,hardware_access=False,uploaded=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r31-local-step-stage'},[],attachments={'local-step-stage.json':canonical(evidence)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    print(saved['path'])


if __name__=='__main__':main()
