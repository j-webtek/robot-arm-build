"""Offline r68 source, binary and partition review. No controller access."""
import hashlib
from pathlib import Path

from stage_r68_t4_lift import specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE = 'wizard-20260924T001828074672Z-b9c72a2480324229ac8283124d0e3e35'
STAGE = 'wizard-20260924T001621373379Z-062b05bcaec148b9b6a6729d1a416f4e'
APP_SHA = '70ea81de94d578360a6afb68462b1e87b660b0c7a4bf1d5c644491ba7136dbad'


def review(root):
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE, 'attachment-r68-t4-lift-stage.json')
    sha = lambda data: hashlib.sha256(data).hexdigest()
    prefix = '.firmware-tools/configured-diagnostic-candidate-r68/RoArm-M3_example/'
    old = root/'.firmware-tools/configured-diagnostic-candidate-r64/RoArm-M3_example'
    expected = specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()})
    actual = {p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    hashes = {p.replace('\\','/'):h for p,h in compiled['source_hashes'].items()}
    if (actual != expected or compiled['status'] != 'COMPILED' or
            compiled['target'] != 'configured-diagnostic-candidate-r68' or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            any(hashes.get(prefix+k) != sha(v) for k,v in actual.items()) or
            staged['selector'] != 'T4L' or staged['path_review']['next_command']['maximum_writes'] != 1 or
            staged['path_review']['retry_allowed'] or staged['return_allowed']):
        raise ValueError('r68 source or stage differs')
    build = root/'.firmware-tools/build-configured-diagnostic-candidate-r68--default-4mb-no-psram'
    image = (build/'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or len(image) > 0x140000 or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not all(s in image for s in (b'RCT4LIFT01', b'LARGE_POSE_T4L_RECORDED',
                                        b'/rocell/large-pose-relief/start'))):
        raise ValueError('r68 binary differs')
    for suffix, digest in (
        ('bootloader.bin','b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin','148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        name = 'RoArm-M3_example.ino.'+suffix
        if sha((build/name).read_bytes()) != digest or compiled['artifact_hashes'][name] != digest:
            raise ValueError('Bootloader or partition differs')
    report = dict(schema='rocell.r68_t4_lift_review.v1', app_sha256=APP_SHA,
        app_bytes=len(image), app_offset=0x10000, app_slot_bytes=0x140000,
        compile_export_id=COMPILE, compile_report_sha256=compile_digest,
        stage_export_id=STAGE, stage_report_sha256=stage_digest,
        source_pose='P3', target_pose='T4L', synchronized_servo_ids=[12,13],
        targets=[2217,1897], maximum_writes=1, retry_allowed=False,
        hardware_access=False, firmware_uploaded=False, deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'r68-t4-lift-review'}, [], attachments={
        'r68-t4-lift-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Review export invalid')
    return saved['path']


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1]))
