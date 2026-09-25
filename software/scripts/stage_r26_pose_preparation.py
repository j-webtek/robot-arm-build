"""Freeze finite auxiliary-joint preparation from verified r25; no hardware I/O."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r25/RoArm-M3_example/'
    source=root/prefix;target=root/'.firmware-tools/configured-diagnostic-candidate-r26/RoArm-M3_example'
    report,receipt=_read(exports,'wizard-20260919T193954046321Z-8795999b45a94b96b3392ff91af09e7f',
        'attachment-compile-review.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    if report['status']!='COMPILED' or set(files)!=set(expected) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned r25 source differs')
    changes={}
    for name in ('shoulder_preload_session.h','shoulder_authorized_start.h','shoulder_board_session.h','shoulder_hold_event_json.h'):
        raw=(root/'firmware/diagnostics'/name).read_bytes()
        if name=='shoulder_board_session.h':raw=b'#define ROCELL_POSE_PREPARATION 1\n'+raw
        if raw==files[name]:raise ValueError('Expected integration change missing')
        changes[name]=dict(before=sha(files[name]),after=sha(raw));files[name]=raw
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback differs')
    evidence=dict(schema='rocell.pose_preparation_stage.v1',revision=26,
        predecessor_compile_receipt=receipt,changed_files=changes,
        command_id='pose-preparation-v1',scope='POSE_PREPARATION',
        maximum_target_writes=4,explicit_torque_commands=0,commanded_travel=False,
        target_writes_may_activate_servos=True,
        hardware_access=False,uploaded=False,settings_modified=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r26-pose-preparation-stage'},[],attachments={'pose-preparation-stage.json':canonical(evidence)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    print(saved['path'])


if __name__=='__main__':main()
