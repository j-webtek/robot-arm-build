"""Offline r65 source, binary and partition review. No controller access."""
import hashlib
from pathlib import Path

from stage_r65_p2_wrist import specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE = 'wizard-20260923T195319510419Z-f65208d64d6c478ca3fc038249eee01f'
STAGE = 'wizard-20260923T195119093561Z-2da9d751633f4de5b22ce349fb0650c2'
APP_SHA = '7ed18ca356194e2b226936c5146e46ec079c326d8140667a07a49923b935b4de'


def review(root):
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE, 'attachment-r65-p2-wrist-stage.json')
    sha = lambda data: hashlib.sha256(data).hexdigest()
    prefix = '.firmware-tools/configured-diagnostic-candidate-r65/RoArm-M3_example/'
    old = root/'.firmware-tools/configured-diagnostic-candidate-r64/RoArm-M3_example'
    expected = specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()})
    actual = {p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    hashes = {p.replace('\\','/'):h for p,h in compiled['source_hashes'].items()}
    if (actual != expected or compiled['status'] != 'COMPILED' or
            compiled['target'] != 'configured-diagnostic-candidate-r65' or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            any(hashes.get(prefix+k) != sha(v) for k,v in actual.items()) or
            staged['selector'] != 'P2' or staged['path_review']['maximum_write_attempts'] != 1 or
            staged['path_review']['retry_allowed'] or staged['path_review']['return_allowed']):
        raise ValueError('r65 source or stage differs')
    build = root/'.firmware-tools/build-configured-diagnostic-candidate-r65--default-4mb-no-psram'
    image = (build/'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or len(image) > 0x140000 or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not all(s in image for s in (b'RCP2WRST01', b'LARGE_POSE_P2_RECORDED',
                                        b'/rocell/large-pose-relief/start'))):
        raise ValueError('r65 binary differs')
    for suffix, digest in (
        ('bootloader.bin','b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin','148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        name = 'RoArm-M3_example.ino.'+suffix
        if sha((build/name).read_bytes()) != digest or compiled['artifact_hashes'][name] != digest:
            raise ValueError('Bootloader or partition differs')
    report = dict(schema='rocell.r65_p2_wrist_review.v1', app_sha256=APP_SHA,
        app_bytes=len(image), app_offset=0x10000, app_slot_bytes=0x140000,
        compile_export_id=COMPILE, compile_report_sha256=compile_digest,
        stage_export_id=STAGE, stage_report_sha256=stage_digest,
        source_pose='P2L', target_pose='P2', synchronized_servo_ids=[15],
        targets=[1785], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'r65-p2-wrist-review'}, [], attachments={
        'r65-p2-wrist-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Review export invalid')
    return saved['path']


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1]))
