"""Offline exact r54-to-r55 app, route, slot and settings-preservation review."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = 'wizard-20260921T224655422019Z-a0d634b9151d406aa3dd750cfa179dc7'
STAGE = 'wizard-20260921T224503324003Z-81930b78d64e474c8e84d113b3d964f4'
R54_REVIEW = 'wizard-20260921T221053269829Z-74b79cc238f64a85ab3e8cc953be7c72'
APP_SHA = '1ea884af0cd717775c67046302ab5e9df82b9514b552b96fc8d27d5ad853d9a5'
R54_SHA = 'c418af3062200c91e6cdf4c5540a7e251f09cdc36fccb9659a9b9a6181f818fe'
DIFF = {'characterization_board_services.h', 'characterization_composition.h',
        'characterization_smoke_board.h', 'park_step_policy.h',
        'park_step_owner.h', 'park_step_routes.h'}


def review(root):
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    compiled, compile_digest = _read(exports, COMPILE, 'attachment-compile-review.json')
    staged, stage_digest = _read(exports, STAGE, 'attachment-r55-park-step-stage.json')
    predecessor, predecessor_digest = _read(exports, R54_REVIEW,
                                            'attachment-r54-fixed-reanchor-review.json')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    target = 'configured-diagnostic-candidate-r55'
    if (compiled['status'] != 'COMPILED' or compiled['target'] != target or
            compiled['build_profile'] != 'default-4mb-no-psram' or
            compiled['hardware_access'] is not False or
            compiled['firmware_uploaded'] is not False or
            staged['revision'] != 55 or staged['predecessor_revision'] != 54 or
            staged['hardware_access'] is not False or staged['uploaded'] is not False or
            set(staged['changed_files']) != DIFF or
            predecessor['app_sha256'] != R54_SHA):
        raise ValueError('Pinned stage, compile or predecessor differs')
    old = root/'.firmware-tools/configured-diagnostic-candidate-r54/RoArm-M3_example'
    new = root/'.firmware-tools/configured-diagnostic-candidate-r55/RoArm-M3_example'
    old_files = {path.name: path.read_bytes() for path in old.iterdir() if path.is_file()}
    new_files = {path.name: path.read_bytes() for path in new.iterdir() if path.is_file()}
    if ({name for name in new_files if old_files.get(name) != new_files[name]} != DIFF or
            set(old_files)-set(new_files)):
        raise ValueError('Unreviewed source change')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r55/RoArm-M3_example/'
    source_hashes = {name.replace('\\', '/'): digest
                     for name, digest in compiled['source_hashes'].items()}
    for name, raw in new_files.items():
        if source_hashes.get(prefix+name) != sha(raw):
            raise ValueError('Compiled source changed')
    for name, delta in staged['changed_files'].items():
        if delta != {'before': sha(old_files[name]) if name in old_files else None,
                     'after': sha(new_files[name])}:
            raise ValueError('Stage hash changed')
    board = new_files['characterization_smoke_board.h']
    if b'CharacterizationPattern::GhostPairTransitionCampaign,false,true));' not in board:
        raise ValueError('Park route not exclusively enabled')
    route = new_files['park_step_routes.h']
    for identity in (b'/rocell/park-step/start', b'/rocell/park-step/status',
                     b'/rocell/park-step/record', b'/rocell/park-step/receipt'):
        if identity not in route:
            raise ValueError('Park route missing')
    image = (root/'.firmware-tools/build-configured-diagnostic-candidate-r55--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    if (sha(image) != APP_SHA or
            compiled['artifact_hashes']['RoArm-M3_example.ino.bin'] != APP_SHA or
            not 0 < len(image) <= 0x140000 or
            any(identity not in image for identity in (
                b'/rocell/park-step/start', b'/rocell/park-step/record',
                b'/rocell/park-step/receipt', b'RCPARK0001'))):
        raise ValueError('Compiled app identity or slot differs')
    old_image = (root/'.firmware-tools/build-configured-diagnostic-candidate-r54--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    if sha(old_image) != R54_SHA:
        raise ValueError('Predecessor image changed')
    for suffix, expected in (
        ('bootloader.bin', 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin', '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        if compiled['artifact_hashes']['RoArm-M3_example.ino.'+suffix] != expected:
            raise ValueError('Boot or partition artifact changed')
    report = dict(schema='rocell.r55_park_step_review.v1', target=target,
                  app_sha256=APP_SHA, app_bytes=len(image), app_offset=0x10000,
                  app_slot_bytes=0x140000, app_headroom_bytes=0x140000-len(image),
                  predecessor_sha256=R54_SHA, predecessor_review_id=R54_REVIEW,
                  predecessor_review_sha256=predecessor_digest,
                  compile_export_id=COMPILE, compile_report_sha256=compile_digest,
                  stage_export_id=STAGE, stage_report_sha256=stage_digest,
                  changed_files=sorted(DIFF),
                  reanchor_route_disabled=True, park_step_route_enabled=True,
                  settings_preserved_by_design=True, runtime_heap_verified=False,
                  device_bytes_verified=False, hardware_access=False,
                  firmware_uploaded=False, deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r55-offline-app-review'}, [], attachments={
        'r55-park-step-review.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline review export invalid')
    return saved['path'], report


if __name__ == '__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
