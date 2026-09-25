"""Offline exact r55-to-r56 settling and fault-record app review."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = 'wizard-20260921T234124765413Z-d90894e35c154a5e9f8a74e42941585c'
STAGE = 'wizard-20260921T233927295150Z-9b531bc6dc3b4227a1dc84dc02b7575c'
R55_REVIEW = 'wizard-20260921T224805390919Z-0a91a71fa008405298c821df110663af'
APP_SHA = '09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79'
R55_SHA = '1ea884af0cd717775c67046302ab5e9df82b9514b552b96fc8d27d5ad853d9a5'
DIFF = {'park_step_policy.h', 'park_step_owner.h'}


def review(root):
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE, 'attachment-r56-park-step-stage.json')
    predecessor, predecessor_digest = _read(exports, R55_REVIEW,
                                            'attachment-r55-park-step-review.json')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    target = 'configured-diagnostic-candidate-r56'
    if (compiled['status'] != 'COMPILED' or compiled['target'] != target or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            compiled['hardware_access'] is not False or
            compiled['firmware_uploaded'] is not False or
            staged['revision'] != 56 or staged['predecessor_revision'] != 55 or
            staged['hardware_access'] is not False or staged['uploaded'] is not False or
            set(staged['changed_files']) != DIFF or
            predecessor['app_sha256'] != R55_SHA):
        raise ValueError('Pinned stage, compile or predecessor differs')
    old = root/'.firmware-tools/configured-diagnostic-candidate-r55/RoArm-M3_example'
    new = root/'.firmware-tools/configured-diagnostic-candidate-r56/RoArm-M3_example'
    old_files = {path.name: path.read_bytes() for path in old.iterdir() if path.is_file()}
    new_files = {path.name: path.read_bytes() for path in new.iterdir() if path.is_file()}
    if (set(old_files) != set(new_files) or
            {name for name in new_files if old_files[name] != new_files[name]} != DIFF):
        raise ValueError('Unreviewed source change')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r56/RoArm-M3_example/'
    source_hashes = {name.replace('\\', '/'): digest
                     for name, digest in compiled['source_hashes'].items()}
    for name, raw in new_files.items():
        if source_hashes.get(prefix+name) != sha(raw):
            raise ValueError('Compiled source changed')
    for name, delta in staged['changed_files'].items():
        if delta != {'before': sha(old_files[name]), 'after': sha(new_files[name])}:
            raise ValueError('Stage hash changed')
    image = (root/'.firmware-tools/build-configured-diagnostic-candidate-r56--default-4mb-no-psram/'
             'RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not 0 < len(image) <= 0x140000 or
            any(identity not in image for identity in (
                b'/rocell/park-step/start', b'/rocell/park-step/record',
                b'/rocell/park-step/receipt', b'ENDPOINT_TIMEOUT'))):
        raise ValueError('Compiled app identity or slot differs')
    old_image = (root/'.firmware-tools/build-configured-diagnostic-candidate-r55--default-4mb-no-psram/'
                 'RoArm-M3_example.ino.bin').read_bytes()
    if sha(old_image) != R55_SHA:
        raise ValueError('Predecessor image changed')
    for suffix, expected in (
        ('bootloader.bin', 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin', '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        if compiled['artifact_hashes']['RoArm-M3_example.ino.'+suffix] != expected:
            raise ValueError('Boot or partition artifact changed')
    report = dict(schema='rocell.r56_park_step_review.v1', target=target,
                  app_sha256=APP_SHA, app_bytes=len(image), app_offset=0x10000,
                  app_slot_bytes=0x140000, app_headroom_bytes=0x140000-len(image),
                  predecessor_sha256=R55_SHA, predecessor_review_id=R55_REVIEW,
                  predecessor_review_sha256=predecessor_digest,
                  compile_export_id=COMPILE, compile_report_sha256=compile_digest,
                  stage_export_id=STAGE, stage_report_sha256=stage_digest,
                  changed_files=sorted(DIFF), settings_preserved_by_design=True,
                  runtime_heap_verified=False, device_bytes_verified=False,
                  hardware_access=False, firmware_uploaded=False,
                  deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r56-offline-app-review'}, [], attachments={
        'r56-park-step-review.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline review export invalid')
    return saved['path'], report


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
