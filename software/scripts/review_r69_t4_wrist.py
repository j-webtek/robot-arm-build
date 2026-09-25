"""Offline r69 source, binary and partition review. No controller access."""
import hashlib
from pathlib import Path

from stage_r69_t4_wrist import specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE = 'wizard-20260924T095347591688Z-949670757f6f46a6a8afa540063e58db'
STAGE = 'wizard-20260924T095113509627Z-9b3a3bd4412748d985f8532d2d4ebd6f'
APP_SHA = '121a4c5b98c7fbb6e94ad448ac056341c284530416bf583c690850792b12a7a8'


def review(root):
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE, 'attachment-r69-t4-wrist-stage.json')
    sha = lambda data: hashlib.sha256(data).hexdigest()
    prefix = '.firmware-tools/configured-diagnostic-candidate-r69/RoArm-M3_example/'
    old = root/'.firmware-tools/configured-diagnostic-candidate-r67/RoArm-M3_example'
    expected = specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()})
    actual = {p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    hashes = {p.replace('\\','/'):h for p,h in compiled['source_hashes'].items()}
    if (actual != expected or compiled['status'] != 'COMPILED' or
            compiled['target'] != 'configured-diagnostic-candidate-r69' or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            any(hashes.get(prefix+k) != sha(v) for k,v in actual.items()) or
            staged['selector'] != 'T4' or staged['path_review']['maximum_write_attempts'] != 1 or
            staged['path_review']['retry_allowed'] or staged['path_review']['return_allowed']):
        raise ValueError('r69 source or stage differs')
    build = root/'.firmware-tools/build-configured-diagnostic-candidate-r69--default-4mb-no-psram'
    image = (build/'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or len(image) > 0x140000 or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not all(s in image for s in (b'RCT4WRST01', b'LARGE_POSE_T4_RECORDED',
                                        b'/rocell/large-pose-relief/start'))):
        raise ValueError('r69 binary differs')
    for suffix, digest in (
        ('bootloader.bin','b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin','148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        name = 'RoArm-M3_example.ino.'+suffix
        if sha((build/name).read_bytes()) != digest or compiled['artifact_hashes'][name] != digest:
            raise ValueError('Bootloader or partition differs')
    report = dict(schema='rocell.r69_t4_wrist_review.v1', app_sha256=APP_SHA,
        app_bytes=len(image), app_offset=0x10000, app_slot_bytes=0x140000,
        compile_export_id=COMPILE, compile_report_sha256=compile_digest,
        stage_export_id=STAGE, stage_report_sha256=stage_digest,
        source_pose='T4L', target_pose='T4', synchronized_servo_ids=[15],
        targets=[1915], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'r69-t4-wrist-review'}, [], attachments={
        'r69-t4-wrist-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Review export invalid')
    return saved['path']


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1]))
