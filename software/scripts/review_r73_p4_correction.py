"""Offline r73 source, binary and partition review; no controller access."""
import hashlib
from pathlib import Path
from stage_r73_p4_correction import specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260924T192012116855Z-79eccb30246b41a9a6bfb7c2d150a932'
STAGE='wizard-20260924T191757232558Z-320c6ffdacd04bb093466d3248b2953e'
APP_SHA='ec2b9f63e6c2157185584f596a7a04551c995bed9de811d9bcd94b7bc3c2373a'
APP_BYTES=1203040
BOOTLOADER_SHA='b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'
PARTITION_SHA='148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1'


def review(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,compile_digest=_read(exports,COMPILE,'attachment-compile-review.json')
    staged,stage_digest=_read(exports,STAGE,'attachment-r73-p4-correction-stage.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    prefix='.firmware-tools/configured-diagnostic-candidate-r73/RoArm-M3_example/'
    old=root/'.firmware-tools/configured-diagnostic-candidate-r72/RoArm-M3_example'
    expected=specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()},root)
    actual={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    source_hashes={p.replace('\\','/'):h for p,h in compiled['source_hashes'].items()}
    if (actual!=expected or compiled['status']!='COMPILED' or
        compiled['target']!='configured-diagnostic-candidate-r73' or
        compiled['build_profile']!='default-4mb-no-psram' or
        any(source_hashes.get(prefix+name)!=sha(data) for name,data in actual.items()) or
        staged['selector']!='P4C16' or staged['comparison_review']['maximum_writes']!=16 or
        staged['comparison_review']['movement_authorized'] or
        staged['predecessor_revision']!=72):
        raise ValueError('r73 staged source or review differs')
    build=root/'.firmware-tools/build-configured-diagnostic-candidate-r73--default-4mb-no-psram'
    image=(build/'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image)!=APP_SHA or len(image)!=APP_BYTES or len(image)>0x140000 or
        compiled['artifact_hashes']['RoArm-M3_example.ino.bin']!=APP_SHA or
        not all(marker in image for marker in
            (b'RCWRCMP001',b'P4_CORRECTION_COMPLETE',b'/rocell/p4-correction/start',b'P4C16')) or
        b'/rocell/p4-repeat/start' in image):
        raise ValueError('r73 application binary differs')
    for suffix,digest in (('bootloader.bin',BOOTLOADER_SHA),('partitions.bin',PARTITION_SHA)):
        name='RoArm-M3_example.ino.'+suffix
        if sha((build/name).read_bytes())!=digest or compiled['artifact_hashes'][name]!=digest:
            raise ValueError('Protected build artifact differs')
    report=dict(schema='rocell.r73_p4_correction_review.v1',app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=72,compile_export_id=COMPILE,compile_report_sha256=compile_digest,
        stage_export_id=STAGE,stage_report_sha256=stage_digest,
        source_pose='P4',target_pose='P4C16',synchronized_servo_ids=[15],
        targets=[1947,1980,1944,1980,1944,1980,1947,1980,
                 1944,1980,1947,1980,1947,1980,1944,1980],
        maximum_writes=16,retry_allowed=False,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r73-p4-correction-review'},[],attachments={
        'r73-p4-correction-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid review export')
    return saved['path']


if __name__=='__main__':print(review(Path(__file__).resolve().parents[1]))
