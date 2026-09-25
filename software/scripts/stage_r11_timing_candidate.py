"""Offline build staging from an immutable predecessor and explicit corrections.

No device, private filesystem image, credentials or deployment is involved.
Generated build inputs are copied to a fresh directory, never over an old build.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description='Offline staging of reviewed diagnostic corrections.')
    parser.add_argument('--revision',type=int,choices=(11,12,13,14),default=11)
    revision=parser.parse_args().revision
    root=Path(__file__).resolve().parents[1];tools=root/'.firmware-tools'
    source=tools/f'configured-diagnostic-candidate-r{revision-1}/RoArm-M3_example'
    target=tools/f'configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
    source_export={
        11:'wizard-20260919T012312312556Z-dd795d7c04f14f68ba11fbc96b7059a0',
        12:'wizard-20260919T023057492784Z-505d17097d1848248a31226581d8b2f2',
        13:'wizard-20260919T025548595225Z-0bd78758280d4d598f4fd9a25e4bc443',
        14:'wizard-20260919T031028594578Z-700a0b7e52de427495497de6fbf3d9f6',
    }[revision]
    report,report_sha=_read(root/'runs/wizard-exports',
        source_export,'attachment-compile-review.json')
    replacements=(('servo_control_state_read.h','servo_evidence.h','hold_state_snapshot.h') if revision==11
        else ('hold_initialization_owner.h',))
    if revision==14:
        replacements=('configured_pair_board_routes.h','held_pair_authenticated_runtime.h')
    files={}
    changes={}
    for path in source.iterdir():
        if not path.is_file() or path.suffix not in ('.h','.ino') or path.is_symlink():
            raise ValueError('Unexpected candidate source entry')
        raw=path.read_bytes();old=hashlib.sha256(raw).hexdigest()
        if report['source_hashes'][str(path.relative_to(root))]!=old:
            raise ValueError('Retained predecessor source changed')
        selected=root/'firmware/diagnostics'/path.name if path.name in replacements else path
        files[path.name]=selected
        if path.name in replacements:
            new=hashlib.sha256(selected.read_bytes()).hexdigest()
            if new==old:raise ValueError('Expected reviewed timing change missing')
            changes[path.name]=dict(before_sha256=old,after_sha256=new)
    if set(changes)!=set(replacements):raise ValueError('Incomplete timing replacements')
    if revision==14:
        for name in ('elbow_configuration_snapshot.h','elbow_configuration_json.h','elbow_configuration_routes.h'):
            if name in files:raise ValueError('New source collides with predecessor')
            files[name]=root/'firmware/diagnostics'/name
            changes[name]=dict(before_sha256=None,after_sha256=hashlib.sha256(files[name].read_bytes()).hexdigest())
    target.mkdir(parents=True,exist_ok=False)
    for name,path in files.items():shutil.copyfile(path,target/name)
    for name,path in files.items():
        if (target/name).read_bytes()!=path.read_bytes():raise ValueError('Staged source differs')
    label={11:'r11-timing',12:'r12-powered-hold',13:'r13-postwrite-dwell',14:'r14-config-readonly'}[revision]
    review=dict(schema=f'rocell.{label.replace("-","_")}_stage.v1',source_compile_sha256=report_sha,
        changed_files=changes,unchanged_files=len(files)-len(changes),
        hardware_access=False,firmware_uploaded=False,provisioning_performed=False)
    exporter=WizardDiagnosticExporter(root/'runs/wizard-exports');exporter.prepare(create=True)
    saved=exporter.export({'mode':label+'-stage'},[],
        attachments={label+'-stage.json':canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'],**review)).decode())


if __name__=='__main__':main()
