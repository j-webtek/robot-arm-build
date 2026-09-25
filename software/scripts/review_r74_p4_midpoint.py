"""Offline r74 source, binary and partition review; no controller access."""
import hashlib
from pathlib import Path
from stage_r74_p4_midpoint import specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260924T193848829614Z-68ba88683b8f4de2a307b30ed5f5b92e'
STAGE='wizard-20260924T193543460141Z-587a8991bef84ff5acd09c9491f162a1'
APP_SHA='1f2c6822f428b9dd9fdf2eb17444d3f89f5d7243a7aad89edae4acda0b721bc5'
APP_BYTES=1203024
BOOTLOADER_SHA='b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'
PARTITION_SHA='148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1'


def review(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,compile_digest=_read(exports,COMPILE,'attachment-compile-review.json')
    staged,stage_digest=_read(exports,STAGE,'attachment-r74-p4-midpoint-stage.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    prefix='.firmware-tools/configured-diagnostic-candidate-r74/RoArm-M3_example/'
    old=root/'.firmware-tools/configured-diagnostic-candidate-r73/RoArm-M3_example'
    expected=specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()},root)
    actual={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    source_hashes={p.replace('\\','/'):h for p,h in compiled['source_hashes'].items()}
    if (actual!=expected or compiled['status']!='COMPILED' or
        compiled['target']!='configured-diagnostic-candidate-r74' or
        compiled['build_profile']!='default-4mb-no-psram' or
        any(source_hashes.get(prefix+name)!=sha(data) for name,data in actual.items()) or
        staged['selector']!='P4M16' or staged['comparison_review']['maximum_writes']!=16 or
        staged['comparison_review']['movement_authorized'] or
        staged['predecessor_revision']!=73):
        raise ValueError('r74 staged source or review differs')
    build=root/'.firmware-tools/build-configured-diagnostic-candidate-r74--default-4mb-no-psram'
    image=(build/'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image)!=APP_SHA or len(image)!=APP_BYTES or len(image)>0x140000 or
        compiled['artifact_hashes']['RoArm-M3_example.ino.bin']!=APP_SHA or
        not all(marker in image for marker in
            (b'RCWRMID001',b'P4_MIDPOINT_COMPLETE',b'/rocell/p4-midpoint/start',b'P4M16')) or
        b'/rocell/p4-correction/start' in image):
        raise ValueError('r74 application binary differs')
    for suffix,digest in (('bootloader.bin',BOOTLOADER_SHA),('partitions.bin',PARTITION_SHA)):
        name='RoArm-M3_example.ino.'+suffix
        if sha((build/name).read_bytes())!=digest or compiled['artifact_hashes'][name]!=digest:
            raise ValueError('Protected build artifact differs')
    report=dict(schema='rocell.r74_p4_midpoint_review.v1',app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=73,compile_export_id=COMPILE,compile_report_sha256=compile_digest,
        stage_export_id=STAGE,stage_report_sha256=stage_digest,
        source_pose='P4',target_pose='P4M16',synchronized_servo_ids=[15],
        targets=[1944,1980,1945,1980,1945,1980,1944,1980,
                 1945,1980,1944,1980,1944,1980,1945,1980],
        maximum_writes=16,retry_allowed=False,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r74-p4-midpoint-review'},[],attachments={
        'r74-p4-midpoint-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid review export')
    return saved['path']


if __name__=='__main__':print(review(Path(__file__).resolve().parents[1]))
